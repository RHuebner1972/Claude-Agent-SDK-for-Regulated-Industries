"""
M05-L07: the same fooled "model" against the same complaints, without and with the policy gate.

    uv run python lessons/M05-L07_prompt-injection-as-a-policy-problem/final/injection_demo.py

The script attempts exactly what the injected text in CMP-3006 and CMP-3007 asks for. We assume the model
IS fooled, then check whether the system still holds.
"""
from __future__ import annotations

import asyncio

from sentinel.policy import Subject
from sentinel.policy.complaint_tools import ComplaintStore, build_complaint_tools, complaint_enforcer
from sentinel.policy.simulate import INJECTED_TRIAGE, run_script

# Regulatory Affairs IS allowed to set MDR assessments, so role alone won't save us here.
RA = Subject(user="a.novak", role="regulatory_affairs", purpose="complaint_handling")


async def main() -> None:
    print("1. NAIVE: no policy, permission_mode='bypassPermissions'")
    store = ComplaintStore()
    log = await run_script(build_complaint_tools(store), INJECTED_TRIAGE, mode="bypassPermissions")
    print(log.table())
    print("  Record changes:", *store.changes, sep="\n    ")
    print("  CMP-3006 now:", {k: store.records["CMP-3006"][k] for k in ("patient_impact", "mdr_assessment", "status")})

    print("\n2. GATED: same script, policy enforced in PreToolUse, taint tracked in PostToolUse")
    store = ComplaintStore()
    enforcer = complaint_enforcer(store, RA)
    log = await run_script(build_complaint_tools(store), INJECTED_TRIAGE, enforcer=enforcer)
    print(log.table())
    print("  Record changes:", *store.changes, sep="\n    ")
    print("  Session state:", enforcer.environment)
    flagged = next(s for s in log.steps if s.context)
    print(f"  Context added after {flagged.tool} {flagged.args['complaint_id']}: {flagged.context[:80]}...")

    print("\n3. TAINT WITHOUT INJECTION: RA reads CMP-3003 (clean text), then says not reportable")
    store = ComplaintStore()
    for approver, label in [(None, "no approver"), (lambda decision, args: True, "approver says yes")]:
        enforcer = complaint_enforcer(store, RA, approver=approver)
        log = await run_script(build_complaint_tools(store), [
            ("get_complaint", {"complaint_id": "CMP-3003"}),
            ("set_mdr_assessment", {"complaint_id": "CMP-3003", "decision": "not_reportable",
                                    "rationale": "Battery shortfall, no therapy interruption, no injury."})],
            enforcer=enforcer)
        last = log.steps[-1]
        print(f"  {label:18} -> {last.outcome.upper():8} {enforcer.decisions[-1].message()[:90]}")


if __name__ == "__main__":
    asyncio.run(main())
