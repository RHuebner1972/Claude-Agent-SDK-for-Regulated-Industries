# claude-regulated-agents

Code for the Udemy course **Claude Agent SDK for Regulated Industries**.

## Layout
| Path | What it is |
|---|---|
| `src/sentinel/` | Reference toolkit built up across the course: `audit`, `privacy`, `policy`, `approvals`, `boundaries`, `monitoring`, `evidence` |
| `lessons/Mxx-Lyy_*` | Code for each code lecture (`starter/` and `final/`) |
| `labs/` | Six labs + capstone, each with `starter/`, `solution/`, `tests/`, `data/` |
| `data/synthetic/` | Synthetic datasets only |
| `tests/` | Tests for the `sentinel` package |

## Setup
```bash
uv sync --extra dev        # or: pip install -e ".[dev]"
cp .env.example .env       # add your key; never commit .env
uv run pytest
```

## Rules
1. Synthetic data only.
2. Keys come from the environment or a secrets manager, never from code.
3. Every lab's acceptance criteria are automated in its `tests/` folder.
