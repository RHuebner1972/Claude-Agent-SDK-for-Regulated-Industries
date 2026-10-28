"""AML alert-triage tools for Bayside Community Bank (synthetic), and the evidence package approvers see.

The assistant can read, note and REQUEST. Closing alerts, SAR recommendations and account restrictions
run only after people sign (policies/oversight.yaml). There is deliberately no tool to contact a customer:
a SAR, and anything that would reveal one, is confidential (31 CFR 1020.320(e)).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from claude_agent_sdk import ToolAnnotations, tool
from course_data import aml_alerts, aml_staff

from .models import Signer, load_oversight

SERVER = "aml"
OVERSIGHT_POLICY = Path(__file__).parent / "policies" / "oversight.yaml"
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
AlertId = Field(pattern=r"^ALR-\d{4}$")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetAlert(_In):
    alert_id: str = AlertId


class CustomerHistory(_In):
    customer_id: str = Field(pattern=r"^CUS-\d{4}$")


class CaseNote(_In):
    alert_id: str = AlertId
    note: str = Field(min_length=10, max_length=2000)


class CloseAlert(_In):
    alert_id: str = AlertId
    disposition: Literal["false_positive", "not_suspicious"]
    rationale: str = Field(min_length=20, max_length=2000)


class RecommendSar(_In):
    alert_id: str = AlertId
    activity_type: Literal["structuring", "rapid_movement_of_funds", "elder_financial_exploitation", "other"]
    suspicious_amount: float = Field(gt=0)
    narrative: str = Field(min_length=40, max_length=4000)


class RestrictAccount(_In):
    alert_id: str = AlertId
    account_id: str = Field(pattern=r"^ACC-\d{5}$")
    restriction: Literal["block_outgoing_wires", "freeze"]
    reason: str = Field(min_length=20, max_length=1000)


class AlertStore:
    def __init__(self):
        self.alerts = {a["alert_id"]: copy.deepcopy(a) for a in aml_alerts()}
        self.notes: dict[str, list[str]] = {}
        self.sar_referrals: list[dict] = []          # handed to the BSA team to file; the agent never files
        self.restrictions: list[dict] = []
        self.changes: list[str] = []

    def evidence(self, tool: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """The decision-support package an approver sees next to the agent's rationale."""
        a = self.alerts.get(tool_input.get("alert_id", ""))
        if not a:
            return {}
        c = a["customer"]
        total = sum(t["amount"] for t in a["transactions"])
        return {"alert_id": a["alert_id"], "scenario": a["scenario"], "rule_id": a["rule_id"],
                "generated": a["generated"], "customer_id": c["customer_id"], "customer": c["name"],
                "customer_type": c["type"], "occupation": c["occupation"], "risk_rating": c["risk_rating"],
                "account_id": c["account_id"], "transactions": len(a["transactions"]), "total_amount": total,
                "prior_alerts_12m": a["prior_alerts_12m"], "prior_sars": a["prior_sars"],
                "analyst_notes": a["analyst_notes"], "relationship_manager": a["relationship_manager"]}


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def build_aml_tools(store: AlertStore):
    @tool("list_alerts", "List open AML alerts: ID, scenario, customer, date.", {}, annotations=READ_ONLY)
    async def list_alerts(args: dict[str, Any]) -> dict[str, Any]:
        return _text([{"alert_id": a["alert_id"], "scenario": a["scenario"], "customer": a["customer"]["name"],
                       "generated": a["generated"]} for a in store.alerts.values() if a["status"] == "open"])

    @tool("get_alert", "Get one alert with its customer profile and transactions.", GetAlert.model_json_schema(),
          annotations=READ_ONLY)
    async def get_alert(args: dict[str, Any]) -> dict[str, Any]:
        a = store.alerts.get(GetAlert.model_validate(args).alert_id)
        return _text({**a, "case_notes": store.notes.get(a["alert_id"], [])}) if a else _error("No such alert.")

    @tool("get_customer_history", "Prior alerts and SAR count for a customer.", CustomerHistory.model_json_schema(),
          annotations=READ_ONLY)
    async def get_customer_history(args: dict[str, Any]) -> dict[str, Any]:
        cid = CustomerHistory.model_validate(args).customer_id
        hits = [a for a in store.alerts.values() if a["customer"]["customer_id"] == cid]
        return _text({"customer_id": cid, "alerts": [a["alert_id"] for a in hits],
                      "prior_alerts_12m": sum(a["prior_alerts_12m"] for a in hits),
                      "prior_sars": sum(a["prior_sars"] for a in hits)}) if hits else _error("No such customer.")

    @tool("add_case_note", "Add a note to the alert's case file.", CaseNote.model_json_schema(), annotations=WRITE)
    async def add_case_note(args: dict[str, Any]) -> dict[str, Any]:
        a = CaseNote.model_validate(args)
        store.notes.setdefault(a.alert_id, []).append(a.note)
        store.changes.append(f"{a.alert_id}: note added")
        return _text({"noted": True})

    @tool("close_alert", "Close an alert as a false positive or not suspicious. Needs human approval.",
          CloseAlert.model_json_schema(), annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    async def close_alert(args: dict[str, Any]) -> dict[str, Any]:
        a = CloseAlert.model_validate(args)
        store.alerts[a.alert_id]["status"] = f"closed_{a.disposition}"
        store.changes.append(f"{a.alert_id}: closed ({a.disposition})")
        return _text({"closed": True, "alert_id": a.alert_id})

    @tool("recommend_sar", "Refer an alert to the BSA team for SAR filing. Needs two approvals.",
          RecommendSar.model_json_schema(), annotations=WRITE)
    async def recommend_sar(args: dict[str, Any]) -> dict[str, Any]:
        a = RecommendSar.model_validate(args)
        store.alerts[a.alert_id]["status"] = "escalated_sar"
        store.sar_referrals.append(a.model_dump())
        store.changes.append(f"{a.alert_id}: referred for SAR ({a.activity_type}, ${a.suspicious_amount:,.0f})")
        return _text({"referred": True, "alert_id": a.alert_id})

    @tool("restrict_account", "Block outgoing wires on, or freeze, an account. Needs BSA Officer approval.",
          RestrictAccount.model_json_schema(), annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True))
    async def restrict_account(args: dict[str, Any]) -> dict[str, Any]:
        a = RestrictAccount.model_validate(args)
        store.restrictions.append(a.model_dump())
        store.changes.append(f"{a.account_id}: {a.restriction}")
        return _text({"restricted": True, "account_id": a.account_id, "restriction": a.restriction})

    return [list_alerts, get_alert, get_customer_history, add_case_note, close_alert, recommend_sar, restrict_account]


READ_TOOLS = ["list_alerts", "get_alert", "get_customer_history"]
ALL_TOOLS = READ_TOOLS + ["add_case_note", "close_alert", "recommend_sar", "restrict_account"]


def full_name(tool_name: str) -> str:
    return f"mcp__{SERVER}__{tool_name}"


def staff_signer(user: str) -> Signer:
    """Look up a (synthetic) staff member. In production this comes from your identity provider after login."""
    s = next(p for p in aml_staff() if p["user"] == user)
    return Signer(user=s["user"], name=s["name"], role=s["role"])


def oversight_policy():
    return load_oversight(OVERSIGHT_POLICY)
