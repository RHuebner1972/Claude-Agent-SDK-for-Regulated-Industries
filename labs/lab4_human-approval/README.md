# Lab 4: AML alert-disposition agent with human approval and SAR escalation

**Module:** M06 Pillar 5, Human Oversight · **Industry:** Financial services (community bank)
**Regulations:** Bank Secrecy Act / AML program requirements (incl. SAR rules, 31 CFR 1020.320) · GLBA Safeguards Rule (16 CFR 314) · SOX segregation of duties
**Time:** about 60-90 minutes · Full instructions: `Modules/M06_p5-human-oversight-approvals/lab/LAB4_instructions.md`

## What you build
`approval_desk`, the human-oversight layer for Bayside Community Bank's AML triage assistant (synthetic bank):
an oversight policy that classifies every tool, a persistent approval queue, segregation-of-duties rules,
electronic signatures linked to the exact action approved, escalation that never auto-approves, an approval
gate for the SDK (defer or deny), and a kill switch you drill.

## Acceptance criteria
1. No account action or SAR recommendation executes without an approval by someone other than the requester
2. Timeouts escalate and never auto-approve
3. Approval records include signer, meaning and time, and verify

## Layout
```
starter/                you work here: 8 TODOs
  approval_desk/
    sod.py              TODO 1  check_segregation
    records.py          TODO 2  make_signature     TODO 3  verify_signature
    queue.py            TODO 4  sweep   TODO 5  sign   TODO 6  approved_for + consume
    gate.py             TODO 7  pre_tool_use
    policies/oversight.yaml     the oversight policy (provided: read it first)
    killswitch.py       provided: the override you drill
  aml_pipeline.py       TODO 8  wire audit trail, queue, gate, kill switch, tools and hooks
  run_offline.py        triage, approvals, escalation, resume and a kill-switch drill (no API key)
  approve.py            the reviewer's console: list what's waiting for your role and sign
  agent.py              live run with the SDK's defer / resume round trip (ANTHROPIC_API_KEY)
solution/  tests/       reference solution and 15 acceptance tests
```
Work in order: TODOs 1-5 plus 8 make the signing tests pass; 6 and 7 make the agent tests pass.

## Run
```bash
cd labs/lab4_human-approval/starter
uv run python run_offline.py                                              # after TODO 8
cd ../../.. && LAB_IMPL=starter uv run pytest labs/lab4_human-approval     # PowerShell: $env:LAB_IMPL="starter"
```
Keys: `AUDIT_HMAC_KEY` and `APPROVAL_SIGNING_KEY` in `.env` (demo values are used if unset). All data is synthetic.
