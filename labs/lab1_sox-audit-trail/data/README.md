# Lab 1 data (synthetic)

| Folder | Contents |
|---|---|
| `sample_run/` | A clean LedgerBot review of JE-1001..JE-1010: `audit.jsonl` (59 events), `audit.checkpoints.jsonl` (signed every 25 events + end of run), `recommendations.jsonl` (the downstream store's copy, same correlation ID) |
| `suspicious/` | The same run after someone edited one decision and rebuilt the hash chain. Used in walkthrough part 2 and the M03 practice activity |
| `make_samples.py` | Regenerates both folders |

Checkpoints are signed with the **demo key** `course-demo-key` (`AUDIT_HMAC_KEY` in `.env.example`).
A real key lives in a secrets manager or KMS, held by people who can't edit the logs.
