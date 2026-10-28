"""
M02-L02 stateful: ClaudeSDKClient keeps one session open across several turns.

    uv run python lessons/M02-L02_query-vs-claudesdkclient-one-shot-vs/final/conversation.py
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from course_data import MODEL, show

options = ClaudeAgentOptions(model=MODEL, tools=[], setting_sources=[], max_turns=2)

TURNS = [
    "Our policy says journal entries of $50,000 or more need Controller approval. Remember that.",
    "An entry for $62,500 arrives. Who needs to approve it? One sentence.",
    "And one for $48,500, followed an hour later by another $48,500 to the same vendor?",
]


async def main() -> None:
    async with ClaudeSDKClient(options=options) as client:   # one session, many turns
        for turn in TURNS:
            print(f"\n[you]     {turn}")
            await client.query(turn)
            async for message in client.receive_response():
                show(message)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
