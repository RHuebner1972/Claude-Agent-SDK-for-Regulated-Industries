"""
M02-L03: ClaudeAgentOptions is your first control surface.

Runs the same harmless prompt twice and prints what the agent was actually given:
first with defaults, then locked down. Compare the [init] lines.

    uv run python lessons/M02-L03_claudeagentoptions-as-your-first/final/options_tour.py
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, query
from course_data import MODEL, show

DEFAULTS = ClaudeAgentOptions()   # whatever the runtime and your settings files decide

LOCKED_DOWN = ClaudeAgentOptions(
    model=MODEL,                         # P7: a pinned, validated model
    system_prompt="You answer questions about accounting policy. Be brief.",
    tools=[],                            # P3: no built-in tools at all
    allowed_tools=[],                    # P3: nothing pre-approved
    disallowed_tools=["Bash", "Write", "Edit", "WebFetch", "WebSearch"],  # belt and braces
    permission_mode="dontAsk",           # P4: anything not pre-approved is denied, never prompted
    strict_mcp_config=True,              # P3: only MCP servers we pass in code
    setting_sources=[],                  # P3: ignore user/project/local settings files
    max_turns=2,                         # P7: hard stop
    max_budget_usd=0.25,                 # P7: hard cost ceiling
)


def describe(name: str, o: ClaudeAgentOptions) -> None:
    print(f"\n=== {name} ===")
    for field in ("model", "tools", "allowed_tools", "disallowed_tools", "permission_mode",
                  "strict_mcp_config", "setting_sources", "max_turns", "max_budget_usd"):
        print(f"  {field:<18} {getattr(o, field)!r}")


async def run(name: str, o: ClaudeAgentOptions) -> None:
    describe(name, o)
    async for message in query(prompt="Say hello in five words.", options=o):
        show(message)


async def main() -> None:
    await run("DEFAULTS", DEFAULTS)
    await run("LOCKED DOWN", LOCKED_DOWN)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
