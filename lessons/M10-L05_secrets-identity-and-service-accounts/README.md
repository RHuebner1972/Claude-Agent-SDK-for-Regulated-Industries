# M10-L05: Secrets, identity and service accounts

Module: M10 Production Deployment in Regulated Infrastructure · Type: Demo

`final/identity_demo.py` shows aml-triage's workload identity, refuses a person's account, issues a 5-minute token
with one scope, refuses broader scopes and longer lifetimes, lets the token expire, adds the credential outside the
agent's sandbox, and scans logs for credential-shaped strings.

```bash
uv run python lessons/M10-L05_secrets-identity-and-service-accounts/final/identity_demo.py
```
Code walked through on screen: `src/sentinel/deploy/identity.py`. `TokenBroker` is a local stand-in for AWS STS, Google workload identity federation or Microsoft Entra workload identities.

Vendor facts (paths, regions, agreements) are as of 2026-10-28 in `src/sentinel/deploy/policies/deployment_paths.yaml`:
re-check them with the provider before relying on them. Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
