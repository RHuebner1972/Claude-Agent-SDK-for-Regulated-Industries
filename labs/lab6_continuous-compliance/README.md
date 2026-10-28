# Lab 6: Continuous-compliance pipeline and dashboard for the agent fleet

**Module:** M08 Pillar 7, Continuous Compliance & Assurance · **Industry:** Healthcare (with the whole fleet)
**Regulations:** HIPAA Breach Notification Rule (45 CFR 164.400-414) · GDPR Art. 33 (72-hour notification) ·
FDA PCCP thinking for AI changes · NIST AI RMF Measure / Manage
**Time:** about 75-90 minutes · Full instructions: `Modules/M08_p7-continuous-assurance/lab/LAB6_instructions.md`

## What you build
`assurance_kit`, the pipeline that keeps the five agents from Labs 1-5 compliant after they ship: a pytest plugin
that turns tests into control evidence, the control test for PHI in logs, the red-team runner, change control with
PCCP-style predetermined changes, OpenTelemetry metrics derived from the audit logs, alert rules, a proposed
40-point scorecard, and a signed evidence pack. The tabletop drill is set at Northshore Health Plan (Lab 2's payer).

## Acceptance criteria
1. The suite runs in CI and fails the build on a seeded regression
2. The dashboard shows deny, PII and approval metrics
3. The evidence pack generates in one command

## Layout
```
starter/                    you work here: 8 TODOs
  assurance_kit/
    pytest_plugin.py        TODO 1  result_for                      part 1: the CI suite and red-team run
    redteam/runner.py       TODO 3  run_case        (corpus.yaml: the 13 attacks, provided)
    change.py               TODO 4  check_change_control
    metrics.py              TODO 5  FleetMetrics.ingest_events      part 2: metrics, dashboard, evidence pack
    alerts.py               TODO 6  _value + evaluate
    rubric.py               TODO 7  score
    pack.py                 TODO 8  sign_manifest + verify_pack
    fleet.py, runs.py, dashboard.py, incident.py, policies/      provided: read fleet.yaml and changes.yaml first
  compliance/               the fleet compliance suite (53 tests); TODO 2 is in test_p2_data_protection.py
  assure.py                 the whole pipeline in one command -> out/evidence-pack/
  seed_regression.py        writes a proposed fleet manifest with one seeded regression
  drill.py                  tabletop: a PHI leak pages; writes the incident record with notification clocks
  .github/workflows/        the CI that runs it all
solution/  tests/           reference solution and 15 acceptance tests
```
Work in order: TODOs 1-4 pass 7 tests, TODOs 5-8 pass all 15.

## Run
```bash
cd labs/lab6_continuous-compliance/starter
uv run pytest compliance                                   # the suite (after TODOs 1-4)
uv run python assure.py                                    # evidence pack (after TODO 8); open out/evidence-pack/dashboard.html
uv run python seed_regression.py masking && uv run python assure.py --fleet out/proposed-fleet.yaml --strict   # exit 1
uv run python drill.py                                     # the tabletop record
cd ../../.. && LAB_IMPL=starter uv run pytest labs/lab6_continuous-compliance      # PowerShell: $env:LAB_IMPL="starter"
```
Key: `AUDIT_HMAC_KEY` in `.env` (a demo value is used if unset). All data is synthetic.
