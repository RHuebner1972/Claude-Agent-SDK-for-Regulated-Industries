"""Lab 5 acceptance tests. Run: uv run pytest labs/lab5_data-boundaries   (LAB_IMPL=starter to check your work)

Acceptance criteria:
  1. CUI never appears in the orchestrator's context or the general logs
  2. Boundary tests pass (every BND rule fires where it should, and only there)
  3. Each subagent has a documented data scope (its card), and its SDK definition is generated from that card
"""
import asyncio
import json

import pytest

from course_data import ecrs
from sentinel.audit import AgentInfo, AuditHooks, AuditStore, verify_log

from boundary_kit.cards import CardSet, Deployment
from boundary_kit.contracts import ChangeImpactSummary, enforce_contract
from boundary_kit.eng_tools import EngineeringStore, build_ccb_tools, build_eng_data_tools, card_set, full_name
from boundary_kit.guard import BoundaryGuard
from boundary_kit.markings import canaries_from, scan
from boundary_kit.residency import check_deployment
from boundary_kit.routing import RoutingAuditHooks
from boundary_kit.simulate import (CHATTY_SUMMARY, FREE_TEXT, GATED, GOOD_SUMMARY, ISOLATION, LEAKY_SUMMARY,
                                   run_scenario, run_script)
from boundary_pipeline import build_pipeline

CANARIES = canaries_from(ecrs())
CLEARED, ORCH = "cleared-engineer-falcon", "ccb-orchestrator"
KEY = b"course-demo-key"


def guard(**kw):
    cards, _ = card_set()
    store = EngineeringStore()
    return BoundaryGuard(cards, resolver=store.resolve, canaries=store.canaries(), **kw)


def pre(tool, args, agent_type=None):
    d = {"session_id": "s", "hook_event_name": "PreToolUse", "tool_name": full_name(tool), "tool_input": args,
         "tool_use_id": "toolu_1"}
    if agent_type:
        d.update(agent_type=agent_type, agent_id="a1")
    return d


def handoff(text, subagent=CLEARED):
    return {"session_id": "s", "hook_event_name": "PostToolUse", "tool_name": "Agent", "tool_use_id": "toolu_9",
            "tool_input": {"subagent_type": subagent, "description": "Assess", "prompt": "Assess ECR-4101"},
            "tool_response": {"status": "completed", "agentId": "a1", "content": [{"type": "text", "text": text}]}}


class FakeAudit:
    def __init__(self):
        self.denials, self.records = [], []

    def record_denial(self, *args, **kw):
        self.denials.append((args, kw))

    def record(self, *args, **kw):
        self.records.append((args, kw))


def gated_run(tmp_path, script=GATED):
    p = build_pipeline(tmp_path)
    log = asyncio.run(run_script(p.tools, script, audit=p.audit, guard=p.guard))
    return p, log


# ---- Part 1, TODOs 1-4: residency, the boundary guard's PreToolUse side, routed logs ---------------------------------------
def test_residency_findings():
    cards, _ = card_set()
    assert all(check_deployment(c) == [] for c in cards.agents)
    cleared = cards.get(CLEARED)
    commercial = cleared.model_copy(update={"deployment": Deployment(provider="anthropic_api", region="us",
                                                                     storage_region="us", environment="general")})
    codes = {f[:7] for f in check_deployment(commercial)}
    assert codes == {"RES-001", "RES-003"}
    abroad = cleared.model_copy(update={"deployment": cleared.deployment.model_copy(update={"storage_region": "eu-central-1"})})
    assert {f[:7] for f in check_deployment(abroad)} == {"RES-002", "RES-004"}


def test_orchestrator_scope():
    g = guard()
    assert g.check(ORCH, "get_ecr_technical", {"ecr_id": "ECR-4101"}).startswith("[BND-001]")
    assert g.check(ORCH, "get_ecr_technical", {"ecr_id": "ECR-4104"}) is None          # commercial ECR
    assert g.check(ORCH, "schedule_ccb_review", {"ecr_id": "ECR-4101"}) is None        # scheduling is metadata
    assert g.check(ORCH, "get_drawing_notes", {"ecr_id": "ECR-4104"}).startswith("[BND-005]")


def test_cleared_subagent_scope_and_tenancy():
    g = guard()
    assert g.check(CLEARED, "get_ecr_technical", {"ecr_id": "ECR-4102"}) is None
    assert g.check(CLEARED, "get_ecr_technical", {"ecr_id": "ECR-4105"}).startswith("[BND-004]")
    assert g.check(CLEARED, "draft_agenda_item", {"ecr_id": "ECR-4101", "text": "x" * 20}).startswith("[BND-005]")
    assert g.check("helpful-intern", "list_ecrs", {}).startswith("[BND-000]")


