"""M11 practice activity: re-validate pa-reviewer after a model change and brief Northshore's quality committee.

Reads your copies in <course-repo>/practice/m11/ (fleet-prod.yaml, changes.yaml, inventory.yaml,
risk_register.yaml, validations.yaml), never the course files. Run from the root of course-repo:

    uv run python lessons/M11-ASSIGNMENT_board-brief/check_board_brief.py [practice-dir]

The platform's rubric score comes from running the compliance suite on the course production fleet (the same
controls run for your upgraded agent). Change control for YOUR change is checked here, against your copies.
"""
import sys
from datetime import date
from pathlib import Path

from sentinel.governance import board_brief, confirmed_scorecard, lint_all, load_governance, status
from sentinel.monitoring.change import check_change_control

ROOT = Path(__file__).resolve().parents[2]                     # course-repo
HERE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "practice" / "m11"
AGENT, ORG, OLD_MODEL = "pa-reviewer", "Northshore Health Plan", "claude-sonnet-5-5"


def check(ok: bool, label: str, hint: str = "") -> bool:
    print(f"  [{'x' if ok else ' '}] {label}" + ("" if ok or not hint else f"\n        -> {hint}"))
    return ok


def main() -> None:
    files = {k: HERE / f"{k}.yaml" for k in ("fleet-prod", "changes", "inventory", "risk_register", "validations")}
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing:
        sys.exit(f"Copy the course files first (see the activity instructions). Missing: {missing}")
    g = load_governance(files["fleet-prod"], inventory=files["inventory"], register=files["risk_register"],
                        validations=files["validations"], changes=files["changes"])
    agent = g.fleet.get(AGENT)
    print(f"{AGENT}: model {agent.model}, running {agent.fingerprint()}\n")

    print("1. THE CHANGE")
    results = [check(agent.model != OLD_MODEL, "pa-reviewer runs a new model in practice/m11/fleet-prod.yaml",
                     f"change `model: {OLD_MODEL}` for pa-reviewer (task 1)")]
    cc = check_change_control(g.fleet, g.changes)
    results.append(check(not any(cc.values()), "every running configuration has an approved change record",
                         "; ".join(f for items in cc.values() for f in items)[:300]))

    print("\n2. THE GOVERNANCE RECORDS")
    lints = lint_all(g)
    for key in ("inventory", "risks", "validation"):
        results.append(check(not lints[key], f"{key} lint clean", "; ".join(lints[key])[:400]))
    v = g.validations.latest(AGENT)
    results.append(check(v is not None and v.id != "VAL-PA-001" and status(v, g.fleet) == "current",
                         "a NEW validation record pins the configuration now running",
                         "add VAL-PA-002 with validated_fingerprint set to the fingerprint printed above (task 5)"))
    aiia = g.inventory.get(AGENT).latest("AIIA")
    results.append(check(aiia is not None and aiia.id != "AIIA-PA-001", "the impact assessment was redone (task 3)",
                         "add AIIA-PA-002 dated on or after the change approval"))
    new_fm = [f for f in g.register.for_agent(AGENT) if f.id not in ("FM-PA-01", "FM-PA-02")]
    results.append(check(bool(new_fm), "the validator's finding is in the risk register (task 4)",
                         "add FM-PA-03 for the wrong-request summary"))
    for f in new_fm:
        print(f"        {f.id}: S{f.s} O{f.o} D{f.d} -> {f.priority}, {f.treatment}")

    print("\n3. THE BRIEF (running the compliance suite on the production fleet first: about 30 seconds)")
    run, confirmed = confirmed_scorecard(load_governance())
    md, problems = board_brief(g, ORG, confirmed, run, audience="Quality and Compliance Committee",
                               prepared_by="L. Brandt, Privacy Officer", as_of=max(date(2026, 10, 28), *(
                                   date.fromisoformat(c.approvals[-1].date) for c in g.changes.records)))
    out = HERE / "brief-northshore.md"
    out.write_text(md, encoding="utf-8")
    results.append(check(not problems, f"brief lint clean: every claim cites evidence ({out})", "; ".join(problems)))
    results.append(check("NOT the one validated" not in md, "the brief says production runs the validated configuration"))

    print("\nALL CHECKS PASS" if all(results) else f"\n{results.count(False)} check(s) to fix")


if __name__ == "__main__":
    main()
