"""
Lab 4 solution: the AML triage assistant, live (needs ANTHROPIC_API_KEY), with the defer round trip.

    cd labs/lab4_human-approval/solution
    uv run python agent.py                                    # runs until a call needs approval, then stops
    uv run python approve.py --as m.chen                      # in another terminal: review and sign
    uv run python agent.py --resume <session_id>              # the deferred call fires again and now runs

Verify the defer/resume round trip against your pinned SDK version (see the Regulatory Watchlist). The deferred
tool must be available when you resume, so this script rebuilds the same in-process MCP server every time.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, create_sdk_mcp_server, query
from course_data import MODEL, show

from approval_desk.aml_tools import ALL_TOOLS, SERVER, full_name
from aml_pipeline import SYSTEM_PROMPT, build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"
TASK = "Triage my open AML alerts. Request the disposition you recommend for each, with a clear rationale."


async def main(resume: str | None) -> None:
    p = build_pipeline(WORKSPACE, mode="defer", session_id=resume)
    server = create_sdk_mcp_server(SERVER, tools=p.tools)
    options = ClaudeAgentOptions(
        model=MODEL, system_prompt=SYSTEM_PROMPT, mcp_servers={SERVER: server}, tools=[],
        allowed_tools=[full_name(t) for t in ALL_TOOLS],      # the gate, not the allowlist, holds the risky ones
        permission_mode="dontAsk", strict_mcp_config=True, setting_sources=[], hooks=p.hooks,
        max_turns=40, max_budget_usd=1.50, resume=resume,
    )
    prompt = "The pending approval has been decided. Continue the triage." if resume else TASK
    async for message in query(prompt=prompt, options=options):
        show(message)
        p.audit.observe(message)
        if isinstance(message, ResultMessage) and message.stop_reason == "tool_deferred":
            d = message.deferred_tool_use
            print(f"\nPAUSED: {d.name} is waiting for approval. Session {message.session_id}")
            print(f"  Review:  uv run python approve.py --as <approver>")
            print(f"  Resume:  uv run python agent.py --resume {message.session_id}")


if __name__ == "__main__":
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume")
    asyncio.run(main(ap.parse_args().resume))
