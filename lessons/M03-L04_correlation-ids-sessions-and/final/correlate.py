"""
M03-L04: reconstruct what happened from IDs alone.

    uv run python lessons/M03-L04_correlation-ids-sessions-and/final/correlate.py [path/to/audit.jsonl]

Three IDs do the work:
  correlation_id  one run, across every system it touches (the audit log AND the recommendations store)
  session_id      the SDK conversation: links to the transcript the SDK keeps on disk
  tool_use_id     one tool call: pairs the request with its result, or with its denial
With no path, it generates a fresh offline run first.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def pair_tool_calls(events: list[dict]) -> dict[str, dict[str, dict]]:
    """tool_use_id -> {"tool.requested": event, "tool.completed"/"tool.denied"/"tool.failed": event}"""
    calls: dict[str, dict[str, dict]] = defaultdict(dict)
    for e in events:
        if e.get("tool_use_id") and e["event_type"].startswith("tool."):
            calls[e["tool_use_id"]][e["event_type"]] = e
    return calls


def report(events: list[dict]) -> None:
    runs = defaultdict(list)
    for e in events:
        runs[e["correlation_id"]].append(e)
    for correlation_id, run in runs.items():
        prompt = next((e for e in run if e["event_type"] == "prompt.submitted"), {})
        print(f"\nRUN {correlation_id}")
        print(f"  asked by {prompt.get('on_behalf_of')} | session {run[0].get('session_id')}")
        print(f"  transcript: {prompt.get('detail', {}).get('transcript_path')}")
        for tid, pair in pair_tool_calls(run).items():
            req = pair.get("tool.requested", {})
            ended = next((k for k in ("tool.completed", "tool.denied", "tool.failed") if k in pair), None)
            name = req.get("tool_name", "?").split("__")[-1]
            status = {"tool.completed": "ran", "tool.denied": "DENIED", "tool.failed": "FAILED"}.get(ended, "NO OUTCOME (investigate)")
            print(f"  {tid}  {name:<22} {json.dumps(req.get('detail', {}).get('input', {}))[:48]:<50} {status}")
        decisions = [e for e in run if e["event_type"] == "decision.recorded"]
        print(f"  decisions: " + ", ".join(f"{d['detail']['entry_id']}={d['detail']['recommendation']}" for d in decisions))


def cross_check(events: list[dict], recommendations: Path) -> None:
    """Every downstream recommendation must trace back to a decision in the audit log, and vice versa."""
    if not recommendations.exists():
        return
    logged = {(e["correlation_id"], e["detail"]["entry_id"]) for e in events if e["event_type"] == "decision.recorded"}
    stored = {(r["correlation_id"], r["entry_id"]) for r in load(recommendations)}
    print(f"\nCross-check with {recommendations.name}: {len(stored & logged)} matched, "
          f"{len(stored - logged)} stored but never logged, {len(logged - stored)} logged but never stored")


async def make_sample(path: Path) -> None:
    from sentinel.audit import AuditHooks, AuditStore
    from sentinel.audit.simulate import DEMO_AGENT, fixed_clock, simulate_ledger_review
    hooks = AuditHooks(AuditStore(path), agent=DEMO_AGENT, on_behalf_of="j.chen", clock=fixed_clock())
    await simulate_ledger_review(hooks, entries=["JE-1001", "JE-1003", "JE-1010"])


def main() -> None:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = Path(tempfile.mkdtemp()) / "audit.jsonl"
        asyncio.run(make_sample(path))
    events = load(path)
    report(events)
    cross_check(events, path.with_name("recommendations.jsonl"))


if __name__ == "__main__":
    main()
