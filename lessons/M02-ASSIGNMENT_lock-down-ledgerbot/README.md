# M02 assignment: Lock down LedgerBot

Turn the naive baseline (`baseline/naive_ledger_agent/`) into a least-privilege agent that can only read entries and recommend.

| Folder | What's in it |
|---|---|
| `starter/locked_agent.py` | Skeleton with numbered TODOs |
| `solution/locked_agent.py` | Model solution (try it yourself first) |

```bash
uv run python lessons/M02-ASSIGNMENT_lock-down-ledgerbot/solution/locked_agent.py   # run it (needs an API key)
uv run pytest tests/test_m02_assignment.py                                           # offline checks, no key needed
```

Full instructions and the reflection questions: `Modules/M02_agent-sdk-foundations/assignment/M02_assignment.md`.
