# M05-L07: Prompt injection as a policy problem: untrusted content and tool gating

Module: M05 Pillars 3 & 4, Least Privilege & Policy Engines · Type: Demo

`final/injection_demo.py` plays a worst-case "model" that obeys the instructions planted in complaints CMP-3006
and CMP-3007. Without the gate it marks a serious-injury complaint not reportable, closes it and emails
complaint data to an outside address. With the gate every privileged call is denied with a rule ID, the session
is marked tainted, and the agent gets a security notice. Part 3 shows taint without injection: a not-reportable
determination after reading complaint text becomes `ask`, which is a deny until Module 6 adds an approver.

```bash
uv run python lessons/M05-L07_prompt-injection-as-a-policy-problem/final/injection_demo.py
```
Code walked through on screen: `post_tool_use` in `src/sentinel/policy/enforce.py`, the INJ rules in
`policies/complaints.yaml`, and `src/sentinel/policy/simulate.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
