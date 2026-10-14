import json
from pathlib import Path
import tempfile
import unittest
from tooltrace_audit.core import audit


def start(attempt,stamp,call='c',run='r',args=None):
    return dict(kind='start',run_id=run,call_id=call,attempt_id=attempt,name='read',arguments=args or {'x':1},time_ns=stamp)

def end(attempt,stamp,run='r'):
    return dict(kind='end',run_id=run,attempt_id=attempt,status='ok',time_ns=stamp)


class TraceTests(unittest.TestCase):
    def test_duplicate_checkpoint_attempts_overlap(self):
        report=audit({'events':[start('a',100),start('b',200),end('a',300),end('b',400)]})
        self.assertEqual(report['finding_counts'],{'repeated_logical_call':1,'overlapping_attempts':1})

    def test_retry_after_end_is_not_overlap(self):
        report=audit({'events':[start('a',100),end('a',200),start('b',200),end('b',300)]})
        self.assertNotIn('overlapping_attempts',report['finding_counts'])

    def test_open_capture_is_explicit(self):
        self.assertEqual(audit({'events':[start('a',1)]})['error_count'],1)
        self.assertEqual(audit({'events':[start('a',1)]},allow_open=True)['error_count'],0)

    def test_run_namespaces_do_not_collide(self):
        report=audit({'events':[start('a',1,run='r1'),start('a',1,run='r2'),end('a',2,run='r1'),end('a',2,run='r2')]})
        self.assertEqual(report['finding_counts'],{})

    def test_repeated_signature_is_a_warning_not_a_proven_loop(self):
        rows=[]
        for i in range(3): rows.extend([start(str(i),i*2,call=str(i)),end(str(i),i*2+1)])
        report=audit({'events':rows})
        self.assertEqual(report['error_count'],0)
        self.assertEqual(report['finding_counts']['repeated_signature'],1)

    def test_budget_orphan_and_negative_duration(self):
        report=audit({'events':[end('missing',1),start('a',10),end('a',9),start('b',20),end('b',21)]},max_calls=1)
        self.assertIn('call_budget_exceeded',report['finding_counts'])
        self.assertIn('orphan_end',report['finding_counts'])
        self.assertIn('negative_duration',report['finding_counts'])

    def test_changed_logical_call_is_error(self):
        report=audit({'events':[start('a',1),end('a',2),start('b',3,args={'x':2}),end('b',4)]})
        self.assertIn('logical_call_changed',report['finding_counts'])

    def test_parallel_conversation_results_can_reorder(self):
        calls=[{'id':str(i),'type':'function','function':{'name':'read','arguments':'{}'}} for i in range(2)]
        report=audit({'messages':[{'role':'assistant','tool_calls':calls},
                                  {'role':'tool','tool_call_id':'1','content':'private'},
                                  {'role':'tool','tool_call_id':'0','content':'private'}]})
        self.assertEqual(report['error_count'],0)
        self.assertNotIn('private',json.dumps(report))

    def test_conversation_missing_and_orphan_results(self):
        report=audit({'messages':[{'role':'assistant','tool_calls':[{'id':'c','function':{'name':'read','arguments':'{}'}}]},
                                  {'role':'tool','tool_call_id':'other','content':'x'}]})
        self.assertEqual(set(report['finding_counts']),{'orphan_result','missing_result'})

    def test_private_arguments_not_reported(self):
        report=audit({'events':[start('a',1,args={'secret':'not-in-report'}),end('a',2)]})
        self.assertNotIn('not-in-report',json.dumps(report))

    def test_duplicate_json_keys_invalid(self):
        with self.assertRaises(ValueError):
            audit({'events':[start('a',1,args='{"x":1,"x":2}')]})

    def test_recorder_hashes_and_records_actual_context_outcome(self):
        from tooltrace_audit.recorder import Recorder
        from tooltrace_audit.core import read_input
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trace.jsonl'
            with Recorder(path,'run') as recorder:
                with recorder.attempt('c1','lookup',{'secret':'never-written'},'a1'):
                    pass
                with self.assertRaises(RuntimeError):
                    with recorder.attempt('c2','lookup',{},'a2'):
                        raise RuntimeError('private failure text')
                with self.assertRaises(ValueError):
                    with recorder.attempt('c3','lookup',{},'a1'): pass
            raw=path.read_text()
            self.assertNotIn('never-written',raw)
            self.assertNotIn('private failure text',raw)
            report=audit(read_input(path))
            self.assertEqual(report['error_count'],0)
            self.assertEqual([c['status'] for c in report['calls']],['ok','error'])
