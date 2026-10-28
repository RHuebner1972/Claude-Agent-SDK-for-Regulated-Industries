# M02-L03: ClaudeAgentOptions as your first control surface

Runs the same prompt with default options and with locked-down options, and prints the `[init]` line for each so you can see which tools, permission mode and MCP servers the agent really got.

## Run it
```bash
uv run python lessons/M02-L03_claudeagentoptions-as-your-first/final/options_tour.py
```

All data is synthetic (`data/synthetic/finance/`). Shared helpers (`MODEL`, data loaders, `show()`) come from `src/course_data`.
