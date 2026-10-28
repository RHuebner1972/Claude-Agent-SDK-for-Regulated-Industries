"""Run every fleet agent offline, configured from the manifest, and collect what the compliance suite checks.

Each runner drives the same toolkit you built in Labs 1-5 (sentinel.audit, .privacy, .policy, .approvals,
.boundaries) with the offline drivers, so the suite needs no API key and gives the same answer every time.
The manifest's `controls` switch each control on or off: that's how a misconfiguration shows up as a failing test.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from sentinel.audit import AgentInfo, AuditHooks, AuditStore

from .fleet import Fleet, FleetAgent

KEY = (os.getenv("AUDIT_HMAC_KEY") or "course-demo-key").encode()    # CI: a repository secret


@dataclass
class FleetRun:
    agent: FleetAgent
    logs: dict[str, Path]                         # "general" and, for the CCB assistant, "enclave"
    seen: str = ""                                # what reached the model / orchestrator (for leak checks)
    canaries: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    @property
    def general_log(self) -> Path:
        return self.logs["general"]

    def events(self, which: str = "general") -> list[dict]:
        path = self.logs.get(which)
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path and path.exists() else []


def _info(agent: FleetAgent, name: str, version: str) -> AgentInfo:
    policy = ";".join(f"{k}={v}" for k, v in sorted(agent.config_versions().items())) or "n/a"
    return AgentInfo(name=name, version=version, model=agent.model, prompt_version=agent.prompt_version,
                     policy_version=policy)


def _store(agent: FleetAgent, work: Path, name: str = "audit.jsonl") -> AuditStore:
    """Signed checkpoints only if the manifest says so (rubric 1.3): turning it off is a detectable regression."""
    signed = agent.controls.get("audit_hmac", True)
    return AuditStore(work / name, hmac_key=KEY if signed else None, checkpoint_every=25 if signed else 0)


async def _ledgerbot(agent: FleetAgent, work: Path) -> FleetRun:
    from sentinel.audit.simulate import simulate_ledger_review
    store = _store(agent, work)
    hooks = AuditHooks(store, agent=_info(agent, "LedgerBot", "1.3.0"), on_behalf_of="j.chen")
    await simulate_ledger_review(hooks)
    return FleetRun(agent, {"general": store.path})


async def _pa_reviewer(agent: FleetAgent, work: Path) -> FleetRun:
    from course_data import patients
    from sentinel.privacy import PrivacyRedactor, TokenVault, canaries_from, new_keys
    from sentinel.privacy.pa_tools import build_pa_tools, simulate_pa_review
    enc, mac = new_keys()
    vault = TokenVault(work / "vault.json", enc_key=enc.encode(), hmac_key=mac.encode())
    masking = agent.controls.get("log_masking")
    extra = {"redactor": PrivacyRedactor(masking, vault)} if masking else {}
    store = _store(agent, work)
    hooks = AuditHooks(store, agent=_info(agent, "PA-Reviewer", "1.0.0"), on_behalf_of="n.alvarez",
                       decision_tool="record_pa_recommendation", **extra)
    minimized = bool(agent.controls.get("minimized_tools"))
    seen = await simulate_pa_review(hooks, build_pa_tools(minimized=minimized, vault=vault if minimized else None))
    return FleetRun(agent, {"general": store.path}, seen=json.dumps(seen), canaries=list(canaries_from(patients())))


async def _complaint_triage(agent: FleetAgent, work: Path) -> FleetRun:
    from sentinel.policy import Subject
    from sentinel.policy.complaint_tools import ComplaintStore, build_complaint_tools, complaint_enforcer
    from sentinel.policy.simulate import INJECTED_TRIAGE, run_script
    store, audit = ComplaintStore(), AuditHooks(_store(agent, work), agent=_info(agent, "ComplaintTriage", "1.0.0"),
                                                 on_behalf_of="a.novak")
    enforcer = None
    if agent.controls.get("policy_enforced"):
        enforcer = complaint_enforcer(store, Subject(user="a.novak", role="regulatory_affairs",
                                                     purpose="complaint_handling"),
                                      policy_path=agent.config_paths()[0], audit=audit)
    log = await run_script(build_complaint_tools(store), INJECTED_TRIAGE, enforcer=enforcer, audit=audit,
                           mode=agent.permission_mode)
    return FleetRun(agent, {"general": audit.store.path},
                    facts={"record_changes": list(store.changes), "emails_sent": len(store.outbox),
                           "denied": [s.tool for s in log.steps if s.outcome == "denied"]})


async def _aml_triage(agent: FleetAgent, work: Path) -> FleetRun:
    from sentinel.approvals import ApprovalGate, ApprovalQueue, FixedClock, load_oversight
    from sentinel.approvals.aml_tools import AlertStore, build_aml_tools, staff_signer
    from sentinel.approvals.simulate import TRIAGE, run_script
    clock = FixedClock()
    policy, _ = load_oversight(agent.config_paths()[0])
    audit = AuditHooks(_store(agent, work), agent=_info(agent, "AML-Triage", "1.0.0"), on_behalf_of="j.rivera", clock=clock)
    queue = ApprovalQueue(work / "approvals.json", policy=policy, clock=clock, audit=audit,
                          signing_key=b"course-demo-signing-key", agent_ids={"AML-Triage"})
    alerts = AlertStore()
    tools = build_aml_tools(alerts)
    mode = agent.controls.get("approval_gate")
    gate = ApprovalGate(queue, user="j.rivera", role="aml_analyst", agent="AML-Triage@1.0.0", mode=mode,
                        evidence=alerts.evidence) if mode else None
    await run_script(tools, TRIAGE, gate=gate, audit=audit)
    signings = [(25, "APR-000001", "m.chen", "Payroll processor and amounts match 2025 history."),
                (40, "APR-000002", "m.chen", "Six sub-$10k cash deposits in 8 days at 3 branches."),
                (95, "APR-000002", "d.okafor", "Agree; no business reason; refer for SAR filing.")]
    for minutes, rid, user, why in signings:
        if rid in queue.requests:
            clock.advance(minutes)
            queue.sign(rid, staff_signer(user), "approve", why)
    if gate:
        await run_script(tools, TRIAGE, gate=gate, audit=audit, session_id="sess-aml-6b21")
    return FleetRun(agent, {"general": audit.store.path},
                    facts={"record_changes": list(alerts.changes),
                           "requests": {r.request_id: {"tool": r.tool, "alert_id": r.tool_input.get("alert_id"),
                                                       "status": r.status,
                                                       "signatures": [{"user": s.user, "meaning": s.meaning,
                                                                       "signed_at": s.signed_at.isoformat(),
                                                                       "verified": ok}
                                                                      for s, (_, ok) in zip(r.signatures,
                                                                                            queue.verify(r.request_id))]}
                                        for r in queue.requests.values()}})


async def _ccb_assistant(agent: FleetAgent, work: Path) -> FleetRun:
    from sentinel.boundaries.simulate import run_scenario
    gated = agent.controls.get("handoff_contracts") and agent.controls.get("routed_logs")
    signed = agent.controls.get("audit_hmac", True)
    outcome = await asyncio.to_thread(run_scenario, "gated" if gated else "subagents", work, None,
                                      KEY if signed else None, _info(agent, "CCB-Assistant", "1.0.0"))
    return FleetRun(agent, {"general": outcome.general_log, "enclave": outcome.enclave_log},
                    seen="\n".join(outcome.log.seen), canaries=outcome.store.canaries(),
                    facts={"handoffs": outcome.guard.handoffs if outcome.guard else []})


RUNNERS: dict[str, Callable] = {"ledgerbot": _ledgerbot, "pa-reviewer": _pa_reviewer,
                                "complaint-triage": _complaint_triage, "aml-triage": _aml_triage,
                                "ccb-assistant": _ccb_assistant}


def run_agent(agent: FleetAgent, workdir: str | Path) -> FleetRun:
    work = Path(workdir) / agent.name
    work.mkdir(parents=True, exist_ok=True)
    for old in work.rglob("*.json*"):
        old.unlink()
    return asyncio.run(RUNNERS[agent.name](agent, work))


def run_fleet(fleet: Fleet, workdir: str | Path) -> dict[str, FleetRun]:
    return {a.name: run_agent(a, workdir) for a in fleet.agents}
