# M00-L03: Quick win: your first audited Claude agent

Follow along from `starter/first_audited_agent.py` (the skeleton with numbered TODOs), or run the finished version:

```bash
uv run python lessons/M00-L03_quick-win-build-your-first-audited/final/first_audited_agent.py
```

What you build in about 60 lines:
1. **One custom tool** (`lookup_policy`) with the `@tool` decorator and an in-process MCP server
2. **An audit trail**: one JSON line per event in `audit.jsonl`
3. **Three hooks** (`UserPromptSubmit`, `PreToolUse`, `PostToolUse`) that write to it on every step
4. **Least-privilege options**: `tools=[]` turns off every built-in tool; `allowed_tools` pre-approves only ours

This is Pillar 1 (Traceability) in miniature. Module 3 makes it tamper-evident and auditor-ready.
