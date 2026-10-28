# M11-L01: AI system inventory and agent cards

Module: M11 Governance, Validation & Board-Ready Evidence · Type: Lecture with demo

`final/inventory_demo.py` lists the AI system inventory joined with the production fleet, deployment manifest,
regulatory map and validation records, then shows what the inventory lint catches: an unregistered sixth agent
(GOV-001), a builder who also owns the use (GOV-003), a missing HIPAA risk analysis (GOV-004), a self-reviewed
assessment (GOV-006) and an impact assessment older than a model change (GOV-009). It ends with the agent card
for aml-triage.

```bash
uv run python lessons/M11-L01_ai-system-inventory-and-agent-cards/final/inventory_demo.py
uv run python -m sentinel.governance inventory
uv run python -m sentinel.governance card --agent aml-triage
```
Code walked through on screen: `src/sentinel/governance/policies/inventory.yaml`, `src/sentinel/governance/inventory.py`, `agent_card()` in `src/sentinel/governance/brief.py`.

Regulatory references are paraphrased and current as of 2026-10-28 (see `00_Course-Plan/Regulatory_Watchlist.md`). Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
