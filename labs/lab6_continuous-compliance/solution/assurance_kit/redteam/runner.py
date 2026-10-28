"""Replay each red-team case against the control that should stop it. A case PASSES when the attack is defended.

Probes (one per kind of control):
  policy_script   tool calls through the complaint policy enforcer         expect {denied: [tools]}
  approval_gate   tool calls through the approval gate, nothing approved   expect {denied: [tools]}
  approval_sign   a signature attempt checked by segregation of duties     expect {refused: SOD-xxx}
  boundary_call   one call checked by the boundary guard                   expect {rule: BND-xxx}
  handoff         a subagent reply put through its handoff contract         expect {rejected: true} or {stripped: [...]}
  log_masking     text put through the log-boundary redactor                expect {masked: true}
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict

from ..fleet import Fleet, load_fleet

CORPUS_PATH = Path(__file__).parent / "corpus.yaml"


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    category: Literal["injection", "exfiltration", "policy_evasion"]
    agent: str
    technique: str
    probe: Literal["policy_script", "approval_gate", "approval_sign", "boundary_call", "handoff", "log_masking"]
    input: dict[str, Any]
    expect: dict[str, Any]


@dataclass
class CaseResult:
    id: str
    category: str
    agent: str
    technique: str
    defended: bool
    observed: str


@dataclass
class RedTeamReport:
    corpus: str
    results: list[CaseResult] = field(default_factory=list)

    @property
    def defended(self) -> int:
        return sum(r.defended for r in self.results)

    @property
    def ok(self) -> bool:
        return self.defended == len(self.results)

    def by_category(self) -> dict[str, dict[str, int]]:
        total, held = Counter(r.category for r in self.results), Counter(r.category for r in self.results if r.defended)
        return {c: {"cases": total[c], "defended": held[c]} for c in sorted(total)}

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "sentinel.redteam-report/1", "corpus": self.corpus, "cases": len(self.results),
                "defended": self.defended, "by_category": self.by_category(),
                "results": [asdict(r) for r in self.results]}

    def table(self) -> str:
        return "\n".join(f"  {'DEFENDED' if r.defended else 'BREACHED':9} {r.id:11} {r.agent:17} {r.observed[:70]}"
                         for r in self.results)


def load_corpus(path: str | Path = CORPUS_PATH) -> tuple[list[Case], str]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [Case.model_validate(c) for c in doc["cases"]], f"{doc['name']}@{doc['version']}"


# ---------------------------------------------------------------------------------------------------- probes
def _policy_script(case: Case, fleet: Fleet) -> tuple[bool, str]:
    from sentinel.policy import Subject
    from sentinel.policy.complaint_tools import ComplaintStore, build_complaint_tools, complaint_enforcer
    from sentinel.policy.simulate import run_script
    agent = fleet.get(case.agent)
    store = ComplaintStore()
    enforcer = complaint_enforcer(store, Subject(user="redteam", role=case.input["role"], purpose="complaint_handling"),
                                  policy_path=agent.config_paths()[0]) if agent.controls.get("policy_enforced") else None
    log = asyncio.run(run_script(build_complaint_tools(store), [tuple(s) for s in case.input["script"]],
                                 enforcer=enforcer, mode=agent.permission_mode))
    denied = {s.tool for s in log.steps if s.outcome == "denied"}
    missing = [t for t in case.expect["denied"] if t not in denied]
    return not missing, (f"denied {sorted(denied)}" if not missing else f"NOT denied: {missing}; changes {store.changes}")


def _approval_gate(case: Case, fleet: Fleet) -> tuple[bool, str]:
    from sentinel.approvals import ApprovalGate, ApprovalQueue, FixedClock, load_oversight
    from sentinel.approvals.aml_tools import AlertStore, build_aml_tools
    from sentinel.approvals.simulate import run_script
    agent = fleet.get(case.agent)
    clock, alerts = FixedClock(), AlertStore()
    queue = ApprovalQueue(Path(tempfile.mkdtemp()) / "q.json", policy=load_oversight(agent.config_paths()[0])[0],
                          clock=clock, signing_key=b"redteam", agent_ids={"AML-Triage"})
    mode = agent.controls.get("approval_gate")
    gate = ApprovalGate(queue, user="redteam", role="aml_analyst", agent="AML-Triage@1.0.0", mode=mode,
                        evidence=alerts.evidence) if mode else None
    log = asyncio.run(run_script(build_aml_tools(alerts), [tuple(s) for s in case.input["script"]], gate=gate))
    denied = {s.tool for s in log.steps if s.outcome == "denied"}
    missing = [t for t in case.expect["denied"] if t not in denied]
    return not missing, (f"held for approval: {sorted(denied)}" if not missing else
                         f"EXECUTED without approval: {missing}; changes {alerts.changes}")


def _approval_sign(case: Case, fleet: Fleet) -> tuple[bool, str]:
    from sentinel.approvals import ApprovalQueue, FixedClock, Signer, check_segregation, load_oversight
    from sentinel.approvals.aml_tools import AlertStore, staff_signer
    from sentinel.approvals.simulate import TRIAGE
    agent = fleet.get(case.agent)
    queue = ApprovalQueue(Path(tempfile.mkdtemp()) / "q.json", policy=load_oversight(agent.config_paths()[0])[0],
                          clock=FixedClock(), signing_key=b"redteam", agent_ids={"AML-Triage"})
    args = next(a for t, a in TRIAGE if t == case.input["tool"])
    request = queue.submit(case.input["tool"], args, requested_by="j.rivera", requester_role="aml_analyst",
                           agent="AML-Triage@1.0.0", rationale="red-team", evidence=AlertStore().evidence(case.input["tool"], args))
    who = case.input["signer"]
    signer = Signer(user=who, name=who, role="agent") if who == "AML-Triage" else staff_signer(who)
    violations = check_segregation(request, signer, "approve", queue.agent_ids)
    want = case.expect["refused"]
    return any(v.startswith(want) for v in violations), ("refused: " + "; ".join(v[:7] for v in violations)
                                                         if violations else "SIGNATURE ACCEPTED")


def _guard():
    from sentinel.boundaries import BoundaryGuard
    from sentinel.boundaries.eng_tools import EngineeringStore, card_set
    cards, _ = card_set()
    store = EngineeringStore()
    return BoundaryGuard(cards, resolver=store.resolve, canaries=store.canaries()), store


def _boundary_call(case: Case, fleet: Fleet) -> tuple[bool, str]:
    guard, _ = _guard()
    reason = guard.check(case.input["caller"], case.input["tool"], case.input.get("tool_input", {}))
    want = case.expect["rule"]
    return bool(reason and reason.startswith(f"[{want}]")), (reason or "ALLOWED")[:120]


def _handoff(case: Case, fleet: Fleet) -> tuple[bool, str]:
    from sentinel.boundaries import CONTRACTS, enforce_contract
    _, store = _guard()
    if not fleet.get(case.agent).controls.get("handoff_contracts"):
        return False, "no handoff contract enforced: the raw reply reaches the orchestrator"
    r = enforce_contract(case.input["text"], CONTRACTS["ChangeImpactSummary"], store.canaries())
    leaked = [c for c in store.canaries() if c in r.text()]
    if case.expect.get("rejected"):
        return (not r.ok and not leaked), ("rejected: " + ", ".join(r.findings) if not r.ok else "ACCEPTED")[:120]
    want = case.expect.get("stripped", [])
    return (r.ok and set(want) <= set(r.stripped) and not leaked), f"ok={r.ok} stripped={r.stripped}"


def _log_masking(case: Case, fleet: Fleet) -> tuple[bool, str]:
    from sentinel.privacy import PrivacyRedactor, TokenVault, new_keys
    strategy = fleet.get(case.agent).controls.get("log_masking")
    if not strategy:
        return False, "no log masking configured: text is logged as-is"
    enc, mac = new_keys()
    vault = TokenVault(Path(tempfile.mkdtemp()) / "v.json", enc_key=enc.encode(), hmac_key=mac.encode())
    masked = str(PrivacyRedactor(strategy, vault)(case.input["text"]))
    left = [v for v in case.input["must_not_contain"] if v in masked]
    return not left, ("masked: " + masked[:80]) if not left else f"STILL VISIBLE: {left}"


PROBES = {"policy_script": _policy_script, "approval_gate": _approval_gate, "approval_sign": _approval_sign,
          "boundary_call": _boundary_call, "handoff": _handoff, "log_masking": _log_masking}


def run_case(case: Case, fleet: Fleet) -> CaseResult:
    try:
        defended, observed = PROBES[case.probe](case, fleet)
    except Exception as exc:                       # a probe that crashes proves nothing: count it as breached
        defended, observed = False, f"probe error: {type(exc).__name__}: {exc}"
    return CaseResult(case.id, case.category, case.agent, case.technique, defended, observed)


def run_redteam(fleet: Fleet | None = None, corpus: str | Path = CORPUS_PATH) -> RedTeamReport:
    fleet = fleet or load_fleet()
    cases, version = load_corpus(corpus)
    return RedTeamReport(version, [run_case(c, fleet) for c in cases])


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Replay the red-team corpus against the fleet's controls.")
    ap.add_argument("--out", default="redteam-report.json")
    args = ap.parse_args()
    report = run_redteam()
    Path(args.out).write_text(json.dumps(report.to_dict(), indent=1), encoding="utf-8")
    print(report.table())
    print(f"{report.defended}/{len(report.results)} defended  {report.by_category()}")
    raise SystemExit(0 if report.ok else 1)
