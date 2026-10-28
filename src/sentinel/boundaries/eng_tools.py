"""Engineering-change tools for Northgate Precision Components (synthetic), split across two MCP servers.

  ccb       general platform: ECR metadata, scheduling, agendas
  eng_data  inside the CUI enclave: technical details and drawing notes (resource-marked; the guard checks them)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from claude_agent_sdk import AgentDefinition, ToolAnnotations, tool
from course_data import ecrs

from .cards import AgentCard, CardSet, load_cards
from .markings import canaries_from

CARDS_PATH = Path(__file__).parent / "policies" / "agent_cards.yaml"
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
EcrId = Field(pattern=r"^ECR-\d{4}$")
MARKED_TOOLS = {"get_ecr_technical", "get_drawing_notes"}
METADATA = ("ecr_id", "program", "part_number", "title", "change_class", "marking", "requested_by", "status")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EcrRef(_In):
    ecr_id: str = EcrId


class Schedule(_In):
    ecr_id: str = EcrId
    meeting_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    summary: str = Field(min_length=10, max_length=600)


class AgendaItem(_In):
    ecr_id: str = EcrId
    text: str = Field(min_length=10, max_length=600)


class EngineeringStore:
    def __init__(self):
        self.ecrs = {e["ecr_id"]: copy.deepcopy(e) for e in ecrs()}
        self.schedule: list[dict] = []
        self.agenda: list[dict] = []

    def resolve(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
        """Only the eng_data tools return marked content. Scheduling ECR-4101 by ID is metadata, not CUI."""
        if tool_name.rsplit("__", 1)[-1] not in MARKED_TOOLS:
            return None
        e = self.ecrs.get(tool_input.get("ecr_id", ""))
        return {k: e[k] for k in ("ecr_id", "program", "marking", "export_control")} if e else None

    def canaries(self) -> list[str]:
        return canaries_from(self.ecrs.values())


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=1)}]}


def _error(msg: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": msg}], "is_error": True}


def build_ccb_tools(store: EngineeringStore):
    @tool("list_ecrs", "List engineering change requests: metadata only.", {}, annotations=READ_ONLY)
    async def list_ecrs(args):
        return _text([{k: e[k] for k in METADATA} for e in store.ecrs.values()])

    @tool("schedule_ccb_review", "Schedule an ECR for a Change Control Board meeting.", Schedule.model_json_schema())
    async def schedule_ccb_review(args):
        a = Schedule.model_validate(args)
        store.schedule.append(a.model_dump())
        return _text({"scheduled": True, "ecr_id": a.ecr_id, "meeting_date": a.meeting_date})

    @tool("draft_agenda_item", "Add an item to the CCB agenda.", AgendaItem.model_json_schema())
    async def draft_agenda_item(args):
        a = AgendaItem.model_validate(args)
        store.agenda.append(a.model_dump())
        return _text({"added": True, "ecr_id": a.ecr_id})

    return [list_ecrs, schedule_ccb_review, draft_agenda_item]


def build_eng_data_tools(store: EngineeringStore):
    @tool("get_ecr_technical", "Technical details of an ECR (drawings, dimensions, materials). Marked data.",
          EcrRef.model_json_schema(), annotations=READ_ONLY)
    async def get_ecr_technical(args):
        e = store.ecrs.get(EcrRef.model_validate(args).ecr_id)
        if not e:
            return _error("No such ECR.")
        return _text({"ecr_id": e["ecr_id"], "marking": e["marking"], "export_control": e["export_control"],
                      **e["technical_details"], "affected_assemblies": e["affected_assemblies"],
                      "schedule_impact_days": e["schedule_impact_days"], "cost_impact_usd": e["cost_impact_usd"],
                      "supplier": e["supplier"]})

    @tool("get_drawing_notes", "Engineering notes for an ECR's drawing. Marked data.", EcrRef.model_json_schema(),
          annotations=READ_ONLY)
    async def get_drawing_notes(args):
        e = store.ecrs.get(EcrRef.model_validate(args).ecr_id)
        return _text({"ecr_id": e["ecr_id"], "marking": e["marking"], "notes": e["technical_details"]["notes"]}) \
            if e else _error("No such ECR.")

    return [get_ecr_technical, get_drawing_notes]


SERVER_OF = {"list_ecrs": "ccb", "schedule_ccb_review": "ccb", "draft_agenda_item": "ccb",
             "get_ecr_technical": "eng_data", "get_drawing_notes": "eng_data"}


def full_name(tool_name: str) -> str:
    return f"mcp__{SERVER_OF[tool_name]}__{tool_name}" if tool_name in SERVER_OF else tool_name


def card_set() -> tuple[CardSet, str]:
    return load_cards(CARDS_PATH)


def agent_definition(card: AgentCard) -> AgentDefinition:
    """Generate the SDK subagent definition FROM the card, so the two can't drift apart.

    Always pass an explicit tools list: a subagent defined with tools=None inherits every tool the parent has.
    """
    missing = sorted({SERVER_OF[t] for t in card.tools if t in SERVER_OF} - set(card.mcp_servers))
    if missing:
        raise ValueError(f"{card.name}: tools need MCP server(s) {missing} that the card does not list")
    return AgentDefinition(description=card.purpose, prompt=card.prompt,
                           tools=[full_name(t) for t in card.tools], mcpServers=list(card.mcp_servers),
                           model=card.model, maxTurns=card.max_turns)


def agent_definitions(cards: CardSet) -> dict[str, AgentDefinition]:
    return {c.name: agent_definition(c) for c in cards.agents if c.role == "subagent"}
