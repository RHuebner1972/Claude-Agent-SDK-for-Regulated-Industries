# M00-L01: Watch an AI agent fail a compliance audit, then pass it

The cold open. One prior-authorization agent, built two ways, on synthetic patient data.

```bash
uv run python lessons/M00-L01_watch-an-ai-agent-fail-a-compliance/final/demo.py --mode naive
uv run python lessons/M00-L01_watch-an-ai-agent-fail-a-compliance/final/demo.py --mode hardened
```

| | Naive | Hardened |
|---|---|---|
| Patient record returned to the model | Everything (name, DOB, SSN, MRN, address) | Minimum necessary for the decision |
| Logging | Raw debug log, unmasked, editable | Masked, hash-chained audit trail |
| Recording the decision | Auto-approved | Human reviewer must approve in the terminal |
| Built-in tools (shell, files) | Disabled | Disabled |
| Turn and budget limits | None | 8 turns, $1.00 |

Each run ends with a compliance scorecard. Output files land in `final/output/` (git-ignored).

> You are not expected to understand the code yet. By the end of the course you will have built every piece of it.
