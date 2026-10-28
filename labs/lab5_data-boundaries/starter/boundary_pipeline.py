"""Lab 5: wire the change-board assistant's boundaries together: cards, tools, two audit logs, guard, hooks."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from course_data import MODEL, change_procedure
from sentinel.audit import AgentInfo, AuditHooks, AuditStore, content_version
from sentinel.policy import merge_hooks

from boundary_kit.cards import CardSet
from boundary_kit.eng_tools import (EngineeringStore, agent_definitions, build_ccb_tools, build_eng_data_tools,
                                    card_set)
from boundary_kit.guard import BoundaryGuard
from boundary_kit.residency import check_all
from boundary_kit.routing import RoutingAuditHooks

SYSTEM_PROMPT = (
    "You are the Change Control Board assistant at Northgate Precision Components. You prepare CCB agendas and "
    "schedules from ECR metadata. You are NOT cleared for controlled technical data: for any FALCON ECR, delegate "
    "the technical assessment to the cleared-engineer-falcon subagent and use only the ENG-FORM-7 summary it "
    "returns. If a call is denied at the boundary, do not retry it another way.\n\nProcedure:\n" + change_procedure()
)
AGENT_NAME, AGENT_VERSION = "CCB-Assistant", "1.0.0"
ENCLAVE_AGENT = "cleared-engineer-falcon"


@dataclass
class Pipeline:
    cards: CardSet
    store: EngineeringStore
    general: AuditHooks          # the general platform's audit log
    enclave: AuditHooks          # the CUI enclave's audit log
    audit: RoutingAuditHooks     # routes each event to the log for the boundary it happened in
    guard: BoundaryGuard
    tools: list
    hooks: dict
    agents: dict
    residency: dict

    @property
    def general_log(self) -> Path:
        return self.general.store.path

    @property
    def enclave_log(self) -> Path:
        return self.enclave.store.path


def build_pipeline(workspace: Path, *, user: str = "l.marsh", **_: Any) -> Pipeline:
    # TODO 8: wire it together (the lab instructions list each object).
    # cards, cards_hash = card_set(); agent = AgentInfo(name=AGENT_NAME, version=AGENT_VERSION, model=MODEL,
    #     prompt_version=content_version(SYSTEM_PROMPT), policy_version=f"{cards.name}@{cards.version} ({cards_hash})")
    # key = AUDIT_HMAC_KEY from the environment (demo value "course-demo-key").encode()
    # general = AuditHooks(AuditStore(workspace / "audit.jsonl", hmac_key=key), agent=agent, on_behalf_of=user)
    # enclave = AuditHooks(AuditStore(workspace / "enclave" / "audit.jsonl", hmac_key=key), agent=agent, on_behalf_of=user)
    # audit = RoutingAuditHooks(general, {ENCLAVE_AGENT: enclave}, cards.contract_bound())
    # store = EngineeringStore(); guard = BoundaryGuard(cards, resolver=store.resolve, canaries=store.canaries(), audit=audit)
    # hooks = merge_hooks(audit.sdk_hooks(), guard.sdk_hooks())          # chained: log first, then enforce
    # tools = build_ccb_tools(store) + build_eng_data_tools(store)
    # return Pipeline(cards, store, general, enclave, audit, guard, tools, hooks, agent_definitions(cards), check_all(cards))
    raise NotImplementedError("Lab 5: build_pipeline")
