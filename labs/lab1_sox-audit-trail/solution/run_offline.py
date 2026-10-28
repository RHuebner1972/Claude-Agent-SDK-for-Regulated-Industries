"""
Lab 1, offline: run the scripted LedgerBot review through your audit pipeline (no API key needed).

    cd labs/lab1_sox-audit-trail/solution      (or starter/ while you build)
    uv run python run_offline.py

Writes workspace/audit.jsonl, verifies it, and writes a decision-replay report for JE-1003.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from audit_trail import AuditHooks, AuditStore, replay_decision, verify_log
from audit_trail.simulate import DEMO_AGENT, simulate_ledger_review

WORKSPACE = Path(__file__).resolve().parent / "workspace"


async def main() -> None:
    key = os.getenv("AUDIT_HMAC_KEY", "course-demo-key").encode()
    for old in WORKSPACE.glob("audit*.jsonl"):
        old.unlink()                                      # fresh log for each practice run
    store = AuditStore(WORKSPACE / "audit.jsonl", hmac_key=key, checkpoint_every=25)
    audit = AuditHooks(store, agent=DEMO_AGENT, on_behalf_of="j.chen")
    await simulate_ledger_review(audit)
    print(f"{len(store.records())} events written to {store.path}")
    try:
        report = verify_log(store.path, key)
    except NotImplementedError:
        print("verify_log: not written yet (TODO 7)")
        return
    print(report.render())
    try:
        replay = replay_decision(store.records(), "JE-1003", report)
    except NotImplementedError:
        print("replay_decision: not written yet (TODO 8)")
        return
    (WORKSPACE / "replay_JE-1003.md").write_text(replay + "\n", encoding="utf-8")
    print(f"Replay report: {WORKSPACE / 'replay_JE-1003.md'}")


if __name__ == "__main__":
    asyncio.run(main())
