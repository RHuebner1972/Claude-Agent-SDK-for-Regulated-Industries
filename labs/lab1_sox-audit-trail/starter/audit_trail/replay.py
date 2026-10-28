"""Decision replay: reconstruct one agent decision from the audit log alone.

    python -m audit_trail replay path/to/audit.jsonl JE-1003 [--key-env AUDIT_HMAC_KEY] [--out report.md]

The report answers the auditor's questions (who asked, which agent and model, what data it
saw, what it decided, why and under what authority) and states whether the chain verified.
If the chain fails, the report says so first: never rely on a log you can't verify.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .verify import VerifyReport, verify_log


def _about(record: dict, entry_id: str) -> bool:
    return record.get("detail", {}).get("input", {}).get("entry_id") == entry_id


def evidence_window(run: list[dict], entry_id: str, decision: dict) -> list[dict]:
    """Tool events from the agent's first look at the entry up to its decision, plus their denials."""
    starts = [r["seq"] for r in run if r["event_type"] == "tool.requested" and _about(r, entry_id)]
    start = min(starts, default=decision["seq"])
    window = [r for r in run if r["event_type"].startswith("tool.") and start <= r["seq"] <= decision["seq"]]
    asked = {r["tool_use_id"] for r in window}
    return window + [r for r in run if r["event_type"] == "tool.denied" and r["tool_use_id"] in asked and r not in window]


def replay_decision(records: list[dict], entry_id: str, report: VerifyReport | None = None) -> str:
    # TODO 8 (walkthrough part 2): decision replay. Return Markdown that answers, from the log alone:
    # chain integrity (from report), who asked, what was asked, which agent, model, prompt and policy versions,
    # what data it saw (use evidence_window(): tool events from the first request whose input entry_id matches,
    # up to the decision, plus their denials), what it was refused,
    # what it decided, why, under what authority, when, and the run (correlation, session, turns, cost),
    # then a timeline table. If no decision.recorded event exists for entry_id, say so.
    raise NotImplementedError("Lab 1: replay_decision")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconstruct one decision from an audit log")
    parser.add_argument("log")
    parser.add_argument("entry_id")
    parser.add_argument("--key-env", default="AUDIT_HMAC_KEY")
    parser.add_argument("--out", help="write the report to this Markdown file")
    args = parser.parse_args(argv)
    try:                                   # pick up AUDIT_HMAC_KEY from .env when python-dotenv is installed
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    key = os.getenv(args.key_env)
    report = verify_log(args.log, key.encode() if key else None)
    records = [json.loads(l) for l in Path(args.log).read_text(encoding="utf-8").splitlines() if l.strip()]
    text = replay_decision(records, args.entry_id, report)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
