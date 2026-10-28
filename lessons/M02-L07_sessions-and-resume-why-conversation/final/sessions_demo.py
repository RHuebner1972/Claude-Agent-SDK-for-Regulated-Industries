"""
M02-L07: sessions are records. Capture the ID, resume it, and find the transcript on disk.

    uv run python lessons/M02-L07_sessions-and-resume-why-conversation/final/sessions_demo.py
"""
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, get_session_messages, list_sessions, query
from course_data import MODEL

WORKDIR = Path(__file__).parent
BASE = dict(model=MODEL, tools=[], setting_sources=[], max_turns=1, cwd=str(WORKDIR))


async def ask(prompt: str, **extra) -> str:
    session_id = ""
    async for message in query(prompt=prompt, options=ClaudeAgentOptions(**BASE, **extra)):
        if isinstance(message, ResultMessage):
            session_id = message.session_id
            print(f"  -> {message.result!r}")
    return session_id


async def main() -> None:
    print("1. Start a session")
    sid = await ask("Remember this reference number for later: REF-4471. Reply 'noted'.")
    print(f"   session_id = {sid}   <- log this with every audit event (Module 3)")

    print("\n2. Resume it later: the conversation history comes back")
    await ask("What reference number did I give you?", resume=sid)

    print("\n3. The transcript is a file on disk, and it holds everything that was said")
    info = next((s for s in list_sessions(directory=str(WORKDIR)) if s.session_id == sid), None)
    print(f"   found in session list: {info is not None}")
    messages = get_session_messages(sid, directory=str(WORKDIR))
    print(f"   messages stored: {len(messages)}")
    print(f"   location: ~/.claude/projects/<project>/{sid}.jsonl")
    print("\n   Regulated question: who can read that file, how long is it kept, and does it contain PHI or PII?")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
