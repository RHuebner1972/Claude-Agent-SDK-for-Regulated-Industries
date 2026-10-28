"""Command line: python -m sentinel.audit verify <log> | replay <log> <entry_id>"""
import sys

from .replay import main as replay_main
from .verify import main as verify_main

COMMANDS = {"verify": verify_main, "replay": replay_main}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: python -m sentinel.audit verify <log> [--key-env VAR]\n"
              "       python -m sentinel.audit replay <log> <entry_id> [--key-env VAR] [--out report.md]")
        sys.exit(2)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))
