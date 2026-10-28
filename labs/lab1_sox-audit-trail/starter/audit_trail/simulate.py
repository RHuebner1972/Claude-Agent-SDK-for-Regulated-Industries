"""Drive AuditHooks with realistic SDK hook inputs, offline: no API key, no model, no cost.

Used by the lessons to show a full audit trail on screen, by the tests, and to generate the
sample logs in the Lab 1 data folder. The events are exactly what a real LedgerBot run emits;
only the model's choices are scripted.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from claude_agent_sdk import ResultMessage

from course_data import approval_policy, journal_entries, vendors

from .hooks import AuditHooks
from .models import AgentInfo, content_version

SERVER = "mcp__ledger__"
TASK = "Review all pending journal entries and record a recommendation for each."
DEMO_AGENT = AgentInfo(name="LedgerBot", version="1.3.0", model="claude-sonnet-5-5",
                       prompt_version="sha256:5d41c0a19e2b", policy_version=content_version(approval_policy()))

# The scripted "model" decisions: what a correct LedgerBot recommends, with the rule it cites.
DECISIONS: dict[str, tuple[str, str, str, str]] = {
    "JE-1001": ("approve", "none", "Routine accrual under $50,000; preparer is not the reviewer", "Policy rules 1-6: no rule triggered"),
    "JE-1002": ("approve", "none", "Routine prepaid under $50,000", "Policy rules 1-6: no rule triggered"),
    "JE-1003": ("escalate", "Controller", "Amount $62,500 is at or above the $50,000 threshold", "Policy rule 1"),
    "JE-1004": ("approve", "none", "Routine travel under $50,000", "Policy rules 1-6: no rule triggered"),
    "JE-1005": ("approve", "none", "Routine reclass under $50,000", "Policy rules 1-6: no rule triggered"),
    "JE-1006": ("reject", "Controller", "Same vendor, same day, two parts of $48,500 total $97,000: split to stay under threshold", "Policy rule 3"),
    "JE-1007": ("reject", "Controller", "Second half of the JE-1006 split", "Policy rule 3"),
    "JE-1008": ("escalate", "CFO", "Manual revenue entry in the last 3 days of the quarter; also over $50,000", "Policy rules 4 and 1"),
    "JE-1009": ("escalate", "Controller", "Prepared by agent-reviewer, the agent's own account: it may not review its own entry", "Policy rule 2"),
    "JE-1010": ("escalate", "Controller", "Over $50,000; the description tries to instruct the AI, which is never authorization", "Policy rules 1 and 5"),
}


def _content(payload: Any) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


class _Clock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        self.now += timedelta(milliseconds=1350)
        return self.now


async def simulate_ledger_review(hooks: AuditHooks, *, session_id: str = "sess-7f3a9c21",
                                 entries: list[str] | None = None, deny_banking_lookup: bool = True) -> None:
    base = {"session_id": session_id, "transcript_path": f"~/.claude/projects/ledgerbot/{session_id}.jsonl",
            "cwd": "/srv/ledgerbot", "permission_mode": "dontAsk"}
    counter = iter(range(1, 1000))
    data = {e["entry_id"]: e for e in journal_entries()}
    wanted = entries or list(DECISIONS)

    async def call(tool: str, tool_input: dict, response: Any) -> str:
        tid = f"toolu_{next(counter):03d}"
        name = SERVER + tool
        await hooks.on_pre_tool({**base, "hook_event_name": "PreToolUse", "tool_name": name,
                                 "tool_input": tool_input, "tool_use_id": tid}, tid, {"signal": None})
        if response is not None:
            await hooks.on_post_tool({**base, "hook_event_name": "PostToolUse", "tool_name": name, "tool_input": tool_input,
                                      "tool_response": _content(response), "tool_use_id": tid, "duration_ms": 42},
                                     tid, {"signal": None})
        return tid

    await hooks.on_prompt({**base, "hook_event_name": "UserPromptSubmit", "prompt": TASK}, None, {"signal": None})
    pending = [{k: e[k] for k in ("entry_id", "date", "amount", "description")} for e in journal_entries()]
    await call("list_pending_entries", {}, pending)

    denials = []
    for entry_id in wanted:
        entry = data[entry_id]
        await call("get_journal_entry", {"entry_id": entry_id}, entry)
        if entry_id == "JE-1010" and deny_banking_lookup:
            # The model tries the treasury-only banking tool: requested, never executed.
            tid = await call("get_vendor_banking", {"vendor_id": entry["vendor_id"]}, None)
            denials.append({"tool_name": SERVER + "get_vendor_banking", "tool_use_id": tid,
                            "tool_input": {"vendor_id": entry["vendor_id"]}})
        if entry_id == "JE-1006":
            vendor = next(v for v in vendors() if v["vendor_id"] == entry["vendor_id"])
            await call("get_vendor_summary", {"vendor_id": vendor["vendor_id"]},
                       {"vendor_id": vendor["vendor_id"], "name": vendor["name"]})
        rec, approver, why, rule = DECISIONS[entry_id]
        rec_input = {"entry_id": entry_id, "recommendation": rec, "approver_required": approver,
                     "rationale": why, "policy_rule": rule}
        await call("record_recommendation", rec_input, {"recorded": True, "entry_id": entry_id})

    summary = "; ".join(f"{e}: {DECISIONS[e][0]}" for e in wanted)
    await hooks.on_stop({**base, "hook_event_name": "Stop", "stop_hook_active": False,
                         "last_assistant_message": f"Review complete. {summary}."}, None, {"signal": None})
    hooks.observe(ResultMessage(subtype="success", duration_ms=48210, duration_api_ms=39877, is_error=False,
                                num_turns=len(wanted) * 2 + 2, session_id=session_id, total_cost_usd=0.1842,
                                permission_denials=denials, terminal_reason="completed"))


def fixed_clock(start: str = "2026-10-01T14:00:00+00:00") -> _Clock:
    return _Clock(datetime.fromisoformat(start).astimezone(timezone.utc))
