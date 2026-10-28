"""
M02-L09 starter: the naive agent. Finished version: baseline/naive_ledger_agent/agent.py
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, query
from course_data import show
from tools import WORKSPACE, debug, ledger_server

# TODO 7: SYSTEM_PROMPT with the review rules written in prose
# TODO 8: options = ClaudeAgentOptions(system_prompt=..., mcp_servers={"ledger": ledger_server},
#         tools=["Read", "Glob", "Grep"], permission_mode="bypassPermissions", cwd=str(WORKSPACE))
# TODO 9: TASK = "Review all pending journal entries ... email the controller a summary with vendor details."


async def main() -> None:
    # TODO 10: async for message in query(prompt=TASK, options=options): debug(...); show(message)
    pass


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
