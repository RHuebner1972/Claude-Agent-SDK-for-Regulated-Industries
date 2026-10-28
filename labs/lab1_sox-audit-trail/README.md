# Lab 1: SOX-ready audit trail for a journal-entry review agent

**Module:** M03 Pillar 1, Traceability · **Industry:** Financial services
**Regulations:** SOX 302/404 ITGCs · PCAOB AS 2201 · 21 CFR Part 11 §11.10(e) (audit-trail parallel)
**Time:** about 60-90 minutes · Full instructions: `Modules/M03_p1-traceability-audit-logging/lab/LAB1_instructions.md`

## What you build
An `audit_trail` package that gives LedgerBot an audit trail an auditor will accept:
hook-driven `AuditEvent`s, a hash-chained append-only JSONL store with signed checkpoints,
a verifier CLI and a decision-replay report.

## Acceptance criteria
1. Every prompt, tool request, tool result, denial, decision and final answer is logged
2. The chain verifies
3. Tampering with one line is detected (and, with the key, chain rewrites and truncation too)
4. A reviewer can reconstruct any decision from the log alone

## Layout
```
starter/            you work here: audit_trail/ has 8 TODOs (store.py, hooks.py, verify.py, replay.py)
  audit_trail/      models.py, hashing.py and redact.py are complete (built in M03-L02 and L06)
  run_offline.py    scripted LedgerBot run through YOUR pipeline (no API key)
  agent.py          live LedgerBot run (API key + AUDIT_HMAC_KEY)
  tools.py          LedgerBot's ledger tools
solution/           reference solution (watch the walkthroughs first)
tests/              acceptance tests, one per criterion
data/               sample_run/ (clean) and suspicious/ (tampered) logs
```

## Run
```bash
cd labs/lab1_sox-audit-trail/starter
uv run python run_offline.py                                   # your pipeline, offline
uv run python -m audit_trail verify workspace/audit.jsonl       # exit code 0 = verified
uv run python -m audit_trail replay workspace/audit.jsonl JE-1003
cd ../../.. && LAB_IMPL=starter uv run pytest labs/lab1_sox-audit-trail   # 22 tests (Windows PowerShell: $env:LAB_IMPL="starter")
```
All data is synthetic. The demo HMAC key is for the course only.
