# M02-L02: query() vs. ClaudeSDKClient

`query()` is one prompt in, a stream of messages out, done. `ClaudeSDKClient` keeps one session open for several turns. Both run with `tools=[]` and `setting_sources=[]`.

## Run it
```bash
uv run python lessons/M02-L02_query-vs-claudesdkclient-one-shot-vs/final/one_shot.py
uv run python lessons/M02-L02_query-vs-claudesdkclient-one-shot-vs/final/conversation.py
```

All data is synthetic (`data/synthetic/finance/`). Shared helpers (`MODEL`, data loaders, `show()`) come from `src/course_data`.
