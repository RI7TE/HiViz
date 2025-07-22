
from __future__ import annotations
import os,sys,ujson as json
from pathlib import Path
from typing import TYPE_CHECKING
sys.path.append(str(Path(__file__).absolute().parent))
if TYPE_CHECKING:
    import typing
import datetime as dt    


from contextlib import contextmanager, redirect_stdout
from colorama import Fore, Style

def viz(*msg, color: str = Fore.BLUE,log=False,debug=False, log_file:str | Path =
    'debug.log',term=True) -> str:
    """
    Print a message in the specified color.
    """
    to_debug = os.getenv('DEBUG', '0') == '1' or debug
    to_log = os.getenv('LOG', '0') == '1' or log
    if len(msg) == 1 and isinstance(msg[0], (list, tuple)):
        msg = msg[0]
    elif len(msg) == 1 and isinstance(msg[0], dict):
        msg = [f"{k}: {v}" for k, v in msg[0].items()]
    _msg = ' '.join(map(str, msg))
    log_msg = dt.datetime.now(dt.UTC).strftime("%d/%m/%Y, %H:%M:%S") + "\n" + "\t" + _msg
    msg = f"{color}{' '.join(map(str, msg))}{Style.RESET_ALL}"
    @contextmanager
    def _log():    # Log to a file if LOG environment variable is set
        nonlocal log_file
        log_file = os.getenv('LOG_FILE', str(log_file))
        with Path(log_file).open('a') as f:
            if term:
                f.write(log_msg + '\n')
            yield f
        if sys.stdout.isatty():
            print(Fore.BLACK + f"Logged to {log_file}" + Style.RESET_ALL, flush=True)
        else:
            print(Fore.YELLOW + f"Warning: Logged to {log_file}" + Style.RESET_ALL, file=sys.stderr, flush=True)
    if to_debug:
        if to_log:
            with _log() as f:
                print(log_msg if not term else msg, file=f if not term else sys.stderr, flush=True)
        else:
            print(msg, flush=True)
    elif to_log:
        with _log() as f:
            print(log_msg if not term else msg, file=f if not term else sys.stderr, flush=True)
    elif sys.stdout.isatty():
        # Print to stdout if it is a terminal
        print(msg, flush=True)
        sys.stdout.flush()
    else:
        # Fallback to stderr if stdout is not a terminal
        print(Fore.YELLOW + "Warning: Not printing to stdout" + Style.RESET_ALL, file=sys.stderr, flush=True)
        sys.stderr.write(msg + '\n')
        sys.stderr.flush()

    return _msg.strip()






def print_help():
    with redirect_stdout(sys.stderr):
        help(dir)
def test():
        viz("This will be printed to stderr instead of stdout")
        viz("This is a test message", color=Fore.GREEN, log=True, debug=True, log_file='test.log')
        viz("Another message", color=Fore.RED, log=True, term=False)
        viz("This message won't be logged", log=False, term=False)
        viz("This message will not be printed to stdout", term=False)
        viz("This message will be printed to stdout", term=True)
        viz("This message will be logged to a file", log=True, log_file='output.log', term=False)
        viz("This message will be printed in red", color=Fore.RED)
        
if __name__ == "__main__":
    test()

