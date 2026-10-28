# Naive baseline: LedgerBot

The agent we build in **M02-L09/L10** and harden for the rest of the course. Every shortcut is marked `# SHORTCUT` in the code.

```bash
uv run python baseline/naive_ledger_agent/agent.py         # run it (synthetic data, no real email)
uv run python baseline/naive_ledger_agent/inspect_run.py   # compare what it did with the policy
```

| File | What it is |
|---|---|
| `tools.py` | Six ledger tools: list, get entry, get vendor, approve, reject, send email |
| `agent.py` | The agent: prompt-only rules, bypassed permissions, disk read access, no limits, no hooks |
| `inspect_run.py` | Reads `workspace/` and flags policy violations and leaked bank/tax numbers |
| `workspace/` | Where decisions, the outbox and the debug log land (git-ignored) |

> Run it only on your course machine. Giving an agent read access to your whole disk is one of the flaws we fix.
