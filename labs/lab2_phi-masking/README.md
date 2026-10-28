# Lab 2: PHI-safe prior-authorization summarization agent

**Module:** M04 Pillar 2, Data Protection · **Industry:** Healthcare (payer)
**Regulations:** HIPAA minimum necessary (45 CFR 164.502(b)) · HIPAA de-identification (45 CFR 164.514) · HIPAA audit controls (45 CFR 164.312(b))
**Time:** about 60-90 minutes · Full instructions: `Modules/M04_p2-data-protection-pii-phi/lab/LAB2_instructions.md`

## What you build
`phi_guard`, a PHI-protection package for a prior-auth review agent: custom Presidio recognizers, a reversible
token vault with role- and purpose-based re-identification, a field-minimized EHR tool, and a privacy redactor
plugged into Module 3's audit hooks.

## Acceptance criteria
1. Zero PHI in logs, tool results, the vault file or downstream records on the synthetic test set
2. Detection recall of at least 95% on the annotated notes
3. Re-identification is access-controlled (role + purpose) and every attempt is audited

## Layout
```
starter/            you work here: 8 TODOs
  phi_guard/        recognizers.py (1-3), vault.py (4-5), minimize.py (6), pa_tools.py (7)
  pipeline.py       TODO 8: wire vault, redactor, hooks and minimized tools together
  run_offline.py    scripted review through YOUR pipeline + leak scan (no API key)
  evaluate.py       detection recall vs. the annotations
  agent.py          live run (ANTHROPIC_API_KEY)
solution/  tests/   reference solution and 13 acceptance tests
```

## Run
```bash
cd labs/lab2_phi-masking/starter
uv run python evaluate.py          # recall (after TODOs 1-3)
uv run python run_offline.py       # end to end (after TODO 8)
cd ../../.. && LAB_IMPL=starter uv run pytest labs/lab2_phi-masking    # PowerShell: $env:LAB_IMPL="starter"
```
Keys: `VAULT_ENC_KEY`, `VAULT_HMAC_KEY`, `AUDIT_HMAC_KEY` in `.env` (demo values in `.env.example`).
All data is synthetic.
