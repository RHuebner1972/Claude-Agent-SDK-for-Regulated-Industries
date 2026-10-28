"""
Lab 2 solution: the PHI-safe prior-auth reviewer, live (needs ANTHROPIC_API_KEY).

    cd labs/lab2_phi-masking/solution
    uv run python agent.py --user n.alvarez
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, query
from course_data import MODEL, show

from pipeline import SYSTEM_PROMPT, build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"
TASK = "Review the pending prior-authorization requests PA-2001 to PA-2008 and record a recommendation for each."


async def main(user: str) -> None:
    p = build_pipeline(WORKSPACE, user=user)
    server = create_sdk_mcp_server("pa", tools=p.tools)
    options = ClaudeAgentOptions(
        model=MODEL, system_prompt=SYSTEM_PROMPT, mcp_servers={"pa": server},
        tools=[], allowed_tools=[f"mcp__pa__{t.name}" for t in p.tools], permission_mode="dontAsk",
        strict_mcp_config=True, setting_sources=[], max_turns=30, max_budget_usd=1.00,
        hooks=p.hooks.sdk_hooks(),
    )
    try:
        async for message in query(prompt=TASK, options=options):
            show(message)                      # what the model sees and says: tokens, not identifiers
            p.hooks.observe(message)
    except Exception as exc:
        print(f"Run stopped: {exc}")
    print(f"\nRecorded {len(p.recorded)} recommendations. Audit log: {p.store.path}")


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    asyncio.run(main(parser.parse_args().user))
