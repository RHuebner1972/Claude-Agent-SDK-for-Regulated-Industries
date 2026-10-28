# Lab 5: CUI-segregated engineering-change agent for a defense manufacturer

**Module:** M07 Pillar 6, Multi-Agent Data Boundaries · **Industry:** Defense manufacturing
**Regulations:** CMMC Level 2 / NIST SP 800-171 · DFARS 252.204-7012 · ITAR (22 CFR 120-130)
**Time:** about 60-90 minutes · Full instructions: `Modules/M07_p6-multi-agent-boundaries/lab/LAB5_instructions.md`

## What you build
`boundary_kit`, the data-boundary layer for Northgate Precision Components' Change Control Board assistant
(synthetic company): agent cards that state each agent's data scope, tools and deployment; a boundary guard
that enforces the cards on every tool call and every delegation; a typed handoff contract (ENG-FORM-7) that strips
and scans what a cleared subagent sends back; audit logs routed so CUI stays in the enclave's log; and residency
checks on where each agent runs.

## Acceptance criteria
1. CUI never appears in the orchestrator's context or the general logs (canary strings prove it)
2. Boundary tests pass: BND-001/003/004/005 denials and the BND-002 handoff rejection fire where they should
3. Each subagent has a documented data scope (its card), and its SDK definition is generated from that card

## Layout
```
starter/                you work here: 8 TODOs
  boundary_kit/
    residency.py        TODO 1  check_deployment                    part 1: the cleared subagent and its tools
    guard.py            TODO 2  check   TODO 3  pre_tool_use
    routing.py          TODO 4  _for + _redact_handoff
    markings.py         TODO 5  scan                                part 2: handoff contracts and boundary tests
    contracts.py        TODO 6  enforce_contract
    guard.py            TODO 7  post_tool_use
    cards.py            provided: AgentCard, CardSet, Deployment
    policies/agent_cards.yaml   the agent cards (provided: read them first)
    eng_tools.py        provided: the ccb and eng_data tools, and agent_definitions() generated from the cards
    simulate.py         provided: the offline driver (orchestrator + subagent hook inputs, as the SDK sends them)
  boundary_pipeline.py  TODO 8  wire cards, tools, two audit logs, guard and hooks
  run_offline.py        baseline vs. gated runs, boundary tests, and where the canaries ended up (no API key)
  agent.py              live run: the orchestrator delegates FALCON ECRs to the cleared subagent (ANTHROPIC_API_KEY)
solution/  tests/       reference solution and 15 acceptance tests
```
Work in order: TODOs 1-4 pass 6 tests, 5-7 pass 11, and TODO 8 passes all 15.

## Run
```bash
cd labs/lab5_data-boundaries/starter
uv run python run_offline.py                                              # after TODO 8
cd ../../.. && LAB_IMPL=starter uv run pytest labs/lab5_data-boundaries     # PowerShell: $env:LAB_IMPL="starter"
```
Key: `AUDIT_HMAC_KEY` in `.env` (a demo value is used if unset). All data is synthetic, including every "CUI"
marking and canary string; never put real CUI or export-controlled data into course code or a commercial endpoint.
