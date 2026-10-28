"""
M02-L04: an agent that can only use our three read-only ledger tools.

    uv run python lessons/M02-L04_custom-tools-with-tool-and-in-process/final/run_ledger_agent.py
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, query
from course_data import MODEL, show
from ledger_tools import LEDGER_TOOL_NAMES, ledger_server

options = ClaudeAgentOptions(
    model=MODEL,
    system_prompt="You help accountants inspect pending journal entries. Use the ledger tools; never guess.",
    mcp_servers={"ledger": ledger_server},
    tools=[],                          # no built-in tools
    allowed_tools=LEDGER_TOOL_NAMES,   # pre-approve exactly our read-only tools
    permission_mode="dontAsk",         # anything else is denied
    strict_mcp_config=True,
    setting_sources=[],
    max_turns=6,
)


async def main() -> None:
    prompt = "Which pending entries are $50,000 or more, and which GL accounts do they hit?"
    async for message in query(prompt=prompt, options=options):
        show(message)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
