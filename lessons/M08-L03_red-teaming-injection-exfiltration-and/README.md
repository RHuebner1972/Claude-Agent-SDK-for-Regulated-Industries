# M08-L03: Red-teaming: injection, exfiltration and policy-evasion suites

Module: M08 Pillar 7, Continuous Compliance & Assurance · Type: Code-along

`final/redteam_demo.py` lists the 13-case corpus, replays it against the fleet's controls (each case assumes the
model was fooled), then replays it against a fleet with log masking and the handoff contract switched off.

```bash
uv run python lessons/M08-L03_red-teaming-injection-exfiltration-and/final/redteam_demo.py
uv run python -m sentinel.monitoring.redteam --out out/redteam-report.json      # what the nightly job runs
```
Code walked through on screen: `src/sentinel/monitoring/redteam/corpus.yaml`, `redteam/runner.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
