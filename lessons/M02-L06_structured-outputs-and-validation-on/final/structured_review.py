"""
M02-L06: structured output, validated on the way out. Fail closed if it doesn't validate.

    uv run python lessons/M02-L06_structured-outputs-and-validation-on/final/structured_review.py JE-1003
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

from dotenv import load_dotenv
from pydantic import ValidationError

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, create_sdk_mcp_server, query
from course_data import MODEL, approval_policy, journal_entries
from models import ReviewDecision
from typed_tools import get_journal_entry   # the typed tool from L05 (copied here so the folder stands alone)

options = ClaudeAgentOptions(
    model=MODEL,
    system_prompt="You review journal entries against this policy:\n\n" + approval_policy(),
    mcp_servers={"ledger": create_sdk_mcp_server("ledger", tools=[get_journal_entry])},
    tools=[],
    allowed_tools=["mcp__ledger__get_journal_entry"],
    permission_mode="dontAsk",
    strict_mcp_config=True,
    setting_sources=[],
    max_turns=4,
    output_format={"type": "json_schema", "schema": ReviewDecision.model_json_schema()},
)


def business_checks(decision: ReviewDecision) -> list[str]:
    """Rules the schema can't express. If any fail, a human gets the entry instead."""
    entry = next(e for e in journal_entries() if e["entry_id"] == decision.entry_id)
    problems = []
    if Decimal(str(entry["amount"])) >= 50000 and decision.decision == "approve" and decision.required_approver != "controller":
        problems.append("approved >= $50,000 without naming the Controller as required approver")
    if entry["preparer"] == "agent-reviewer" and decision.decision == "approve":
        problems.append("agent approved an entry prepared by its own account")
    return problems


def fail_closed(entry_id: str, why: str) -> None:
    print(f"\nROUTED TO HUMAN REVIEW: {entry_id}. Reason: {why}")


async def main(entry_id: str) -> None:
    result: ResultMessage | None = None
    try:
        async for message in query(prompt=f"Review journal entry {entry_id}.", options=options):
            if isinstance(message, ResultMessage):
                result = message
    except Exception as exc:   # query() raises after an error result, e.g. error_max_structured_output_retries
        if result is None:
            return fail_closed(entry_id, f"agent run failed: {exc}")
    if result is None or result.is_error or result.structured_output is None:
        return fail_closed(entry_id, f"no structured output ({result.subtype if result else 'no result'})")
    try:
        decision = ReviewDecision.model_validate(result.structured_output)
    except ValidationError as exc:
        return fail_closed(entry_id, f"output failed schema validation: {exc.errors()[0]['msg']}")
    if decision.entry_id != entry_id:
        return fail_closed(entry_id, f"output is about {decision.entry_id}, not {entry_id}")
    if problems := business_checks(decision):
        return fail_closed(entry_id, "; ".join(problems))
    print(decision.model_dump_json(indent=2))


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "JE-1003"))
