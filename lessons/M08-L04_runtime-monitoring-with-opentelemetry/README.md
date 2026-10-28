# M08-L04: Runtime monitoring with OpenTelemetry: deny rates, PII hits, approvals and cost

Module: M08 Pillar 7, Continuous Compliance & Assurance · Type: Code-along

`final/monitoring_demo.py` runs the fleet, turns each agent's audit log into OpenTelemetry metrics, evaluates the
alert rules and writes a dashboard to `final/out/`. Then it reruns with the CCB assistant's handoff contract
switched off and the leak alert pages.

```bash
uv run python lessons/M08-L04_runtime-monitoring-with-opentelemetry/final/monitoring_demo.py
```
Code walked through on screen: `src/sentinel/monitoring/metrics.py`, `alerts.py`, `policies/alerts.yaml`,
`dashboard.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
