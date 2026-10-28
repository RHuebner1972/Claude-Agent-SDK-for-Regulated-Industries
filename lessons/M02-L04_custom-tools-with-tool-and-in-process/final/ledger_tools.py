"""
M02-L04: custom tools with @tool, served by an in-process MCP server.

Read-only ledger tools over the synthetic finance data in data/synthetic/finance/.
"""
from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool
from course_data import gl_accounts, journal_entries

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


@tool("list_pending_entries", "List journal entries waiting for review: ID, date, amount, description.", {},
      annotations=READ_ONLY)
async def list_pending_entries(args: dict[str, Any]) -> dict[str, Any]:
    rows = [{k: e[k] for k in ("entry_id", "date", "amount", "description")}
            for e in journal_entries() if e["status"] == "pending_review"]
    return _text(rows)


@tool("get_journal_entry", "Get one journal entry by ID, for example JE-1003.", {"entry_id": str},
      annotations=READ_ONLY)
async def get_journal_entry(args: dict[str, Any]) -> dict[str, Any]:
    entry = next((e for e in journal_entries() if e["entry_id"] == args["entry_id"]), None)
    return _text(entry) if entry else _error(f"No journal entry with ID {args['entry_id']!r}.")


@tool("get_gl_account", "Look up a general-ledger account by its 4-digit number.", {"account": str},
      annotations=READ_ONLY)
async def get_gl_account(args: dict[str, Any]) -> dict[str, Any]:
    acct = next((a for a in gl_accounts() if a["account"] == args["account"]), None)
    return _text(acct) if acct else _error(f"No GL account {args['account']!r}.")


TOOLS = [list_pending_entries, get_journal_entry, get_gl_account]
ledger_server = create_sdk_mcp_server("ledger", version="1.0.0", tools=TOOLS)

# The SDK names custom tools mcp__<server key>__<tool name>.
LEDGER_TOOL_NAMES = [f"mcp__ledger__{t.name}" for t in TOOLS]
