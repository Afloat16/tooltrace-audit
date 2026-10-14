"""Diagnostics from execution receipts or conversation protocol evidence."""
from collections import defaultdict
import hashlib
import json
import re
from pathlib import Path
from .common import Findings, integer, load, loads, text


def read_input(path):
    path=Path(path)
    if path.suffix.lower()=='.jsonl':
        rows=[]
        with path.open('r',encoding='utf-8-sig') as stream:
            while line:=stream.readline(1024*1024+1):
                if len(line)>1024*1024: raise ValueError('JSONL line exceeds 1 MiB.')
                if line.strip(): rows.append(loads(line))
                if len(rows)>1_000_000: raise ValueError('Event limit exceeded.')
        return {'events':rows}
    return load(path)


def args_digest(arguments):
    if isinstance(arguments,str): arguments=loads(arguments)
    if not isinstance(arguments,dict): raise ValueError('Tool arguments must be an object or object JSON string.')
    encoded=json.dumps(arguments,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def conversation(messages,findings):
    if not isinstance(messages,list): raise ValueError('messages must be a list.')
    calls=[]; pending={}; seen=set(); signatures=defaultdict(int)
    for index,message in enumerate(messages):
        if not isinstance(message,dict): raise ValueError('Message must be an object.')
        role=message.get('role')
        if role=='assistant':
            if pending:
                findings.add('unresolved_before_assistant','error','Assistant message appears before outstanding tool results.',message_index=index)
            for call in message.get('tool_calls',[]):
                ident=text(call.get('id'),'tool call id')
                function=call['function']; name=text(function.get('name'),'tool name')
                digest=args_digest(function.get('arguments'))
                if ident in seen: findings.add('duplicate_call_id','error','Tool call ID is reused.',call_id=ident)
                seen.add(ident); pending[ident]=index
                signatures[(name,digest)]+=1
                calls.append({'call_id':ident,'name':name,'arguments_sha256':digest,'message':index})
        elif role=='tool':
            ident=text(message.get('tool_call_id'),'tool result id')
            if ident not in pending:
                findings.add('orphan_result','error','Tool result has no outstanding matching call.',message_index=index,call_id=ident)
            else: del pending[ident]
        elif pending:
            findings.add('interleaved_message','error','Non-tool message interrupts outstanding tool results.',message_index=index)
    for ident in pending:
        findings.add('missing_result','error','Tool call has no result at the end of this conversation.',call_id=ident)
    return calls,signatures


def execution(events,findings,allow_open=False):
    if not isinstance(events,list): raise ValueError('events must be a list.')
    attempts={}; previous={}
    signatures=defaultdict(int)
    for index,event in enumerate(events):
        if index>=1_000_000: raise ValueError('Event limit exceeded.')
        if not isinstance(event,dict): raise ValueError('Event must be an object.')
        run=text(event.get('run_id'),'run_id'); attempt=text(event.get('attempt_id'),'attempt_id')
        stamp=integer(event.get('time_ns'),'time_ns')
        if run in previous and stamp<previous[run]:
            findings.add('event_time_regression','warning','Event time decreases in recorded order within a run.',event=index,run_id=run)
        previous[run]=stamp
        key=(run,attempt); kind=event.get('kind')
        if kind=='start':
            ident=text(event.get('call_id'),'call_id'); name=text(event.get('name'),'name')
            if 'arguments_sha256' in event:
                digest=event['arguments_sha256']
                if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
                    raise ValueError('arguments_sha256 must be a lowercase 64-digit SHA-256 hex digest.')
                if 'arguments' in event and digest!=args_digest(event['arguments']):
                    raise ValueError('Supplied argument digest does not match arguments.')
            else:
                digest=args_digest(event.get('arguments'))
            if key in attempts:
                findings.add('duplicate_attempt_start','error','Attempt ID was started twice within the same run.',run_id=run,attempt_id=attempt)
                continue
            attempts[key]=dict(run_id=run,attempt_id=attempt,call_id=ident,name=name,
                               arguments_sha256=digest,start_ns=stamp,end_ns=None,status=None)
            signatures[(run,name,digest)]+=1
        elif kind=='end':
            if key not in attempts:
                findings.add('orphan_end','error','End event has no observed start.',run_id=run,attempt_id=attempt)
                continue
            current=attempts[key]
            if current['end_ns'] is not None:
                findings.add('duplicate_attempt_end','error','Attempt has more than one end event.',run_id=run,attempt_id=attempt)
                continue
            if stamp<current['start_ns']:
                findings.add('negative_duration','error','Attempt ends before it starts.',run_id=run,attempt_id=attempt)
            current.update(end_ns=stamp,status=text(event.get('status'),'status'))
        else:
            raise ValueError('Execution event kind must be start or end.')
    grouped=defaultdict(list)
    for current in attempts.values():
        if current['end_ns'] is None:
            findings.add('unfinished_attempt','warning' if allow_open else 'error',
                         'Attempt has no end event in the captured trace.',run_id=current['run_id'],attempt_id=current['attempt_id'])
        current['duration_ns']=current['end_ns']-current['start_ns'] if current['end_ns'] is not None else None
        grouped[(current['run_id'],current['call_id'])].append(current)
    for (run,ident), values in grouped.items():
        if len(values)>1:
            findings.add('repeated_logical_call','warning','A logical call has multiple attempts; retry intent is not inferred.',run_id=run,call_id=ident,attempts=len(values))
        signatures_for_id={(v['name'],v['arguments_sha256']) for v in values}
        if len(signatures_for_id)>1:
            findings.add('logical_call_changed','error','Same logical call ID has conflicting name or arguments.',run_id=run,call_id=ident)
        ordered=sorted(values,key=lambda v:(v['start_ns'],v['attempt_id']))
        frontier=None
        for current in ordered:
            if frontier is not None and (frontier['end_ns'] is None or current['start_ns']<frontier['end_ns']):
                findings.add('overlapping_attempts','warning','Multiple attempts of this logical call overlap in supplied timestamps.',run_id=run,call_id=ident,attempts=[frontier['attempt_id'],current['attempt_id']])
            if frontier is None or frontier['end_ns'] is not None and (current['end_ns'] is None or current['end_ns']>frontier['end_ns']):
                frontier=current
    return list(attempts.values()),signatures


def audit(data,max_calls=1000,repeat_threshold=3,allow_open=False):
    integer(max_calls,'max_calls',1); integer(repeat_threshold,'repeat_threshold',2)
    if not isinstance(data,dict): raise ValueError('Use an object with exactly one of messages or events.')
    if ('messages' in data)==('events' in data): raise ValueError('Use exactly one of messages or events.')
    findings=Findings()
    if 'messages' in data:
        calls,signatures=conversation(data['messages'],findings); mode='conversation_protocol'
    else:
        calls,signatures=execution(data['events'],findings,allow_open); mode='execution_events'
    if not calls: findings.add('empty_calls','warning','No tool call evidence was observed.')
    if len(calls)>max_calls:
        findings.add('call_budget_exceeded','error','Observed calls/attempts exceed the explicit diagnostic budget.',count=len(calls),budget=max_calls)
    for key,count in signatures.items():
        if count>=repeat_threshold:
            findings.add('repeated_signature','warning','Same tool/arguments recur; this is a candidate for review, not proof of an infinite loop.',name=key[-2],arguments_sha256=key[-1],count=count)
    return dict(tool='tooltrace-audit',schema_version=1,mode=mode,calls=calls,
                argument_values_in_report=False,semantics='Offline diagnostics only; no execution, blocking, billing or idempotency guarantee.',**findings.report())