def test_delegation_only_to_listed_subagents():
    g = guard()
    assert g.check(ORCH, "Agent", {"subagent_type": CLEARED}) is None
    assert g.check(ORCH, "Agent", {"subagent_type": "general-purpose"}).startswith("[BND-003]")
    assert g.check(ORCH, "Task", {"subagent_type": "general-purpose"}).startswith("[BND-003]")   # the old name too
    assert g.check(CLEARED, "Agent", {"subagent_type": CLEARED}).startswith("[BND-003]")      # no re-delegation


def test_pre_tool_use_denies_and_records_in_callers_log():
    audit = FakeAudit()
    g = guard(audit=audit)
    out = asyncio.run(g.pre_tool_use(pre("get_ecr_technical", {"ecr_id": "ECR-4105"}, CLEARED), "toolu_1", None))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "BND-004" in out["hookSpecificOutput"]["permissionDecisionReason"]
    (args, kw), = audit.denials
    assert kw["actor_id"] == "boundary-guard" and kw["agent_type"] == CLEARED
    assert asyncio.run(g.pre_tool_use(pre("get_ecr_technical", {"ecr_id": "ECR-4101"}, CLEARED), "t", None)) == {}


def test_routing_keeps_cui_in_the_enclave_log(tmp_path):
    cards, _ = card_set()
    info = AgentInfo(name="CCB-Assistant", version="1.0.0", model="m", prompt_version="p", policy_version="v")
    general = AuditHooks(AuditStore(tmp_path / "audit.jsonl"), agent=info, on_behalf_of="l.marsh")
    enclave = AuditHooks(AuditStore(tmp_path / "enclave.jsonl"), agent=info, on_behalf_of="l.marsh")
    routed = RoutingAuditHooks(general, {CLEARED: enclave}, cards.contract_bound())
    store = EngineeringStore()
    asyncio.run(run_script(build_ccb_tools(store) + build_eng_data_tools(store), ISOLATION, audit=routed))
    general_text, enclave_text = (tmp_path / "audit.jsonl").read_text(), (tmp_path / "enclave.jsonl").read_text()
    assert "get_ecr_technical" in enclave_text and "get_ecr_technical" not in general_text
    assert "held in cleared-engineer-falcon's enclave log; sha256=" in general_text
    assert any(c in enclave_text for c in CANARIES)
    handoff_events = [line for line in general_text.splitlines() if '"Agent"' in line]
    assert handoff_events and not any(c in line for line in handoff_events for c in CANARIES)
    # (without the guard's contract, the orchestrator's own final message can still leak: TODO 7 closes that)


# ---- Part 2, TODOs 5-7: markings, the handoff contract, PostToolUse --------------------------------------------------------
def test_scan_reports_kinds_never_values():
    text = "Drawing D-77812-3 rev F: bore 1.2500 in ±0.0004 in, Ti-6Al-4V per AMS 4928. CUI//SP-CTI CANARY-CUI-7Q4K"
    found = scan(text, CANARIES)
    assert {"drawing number", "tolerance value", "precise dimension", "material specification",
            "CUI banner marking"} <= set(found)
    assert any(f.startswith("known controlled value") for f in found)
    assert not any("7Q4K" in f or "77812" in f for f in found)          # findings are safe to log
    assert scan("Class II change, approve, 12 days, 10k-100k.", CANARIES) == []


def test_contract_strips_extra_fields():
    for raw, extras in [(GOOD_SUMMARY, ["drawing", "tolerance_change"]), (CHATTY_SUMMARY, ["technical_notes"])]:
        r = enforce_contract(raw, ChangeImpactSummary, CANARIES)
        assert r.ok and r.stripped == extras
        assert set(r.payload) == set(ChangeImpactSummary.model_fields)
        assert not any(c in r.text() for c in CANARIES) and "D-77812" not in r.text()


def test_contract_fails_closed():
    leaky = enforce_contract(LEAKY_SUMMARY, ChangeImpactSummary, CANARIES)
    assert not leaky.ok and leaky.findings and "BND-002" in leaky.text()
    assert "2M8P" not in leaky.text() and "0.139" not in leaky.text()   # the rejection doesn't repeat the leak
    assert not enforce_contract(FREE_TEXT, ChangeImpactSummary, CANARIES).ok
    bad_band = json.loads(GOOD_SUMMARY) | {"cost_impact_band": "about 60 thousand"}
    assert not enforce_contract(json.dumps(bad_band), ChangeImpactSummary, CANARIES).ok


