"""
M02-L05: a tool whose input schema comes from Pydantic and whose output is validated before
it ever reaches the model.

    uv run python lessons/M02-L05_pydantic-everywhere-typed-tool-inputs/final/typed_tools.py
"""
from __future__ import annotations

import asyncio
from typing import Any

from pydantic import ValidationError

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool
from course_data import journal_entries
from models import EntryLookup, JournalEntry


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


@tool("get_journal_entry", "Get one journal entry by ID, for example JE-1003.",
      EntryLookup.model_json_schema(),                       # the schema Claude sees
      annotations=ToolAnnotations(readOnlyHint=True))
async def get_journal_entry(args: dict[str, Any]) -> dict[str, Any]:
    try:
        request = EntryLookup.model_validate(args)           # validate again: defense in depth
    except ValidationError as exc:
        return _error(f"Invalid request: {exc.errors()[0]['msg']}")
    raw = next((e for e in journal_entries() if e["entry_id"] == request.entry_id), None)
    if raw is None:
        return _error(f"No journal entry {request.entry_id}.")
    try:
        entry = JournalEntry.model_validate(raw)             # never pass bad records to the model
    except ValidationError as exc:
        return _error(f"Record {request.entry_id} failed validation and was withheld: {exc.errors()[0]['msg']}")
    return {"content": [{"type": "text", "text": entry.model_dump_json(indent=2)}]}


typed_server = create_sdk_mcp_server("ledger", tools=[get_journal_entry])


async def demo() -> None:
    """Call the handler directly (no model needed) to watch validation work."""
    for args in ({"entry_id": "JE-1003"}, {"entry_id": "1003"}, {"entry_id": "JE-1003; DROP TABLE"}, {"entry_id": "JE-9999"}):
        result = await get_journal_entry.handler(args)
        tag = "ERROR" if result.get("is_error") else "OK"
        print(f"{tag:<5} {args} -> {result['content'][0]['text'][:80]!r}")


if __name__ == "__main__":
    asyncio.run(demo())
