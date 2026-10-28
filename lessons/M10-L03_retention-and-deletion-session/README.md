# M10-L03: Retention and deletion: session transcripts, audit logs and caches

Module: M10 Production Deployment in Regulated Infrastructure · Type: Code-along

`final/retention_demo.py` shows pa-reviewer's retention rules from `deploy/policies/deployment.yaml`, ships its audit
log to write-once storage (delete, overwrite and shortening the lock are all refused; a legal hold outlasts the
retention period), then mirrors session transcripts into a governed `TranscriptStore` (the Agent SDK's
`SessionStore` protocol) and sweeps them on schedule, leaving signed deletion receipts in the audit trail.

```bash
uv run python lessons/M10-L03_retention-and-deletion-session/final/retention_demo.py
```
Code walked through on screen: `src/sentinel/deploy/retention.py`, `src/sentinel/deploy/policies/deployment.yaml`. `WormStore` is a local stand-in for S3 Object Lock (compliance mode), Azure immutable blob storage or Cloud Storage bucket lock.

Vendor facts (paths, regions, agreements) are as of 2026-10-28 in `src/sentinel/deploy/policies/deployment_paths.yaml`:
re-check them with the provider before relying on them. Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
