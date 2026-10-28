"""
M00-L03 quick win: your first audited Claude agent.

    uv run python lessons/M00-L03_quick-win-build-your-first-audited/final/first_audited_agent.py

One custom tool, no built-in tools, and three hooks that write an audit trail
of everything the agent was asked, every tool it called and what came back.
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

# 1. A tool: the only thing this agent is allowed to do.
POLICIES = {
    "travel": "Economy class for flights under 6 hours. Receipts required above $75.",
    "meals": "Up to $60 per person per day while traveling. Alcohol is not reimbursable.",
    "gifts": "No gifts to government officials. Other business gifts capped at $100 per year.",
}


@tool("lookup_policy", "Look up the expense policy for one topic: travel, meals or gifts", {"topic": str})
async def lookup_policy(args):
    text = POLICIES.get(args["topic"].lower(), "No policy found for that topic.")
    return {"content": [{"type": "text", "text": text}]}


# 2. The audit trail: one JSON line per event.
def audit(event: str, **fields) -> None:
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")


# 3. Hooks: the SDK calls these at each step, whether or not the model "remembers" to.
async def on_prompt(input_data, tool_use_id, context):
    audit("prompt", session=input_data["session_id"], prompt=input_data["prompt"])
    return {}


async def before_tool(input_data, tool_use_id, context):
    audit("tool_call", session=input_data["session_id"], tool=input_data["tool_name"],
          input=input_data["tool_input"])
    return {}


async def after_tool(input_data, tool_use_id, context):
    audit("tool_result", session=input_data["session_id"], tool=input_data["tool_name"],
          output=input_data["tool_response"])
    return {}


# 4. Options: the agent's first control surface.
SYSTEM_PROMPT = ("You answer employee expense questions. "
                 "Always check the policy with lookup_policy. Never guess.")
policy_server = create_sdk_mcp_server("policy", tools=[lookup_policy])

options = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    mcp_servers={"policy": policy_server},
    tools=[],                                      # no built-in tools
    allowed_tools=["mcp__policy__lookup_policy"],  # pre-approve one tool
    max_turns=4,                                   # hard stop
    hooks={
        "UserPromptSubmit": [HookMatcher(hooks=[on_prompt])],
        "PreToolUse": [HookMatcher(hooks=[before_tool])],
        "PostToolUse": [HookMatcher(hooks=[after_tool])],
    },
)


async def main() -> None:
    AUDIT_LOG.unlink(missing_ok=True)
    question = "Can I expense a $90 dinner with a bottle of wine on a business trip?"
    print(f"You: {question}\n")
    async for message in query(prompt=question, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"Claude: {block.text}")
        elif isinstance(message, ResultMessage):
            audit("result", session=message.session_id, turns=message.num_turns, cost_usd=message.total_cost_usd)

    print("\n--- audit.jsonl ---")
    for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        print(f"{rec['ts'][11:19]}  {rec['event']:<12} {json.dumps({k: v for k, v in rec.items() if k not in ('ts', 'event', 'session')})[:90]}")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
