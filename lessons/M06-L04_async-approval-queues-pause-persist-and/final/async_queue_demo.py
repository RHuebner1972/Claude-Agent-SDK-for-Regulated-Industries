"""
M06-L04: pause, persist and resume. The run defers at a high-impact call, the process can exit, a person signs
hours later, and the SAME session resumes and runs exactly the approved call.

    uv run python lessons/M06-L04_async-approval-queues-pause-persist-and/final/async_queue_demo.py
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from sentinel.approvals import ApprovalGate, ApprovalQueue, FixedClock
from sentinel.approvals.aml_tools import AlertStore, build_aml_tools, oversight_policy, staff_signer
from sentinel.approvals.simulate import TRIAGE, run_script

KEY = b"course-demo-signing-key"
SESSION = "sess-aml-6b20"


def open_queue(path: Path, clock: FixedClock) -> ApprovalQueue:
    return ApprovalQueue(path, policy=oversight_policy()[0], signing_key=KEY, clock=clock)


async def main() -> None:
    work, clock, store = Path(tempfile.mkdtemp()), FixedClock(), AlertStore()
    tools = build_aml_tools(store)
    qpath = work / "approvals.json"

    def gate(q):
        return ApprovalGate(q, user="j.rivera", role="aml_analyst", agent="AML-Triage@1.0.0", mode="defer",
                            evidence=store.evidence, session_id=SESSION)

    print("RUN 1: the agent works until it reaches a call that needs a person")
    log = await run_script(tools, TRIAGE, gate=gate(open_queue(qpath, clock)), session_id=SESSION)
    print(log.table())
    print(f"  stop_reason=tool_deferred  deferred_tool_use={{id: {log.deferred.id}, name: {log.deferred.name}}}")

    print("\n... process exits. The queue is a file:")
    saved = json.loads(qpath.read_text())["requests"]["APR-000001"]
    print("  ", {k: saved[k] for k in ("request_id", "tool", "status", "requested_by", "due_at")})

    clock.advance(95)                                         # an hour and a half later, in another process
    reviewer_queue = open_queue(qpath, clock)
    print(f"\nREVIEW (95 min later, new process): {len(reviewer_queue.pending('aml_senior_analyst'))} waiting for a senior analyst")
    reviewer_queue.sign("APR-000001", staff_signer("m.chen"), "approve",
                        "Payroll pattern confirmed against 2025 history; amounts match headcount.")

    print("\nRUN 2: resume the same session; the deferred call fires PreToolUse again")
    log = await run_script(tools, TRIAGE, gate=gate(open_queue(qpath, clock)), start=log.paused_at, session_id=SESSION)
    print(log.table())
    final = open_queue(qpath, clock).get("APR-000001")
    print(f"  APR-000001 is now {final.status}; history: {[h['status'] for h in final.history]}")
    print(f"  Record changes: {store.changes}")


if __name__ == "__main__":
    asyncio.run(main())
