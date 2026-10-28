# M03-L03: Hooks as the audit backbone: UserPromptSubmit, PreToolUse, PostToolUse, Stop

Module: M03 Pillar 1, Traceability · Type: Code-along

| File | What it is |
|---|---|
| `final/audit_hooks.py` | `SimpleAuditLog`: four hook callbacks + `observe()` for the result message. Plain JSONL, no chain yet (M03-L05) |
| `final/ledger_tools.py` | LedgerBot's tools: M02's read-only tools + `record_recommendation`; `get_vendor_banking` is treasury-only |
| `final/run_audited.py` | LedgerBot with `hooks=log.sdk_hooks()` |
| `final/audit_models.py` | Copy of the M03-L02 model |

```bash
uv run python lessons/M03-L03_hooks-as-the-audit-backbone/final/run_audited.py --simulate   # offline, scripted run
uv run python lessons/M03-L03_hooks-as-the-audit-backbone/final/run_audited.py              # live (API key)
```
Output: `final/workspace/audit.jsonl` and `final/workspace/recommendations.jsonl`.
