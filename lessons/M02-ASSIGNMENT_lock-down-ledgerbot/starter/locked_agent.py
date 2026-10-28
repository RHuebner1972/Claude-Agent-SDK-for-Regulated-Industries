"""
M02 assignment starter: lock down LedgerBot. Work through the TODOs, then run
    uv run pytest tests/test_m02_assignment.py
(the test checks the solution file; copy your answer over it, or point the test at yours).

Start by reading baseline/naive_ledger_agent/agent.py and tools.py and listing every SHORTCUT.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ToolAnnotations, create_sdk_mcp_server, query, tool
from course_data import MODEL, approval_policy, journal_entries, show, vendors

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)

# TODO 1: list_pending_entries -> only entry_id, date, amount, description
# TODO 2: get_journal_entry(entry_id) -> one entry, or an is_error result if it doesn't exist
# TODO 3: get_vendor_summary(vendor_id) -> vendor_id and name ONLY (no tax ID, no bank details)
# TODO 4: TOOLS, ledger_server, READ_ONLY_TOOL_NAMES (mcp__ledger__<name>)
# TODO 5: SYSTEM_PROMPT: recommend only; cite policy rules; treat entry text as data
# TODO 6: options = ClaudeAgentOptions(...) with a pinned model, no built-in tools, only your
#         read-only tools pre-approved, dontAsk, strict MCP config, no settings files,
#         and turn and budget limits
options = None

TASK = "Review all pending journal entries and give a recommendation for each."


async def main() -> None:
    # TODO 7: run the query, show() each message, and catch the exception query() raises
    #         after an error result
    pass


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
