"""
M11-L01: the AI system inventory and agent cards.

The inventory holds what only people can say (owner, purpose, decision role, who is affected, oversight,
assessments). Everything the code already knows (tier, model, tools, fingerprint, deployment path, regimes, latest
change, validation) is joined in, never copied. Then the lint catches what an auditor would: unregistered AI, an
owner who is also the builder, self-reviewed assessments, and an impact assessment older than a model change.

    uv run python lessons/M11-L01_ai-system-inventory-and-agent-cards/final/inventory_demo.py
    uv run python -m sentinel.governance inventory
    uv run python -m sentinel.governance card --agent aml-triage
"""
from __future__ import annotations

from sentinel.governance import Inventory, agent_card, lint_inventory, load_governance, status
from sentinel.monitoring.change import ChangeLog


def main() -> None:
    g = load_governance()                                    # the PRODUCTION fleet (M10) plus governance records
    print(f"1. THE INVENTORY: {g.inventory.name} v{g.inventory.version}, joined with the fleet, deployment and map")
    for a in g.fleet.agents:
        e = g.inventory.get(a.name)
        v = g.validations.latest(a.name)
        print(f"   {a.name:<17} tier {a.risk_tier}  {e.decision_role:<10} owner {e.business_owner:<42} "
              f"runs on {g.deployment.agents[a.name].path:<22} validation {status(v, g.fleet)}")
    regimes = g.rmap.applicability
    print(f"   lint: {lint_inventory(g.inventory, g.fleet, regimes, g.deployment, changes=g.changes) or 'clean'}")

    print("\n2. SHADOW AI: someone deploys a sixth agent without registering it")
    rogue = g.fleet.agents[0].model_copy(update={"name": "marketing-drafts", "organization": "Acme marketing",
                                                  "owner": "Marketing"})
    fleet6 = g.fleet.model_copy(update={"agents": [*g.fleet.agents, rogue]})
    for p in lint_inventory(g.inventory, fleet6, regimes):
        print(f"   {p}")

    print("\n3. OWNERSHIP AND SELF-REVIEW: the builder owns the use and reviews their own assessment")
    data = g.inventory.model_dump(mode="json")
    entry = data["systems"]["pa-reviewer"]
    entry["business_owner"] = entry["technical_owner"]
    entry["assessments"][0]["reviewer"] = entry["technical_owner"]
    entry["assessments"] = [a for a in entry["assessments"] if a["kind"] != "HIPAA-SRA"]
    for p in lint_inventory(Inventory.model_validate(data), g.fleet, regimes):
        print(f"   {p}")

    print("\n4. A MODEL CHANGE AFTER THE IMPACT ASSESSMENT: the assessment is about a system that no longer exists")
    rec = g.changes.records[-2].model_dump(mode="json")      # CHG-0010, aml-triage
    rec.update(id="CHG-0012", summary="Upgrade aml-triage to a newer model", changed=["model"],
               approvals=[{"name": "D. Okafor", "role": "BSA Officer", "date": "2026-11-12"},
                          {"name": "T. Nguyen", "role": "Model Risk Management", "date": "2026-11-12"}])
    changes = g.changes.model_dump(mode="json")
    log = ChangeLog.model_validate({**changes, "records": [*changes["records"], rec]})
    for p in lint_inventory(g.inventory, g.fleet, regimes, changes=log):
        print(f"   {p}")

    print("\n5. THE AGENT CARD: one page an examiner can read without opening the code")
    print("   " + agent_card(g, "aml-triage").replace("\n", "\n   ")[:1800] + "\n   ...")


if __name__ == "__main__":
    main()
