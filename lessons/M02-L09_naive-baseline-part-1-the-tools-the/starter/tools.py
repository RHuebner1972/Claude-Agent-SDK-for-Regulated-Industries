"""
M02-L09 starter: build the naive ledger tools. Follow the TODOs in order.
Finished version: baseline/naive_ledger_agent/tools.py
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

# TODO 1: debug(event, payload) that appends a raw line to DEBUG_LOG
# TODO 2: list_pending_entries -> every pending entry, all fields
# TODO 3: get_journal_entry(entry_id) and get_vendor(vendor_id) -> the full records
# TODO 4: approve_entry(entry_id, comment) and reject_entry(entry_id, reason) -> append to DECISIONS
# TODO 5: send_email(to, subject, body) -> append to OUTBOX (nothing is really sent)
# TODO 6: TOOLS = [...]; ledger_server = create_sdk_mcp_server("ledger", tools=TOOLS)
