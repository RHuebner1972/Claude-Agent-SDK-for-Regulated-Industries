# M10-L08: Reference architecture walkthrough

Module: M10 Production Deployment in Regulated Infrastructure · Type: Demo

`final/reference_demo.py` checks each agent's requirements against the path catalog, runs the deployment pre-flight
for the production manifest, checks `deploy/reference` (compose, proxy allowlist) and a broken 'quick fix', then
builds the evidence pack for the production fleet: proposed 40/40, confirmed 39/40 after review (7.5 is still
challenged until the banking clock exists).

```bash
uv run python lessons/M10-L08_reference-architecture-walkthrough/final/reference_demo.py
uv run python -m sentinel.deploy preflight
FLEET_FILE=src/sentinel/monitoring/policies/fleet-prod.yaml uv run pytest compliance
```
Code walked through on screen: `deploy/reference/` (Dockerfile, compose.yaml, egress-proxy/squid.conf), `src/sentinel/deploy/deployment.py`, `src/sentinel/monitoring/policies/fleet-prod.yaml`.

Vendor facts (paths, regions, agreements) are as of 2026-10-28 in `src/sentinel/deploy/policies/deployment_paths.yaml`:
re-check them with the provider before relying on them. Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
