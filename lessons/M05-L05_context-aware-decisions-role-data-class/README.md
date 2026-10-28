# M05-L05: Context-aware decisions: role, data class and purpose of use (ABAC)

Module: M05 Pillars 3 & 4, Least Privilege & Policy Engines · Type: Code-along

`final/abac_demo.py` prints a role-by-action matrix for the three complaint roles, including decisions that
depend on the record (MDR status) and on a value inside the record (the complainant's email on file), then
shows the same read allowed for complaint handling and denied for another purpose.

```bash
uv run python lessons/M05-L05_context-aware-decisions-role-data-class/final/abac_demo.py
```
Code walked through on screen: `Condition.matches` in `src/sentinel/policy/models.py` and `build_context` in `engine.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
