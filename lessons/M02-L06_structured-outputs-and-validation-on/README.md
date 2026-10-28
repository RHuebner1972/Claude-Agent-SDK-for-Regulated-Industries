# M02-L06: Structured outputs and validation on the way out

The agent must return a `ReviewDecision`. The script validates it with Pydantic and runs business checks; anything that fails is routed to a human (fail closed).

## Run it
```bash
uv run python lessons/M02-L06_structured-outputs-and-validation-on/final/structured_review.py JE-1003
uv run python lessons/M02-L06_structured-outputs-and-validation-on/final/structured_review.py JE-1009
```

All data is synthetic (`data/synthetic/finance/`). Shared helpers (`MODEL`, data loaders, `show()`) come from `src/course_data`.
