"""
M05-L06: pre-conditions (typed inputs, checked before the policy) and post-conditions (checked on what came back).

    uv run python lessons/M05-L06_pre-and-post-conditions-validating-tool/final/conditions_demo.py
"""
from __future__ import annotations

import asyncio

from sentinel.policy import Subject
from sentinel.policy.complaint_tools import ComplaintStore, build_complaint_tools, complaint_enforcer
from sentinel.policy.simulate import run_script

RA = Subject(user="a.novak", role="regulatory_affairs", purpose="complaint_handling")


async def main() -> None:
    print("PRE-CONDITIONS: the input must match the tool's schema before the policy is even asked")
    store = ComplaintStore()
    enforcer = complaint_enforcer(store, RA)
    for args in [{"complaint_id": "CMP-3003", "decision": "reportable",
                  "rationale": "Battery failure could delay therapy; meets 803.50 malfunction criteria."},
                 {"complaint_id": "3003", "decision": "reportable", "rationale": "short"},
                 {"complaint_id": "CMP-3003", "decision": "probably_fine", "rationale": "x" * 25,
                  "override": True}]:
        d = enforcer.decide("mcp__complaints__set_mdr_assessment", args)
        print(f"  {d.effect.upper():5} [{d.rule_id}] {d.reason[:110]}")

    print("\nPOST-CONDITIONS: a search tool with a bug returns other complainants' contact details")
    for leaky in (False, True):
        store = ComplaintStore(leaky_search=leaky)
        enforcer = complaint_enforcer(store, RA)
        log = await run_script(build_complaint_tools(store), [("search_similar", {"complaint_id": "CMP-3001"})],
                               enforcer=enforcer)
        step = log.steps[0]
        print(f"  leaky_search={leaky!s:5} -> {step.outcome:8} model sees: {step.message[:90]!r}")


if __name__ == "__main__":
    asyncio.run(main())
