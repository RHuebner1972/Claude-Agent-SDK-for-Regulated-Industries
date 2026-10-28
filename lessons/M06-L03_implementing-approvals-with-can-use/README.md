# M06-L03: Implementing approvals with can_use_tool and hooks

Module: M06 Pillar 5, Human Oversight: Approval Workflows · Type: Code-along

`final/gate_demo.py` shows the two ways to put a person in the loop. Part 1 uses `can_use_tool`: the run waits
while a (simulated) reviewer approves, rejects, or doesn't answer; no answer in time means no. Part 2 uses a
PreToolUse hook in deny mode: the agent queues three requests on Bayside Community Bank's synthetic alerts and
carries on with the work that needs no approval.

```bash
uv run python lessons/M06-L03_implementing-approvals-with-can-use/final/gate_demo.py
```
Code walked through on screen: `src/sentinel/approvals/gate.py` and `policies/oversight.yaml`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
