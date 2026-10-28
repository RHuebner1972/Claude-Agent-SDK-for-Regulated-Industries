# M07-L05: Typed handoffs: Pydantic contracts between agents

Module: M07 Pillar 6, Multi-Agent Data Boundaries · Type: Code-along

`final/handoff_demo.py` prints the `ChangeImpactSummary` contract (ENG-FORM-7), then puts six candidate subagent
replies through `enforce_contract`: a clean form, extra fields, an extra field carrying test data, CUI hidden in
the rationale, free text, and an out-of-range value. Extras are stripped; anything else wrong is rejected with
BND-002, and the orchestrator gets the rejection instead of the text.

```bash
uv run python lessons/M07-L05_typed-handoffs-pydantic-contracts/final/handoff_demo.py
```
Code walked through on screen: `src/sentinel/boundaries/contracts.py`, `markings.py`, and the `post_tool_use`
hook in `guard.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
