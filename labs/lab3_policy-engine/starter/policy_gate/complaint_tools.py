"""Complaint-handling tools for Harborline Medical (synthetic), their typed inputs, and the policy hooks they need.

    store = ComplaintStore()
    tools = build_complaint_tools(store)             # pass to create_sdk_mcp_server("complaints", tools=tools)
    enforcer = complaint_enforcer(store, subject, audit=audit)

get_complaint and search_similar return complaint text written by outsiders, so they are UNTRUSTED sources:
after either runs, the session is tainted and the policy treats high-impact actions more strictly.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from claude_agent_sdk import ToolAnnotations, tool
from course_data import complaints

from .engine import PolicyEngine
from .enforce import PolicyEnforcer
from .models import Subject

SERVER = "complaints"
POLICY_DIR = Path(__file__).parent / "policies"
COMPLAINTS_POLICY = POLICY_DIR / "complaints.yaml"
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
UNTRUSTED_TOOLS = ("get_complaint", "search_similar")
CONTACT_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\b\d{3}-\d{3}-\d{4}\b")

ComplaintId = Field(pattern=r"^CMP-\d{4}$")


# ---- pre-conditions: one strict input model per tool (rubric 4.4) ----------------------------
class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListComplaints(_In):
    status: Literal["open", "investigating", "closed", "any"] = "any"


class GetComplaint(_In):
    complaint_id: str = ComplaintId


class SearchSimilar(_In):
    complaint_id: str = ComplaintId


class AddNote(_In):
    complaint_id: str = ComplaintId
    note: str = Field(min_length=10, max_length=2000)


class SetMdrAssessment(_In):
    complaint_id: str = ComplaintId
    decision: Literal["reportable", "not_reportable"]
    rationale: str = Field(min_length=20, max_length=2000)


class CloseComplaint(_In):
    complaint_id: str = ComplaintId
    rationale: str = Field(min_length=20, max_length=2000)


class SendCustomerEmail(_In):
    complaint_id: str = ComplaintId
    to: str = Field(pattern=r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
    subject: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=10, max_length=4000)


VALIDATORS: dict[str, type[BaseModel]] = {
    "list_complaints": ListComplaints, "get_complaint": GetComplaint, "search_similar": SearchSimilar,
    "add_investigation_note": AddNote, "set_mdr_assessment": SetMdrAssessment,
    "close_complaint": CloseComplaint, "send_customer_email": SendCustomerEmail,
}


# ---- the system of record (in memory, so every run starts clean) --------------------------
class ComplaintStore:
    def __init__(self, *, leaky_search: bool = False):
        self.records = {c["complaint_id"]: copy.deepcopy(c) for c in complaints()}
        self.notes: dict[str, list[str]] = {}
        self.outbox: list[dict[str, Any]] = []
        self.changes: list[str] = []
        self.leaky_search = leaky_search          # L06: a "buggy" search that leaks contact details

    def get(self, complaint_id: str) -> dict[str, Any] | None:
        record = self.records.get(complaint_id)
        return copy.deepcopy(record) if record else None

    def resolve(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
        """The policy's view of the resource a call touches: the complaint record as stored right now."""
        cid = tool_input.get("complaint_id")
        return self.get(cid) if isinstance(cid, str) else None


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def build_complaint_tools(store: ComplaintStore):
    @tool("list_complaints", "List complaints: ID, product, status, patient impact, MDR assessment. No free text.",
          ListComplaints.model_json_schema(), annotations=READ_ONLY)
    async def list_complaints(args: dict[str, Any]) -> dict[str, Any]:
        status = ListComplaints.model_validate(args).status
        rows = [{k: c[k] for k in ("complaint_id", "received", "product", "status", "patient_impact",
                                   "mdr_assessment", "mdr_filed")}
                for c in store.records.values() if status in ("any", c["status"])]
        return _text(rows)

    @tool("get_complaint", "Get one complaint record, including the complainant's description (untrusted text).",
          GetComplaint.model_json_schema(), annotations=READ_ONLY)
    async def get_complaint(args: dict[str, Any]) -> dict[str, Any]:
        record = store.get(GetComplaint.model_validate(args).complaint_id)
        if not record:
            return _error(f"No complaint {args['complaint_id']!r}.")
        record["notes"] = store.notes.get(record["complaint_id"], [])
        return _text(record)

    @tool("search_similar", "Find other complaints for the same product lot (for trending and duplicates).",
          SearchSimilar.model_json_schema(), annotations=READ_ONLY)
    async def search_similar(args: dict[str, Any]) -> dict[str, Any]:
        target = store.get(SearchSimilar.model_validate(args).complaint_id)
        if not target:
            return _error(f"No complaint {args['complaint_id']!r}.")
        fields = ["complaint_id", "received", "lot", "description", "patient_impact"]
        if store.leaky_search:
            fields.append("complainant")
        hits = [{k: c[k] for k in fields} for c in store.records.values()
                if c["lot"] == target["lot"] and c["complaint_id"] != target["complaint_id"]]
        return _text({"lot": target["lot"], "similar": hits})

    @tool("add_investigation_note", "Add an investigation note to a complaint.", AddNote.model_json_schema(),
          annotations=WRITE)
    async def add_investigation_note(args: dict[str, Any]) -> dict[str, Any]:
        a = AddNote.model_validate(args)
        if a.complaint_id not in store.records:
            return _error(f"No complaint {a.complaint_id!r}.")
        store.notes.setdefault(a.complaint_id, []).append(a.note)
        store.changes.append(f"{a.complaint_id}: note added")
        return _text({"noted": True, "complaint_id": a.complaint_id})

    @tool("set_mdr_assessment", "Record the MDR reportability determination (21 CFR 803) for a complaint.",
          SetMdrAssessment.model_json_schema(), annotations=WRITE)
    async def set_mdr_assessment(args: dict[str, Any]) -> dict[str, Any]:
        a = SetMdrAssessment.model_validate(args)
        if a.complaint_id not in store.records:
            return _error(f"No complaint {a.complaint_id!r}.")
        store.records[a.complaint_id]["mdr_assessment"] = a.decision
        store.changes.append(f"{a.complaint_id}: MDR assessment set to {a.decision}")
        return _text({"updated": True, "complaint_id": a.complaint_id, "mdr_assessment": a.decision})

    @tool("close_complaint", "Close a complaint with a rationale.", CloseComplaint.model_json_schema(),
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    async def close_complaint(args: dict[str, Any]) -> dict[str, Any]:
        a = CloseComplaint.model_validate(args)
        if a.complaint_id not in store.records:
            return _error(f"No complaint {a.complaint_id!r}.")
        store.records[a.complaint_id]["status"] = "closed"
        store.changes.append(f"{a.complaint_id}: closed")
        return _text({"closed": True, "complaint_id": a.complaint_id})

    @tool("send_customer_email", "Send an email about a complaint.", SendCustomerEmail.model_json_schema(),
          annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True))
    async def send_customer_email(args: dict[str, Any]) -> dict[str, Any]:
        a = SendCustomerEmail.model_validate(args)
        store.outbox.append(a.model_dump())
        store.changes.append(f"{a.complaint_id}: email sent to {a.to}")
        return _text({"sent": True, "to": a.to})

    return [list_complaints, get_complaint, search_similar, add_investigation_note,
            set_mdr_assessment, close_complaint, send_customer_email]


