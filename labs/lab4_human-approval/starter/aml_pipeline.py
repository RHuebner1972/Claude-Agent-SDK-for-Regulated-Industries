"""Lab 4: wire the AML triage assistant's oversight together: audit trail, approval queue, gate, tools, hooks."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from course_data import MODEL, aml_procedure
from sentinel.audit import AgentInfo, AuditHooks, AuditStore, content_version
from sentinel.policy import merge_hooks

from approval_desk.aml_tools import AlertStore, build_aml_tools, oversight_policy
from approval_desk.gate import ApprovalGate
from approval_desk.killswitch import KillSwitch
from approval_desk.queue import ApprovalQueue

SYSTEM_PROMPT = (
    "You are the AML alert-triage ASSISTANT at Bayside Community Bank. Read alerts, investigate, add case notes and "
    "REQUEST dispositions: close_alert, recommend_sar, restrict_account. Those requests are decided by people; you "
    "never decide them. When a request is waiting for approval, say so and move on. Never contact customers and "
    "never reveal that a SAR may be filed.\n\nProcedure:\n" + aml_procedure()
)
AGENT_NAME, AGENT_VERSION = "AML-Triage", "1.0.0"


@dataclass
class Pipeline:
    alerts: AlertStore
    store: AuditStore
    audit: AuditHooks
    queue: ApprovalQueue
    gate: ApprovalGate
    kill: KillSwitch
    tools: list
    hooks: dict


def build_pipeline(workspace: Path, *, user: str = "j.rivera", role: str = "aml_analyst", mode: str = "deny",
                   clock: Callable | None = None, session_id: str | None = None, **_: Any) -> Pipeline:
    # TODO 8: wire it together (the lab instructions list each object).
    # policy, policy_hash = oversight_policy(); agent = AgentInfo(name=AGENT_NAME, version=AGENT_VERSION, model=MODEL,
    #     prompt_version=content_version(SYSTEM_PROMPT), policy_version=f"{policy.name}@{policy.version} ({policy_hash})")
    # store = AuditStore(workspace / "audit.jsonl", hmac_key=..., checkpoint_every=25)
    # audit = AuditHooks(store, agent=agent, on_behalf_of=user, clock=clock)
    # queue = ApprovalQueue(workspace / "approvals.json", policy=policy, clock=clock, audit=audit,
    #                       signing_key=..., agent_ids={AGENT_NAME})
    # alerts = AlertStore(); gate = ApprovalGate(queue, user=user, role=role, agent=f"{AGENT_NAME}@{AGENT_VERSION}",
    #                       mode=mode, evidence=alerts.evidence, session_id=session_id)
    # kill = KillSwitch(workspace / "KILL_SWITCH", audit=audit, clock=clock)    # provided; see killswitch.py
    # hooks = merge_hooks(audit.sdk_hooks(), kill.sdk_hooks(), gate.sdk_hooks())   # chained: log, stop?, approve?
    # return Pipeline(alerts, store, audit, queue, gate, kill, build_aml_tools(alerts), hooks)
    raise NotImplementedError("Lab 4: build_pipeline")
