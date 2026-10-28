# M11 practice activity: Brief the board after a model change

Northshore Health Plan upgrades pa-reviewer to a new model. You put the change under change control, redo the
impact assessment, add the validator's finding to the risk register, write a new validation record pinned to the
new configuration, and generate a brief for the Quality and Compliance Committee that lints clean.

Instructions and questions: `Modules/M11_governance-and-board-evidence/assignment/M11_assignment.md`.

```bash
mkdir -p practice/m11
cp src/sentinel/monitoring/policies/fleet-prod.yaml src/sentinel/monitoring/policies/changes.yaml practice/m11/
cp src/sentinel/governance/policies/inventory.yaml src/sentinel/governance/policies/risk_register.yaml \
   src/sentinel/governance/policies/validations.yaml practice/m11/
uv run python lessons/M11-ASSIGNMENT_board-brief/check_board_brief.py      # repeat until ALL CHECKS PASS
```

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
