"""
M00-L02 environment check.

    uv run python lessons/M00-L02_set-up-your-environment-python-uv-the/final/check_setup.py

Checks Python, the Claude Agent SDK, your credentials, and makes one tiny call to Claude.
It never prints your API key, not even part of it. Get used to that habit now.
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

PASS, FAIL = "[ OK ]", "[FAIL]"


def check_python() -> bool:
    ok = sys.version_info >= (3, 10)
    print(f"{PASS if ok else FAIL} Python {sys.version.split()[0]} (need 3.10+)")
    return ok


def check_sdk() -> bool:
    try:
        import claude_agent_sdk
    except ImportError:
        print(f"{FAIL} claude-agent-sdk not installed. Run: uv sync")
        return False
    print(f"{PASS} claude-agent-sdk {claude_agent_sdk.__version__}")
    return True


def check_credentials() -> bool:
    if os.getenv("CLAUDE_CODE_USE_BEDROCK") or os.getenv("CLAUDE_CODE_USE_VERTEX"):
        print(f"{PASS} Cloud provider credentials selected (Bedrock or Vertex)")
        return True
    if os.getenv("ANTHROPIC_API_KEY"):
        print(f"{PASS} ANTHROPIC_API_KEY found (value not displayed)")
        return True
    print(f"{FAIL} No credentials. Copy .env.example to .env and add ANTHROPIC_API_KEY")
    return False


async def smoke_test() -> bool:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query

    options = ClaudeAgentOptions(tools=[], max_turns=1,  # no tools at all for a smoke test
                                 setting_sources=[],  # ignore ~/.claude/settings.json, which may route to a gateway
                                 env={"ANTHROPIC_BASE_URL": "https://api.anthropic.com"})
    reply = ""
    prompt = "Reply with exactly one word: READY"

    async def collect() -> None:
        nonlocal reply
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                reply += "".join(b.text for b in message.content if isinstance(b, TextBlock))

    try:
        await asyncio.wait_for(collect(), timeout=90)
    except asyncio.TimeoutError:
        print(f"{FAIL} No reply from Claude within 90s (check network, proxy, or API key)")
        return False
    ok = "READY" in reply.upper()
    print(f"{PASS if ok else FAIL} Claude replied: {reply.strip()!r}")
    return ok


def main() -> None:
    load_dotenv()
    ok = check_python() and check_sdk() and check_credentials()
    if ok:
        ok = asyncio.run(smoke_test())
    print("\nYou're ready for the quick win." if ok else "\nFix the item marked FAIL and run this again.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
