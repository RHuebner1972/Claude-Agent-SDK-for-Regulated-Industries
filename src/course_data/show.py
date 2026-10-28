"""Print Claude Agent SDK messages in a readable, one-line-per-event form for demos."""
from __future__ import annotations

import json

from claude_agent_sdk import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)


def _short(value, n: int = 110) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= n else text[: n - 3] + "..."


def show(message) -> None:
    if isinstance(message, SystemMessage) and message.subtype == "init":
        d = message.data
        print(f"[init]    model={d.get('model')} permissionMode={d.get('permissionMode')}")
        print(f"[init]    tools={d.get('tools')}")
        servers = [f"{s.get('name')}:{s.get('status')}" for s in d.get("mcp_servers", [])]
        print(f"[init]    mcp_servers={servers}")
    elif isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"[claude]  {block.text}")
            elif isinstance(block, ToolUseBlock):
                print(f"[tool ->] {block.name} {_short(block.input)}")
    elif isinstance(message, UserMessage) and isinstance(message.content, list):
        for block in message.content:
            if isinstance(block, ToolResultBlock):
                flag = " (error)" if block.is_error else ""
                print(f"[tool <-]{flag} {_short(block.content)}")
    elif isinstance(message, ResultMessage):
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd is not None else "n/a"
        print(f"[result]  subtype={message.subtype} turns={message.num_turns} cost={cost} "
              f"session={message.session_id} stop={message.terminal_reason}")
