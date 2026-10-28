"""
M00-L03 quick win (starter): follow the TODOs in order while you watch the lecture.
The finished version is in ../final/first_audited_agent.py
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

AUDIT_LOG = Path(__file__).parent / "audit.jsonl"

POLICIES = {
    "travel": "Economy class for flights under 6 hours. Receipts required above $75.",
    "meals": "Up to $60 per person per day while traveling. Alcohol is not reimbursable.",
    "gifts": "No gifts to government officials. Other business gifts capped at $100 per year.",
}

# TODO 1: define a lookup_policy tool with @tool("lookup_policy", "<description>", {"topic": str})
#         that returns {"content": [{"type": "text", "text": <policy text>}]}


# TODO 2: write audit(event, **fields) that appends one JSON line (with a UTC timestamp) to AUDIT_LOG


# TODO 3: write three async hooks (input_data, tool_use_id, context) -> {}:
#         on_prompt -> audit("prompt", ...), before_tool -> audit("tool_call", ...),
#         after_tool -> audit("tool_result", ...)


# TODO 4: write SYSTEM_PROMPT, wrap the tool in policy_server = create_sdk_mcp_server(...),
#         then build ClaudeAgentOptions with: system_prompt, mcp_servers={"policy": policy_server},
#         tools=[], allowed_tools=["mcp__policy__lookup_policy"], max_turns=4, hooks={...}
options = None


async def main() -> None:
    AUDIT_LOG.unlink(missing_ok=True)
    question = "Can I expense a $90 dinner with a bottle of wine on a business trip?"
    print(f"You: {question}\n")
    # TODO 5: async for message in query(prompt=question, options=options): print Claude's text,
    #         and audit("result", ...) when you get the ResultMessage
    # TODO 6: print the audit trail


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
