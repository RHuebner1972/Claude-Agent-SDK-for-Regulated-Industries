"""Verify an audit log: schema, sequence, hash links, content hashes and signed checkpoints.

    python -m sentinel.audit verify path/to/audit.jsonl [--key-env AUDIT_HMAC_KEY]

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
    path = Path(path)
    report = VerifyReport(str(path))
    hashes: dict[int, str] = {}
    prev, expected_seq = GENESIS, 1
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            report.problems.append(f"line {lineno}: not valid JSON")
            continue
        report.events += 1
        seq = record.get("seq")
        try:
            AuditEvent.model_validate(record)
        except ValidationError as exc:
            report.problems.append(f"seq {seq}: schema: {exc.errors()[0]['msg']}")
        if seq != expected_seq:
            report.problems.append(f"line {lineno}: expected seq {expected_seq}, found {seq} (missing, inserted or reordered event)")
        if record.get("prev_hash") != prev:
            report.problems.append(f"seq {seq}: broken link: prev_hash does not match the previous event's hash")
        if record_hash(record) != record.get("hash"):
            report.problems.append(f"seq {seq}: content altered: hash does not match the event's contents")
        hashes[seq] = record.get("hash")
        prev = record.get("hash")
        expected_seq = (seq if isinstance(seq, int) else expected_seq) + 1

    checkpoint_path = path.with_name(path.stem + ".checkpoints.jsonl")
    if checkpoint_path.exists():
        if hmac_key is None:
            report.problems.append("signed checkpoints exist but no key was supplied: whole-chain rewrites and truncation can't be ruled out")
        else:
            for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                cp = json.loads(line)
                report.checkpoints_checked += 1
                if not signature_ok(hmac_key, f"{cp['seq']}:{cp['head_hash']}", cp.get("hmac", "")):
                    report.problems.append(f"checkpoint at seq {cp['seq']}: bad signature (checkpoint forged or key wrong)")
                elif cp["seq"] not in hashes:
                    report.problems.append(f"checkpoint at seq {cp['seq']}: event missing: log truncated after seq {max(hashes, default=0)}")
                elif hashes[cp["seq"]] != cp["head_hash"]:
                    report.problems.append(f"checkpoint at seq {cp['seq']}: hash differs from signed value: chain was rewritten")
    return report


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
