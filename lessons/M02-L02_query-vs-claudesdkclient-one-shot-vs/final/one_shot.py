"""
M02-L02 one-shot: query() sends one prompt, streams messages back, and ends.

    uv run python lessons/M02-L02_query-vs-claudesdkclient-one-shot-vs/final/one_shot.py
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, query
from course_data import MODEL, show

options = ClaudeAgentOptions(
    model=MODEL,            # pinned, not "whatever the default is today"
    tools=[],               # no tools: this agent can only talk
    setting_sources=[],     # don't load anyone's local settings files
    max_turns=1,
)


async def main() -> None:
    prompt = "In two sentences, what is a journal entry in accounting?"
    async for message in query(prompt=prompt, options=options):
        show(message)       # init -> assistant text -> result


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
