"""Decision replay: reconstruct one agent decision from the audit log alone.

    python -m sentinel.audit replay path/to/audit.jsonl JE-1003 [--key-env AUDIT_HMAC_KEY] [--out report.md]

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
    out = [f"# Decision replay: {entry_id}", ""]
    if report is not None:
        verdict = "VERIFIED" if report.ok else "FAILED: do not rely on this log until the break is explained"
        out += [f"**Chain integrity:** {verdict} ({report.events} events, {report.checkpoints_checked} signed checkpoints)", ""]
        out += [f"- {p}" for p in report.problems] + ([""] if report.problems else [])

    decisions = [r for r in records if r["event_type"] == "decision.recorded"
                 and r.get("detail", {}).get("entry_id") == entry_id]
    if not decisions:
        return "\n".join(out + [f"No decision for {entry_id} was recorded in this log."])

    decision = decisions[-1]
    run = [r for r in records if r["correlation_id"] == decision["correlation_id"]]
    prompt = next((r for r in run if r["event_type"] == "prompt.submitted"), None)
    result = next((r for r in run if r["event_type"] == "run.completed"), None)
    evidence = evidence_window(run, entry_id, decision)
    seen = [r for r in evidence if r["event_type"] == "tool.completed" and r["tool_name"] != decision.get("tool_name")]
    denied = [r for r in evidence if r["event_type"] == "tool.denied"]
    d = decision["detail"]

    out += [
        "| Auditor's question | Answer from the log |",
        "|---|---|",
        f"| Who asked? | {prompt['on_behalf_of'] if prompt else '(no prompt recorded)'} at {prompt['timestamp'] if prompt else '?'} |",
        f"| What was asked? | {prompt['detail'].get('prompt') if prompt else '?'} |",
        f"| Which agent and model? | {decision['agent']['name']} {decision['agent']['version']} on {decision['agent']['model']} |",
        f"| Prompt and policy versions | prompt {decision['agent'].get('prompt_version')}, policy {decision['agent'].get('policy_version')} |",
        f"| What data did it see? | " + "; ".join(
            f"{r['tool_name'].split('__')[-1]} at {r['timestamp']} ({r['detail'].get('response_sha256', '')[:19]}...)" for r in seen
        ) + " |",
        f"| What was it refused? | " + ("; ".join(f"{r['tool_name'].split('__')[-1]} ({r['reason']})" for r in denied) or "nothing") + " |",
        f"| What did it decide? | **{d.get('recommendation')}**; approver required: {d.get('approver_required')} |",
        f"| Why? | {decision['reason']} |",
        f"| Under what authority? | {decision['authority']} |",
        f"| When? | {decision['timestamp']} (seq {decision['seq']}) |",
        f"| Run | correlation {decision['correlation_id']}, session {decision.get('session_id')}"
        + (f", {result['detail'].get('num_turns')} turns, ${result['detail'].get('total_cost_usd')}" if result else "") + " |",
        "",
        f"## Timeline (evidence window: seq {min(r['seq'] for r in evidence) if evidence else decision['seq']}-{decision['seq']}, plus denials)",
        "| seq | time | event | tool | outcome | tool_use_id |",
        "|---|---|---|---|---|---|",
    ]
    timeline = [r for r in run if r in evidence or r is prompt or r is result or r["seq"] == decision["seq"]
                or (r["event_type"] == "tool.completed" and r.get("tool_use_id") == decision.get("tool_use_id"))]
    for r in sorted(timeline, key=lambda r: r["seq"]):
        tool = (r.get("tool_name") or "").split("__")[-1]
        out.append(f"| {r['seq']} | {r['timestamp']} | {r['event_type']} | {tool} | {r['outcome']} | {r.get('tool_use_id') or ''} |")
    if len(decisions) > 1:
        out += ["", f"Note: {len(decisions)} decisions were recorded for {entry_id}; this report shows the latest."]
    return "\n".join(out)


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
