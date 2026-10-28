# M10-L04: Sandboxing the agent runtime: containers, filesystem and network egress

Module: M10 Production Deployment in Regulated Infrastructure · Type: Code-along

`final/sandbox_demo.py` prints the hardened `docker run` for aml-triage, lints a profile a reviewer would reject,
checks URLs against the egress allowlist, runs the filesystem guard (a PreToolUse hook for file tools), and prints the
Agent SDK sandbox settings used as a backstop for Bash.

```bash
uv run python lessons/M10-L04_sandboxing-the-agent-runtime-containers/final/sandbox_demo.py
uv run python -m sentinel.deploy docker aml-triage
```
Code walked through on screen: `src/sentinel/deploy/sandbox.py`. Container flags follow Anthropic's secure-deployment guide for the Agent SDK.

Vendor facts (paths, regions, agreements) are as of 2026-10-28 in `src/sentinel/deploy/policies/deployment_paths.yaml`:
re-check them with the provider before relying on them. Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
