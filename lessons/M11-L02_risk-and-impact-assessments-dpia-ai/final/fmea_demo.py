"""
M11-L02: risk and impact assessments for agents, and an FMEA that knows when its controls stop being true.

Which assessments an agent needs depends on its regimes. The FMEA rates each failure mode with today's controls,
ranks severity first (not by RPN), and ties every control to a rubric item, so a withheld point in the rubric
review shows up as a risk rating that rests on a control nobody confirmed.

    uv run python lessons/M11-L02_risk-and-impact-assessments-dpia-ai/final/fmea_demo.py
    uv run python -m sentinel.governance risks --agent complaint-triage
"""
from __future__ import annotations

from sentinel.governance import (RiskRegister, confirmed_scorecard, lint_register, load_governance, priority,
                                 render_register, required_assessments)


def main() -> None:
    g = load_governance()
    print("1. WHICH ASSESSMENTS? The regimes decide (course policy; your AI policy sets its own list)")
    for a in g.fleet.agents:
        print(f"   {a.name:<17} {', '.join(g.rmap.regimes_for(a.name)):<34} -> "
              f"{', '.join(required_assessments(g.rmap.regimes_for(a.name)))}")
    print(f"   an agent processing EU personal data (GDPR) -> {', '.join(required_assessments(['GDPR']))}")

    print("\n2. RPN vs SEVERITY FIRST: complaint-triage, ranked both ways")
    rows = g.register.for_agent("complaint-triage")
    print("   by RPN      : " + ", ".join(f"{f.id} (RPN {f.rpn})" for f in sorted(rows, key=lambda f: -f.rpn)))
    print("   by priority : " + ", ".join(f"{f.id} ({f.priority}, S{f.s})" for f in rows))
    print("   RPN puts noisy search suggestions (S3) above a missed death report (S10).")
    for s, o, d in [(10, 3, 3), (3, 7, 6), (9, 4, 7), (7, 6, 2)]:
        print(f"   priority(S={s}, O={o}, D={d}) = {priority(s, o, d):<6} RPN {s * o * d}")

    print("\n3. THE REGISTER, WITH TODAY'S CONTROLS")
    print("   " + render_register(g.register.for_agent("aml-triage")).replace("\n", "\n   "))

    print("\n4. ARE THE CONTROLS STILL TRUE? Run the suite and the review (as CI does), then lint the register")
    _, confirmed = confirmed_scorecard(g)
    print(f"   confirmed {confirmed.score}/40 ({confirmed.rating})")
    rubric_ids, agents = g.rubric_ids, [a.name for a in g.fleet.agents]
    for p in lint_register(g.register, agents, rubric_ids, confirmed):
        print(f"   {p}")

    print("\n5. ACCEPTANCE RULES: who may accept a risk, and for how long")
    data = g.register.model_dump(mode="json")
    fm = next(f for f in data["failure_modes"] if f["id"] == "FM-AML-02")
    fm["action"] = None
    fm["acceptance"] = {"by": "S. Patel, Chief Compliance Officer", "date": "2026-10-28", "expires": "2027-04-30",
                        "rationale": "We will add the clock eventually"}
    fm2 = next(f for f in data["failure_modes"] if f["id"] == "FM-PA-01")
    fm2["acceptance"]["by"] = fm2["owner"]
    for p in lint_register(RiskRegister.model_validate(data), agents, rubric_ids):
        print(f"   {p}")


if __name__ == "__main__":
    main()
