"""
M06-L03: two ways to put a human in the loop with the Agent SDK.

    uv run python lessons/M06-L03_implementing-approvals-with-can-use/final/gate_demo.py

Part 1, can_use_tool: the run WAITS while a reviewer decides in another window. No decision in time = no.
Part 2, PreToolUse hook (deny mode): the agent doesn't wait; it queues the request and carries on.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from sentinel.approvals import ApprovalGate, ApprovalQueue, FixedClock
from sentinel.approvals.aml_tools import AlertStore, build_aml_tools, full_name, oversight_policy, staff_signer
from sentinel.approvals.simulate import TRIAGE, run_script

CLOSE = {"alert_id": "ALR-5002", "disposition": "false_positive",
         "rationale": "Bi-weekly ACH to the same payroll processor since 2015; amounts match payroll."}


async def reviewer(queue: ApprovalQueue, after_s: float, user: str, meaning: str, reason: str) -> None:
    """Stands in for a person clicking Approve or Reject in a review screen."""
    await asyncio.sleep(after_s)
    request = queue.pending()[-1]
    queue.sign(request.request_id, staff_signer(user), meaning, reason)
    print(f"    reviewer {user} signed {request.request_id}: {meaning}")


async def main() -> None:
    work, store = Path(tempfile.mkdtemp()), AlertStore()
    policy, _ = oversight_policy()
    queue = ApprovalQueue(work / "approvals.json", policy=policy, signing_key=b"course-demo-signing-key")
    gate = ApprovalGate(queue, user="j.rivera", role="aml_analyst", agent="AML-Triage@1.0.0", evidence=store.evidence)

    print("PART 1  can_use_tool waits for a reviewer")
    for label, who, meaning, wait in [("reviewer approves after 1s", "m.chen", "approve", 1.0),
                                      ("reviewer rejects after 1s", "m.chen", "reject", 1.0),
                                      ("nobody answers within 2s", None, None, None)]:
        args = {**CLOSE, "rationale": CLOSE["rationale"] + f" ({label})"}   # a distinct call each time
        task = asyncio.create_task(reviewer(queue, wait, who, meaning, "Checked payroll history for 2025-26.")) if who else None
        result = await gate.can_use_tool(full_name("close_alert"), args, SimpleNamespace(tool_use_id="t1"),
                                         max_wait_s=2.0, poll_s=0.25)
        if task:
            await task
        print(f"  {label:28} -> {type(result).__name__}  {getattr(result, 'message', '')}")

    print("\nPART 2  PreToolUse hook in deny mode: queue it, keep working")
    queue2 = ApprovalQueue(work / "approvals2.json", policy=policy, signing_key=b"course-demo-signing-key",
                           clock=FixedClock())
    gate2 = ApprovalGate(queue2, user="j.rivera", role="aml_analyst", agent="AML-Triage@1.0.0", mode="deny",
                         evidence=store.evidence)
    log = await run_script(build_aml_tools(store), TRIAGE, gate=gate2)
    print(log.table())
    print(f"  Queue: {[(r.request_id, r.tool, r.status) for r in queue2.requests.values()]}")
    print(f"  Record changes so far: {store.changes}")


if __name__ == "__main__":
    asyncio.run(main())
