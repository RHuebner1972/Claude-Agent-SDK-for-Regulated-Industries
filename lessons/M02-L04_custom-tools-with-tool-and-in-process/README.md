# M02-L04: Custom tools with @tool and in-process MCP servers

`ledger_tools.py` defines three read-only tools over the synthetic finance data. `run_ledger_agent.py` gives an agent exactly those tools and nothing else.

## Run it
```bash
uv run python lessons/M02-L04_custom-tools-with-tool-and-in-process/final/run_ledger_agent.py
```

All data is synthetic (`data/synthetic/finance/`). Shared helpers (`MODEL`, data loaders, `show()`) come from `src/course_data`.
