"""Run in a writable directory; writes a new trace with no raw argument values."""
from tooltrace_audit.recorder import Recorder

with Recorder('tool-attempts.jsonl',run_id='local-demo') as recorder:
    with recorder.attempt('logical-read-1','read_example',{'path':'example.txt'}):
        result=2+2  # Replace with your own tool call; the recorder does not execute it.
print('Created tool-attempts.jsonl; audit it with tooltrace-audit.')
