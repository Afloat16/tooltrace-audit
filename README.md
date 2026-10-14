# tooltrace-audit

Offline tool execution and conversation trace diagnostics for duplicate attempts, overlapping retries and unmatched results.

[中文](README.zh-CN.md) · [Demand evidence](docs/EVIDENCE.md) · [License](LICENSE)

Independent, experimental utility maintained by **Afloat16**. Original implementation; no upstream endorsement is implied.

## Install

Python 3.10+.

```bash
git clone https://github.com/Afloat16/tooltrace-audit.git
cd tooltrace-audit
python -m venv .venv
# Activate the virtual environment for your OS, then:
python -m pip install -e '.[dev]'
```

The core package uses the Python standard library only. No GPU, ROS runtime, API key, hosted service or model weights are required for the core offline workflow.

## First run

```bash
tooltrace-audit examples/attempts.jsonl --strict
tooltrace-audit conversation.json --max-calls 100 --repeat-threshold 3 --output trace-report.json
```

## Inputs and checks

Execution JSONL or `{events:[...]}`: start records have `kind:start,run_id,call_id,attempt_id,name,arguments,time_ns`; ends have `kind:end,run_id,attempt_id,status,time_ns`. Times must share a meaningful clock within each run. Alternatively `{messages:[...]}` accepts assistant tool_calls and tool tool_call_id results. Conversation mode validates protocol ordering only, not real execution/duration.

Checks duplicate/orphan/missing attempt outcomes, overlapping retries, conflicting logical identities, conversation call/result ordering and repeated name/argument signatures. `--max-calls` is an explicit diagnostic budget. `--allow-open` treats unfinished execution captures as warnings.

## Boundaries

For opt-in instrumentation, `tooltrace_audit.recorder.Recorder` writes start/end events around your own context-managed call, records success/error outcomes, and hashes arguments before writing. See `examples/instrument.py`. Execution input also accepts `arguments_sha256` instead of raw arguments. Recorder timestamps use Unix nanoseconds; cross-host clock synchronization and stable run/logical-call IDs remain the caller's responsibility. Existing trace files are not overwritten.

Repeated calls are review candidates, not proof of an infinite loop or unintended duplication. Does not execute/block/cancel/deduplicate tools, calculate billing or fix checkpoint dispatch. Native LangGraph/LangSmith archive imports are not claimed; use the documented event contract. Reports omit argument/result content but retain IDs, timing and hashes. Limits: 1,000,000 execution events, 64 MiB ordinary JSON, 1 MiB JSONL lines.

## Output and development

Audit commands exit 0 for no error findings, 1 for errors (also warnings with --strict), and 2 for malformed input/report-write failure. --output creates a new JSON file exclusively; existing files are never overwritten. Detailed audit findings are capped at 200 while total severity counts remain accurate.

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m build
```

The configured CI matrix covers Ubuntu, Windows and macOS with Python 3.10/3.13; inspect Actions for actual results. Fixtures are synthetic. No private captures or upstream user attachments are redistributed.

Report problems with command/version, expected/actual result and a minimal synthetic reproduction. Keep source attribution and compatible licensing. MIT license, copyright Afloat16.
