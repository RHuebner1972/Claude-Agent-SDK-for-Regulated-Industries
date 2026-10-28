# M08-L02: Compliance tests: evals as executable controls

Module: M08 Pillar 7, Continuous Compliance & Assurance · Type: Code-along

`final/suite_demo.py` runs the fleet compliance suite (`compliance/`) twice: as deployed, and with a proposed
manifest that switches off the complaint agent's policy engine. Each test is tagged with the rubric items it
evidences (`@pytest.mark.control("2.2", agent=...)`); the plugin writes `compliance-results.json`.

```bash
uv run python lessons/M08-L02_compliance-tests-evals-as-executable/final/suite_demo.py
uv run pytest compliance                         # the suite itself, exactly as CI runs it
```
Code walked through on screen: `compliance/test_p2_data_protection.py`, `compliance/conftest.py`,
`src/sentinel/monitoring/pytest_plugin.py`, `fleet.py`, `runs.py`, `.github/workflows/compliance.yml`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
