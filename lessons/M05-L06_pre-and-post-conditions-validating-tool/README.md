# M05-L06: Pre- and post-conditions: validating tool inputs and outputs against policy

Module: M05 Pillars 3 & 4, Least Privilege & Policy Engines · Type: Code-along

`final/conditions_demo.py` shows pre-conditions (strict Pydantic input models, checked before the policy: bad
IDs, short rationales, unknown values and extra fields all fail with rule `PRE-001`) and post-conditions (a
search tool with a bug returns other complainants' contact details, and the PostToolUse hook withholds the
output with `POST-001`).

```bash
uv run python lessons/M05-L06_pre-and-post-conditions-validating-tool/final/conditions_demo.py
```
Code walked through on screen: `decide` and `post_tool_use` in `src/sentinel/policy/enforce.py`, and the
input models and output checks in `complaint_tools.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
