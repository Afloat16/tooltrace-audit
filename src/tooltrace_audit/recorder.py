"""Opt-in instrumentation for user code; arguments are hashed before writing."""
from contextlib import contextmanager
import json
from pathlib import Path
import threading
import time
import uuid
from .common import text
from .core import args_digest


class Recorder:
    def __init__(self,path,run_id):
        self.run_id=text(run_id,'run_id')
        self.stream=Path(path).open('x',encoding='utf-8')
        self.lock=threading.Lock()
        self.attempt_ids=set()

    def __enter__(self): return self
    def __exit__(self,*args): self.stream.close()

    def write(self,event):
        with self.lock:
            event['time_ns']=time.time_ns()
            self.stream.write(json.dumps(event,ensure_ascii=False,allow_nan=False)+'\n')
            self.stream.flush()

    @contextmanager
    def attempt(self,call_id,name,arguments,attempt_id=None):
        ident=text(attempt_id or uuid.uuid4().hex,'attempt_id')
        call_id=text(call_id,'call_id'); name=text(name,'name'); digest=args_digest(arguments)
        with self.lock:
            if ident in self.attempt_ids: raise ValueError('Recorder attempt ID is already used.')
            self.attempt_ids.add(ident)
        self.write(dict(kind='start',run_id=self.run_id,call_id=call_id,attempt_id=ident,name=name,
                        arguments_sha256=digest,time_ns=time.time_ns(),clock='unix_ns'))
        status='ok'
        try:
            yield ident
        except BaseException:
            status='error'
            raise
        finally:
            self.write(dict(kind='end',run_id=self.run_id,attempt_id=ident,status=status,
                            time_ns=time.time_ns(),clock='unix_ns'))
