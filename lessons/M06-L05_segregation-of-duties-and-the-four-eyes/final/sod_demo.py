"""
M06-L05: segregation of duties. Who may sign, and who may not, even with the right job title.

    uv run python lessons/M06-L05_segregation-of-duties-and-the-four-eyes/final/sod_demo.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sentinel.approvals import ApprovalQueue, FixedClock, SegregationOfDutiesError, Signer
from sentinel.approvals.aml_tools import AlertStore, oversight_policy, staff_signer

SAR = {"alert_id": "ALR-5001", "activity_type": "structuring", "suspicious_amount": 57800,
       "narrative": "Six cash deposits of $9,300-$9,900 in 8 days across three branches; expected cash is "
                    "about $4,000 a month. Pattern consistent with structuring."}
REASON = "Deposits split across branches just below the CTR threshold; no business explanation."


def main() -> None:
    store, clock = AlertStore(), FixedClock()
    queue = ApprovalQueue(Path(tempfile.mkdtemp()) / "q.json", policy=oversight_policy()[0],
                          signing_key=b"course-demo-signing-key", clock=clock, agent_ids={"AML-Triage"})
    r = queue.submit("recommend_sar", SAR, requested_by="j.rivera", requester_role="aml_analyst",
                     agent="AML-Triage@1.0.0", rationale=SAR["narrative"], evidence=store.evidence("recommend_sar", SAR))
    print(f"{r.request_id}: recommend_sar on ALR-5001, needs {r.approvals_required} approvals incl. {r.must_include_role}\n")
    attempts = [
        ("j.rivera, the analyst who asked", staff_signer("j.rivera")),
        ("the agent itself", Signer(user="AML-Triage", name="AML Triage Assistant", role="agent")),
        ("k.ward, relationship manager", staff_signer("k.ward")),
        ("t.nguyen, senior analyst AND this customer's RM", staff_signer("t.nguyen")),
        ("m.chen, senior analyst", staff_signer("m.chen")),
        ("m.chen again", staff_signer("m.chen")),
        ("a.brooks, a second senior analyst", Signer(user="a.brooks", name="Alex Brooks", role="aml_senior_analyst")),
        ("d.okafor, BSA Officer", staff_signer("d.okafor")),
    ]
    for label, signer in attempts:
        try:
            queue.sign(r.request_id, signer, "approve", REASON)
            req = queue.get(r.request_id)
            print(f"  SIGNED  {label:48} -> {len(req.approvals)}/{req.approvals_required}, status {req.status}")
        except SegregationOfDutiesError as exc:
            print(f"  REFUSED {label:48} -> " + "; ".join(v.split(' ')[0] for v in exc.violations))
            for v in exc.violations:
                print(f"            {v}")
    print(f"\nSignatures verify: {queue.verify(r.request_id)}")


if __name__ == "__main__":
    main()
