# M08-L07: Automated evidence packs

Module: M08 Pillar 7, Continuous Compliance & Assurance · Type: Code-along

`final/evidence_demo.py` builds the evidence pack in one call (suite, red team, fleet run, metrics, alerts,
dashboard, change control, scorecard and crosswalk, every file hashed and the manifest signed), verifies it, then
edits one file and verifies again.

```bash
uv run python lessons/M08-L07_automated-evidence-packs/final/evidence_demo.py
uv run python -m sentinel.evidence build --out out/evidence-pack && uv run python -m sentinel.evidence verify out/evidence-pack
```
Code walked through on screen: `src/sentinel/evidence/pack.py`, `rubric.py`, `policies/attestations.yaml`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
