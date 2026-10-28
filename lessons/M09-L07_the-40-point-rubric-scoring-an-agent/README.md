# M09-L07: The 40-point rubric: scoring an agent with engineering and compliance together

Module: M09 The Regulatory Mapping Framework & 40-Point Rubric · Type: Demo

`final/rubric_review_demo.py` runs the compliance suite, proposes a rubric score, scopes each fleet agent to the
regimes that apply, traces aml-triage's clauses to code, tests and evidence, then applies a review session in which
reviewers who didn't build the evidence confirm or challenge each point. One challenge (rubric 7.5, the missing
federal banking 36-hour clock) turns a proposed 36/40 Audit-ready into a confirmed 35/40 Conditionally ready.

```bash
uv run python lessons/M09-L07_the-40-point-rubric-scoring-an-agent/final/rubric_review_demo.py
uv run python -m sentinel.evidence trace --agent aml-triage      # the clause-level trace
uv run python -m sentinel.evidence trace --regime HIPAA          # one regime across the fleet
uv run python -m sentinel.evidence review                        # proposed vs confirmed sign-off page
```
Code walked through on screen: `src/sentinel/evidence/mapping.py`, `review.py`,
`policies/regulatory_map.yaml`, `policies/reviews/fleet-2026-q4.yaml`.

The map is a teaching map, not legal advice. Confirm which clauses apply with your compliance partner.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
