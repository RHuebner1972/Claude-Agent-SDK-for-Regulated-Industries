# M06-L04: Async approval queues: pause, persist and resume sessions

Module: M06 Pillar 5, Human Oversight: Approval Workflows · Type: Code-along

`final/async_queue_demo.py` runs the SDK's defer round trip offline: the PreToolUse hook returns `defer`, the run
stops with `stop_reason="tool_deferred"`, the request sits in a JSON queue on disk, a reviewer in another process
signs 95 minutes later, and the same session resumes and runs exactly the approved call, once.

```bash
uv run python lessons/M06-L04_async-approval-queues-pause-persist-and/final/async_queue_demo.py
```
Code walked through on screen: `src/sentinel/approvals/queue.py` (submit, sign, consume, persistence) and
`simulate.py` (how the driver models the documented defer behavior).

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
