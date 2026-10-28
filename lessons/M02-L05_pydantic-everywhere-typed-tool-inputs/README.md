# M02-L05: Pydantic everywhere

`models.py` holds typed domain models with business rules (balanced entries, ID formats). `typed_tools.py` builds a tool whose input schema comes from Pydantic and whose output is validated before the model sees it. Running it calls the handler directly, so no API key is needed.

## Run it
```bash
uv run python lessons/M02-L05_pydantic-everywhere-typed-tool-inputs/final/typed_tools.py
```

All data is synthetic (`data/synthetic/finance/`). Shared helpers (`MODEL`, data loaders, `show()`) come from `src/course_data`.
