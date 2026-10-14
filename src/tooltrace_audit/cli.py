import argparse
import sys
from .common import emit, code
from .core import audit, read_input


def main(argv=None):
    parser=argparse.ArgumentParser(description='Offline execution attempt and conversation protocol audit.')
    parser.add_argument('input')
    parser.add_argument('--max-calls',type=int,default=1000)
    parser.add_argument('--repeat-threshold',type=int,default=3)
    parser.add_argument('--allow-open',action='store_true',help='Treat unfinished execution attempts as warnings.')
    parser.add_argument('--strict',action='store_true')
    parser.add_argument('--output')
    args=parser.parse_args(argv)
    try:
        report=audit(read_input(args.input),args.max_calls,args.repeat_threshold,args.allow_open)
        emit(report,args.output)
        return code(report,args.strict)
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as exc:
        print(f'Input/report error: {exc}',file=sys.stderr)
        return 2
