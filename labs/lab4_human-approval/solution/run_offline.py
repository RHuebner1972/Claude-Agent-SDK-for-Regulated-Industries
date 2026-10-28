"""
Lab 4, offline: triage, approvals (and refusals), an escalation, then the resumed run executes what was approved.

    cd labs/lab4_human-approval/solution        (or starter/ while you build)
    uv run python run_offline.py
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from sentinel.audit import AuditStore, verify_log

from approval_desk.aml_tools import staff_signer
from approval_desk.simulate import TRIAGE, FixedClock, run_script
from approval_desk.sod import SegregationOfDutiesError
from aml_pipeline import build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace" / "offline"   # simulated clock; agent.py uses workspace/


def try_sign(p, request_id: str, user: str, meaning: str, reason: str) -> None:
    try:
        r = p.queue.sign(request_id, staff_signer(user), meaning, reason)
        print(f"  SIGNED  {request_id} by {user:9} -> {r.status} ({len(r.approvals)}/{r.approvals_required})")
    except SegregationOfDutiesError as exc:
        print(f"  REFUSED {request_id} by {user:9} -> {'; '.join(v[:7] for v in exc.violations)}")


async def main() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    for old in list(WORKSPACE.glob("*.json")) + list(WORKSPACE.glob("*.jsonl")):
        old.unlink()                                                  # fresh run each time
    clock = FixedClock()
    p = build_pipeline(WORKSPACE, clock=clock, mode="deny")
    print("RUN 1 (analyst j.rivera): the agent requests three actions")
    print((await run_script(p.tools, TRIAGE, gate=[p.kill, p.gate], audit=p.audit)).table())

    print("\nAPPROVALS")
    try_sign(p, "APR-000001", "j.rivera", "approve", "My own alert; payroll pattern is obvious.")
    try_sign(p, "APR-000001", "m.chen", "approve", "Payroll processor and amounts match 2025 history.")
    try_sign(p, "APR-000002", "t.nguyen", "approve", "Structuring pattern; recommend SAR.")
    try_sign(p, "APR-000002", "m.chen", "approve", "Six sub-$10k cash deposits in 8 days at 3 branches.")
    try_sign(p, "APR-000002", "d.okafor", "approve", "Agree; no business reason; refer for SAR filing.")
    clock.advance(70)                                                 # the BSA Officer is in a meeting...
    print(f"  70 minutes later: {p.queue.sweep() or 'no change'}; APR-000003 now open to "
          f"{p.queue.get('APR-000003').allowed_roles()}")
    try_sign(p, "APR-000003", "s.patel", "approve", "Funds moving to crypto within 24h; block wires pending review.")

    print("\nRUN 2 (resume): approved calls run once; nothing else changes")
    p2 = build_pipeline(WORKSPACE, clock=clock, mode="deny")         # a new process, same queue file
    log = await run_script(p2.tools, TRIAGE, gate=[p2.kill, p2.gate], audit=p2.audit, session_id="sess-aml-6b21")
    print(log.table())
    print(f"  Record changes: {p2.alerts.changes}")

    print("\nAPPROVAL RECORDS")
    for r in p2.queue.requests.values():
        for s in r.signatures:
            print(f"  {r.request_id} {r.tool:17} {s.name:13} {s.role:24} {s.meaning:8} {s.signed_at:%Y-%m-%d %H:%M:%S}Z")
        print(f"  {'':11}{'':18}signatures verify: {all(ok for _, ok in p2.queue.verify(r.request_id))}; status {r.status}")
    print("\nKILL-SWITCH DRILL (rubric 5.6)")
    p2.kill.engage(staff_signer("d.okafor"), "Drill: confirm the assistant stops on demand.")
    drill = await run_script(p2.tools, TRIAGE, gate=[p2.kill, p2.gate], audit=p2.audit, session_id="sess-aml-drill")
    print(f"  engaged -> {drill.steps[-1].outcome.upper()} at the first call: {drill.steps[-1].message[:70]}...")
    p2.kill.release(staff_signer("d.okafor"), "Drill complete; assistant may resume.")
    after = await run_script(p2.tools, TRIAGE[:1], gate=[p2.kill, p2.gate], audit=p2.audit, session_id="sess-aml-drl2")
    print(f"  released -> {after.steps[0].outcome}")

    key = os.getenv("AUDIT_HMAC_KEY", "course-demo-key").encode()
    events = AuditStore(WORKSPACE / "audit.jsonl").records()
    kinds = {k: sum(e["event_type"] == k for e in events) for k in
             ("approval.requested", "approval.decided", "approval.escalated", "tool.denied")}
    print(f"\nAudit log: {kinds}")
    print(verify_log(WORKSPACE / "audit.jsonl", key).render().splitlines()[0])


if __name__ == "__main__":
    asyncio.run(main())
