# M03-L05: Tamper evidence: hash chaining, signing and WORM storage

Module: M03 Pillar 1, Traceability · Type: Code-along

`final/tamper_lab.py` builds a hash-chained, checkpoint-signed log with `sentinel.audit.AuditStore`, then
attacks four copies of it and runs the verifier with and without the HMAC key:

| Attack | Chain alone | Chain + signed checkpoint |
|---|---|---|
| Edit a field | caught | caught |
| Edit + recompute that hash | caught | caught |
| Rewrite the whole chain | **missed** | caught |
| Delete the tail | **missed** | caught |

```bash
uv run python lessons/M03-L05_tamper-evidence-hash-chaining-signing/final/tamper_lab.py
uv run python -m sentinel.audit verify labs/lab1_sox-audit-trail/data/sample_run/audit.jsonl
```
Code walked through on screen: `src/sentinel/audit/hashing.py`, `store.py`, `verify.py`.
