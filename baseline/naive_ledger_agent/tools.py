"""
Naive baseline (M02-L09): the ledger tools, written the way many first agents are written.

Every shortcut here is deliberate. Module 2, Lecture 11 threat-models them; Modules 3-8 fix them.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from course_data import journal_entries, vendors

WORKSPACE = Path(__file__).parent / "workspace"
DEBUG_LOG = WORKSPACE / "naive_debug.log"
DECISIONS = WORKSPACE / "decisions.jsonl"
OUTBOX = WORKSPACE / "outbox.jsonl"


def debug(event: str, payload: Any) -> None:
    # SHORTCUT: raw, unmasked, editable, no identity. "Just for debugging."
    WORKSPACE.mkdir(exist_ok=True)
    with DEBUG_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} {event} {json.dumps(payload, default=str)}\n")


def _text(payload: Any) -> dict[str, Any]:
    debug("tool_result", payload)
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}]}


def _record(path: Path, row: dict) -> None:
    WORKSPACE.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **row}) + "\n")


@tool("list_pending_entries", "List all journal entries waiting for review.", {})
async def list_pending_entries(args: dict[str, Any]) -> dict[str, Any]:
    return _text([e for e in journal_entries() if e["status"] == "pending_review"])   # SHORTCUT: everything


@tool("get_journal_entry", "Get a journal entry.", {"entry_id": str})
async def get_journal_entry(args: dict[str, Any]) -> dict[str, Any]:
    return _text(next((e for e in journal_entries() if e["entry_id"] == args["entry_id"]), {}))


@tool("get_vendor", "Get everything we know about a vendor.", {"vendor_id": str})
async def get_vendor(args: dict[str, Any]) -> dict[str, Any]:
    # SHORTCUT: returns tax ID and bank account "in case they're useful"
    return _text(next((v for v in vendors() if v["vendor_id"] == args["vendor_id"]), {}))


@tool("approve_entry", "Approve a journal entry for posting.", {"entry_id": str, "comment": str})
async def approve_entry(args: dict[str, Any]) -> dict[str, Any]:
    # SHORTCUT: no policy check, no approver identity, no segregation of duties
    _record(DECISIONS, {"entry_id": args["entry_id"], "decision": "approve", "comment": args.get("comment", "")})
    return _text({"status": "approved", "entry_id": args["entry_id"]})


@tool("reject_entry", "Reject a journal entry.", {"entry_id": str, "reason": str})
async def reject_entry(args: dict[str, Any]) -> dict[str, Any]:
    _record(DECISIONS, {"entry_id": args["entry_id"], "decision": "reject", "comment": args.get("reason", "")})
    return _text({"status": "rejected", "entry_id": args["entry_id"]})


@tool("send_email", "Send an email to anyone.", {"to": str, "subject": str, "body": str})
async def send_email(args: dict[str, Any]) -> dict[str, Any]:
    # SHORTCUT: any recipient, any content. (It only writes to outbox.jsonl, nothing is really sent.)
    _record(OUTBOX, args)
    return _text({"status": "sent", "to": args["to"]})


TOOLS = [list_pending_entries, get_journal_entry, get_vendor, approve_entry, reject_entry, send_email]
ledger_server = create_sdk_mcp_server("ledger", tools=TOOLS)
