"""
M11-L03 (and L04): validation records under CSA and under a model-risk lens.

A record says the agent is fit for ONE intended use, in ONE configuration (the fleet fingerprint), on stated
evidence, judged by someone who didn't build it. CSA scales the rigor to process risk; the MRM lens asks for
conceptual soundness, outcomes analysis, ongoing monitoring and effective challenge. Change the model and every
record that pinned the old configuration goes stale.

    uv run python lessons/M11-L03_validation-in-gxp-and-quality-systems/final/validation_demo.py
    uv run python -m sentinel.governance validate
"""
from __future__ import annotations

from sentinel.governance import (ValidationSet, confirmed_scorecard, lint_validations, load_governance,
                                 summary_md)
from sentinel.monitoring.change import check_change_control


def main() -> None:
    g = load_governance()
    print("1. EVERY PRODUCTION AGENT HAS A CURRENT RECORD")
    print("   " + summary_md(g.validations, g.fleet).replace("\n", "\n   "))

    print("\n2. A CSA RECORD (complaint-triage): intended use -> process risk -> assurance activities -> record")
    r = g.validations.latest("complaint-triage")
    print(f"   intended use : {r.intended_use}")
    print(f"   process risk : {r.process_risk} (a failure could foreseeably compromise safety: a missed MDR)")
    for a in r.activities:
        print(f"   {a.method:<19} {a.what:<62} -> {a.result}")
    print(f"   validator    : {r.validator} (developer: {r.developer})")

    print("\n3. WHAT THE LINT CATCHES: no scripted tests for high risk; the developer validates their own work")
    data = g.validations.model_dump(mode="json")
    rec = next(x for x in data["records"] if x["agent"] == "complaint-triage")
    rec["activities"] = [a for a in rec["activities"] if a["method"] != "scripted"]
    rec["validator"] = rec["developer"]
    for p in lint_validations(ValidationSet.model_validate(data), g.fleet, g.rubric_ids):
        print(f"   {p}")

    print("\n4. THE MRM LENS (aml-triage): drop effective challenge, then claim an unconditional 'fit'")
    _, confirmed = confirmed_scorecard(g)
    data = g.validations.model_dump(mode="json")
    rec = next(x for x in data["records"] if x["agent"] == "aml-triage")
    print("   elements: " + ", ".join(a["method"] for a in rec["activities"]))
    rec["conclusion"], rec["conditions"] = "fit", []
    for p in lint_validations(ValidationSet.model_validate(data), g.fleet, g.rubric_ids, confirmed):
        print(f"   {p}")
    rec["activities"] = [a for a in rec["activities"] if a["method"] != "effective_challenge"]
    for p in lint_validations(ValidationSet.model_validate(data), g.fleet, g.rubric_ids, confirmed):
        print(f"   {p}")

    print("\n5. A MODEL CHANGE: the configuration in production is no longer the one validated")
    upgraded = [a.model_copy(update={"model": "claude-opus-5-5"}) if a.name == "pa-reviewer" else a
                for a in g.fleet.agents]
    fleet = g.fleet.model_copy(update={"agents": upgraded})
    for p in lint_validations(g.validations, fleet, g.rubric_ids):
        print(f"   {p}")
    print(f"   change control agrees: {check_change_control(fleet, g.changes)['pa-reviewer'][0]}")


if __name__ == "__main__":
    main()
