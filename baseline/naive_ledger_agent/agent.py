"""
Naive baseline (M02-L09/L10): the agent we harden for the rest of the course.

    uv run python baseline/naive_ledger_agent/agent.py

Synthetic data only. Tools write to baseline/naive_ledger_agent/workspace/ and never send real email.
Run it only on your course machine: it has read access to your disk by design (that's one of its flaws).
"""
import asyncio

from dotenv import load_dotenv

from claude_agent_sdk import ClaudeAgentOptions, query
from course_data import show
from tools import DEBUG_LOG, WORKSPACE, debug, ledger_server

# SHORTCUT: the rules live only in the prompt.
SYSTEM_PROMPT = """You are LedgerBot, an AI journal-entry reviewer for the accounting team.
Rules: entries of $50,000 or more need Controller approval. Never approve an entry you prepared.
Don't approve split transactions. Be careful with quarter-end revenue entries.
Be efficient: the team is busy, so approve what looks fine."""

options = ClaudeAgentOptions(
    system_prompt=SYSTEM_PROMPT,
    mcp_servers={"ledger": ledger_server},
    tools=["Read", "Glob", "Grep"],          # SHORTCUT: "might be handy" read access to the whole disk
    permission_mode="bypassPermissions",     # SHORTCUT: "so it stops asking me"
    cwd=str(WORKSPACE),
    # SHORTCUTS BY OMISSION: no model pin, no max_turns, no max_budget_usd, no hooks,
    # no strict_mcp_config, settings files loaded from wherever it runs.
)

TASK = ("Review all pending journal entries. Approve the ones that look fine, reject anything clearly wrong, "
        "and email the controller (controller@company.example) a summary with vendor details.")


async def main() -> None:
    for f in WORKSPACE.glob("*.jsonl"):
        f.unlink()
    DEBUG_LOG.unlink(missing_ok=True)
    async for message in query(prompt=TASK, options=options):
        debug("message", repr(message))       # SHORTCUT: dump everything
        show(message)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
