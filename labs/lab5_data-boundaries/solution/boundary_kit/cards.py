"""Agent cards: each agent's documented data scope, tools, programs and deployment (rubric 6.1).

A card is the boundary's source of truth. The guard enforces it, the SDK AgentDefinition is generated from it,
and an auditor can read it without reading code.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from sentinel.audit import content_version

from .contracts import CONTRACTS

Marking = Literal["NONE", "CUI", "CUI//SP-CTI"]


class Deployment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    provider: Literal["anthropic_api", "aws_bedrock", "google_vertex", "microsoft_foundry", "self_hosted"]
    region: str
    storage_region: str
    environment: str
    fedramp: Literal["none", "moderate", "moderate_equivalent", "high"] = "none"
    us_persons_only: bool = False


class AgentCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]+$")
    role: Literal["orchestrator", "subagent"]
    purpose: str = Field(min_length=20)
    data_scope: list[Marking]                       # markings this agent may read
    export_authorizations: list[Literal["ITAR", "EAR"]] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)   # empty = no program restriction
    tools: list[str]                                # short tool names this agent may call
    mcp_servers: list[str] = Field(default_factory=list)
    may_delegate_to: list[str] = Field(default_factory=list)
    handoff_contract: str | None = None             # the ONLY shape its results may take upward
    model: str = "inherit"
    max_turns: int = 10
    prompt: str = ""
    deployment: Deployment


class CardSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    orchestrator: str
    agents: list[AgentCard]

    @field_validator("agents")
    @classmethod
    def _unique(cls, agents: list[AgentCard]) -> list[AgentCard]:
        names = [a.name for a in agents]
        if len(names) != len(set(names)):
            raise ValueError("agent names must be unique")
        return agents

    @model_validator(mode="after")
    def _consistent(self) -> "CardSet":
        """A card set that doesn't add up never loads: unknown delegates, unknown contracts, no orchestrator."""
        by_name = {a.name: a for a in self.agents}
        problems = [] if by_name.get(self.orchestrator, None) and by_name[self.orchestrator].role == "orchestrator" \
            else [f"orchestrator {self.orchestrator!r} has no orchestrator card"]
        for a in self.agents:
            problems += [f"{a.name} delegates to {t!r}, which is not a subagent card" for t in a.may_delegate_to
                         if t not in by_name or by_name[t].role != "subagent"]
            if a.handoff_contract and a.handoff_contract not in CONTRACTS:
                problems.append(f"{a.name}: unknown handoff contract {a.handoff_contract!r}")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def get(self, name: str) -> AgentCard | None:
        return next((a for a in self.agents if a.name == name), None)

    def contract_bound(self) -> set[str]:
        return {a.name for a in self.agents if a.handoff_contract}


def load_cards(path: str | Path) -> tuple[CardSet, str]:
    text = Path(path).read_text(encoding="utf-8")
    return CardSet.model_validate(yaml.safe_load(text)), content_version(text)
