"""
M05-L05: attribute-based decisions. The same tool call, decided by WHO asks, WHY, and the state of the RECORD.

    uv run python lessons/M05-L05_context-aware-decisions-role-data-class/final/abac_demo.py
"""
from __future__ import annotations

from sentinel.policy import PolicyEngine, Subject, build_context
from sentinel.policy.complaint_tools import COMPLAINTS_POLICY, ComplaintStore

ROLES = ["complaint_intake", "qa_specialist", "regulatory_affairs"]
ACTIONS = [
    ("get_complaint", {"complaint_id": "CMP-3001"}),
    ("add_investigation_note", {"complaint_id": "CMP-3001", "note": "Lot FS3-2611 trend check started."}),
    ("set_mdr_assessment", {"complaint_id": "CMP-3003", "decision": "reportable", "rationale": "x" * 20}),
    ("close_complaint", {"complaint_id": "CMP-3001"}),
    ("close_complaint", {"complaint_id": "CMP-3002"}),
    ("send_customer_email", {"complaint_id": "CMP-3009", "to": "alan.fisk@example.net"}),
    ("send_customer_email", {"complaint_id": "CMP-3009", "to": "alan.fisk.home@example.com"}),
]


def main() -> None:
    engine, store = PolicyEngine.from_file(COMPLAINTS_POLICY), ComplaintStore()
    env = {"tainted": False, "injection_suspected": False}
    print(f"{'action':44}" + "".join(f"{r:>22}" for r in ROLES))
    for tool, args in ACTIONS:
        label = f"{tool} {args['complaint_id']}" + (f" -> {args['to'].split('@')[0]}" if "to" in args else "")
        cells = []
        for role in ROLES:
            subject = Subject(user="demo", role=role, purpose="complaint_handling")
            d = engine.evaluate(build_context(subject, tool, args, store.resolve(tool, args), env))
            cells.append(f"{d.effect} {d.rule_id}")
        print(f"{label:44}" + "".join(f"{c:>22}" for c in cells))

    # Purpose of use: the same QA specialist, the same read, a different reason for asking.
    print("\nPurpose of use (qa_specialist, get_complaint CMP-3001):")
    for purpose in ("complaint_handling", "marketing_analytics"):
        subject = Subject(user="r.patel", role="qa_specialist", purpose=purpose)
        d = engine.evaluate(build_context(subject, "get_complaint", {"complaint_id": "CMP-3001"},
                                          store.resolve("get_complaint", {"complaint_id": "CMP-3001"}), env))
        print(f"  {purpose:20} {d.effect.upper():5} [{d.rule_id}] {d.reason}")


if __name__ == "__main__":
    main()
