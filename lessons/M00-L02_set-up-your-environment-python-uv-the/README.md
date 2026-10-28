# M00-L02: Set up your environment

```bash
# 1. Install uv (https://docs.astral.sh/uv/), then from the course-repo folder:
uv sync --extra dev
# 2. Credentials: copy the template and add your key. Never commit .env.
cp .env.example .env
# 3. Check everything:
uv run python lessons/M00-L02_set-up-your-environment-python-uv-the/final/check_setup.py
```

`check_setup.py` checks Python 3.10+, the Claude Agent SDK, that credentials exist (without ever printing them), and makes one tiny call to Claude with every tool disabled.

**Regulated habit #1:** keys live in the environment or a secrets manager, never in code, never on screen, never in logs.