def test_post_tool_use_replaces_what_the_orchestrator_sees():
    audit = FakeAudit()
    g = guard(audit=audit)
    out = asyncio.run(g.post_tool_use(handoff(CHATTY_SUMMARY), "toolu_9", None))["hookSpecificOutput"]
    seen = out["updatedToolOutput"]["content"][0]["text"]
    assert json.loads(seen)["recommendation"] == "approve" and "technical_notes" not in seen
    assert out["updatedToolOutput"]["agentId"] == "a1"                   # same shape as the Agent tool's output
    rejected = asyncio.run(g.post_tool_use(handoff(LEAKY_SUMMARY), "toolu_9", None))["hookSpecificOutput"]
    assert rejected["updatedToolOutput"]["content"][0]["text"].startswith("[BND-002]")
    assert not any(c in str(audit.records) for c in CANARIES)            # the audit note names fields, not values
    assert asyncio.run(g.post_tool_use(pre("list_ecrs", {}) | {"tool_response": {}}, "t", None)) == {}


def test_ac1_the_baseline_does_leak(tmp_path):
    base = run_scenario("naive", tmp_path)                                 # proves the canary test can fail
    assert base.leaks()["orchestrator context"] and base.leaks()["general audit log"]
    assert "precise dimension" in scan("\n".join(base.log.seen))


# ---- TODO 8 + acceptance criteria ------------------------------------------------------------------------------------------
def test_ac1_no_cui_in_orchestrator_context_or_general_log(tmp_path):
    p, log1 = gated_run(tmp_path, ISOLATION)
    log2 = asyncio.run(run_script(p.tools, GATED, audit=p.audit, guard=p.guard, session_id="sess-2"))
    seen, general = "\n".join(log1.seen + log2.seen), p.general_log.read_text()
    assert not [c for c in CANARIES if c in seen or c in general]
    falcon_drawings = [e["technical_details"]["drawing"].split()[0] for e in ecrs() if e["program"] == "FALCON"]
    assert not [d for d in falcon_drawings if d in seen or d in general]      # commercial drawings are fine
    assert p.store.agenda and p.store.schedule                            # and the job still got done


def test_ac2_every_boundary_rule_fires(tmp_path):
    p, log = gated_run(tmp_path)
    denied = {s.message[:9] for s in log.steps if s.outcome == "denied"}
    assert denied == {"[BND-001]", "[BND-003]", "[BND-004]"}
    assert [h["ok"] for h in p.guard.handoffs] == [True, False]           # stripped, then rejected (BND-002)
    executed = {(s.who.strip(), s.tool, s.args.get("ecr_id")) for s in log.steps if s.outcome == "executed"}
    assert (ORCH, "get_ecr_technical", "ECR-4104") in executed and (CLEARED, "get_ecr_technical", "ECR-4101") in executed
    for path in (p.general_log, p.enclave_log):
        assert verify_log(path, KEY).ok


def test_ac2_denials_land_in_the_callers_log(tmp_path):
    p, _ = gated_run(tmp_path)
    general, enclave = p.general_log.read_text(), p.enclave_log.read_text()
    assert "BND-001" in general and "BND-003" in general and "BND-004" not in general
    assert "BND-004" in enclave
    assert all(json.loads(line)["actor"]["id"] == "boundary-guard"
               for line in (general + enclave).splitlines() if json.loads(line)["event_type"] == "tool.denied")


def test_ac3_every_agent_has_a_documented_scope_and_a_generated_definition(tmp_path):
    p = build_pipeline(tmp_path)
    assert p.residency == {c.name: [] for c in p.cards.agents}
    for card in p.cards.agents:
        assert card.purpose and card.data_scope and card.deployment.environment
    for name, d in p.agents.items():
        card = p.cards.get(name)
        assert d.tools is not None and d.tools == [full_name(t) for t in card.tools]   # never inherit-everything
        assert card.handoff_contract, f"{name} returns free text to the orchestrator"
    assert set(p.agents) == set(p.cards.get(ORCH).may_delegate_to)
    rogue = p.cards.model_dump()
    rogue["agents"][0]["may_delegate_to"] = ["general-purpose"]            # a card set that doesn't add up
    with pytest.raises(ValueError, match="not a subagent card"):
        CardSet.model_validate(rogue)