TOOL_NAMES = list(VALIDATORS)
READ_TOOLS = ["list_complaints", "get_complaint", "search_similar"]


def full_name(tool_name: str) -> str:
    return f"mcp__{SERVER}__{tool_name}"


# ---- post-conditions: checks on what a tool RETURNED --------------------------------------------
def no_contact_details(tool_input: dict[str, Any], response: Any) -> str | None:
    """search_similar is for trending: it must never return other complainants' contact details."""
    found = CONTACT_RE.findall(str(response))
    return f"search results contained {len(found)} contact detail(s) of other complainants" if found else None


def returns_requested_record(tool_input: dict[str, Any], response: Any) -> str | None:
    """get_complaint must return the complaint that was asked for, and only that one."""
    try:
        record = json.loads(response) if isinstance(response, str) else response
    except (TypeError, ValueError):
        return None
    if isinstance(record, dict) and record.get("complaint_id") not in (None, tool_input.get("complaint_id")):
        return f"asked for {tool_input.get('complaint_id')} but got {record.get('complaint_id')}"
    return None


OUTPUT_CHECKS = {"search_similar": no_contact_details, "get_complaint": returns_requested_record}


def complaint_enforcer(store: ComplaintStore, subject: Subject, *, policy_path: str | Path = COMPLAINTS_POLICY,
                       audit: Any | None = None, approver: Any | None = None) -> PolicyEnforcer:
    return PolicyEnforcer(PolicyEngine.from_file(policy_path), subject, resolver=store.resolve,
                          validators=VALIDATORS, output_checks=OUTPUT_CHECKS, untrusted_tools=UNTRUSTED_TOOLS,
                          audit=audit, approver=approver)
