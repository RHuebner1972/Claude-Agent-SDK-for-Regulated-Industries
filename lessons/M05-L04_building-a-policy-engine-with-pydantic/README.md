# M05-L04: Building a policy engine with Pydantic models and YAML rules

Module: M05 Pillars 3 & 4, Least Privilege & Policy Engines · Type: Code-along

`final/policy_demo.py` loads `complaints.yaml` into Pydantic models, evaluates four close requests (allow,
two state-based denies, and a default deny for a tool no rule mentions), prints a Decision as JSON, shows a
broken policy file being rejected at load time, and shows the content hash changing after a one-character edit.

```bash
uv run python lessons/M05-L04_building-a-policy-engine-with-pydantic/final/policy_demo.py
```
Code walked through on screen: `src/sentinel/policy/models.py`, `engine.py` and `policies/complaints.yaml`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
