# M07-L04: Context isolation: what crosses a boundary and what must not

Module: M07 Pillar 6, Multi-Agent Data Boundaries · Type: Demo

`final/isolation_demo.py` runs the same change-board job three ways (one agent with every tool; a cleared
subagent without a handoff contract; the full gated design) and reports where the CUI canary strings ended up:
the orchestrator's context, the general audit log, the enclave audit log.

```bash
uv run python lessons/M07-L04_context-isolation-what-crosses-a/final/isolation_demo.py
```
Code walked through on screen: `src/sentinel/boundaries/guard.py`, `routing.py`, `simulate.py` (`run_scenario`).

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
