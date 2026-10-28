"""
Lab 3 solution: the policy-gated complaint assistant, live (needs ANTHROPIC_API_KEY).

    cd labs/lab3_policy-engine/solution
    uv run python agent.py --user m.ortiz --role complaint_intake
    uv run python agent.py --user a.novak --role regulatory_affairs --task "Make the MDR call on CMP-3006."

Two enforcement points, one policy:
  * PreToolUse hook   runs for EVERY call (reads included) and can deny.
  * can_use_tool      runs for calls that are not pre-approved: here, every write.
An 'ask' decision prompts in this terminal. Module 6 replaces that with a real approval queue.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, create_sdk_mcp_server
from course_data import MODEL, show

from policy_gate.complaint_tools import READ_TOOLS, SERVER, full_name
from triage_pipeline import SYSTEM_PROMPT, build_pipeline

WORKSPACE = Path(__file__).resolve().parent / "workspace"
TASK = ("Triage the open complaints: read each one, check for similar complaints, add an investigation note, "
        "and tell me what should happen next.")


def console_approver(decision, tool_input) -> bool:
    print(f"\n  APPROVAL NEEDED [{decision.rule_id}] {decision.reason}\n  {decision.tool} {tool_input}")
    return input("  Approve? [y/N] ").strip().lower() == "y"


async def main(user: str, role: str, task: str) -> None:
    p = build_pipeline(WORKSPACE, user=user, role=role, approver=console_approver)
    server = create_sdk_mcp_server(SERVER, tools=p.tools)
    options = ClaudeAgentOptions(
        model=MODEL, system_prompt=SYSTEM_PROMPT, mcp_servers={SERVER: server},
        tools=[],                                              # no built-in tools at all
        allowed_tools=[full_name(t) for t in READ_TOOLS],      # pre-approved: reads only
        disallowed_tools=["Bash", "Write", "Edit", "WebFetch", "WebSearch"],
        permission_mode="default",                             # writes fall through to can_use_tool
        can_use_tool=p.enforcer.can_use_tool,
        hooks=p.hooks, strict_mcp_config=True, setting_sources=[], max_turns=30, max_budget_usd=1.00,
    )
    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        async for message in client.receive_response():
            show(message)
            p.audit.observe(message)
    print(f"\nRecord changes: {p.complaints.changes or '(none)'}\nAudit log: {p.store.path}")
    print(f"Policy decisions: {[d.message()[:60] for d in p.enforcer.decisions if d.effect != 'allow']}")


if __name__ == "__main__":
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--role", required=True, choices=["complaint_intake", "qa_specialist", "regulatory_affairs"])
    parser.add_argument("--task", default=TASK)
    args = parser.parse_args()
    asyncio.run(main(args.user, args.role, args.task))
