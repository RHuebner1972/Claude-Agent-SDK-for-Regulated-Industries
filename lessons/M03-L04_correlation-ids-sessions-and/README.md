# M03-L04: Correlation IDs, sessions and reconstructing a decision

Module: M03 Pillar 1, Traceability · Type: Demo

`final/correlate.py` groups a log by `correlation_id`, pairs every `tool.requested` with its outcome by
`tool_use_id`, shows the SDK transcript path for the session, and cross-checks decisions against the
downstream `recommendations.jsonl`.

```bash
uv run python lessons/M03-L04_correlation-ids-sessions-and/final/correlate.py              # makes an offline sample run first
uv run python lessons/M03-L04_correlation-ids-sessions-and/final/correlate.py lessons/M03-L03_hooks-as-the-audit-backbone/final/workspace/audit.jsonl
```
