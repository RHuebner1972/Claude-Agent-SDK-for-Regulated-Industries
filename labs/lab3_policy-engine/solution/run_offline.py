"""
Lab 3, offline: three scripted runs through YOUR pipeline, then read the denials back from the audit logs.

    cd labs/lab3_policy-engine/solution        (or starter/ while you build)
    uv run python run_offline.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sentinel.audit import AuditStore, verify_log

from policy_gate.simulate import INJECTED_TRIAGE, QA_CLOSEOUT, run_script
from triage_pipeline import build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"
RUNS = [
    ("QA close-out (r.patel, qa_specialist)", "r.patel", "qa_specialist", QA_CLOSEOUT, "audit_qa.jsonl"),
    ("Injected triage (a.novak, regulatory_affairs)", "a.novak", "regulatory_affairs", INJECTED_TRIAGE, "audit_ra.jsonl"),
    ("Injected triage (m.ortiz, complaint_intake)", "m.ortiz", "complaint_intake", INJECTED_TRIAGE, "audit_intake.jsonl"),
]


async def main() -> None:
    for old in WORKSPACE.glob("*.jsonl"):
        old.unlink()                                              # fresh run each time
    key = os.getenv("AUDIT_HMAC_KEY", "course-demo-key").encode()
    for title, user, role, script, log_name in RUNS:
        p = build_pipeline(WORKSPACE, user=user, role=role, log_name=log_name)
        log = await run_script(p.tools, script, enforcer=p.enforcer, audit=p.audit,
                               session_id=f"sess-{role[:6]}-5a11")
        print(f"\n== {title}\n{log.table()}")
        print("  Record changes:", ", ".join(p.complaints.changes) or "(none)")
        print("  Emails sent:", len(p.complaints.outbox))
        denied = [r for r in AuditStore(WORKSPACE / log_name).records() if r["event_type"] == "tool.denied"]
        print(f"  Audit log: {len(denied)} denials, each with its rule ->",
              sorted({r['authority'].split(' ')[0] for r in denied}))
        print("  " + verify_log(WORKSPACE / log_name, key).render().splitlines()[0])
    print(f"\nPolicy: {p.enforcer.engine.version}")


if __name__ == "__main__":
    asyncio.run(main())
