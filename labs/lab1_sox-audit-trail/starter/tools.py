"""Lab 1: LedgerBot's tools: the M02 read-only tools plus record_recommendation.

record_recommendation writes the agent's decision to a downstream store, stamped with the run's
correlation ID so the decision can be traced back to the audit log (M03-L04).
get_vendor_banking lives on the same shared ledger server for the treasury agent; LedgerBot is
NOT allowed to call it, which gives us a real permission denial to audit.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool
from course_data import journal_entries, vendors

WORKSPACE = Path(__file__).resolve().parent / "workspace"
RECOMMENDATIONS = WORKSPACE / "recommendations.jsonl"
RUN = {"correlation_id": "unset"}            # set by the runner before each run
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


class Recommendation(BaseModel):
    entry_id: str = Field(pattern=r"^JE-\d{4}$")
    recommendation: Literal["approve", "reject", "escalate"]
    approver_required: Literal["none", "Controller", "CFO"]
    rationale: str = Field(min_length=10)
    policy_rule: str = Field(min_length=3, description="The policy rule(s) this decision relies on")


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


@tool("list_pending_entries", "List journal entries waiting for review.", {}, annotations=READ_ONLY)
async def list_pending_entries(args: dict[str, Any]) -> dict[str, Any]:
    return _text([{k: e[k] for k in ("entry_id", "date", "amount", "description")}
                  for e in journal_entries() if e["status"] == "pending_review"])


@tool("get_journal_entry", "Get one journal entry by ID, for example JE-1003.", {"entry_id": str}, annotations=READ_ONLY)
async def get_journal_entry(args: dict[str, Any]) -> dict[str, Any]:
    entry = next((e for e in journal_entries() if e["entry_id"] == args["entry_id"]), None)
    return _text(entry) if entry else _error(f"No journal entry {args['entry_id']!r}.")


@tool("get_vendor_summary", "Get a vendor's ID and name.", {"vendor_id": str}, annotations=READ_ONLY)
async def get_vendor_summary(args: dict[str, Any]) -> dict[str, Any]:
    v = next((v for v in vendors() if v["vendor_id"] == args["vendor_id"]), None)
    return _text({"vendor_id": v["vendor_id"], "name": v["name"]}) if v else _error("No such vendor.")


@tool("get_vendor_banking", "TREASURY ONLY: a vendor's bank and tax details.", {"vendor_id": str}, annotations=READ_ONLY)
async def get_vendor_banking(args: dict[str, Any]) -> dict[str, Any]:
    v = next((v for v in vendors() if v["vendor_id"] == args["vendor_id"]), None)
    return _text(v) if v else _error("No such vendor.")


@tool("record_recommendation", "Record your recommendation for one entry. Required for every entry you review.",
      Recommendation.model_json_schema())
async def record_recommendation(args: dict[str, Any]) -> dict[str, Any]:
    rec = Recommendation.model_validate(args)
    WORKSPACE.mkdir(exist_ok=True)
    row = {**rec.model_dump(), "correlation_id": RUN["correlation_id"],      # propagate the run ID downstream
           "recorded_at": datetime.now(timezone.utc).isoformat()}
    with RECOMMENDATIONS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    return _text({"recorded": True, "entry_id": rec.entry_id})


TOOLS = [list_pending_entries, get_journal_entry, get_vendor_summary, get_vendor_banking, record_recommendation]
ledger_server = create_sdk_mcp_server("ledger", tools=TOOLS)
LEDGERBOT_ALLOWED = [f"mcp__ledger__{t.name}" for t in TOOLS if t.name != "get_vendor_banking"]
