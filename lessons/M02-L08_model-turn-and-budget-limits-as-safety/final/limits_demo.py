"""
M02-L08: model, turn and budget limits are safety controls. Watch each one stop a run.

    uv run python lessons/M02-L08_model-turn-and-budget-limits-as-safety/final/limits_demo.py
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query
from course_data import MODEL

from ledger_tools import LEDGER_TOOL_NAMES, ledger_server   # L04's read-only tools (copied here)

TASK = "Review every pending journal entry one by one and list any over $50,000 with their GL accounts."


def options(**limits) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=MODEL, mcp_servers={"ledger": ledger_server}, tools=[], allowed_tools=LEDGER_TOOL_NAMES,
        permission_mode="dontAsk", strict_mcp_config=True, setting_sources=[], **limits)


async def run(label: str, **limits) -> None:
    print(f"\n=== {label}: {limits} ===")
    result = None
    try:
        async for message in query(prompt=TASK, options=options(**limits)):
            if isinstance(message, ResultMessage):
                result = message
    except Exception as exc:          # query() raises after an error result: that's the stop working
        print(f"  stopped: {type(exc).__name__}")
    if result:
        cost = f"${result.total_cost_usd:.4f}" if result.total_cost_usd is not None else "n/a"
        print(f"  subtype={result.subtype} terminal_reason={result.terminal_reason} turns={result.num_turns} cost={cost}")


async def main() -> None:
    await run("Turn limit too low", max_turns=1)
    await run("Budget too low", max_budget_usd=0.001)
    await run("Sensible limits", max_turns=12, max_budget_usd=0.50)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
