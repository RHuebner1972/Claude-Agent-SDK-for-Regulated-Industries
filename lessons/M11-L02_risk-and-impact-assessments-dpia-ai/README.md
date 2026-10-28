# M11-L02: Risk and impact assessments: DPIA, AI impact assessment and FMEA

Module: M11 Governance, Validation & Board-Ready Evidence · Type: Lecture with demo

`final/fmea_demo.py` shows which assessments each agent's regimes require, ranks complaint-triage's failure modes
by RPN and by the course's severity-first priority, prints aml-triage's register, then runs the compliance suite
and the rubric review: FM-AML-02 is flagged because its rating assumes rubric item 7.5, which the reviewer
challenged (RISK-007). Last, it shows who may accept a risk (RISK-002, RISK-003). The suite run takes about 30
seconds.

```bash
uv run python lessons/M11-L02_risk-and-impact-assessments-dpia-ai/final/fmea_demo.py
uv run python -m sentinel.governance risks --agent complaint-triage
```
Code walked through on screen: `src/sentinel/governance/policies/risk_register.yaml` (rating scales at the top), `src/sentinel/governance/risk.py`.

Regulatory references are paraphrased and current as of 2026-10-28 (see `00_Course-Plan/Regulatory_Watchlist.md`). Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
