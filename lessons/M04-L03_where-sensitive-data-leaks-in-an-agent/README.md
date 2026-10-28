# M04-L03: Where sensitive data leaks in an agent

Module: M04 Pillar 2, Data Protection · Type: Demo

`final/leak_tour.py` runs a naive prior-auth reviewer offline and writes the artifacts a real agent produces:
the prompt, the tool result (the model's context), the transcript, a debug log, a trace span, an error message
and the final answer. A canary scan then counts the patient identifiers in each one.

```bash
uv run python lessons/M04-L03_where-sensitive-data-leaks-in-an-agent/final/leak_tour.py
```
Output files land in `final/workspace/` (git-ignored). All data is synthetic.
