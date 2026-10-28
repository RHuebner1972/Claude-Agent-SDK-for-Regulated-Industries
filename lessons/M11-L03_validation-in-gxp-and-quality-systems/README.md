# M11-L03: Validation in GxP and quality systems: CSV vs. CSA

Module: M11 Governance, Validation & Board-Ready Evidence · Type: Lecture with demo

`final/validation_demo.py` prints every agent's validation record and whether production still runs the
validated configuration, walks through the CSA record for complaint-triage (intended use, process risk,
assurance activities, record), then breaks it: no scripted testing for high process risk (VAL-002) and a
developer who validates their own work (VAL-001). Step 4 is the model-risk lens used in M11-L04: an unconditional
'fit' on challenged evidence (VAL-005) and a missing effective challenge (VAL-003). Step 5 swaps pa-reviewer's
model and both the validation record (VAL-004) and change control go red.

```bash
uv run python lessons/M11-L03_validation-in-gxp-and-quality-systems/final/validation_demo.py
uv run python -m sentinel.governance validate
```
Code walked through on screen: `src/sentinel/governance/policies/validations.yaml`, `src/sentinel/governance/validation.py`.

Regulatory references are paraphrased and current as of 2026-10-28 (see `00_Course-Plan/Regulatory_Watchlist.md`). Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
