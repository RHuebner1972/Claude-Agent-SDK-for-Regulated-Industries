"""Verify an audit log: schema, sequence, hash links, content hashes and signed checkpoints.

    python -m audit_trail verify path/to/audit.jsonl [--key-env AUDIT_HMAC_KEY]

Exit code 0 = verified, 1 = problems found. Run it in CI, on a schedule, and before you
hand a log to an auditor.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .hashing import GENESIS, record_hash, signature_ok
from .models import AuditEvent


@dataclass
class VerifyReport:
    path: str
    events: int = 0
    checkpoints_checked: int = 0
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems

    def render(self) -> str:
        status = "VERIFIED" if self.ok else "FAILED"
        lines = [f"{status}: {self.path}: {self.events} events, {self.checkpoints_checked} signed checkpoints checked"]
        lines += [f"  - {p}" for p in self.problems]
        return "\n".join(lines)


def verify_log(path: str | Path, hmac_key: bytes | None = None) -> VerifyReport:
    # TODO 7 (walkthrough part 2): the verifier. Walk the file line by line, tracking prev (start GENESIS)
    # and expected_seq (start 1). For each record report a problem when:
    #   - the line isn't JSON, or AuditEvent.model_validate fails (schema)
    #   - seq != expected_seq                       (missing, inserted or reordered event)
    #   - prev_hash != prev                         (broken link)
    #   - record_hash(record) != record["hash"]     (content altered)
    # Then, if <stem>.checkpoints.jsonl exists: with no key, report that rewrites and truncation can't be
    # ruled out; with a key, check each checkpoint's signature, that its seq exists (truncation) and that
    # the event's hash equals head_hash (chain rewritten). Return a VerifyReport.
    raise NotImplementedError("Lab 1: verify_log")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a hash-chained audit log")
    parser.add_argument("log")
    parser.add_argument("--key-env", default="AUDIT_HMAC_KEY", help="environment variable holding the HMAC key")
    args = parser.parse_args(argv)
    try:                                   # pick up AUDIT_HMAC_KEY from .env when python-dotenv is installed
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    key = os.getenv(args.key_env)
    report = verify_log(args.log, key.encode() if key else None)
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
