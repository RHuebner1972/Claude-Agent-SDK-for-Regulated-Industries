"""
Lab 5 solution: the change-board assistant, live (needs ANTHROPIC_API_KEY), with a cleared FALCON subagent.

    cd labs/lab5_data-boundaries/solution
    uv run python agent.py

Course setting: both agents run in ONE SDK process on your API key, with synthetic data. That exercises every control,
but it is not an enclave: an in-process subagent shares the parent's host, provider credentials and transcript storage.
In production, run the cleared agent as its own service inside the enclave (its card's deployment block) and give the
orchestrator one tool that returns only ENG-FORM-7, with the contract enforced on both sides (M07-L06).
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server, query
from course_data import MODEL, show

from boundary_kit.eng_tools import full_name
from boundary_pipeline import SYSTEM_PROMPT, build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"
TASK = ("Prepare next week's CCB agenda. For each open ECR, add an agenda item with the recommendation and impact. "
        "Schedule the FALCON items for 2026-11-04.")


async def main() -> None:
    p = build_pipeline(WORKSPACE)
    by_server = {"ccb": [t for t in p.tools if full_name(t.name).startswith("mcp__ccb__")],
                 "eng_data": [t for t in p.tools if full_name(t.name).startswith("mcp__eng_data__")]}
    every_card_tool = sorted({full_name(t) for c in p.cards.agents for t in c.tools})
    options = ClaudeAgentOptions(
        model=MODEL, system_prompt=SYSTEM_PROMPT,
        mcp_servers={name: create_sdk_mcp_server(name, tools=ts) for name, ts in by_server.items()},
        tools=["Agent"],                                   # [] would remove the Agent tool too
        allowed_tools=["Agent"] + every_card_tool,         # allow rules are session-wide; the guard is per agent
        agents=p.agents, permission_mode="dontAsk", strict_mcp_config=True, setting_sources=[], hooks=p.hooks,
        max_turns=30, max_budget_usd=1.50)
    async for message in query(prompt=TASK, options=options):
        show(message)
        p.audit.observe(message)
    print("\nHandoffs:", p.guard.handoffs)
    print("Agenda:", p.store.agenda)
    print(f"Logs: {p.general_log} (general), {p.enclave_log} (enclave)")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
