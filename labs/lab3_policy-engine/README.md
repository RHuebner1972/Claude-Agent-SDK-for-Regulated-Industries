# Lab 3: Policy-gated complaint-handling agent for a medical device maker

**Module:** M05 Pillars 3 & 4, Least Privilege & Policy Engines · **Industry:** Medical devices
**Regulations:** 21 CFR 820 (QMSR, incl. complaint files, 820.35) · 21 CFR 803 Medical Device Reporting · 21 CFR Part 11 access controls (11.10(d), 11.10(g))
**Time:** about 60-90 minutes · Full instructions: `Modules/M05_p3-p4-least-privilege-policy/lab/LAB3_instructions.md`

## What you build
`policy_gate`, a policy engine for Harborline Medical's complaint triage assistant (synthetic company): typed
Pydantic rules loaded from a versioned YAML file, a deny-overrides evaluator with default deny, and three SDK
adapters (a PreToolUse hook for every call, a `can_use_tool` callback, and a PostToolUse hook that tracks
untrusted content and checks tool output). Denials go to Module 3's audit trail with their rule ID.

## Acceptance criteria
1. The agent cannot close an MDR-reportable complaint (or one whose MDR determination is still pending)
2. Every deny carries a rule ID, and the audit log records it with the exact policy version
3. Injected instructions in complaint text (CMP-3006, CMP-3007) cannot trigger privileged tools

## Layout
```
starter/                you work here: 8 TODOs
  policy_gate/
    models.py           TODO 1  Condition.matches
    engine.py           TODO 2  PolicyEngine.evaluate     TODO 3  load_policy
    enforce.py          TODO 4  pre_tool_use   TODO 5  can_use_tool   TODO 6  post_tool_use
    policies/complaints.yaml   TODO 7  write rules MDR-001, MDR-002, INJ-001
  triage_pipeline.py    TODO 8  wire audit trail, engine, enforcer, tools and hooks together
  run_offline.py        three scripted runs through YOUR pipeline (no API key)
  agent.py              live run (ANTHROPIC_API_KEY)
solution/  tests/       reference solution and 16 acceptance tests
```

## Run
```bash
cd labs/lab3_policy-engine/starter
uv run python run_offline.py                                            # after TODO 8
cd ../../.. && LAB_IMPL=starter uv run pytest labs/lab3_policy-engine    # PowerShell: $env:LAB_IMPL="starter"
cd labs/lab3_policy-engine/solution && uv run python agent.py --user m.ortiz --role complaint_intake
```
All data is synthetic. Complaints CMP-3006 and CMP-3007 contain planted prompt-injection text on purpose.
