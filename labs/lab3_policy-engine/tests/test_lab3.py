"""Lab 3 acceptance tests. Run: uv run pytest labs/lab3_policy-engine   (LAB_IMPL=starter to check your work)

Acceptance criteria:
  1. The agent cannot close an MDR-reportable (or not-yet-assessed) complaint
  2. Every deny carries a rule ID, and the audit log records it with the policy version
  3. Injected instructions in complaint text cannot trigger privileged tools
"""
import asyncio
import re
from types import SimpleNamespace

import pytest

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny
from sentinel.audit import AuditStore

from triage_pipeline import build_pipeline
from policy_gate.complaint_tools import COMPLAINTS_POLICY, ComplaintStore, build_complaint_tools
from policy_gate.engine import PolicyEngine, build_context, load_policy
from policy_gate.models import Condition, Subject
from policy_gate.simulate import INJECTED_TRIAGE, QA_CLOSEOUT, run_script

RULE_ID = re.compile(r"^\[([A-Z]+-\d{3}|DEFAULT-DENY)\] ")
CLEAN = {"tainted": False, "injection_suspected": False}


def decide(role, tool, args, env=CLEAN, purpose="complaint_handling"):
    engine, store = PolicyEngine.from_file(COMPLAINTS_POLICY), ComplaintStore()
    subject = Subject(user="t.tester", role=role, purpose=purpose)
    return engine.evaluate(build_context(subject, tool, args, store.resolve(tool, args), env))


def run(tmp_path, role, script, **kw):
    p = build_pipeline(tmp_path, user="t.tester", role=role, **kw)
    log = asyncio.run(run_script(p.tools, script, enforcer=p.enforcer, audit=p.audit))
    return p, log


# ---- TODO 1: conditions ----------------------------------------------------------------------
def test_condition_operators_and_field_references():
    ctx = {"subject": {"role": "qa_specialist"}, "tool": "x", "environment": {"tainted": True},
           "input": {"to": "a@x.org", "note": "abcdef"}, "resource": {"complainant": {"email": "a@x.org"}}}
    assert Condition(field="subject.role", op="eq", value="qa_specialist").matches(ctx)
    assert Condition(field="subject.role", op="in", value=["qa_specialist", "x"]).matches(ctx)
    assert not Condition(field="subject.role", op="not_in", value=["qa_specialist"]).matches(ctx)
    assert Condition(field="input.to", op="eq", value="$resource.complainant.email").matches(ctx)
    assert not Condition(field="input.to", op="ne", value="$resource.complainant.email").matches(ctx)
    assert Condition(field="input.note", op="len_ge", value=6).matches(ctx)
    assert Condition(field="input.to", op="matches", value=r"@x\.org$").matches(ctx)
    assert Condition(field="resource.mdr_filed", op="missing").matches(ctx)
    assert not Condition(field="resource.mdr_filed", op="eq", value=False).matches(ctx)   # missing never matches


# ---- TODOs 2, 3, 7: engine, loader, rules ---------------------------------------------------------
def test_policy_loads_versioned_with_the_three_new_rules():
    policy, version = load_policy(COMPLAINTS_POLICY)
    ids = {r.id for r in policy.rules}
    assert {"MDR-001", "MDR-002", "INJ-001"} <= ids and policy.default_effect == "deny"
    assert re.fullmatch(r"sha256:[0-9a-f]{12}", version)
    assert PolicyEngine(policy, version).version == f"complaint-handling@{policy.version} ({version})"


def test_policy_change_changes_the_version(tmp_path):
    edited = tmp_path / "complaints.yaml"
    edited.write_text(COMPLAINTS_POLICY.read_text().replace("version: 1.0.0", "version: 1.0.1"))
    assert load_policy(edited)[1] != load_policy(COMPLAINTS_POLICY)[1]


def test_broken_policy_fails_to_load(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: x\nversion: 1.0.0\nrules:\n  - {id: ok-1, description: anything goes here, "
                   "effect: permit, tools: ['*']}\n")
    with pytest.raises(Exception):
        load_policy(bad)


def test_deny_overrides_allow_and_default_is_deny():
    d = decide("qa_specialist", "close_complaint", {"complaint_id": "CMP-3002"})
    assert (d.effect, d.rule_id) == ("deny", "MDR-002") and "QA-001" in d.matched
    assert decide("qa_specialist", "delete_complaint", {"complaint_id": "CMP-3001"}).rule_id == "DEFAULT-DENY"
    assert decide("qa_specialist", "get_complaint", {"complaint_id": "CMP-3001"},
                  purpose="marketing_analytics").rule_id == "PUR-001"


def test_roles_least_privilege():
    assert decide("regulatory_affairs", "set_mdr_assessment",
                  {"complaint_id": "CMP-3003", "decision": "reportable"}).effect == "allow"
    for role in ("complaint_intake", "qa_specialist"):
        assert decide(role, "set_mdr_assessment", {"complaint_id": "CMP-3003", "decision": "reportable"}).effect == "deny"
    assert decide("regulatory_affairs", "close_complaint", {"complaint_id": "CMP-3001"}).effect == "deny"


def test_email_only_to_the_complainant_on_file():
    ok = decide("complaint_intake", "send_customer_email", {"complaint_id": "CMP-3009", "to": "alan.fisk@example.net"})
    bad = decide("complaint_intake", "send_customer_email", {"complaint_id": "CMP-3009", "to": "someone@example.org"})
    assert ok.effect == "allow" and (bad.effect, bad.rule_id) == ("deny", "COM-001")


# ---- acceptance 1 and 2, through the wired pipeline (TODOs 4 and 8) --------------------------------
def test_cannot_close_reportable_or_pending_complaints(tmp_path):
    p, log = run(tmp_path, "qa_specialist", QA_CLOSEOUT)
    by_id = {s.args.get("complaint_id"): s for s in log.steps if s.tool == "close_complaint"}
    assert by_id["CMP-3001"].outcome == by_id["CMP-3008"].outcome == "executed"
    assert by_id["CMP-3002"].message.startswith("[MDR-002]") and by_id["CMP-3003"].message.startswith("[MDR-001]")
    assert p.complaints.records["CMP-3002"]["status"] != "closed" and p.complaints.records["CMP-3003"]["status"] == "open"


def test_every_denial_has_a_rule_id_and_is_logged_once(tmp_path):
    p, log = run(tmp_path, "complaint_intake", INJECTED_TRIAGE)
    assert log.denied and all(RULE_ID.match(s.message) for s in log.denied)
    denied = [r for r in AuditStore(p.store.path).records() if r["event_type"] == "tool.denied"]
    assert len(denied) == len(log.denied)                                  # not double-logged by observe()
    for r in denied:
        assert r["actor"] == {"kind": "system", "id": "policy-engine"}
        assert re.match(r"^([A-Z]+-\d{3}|DEFAULT-DENY) \(complaint-handling@", r["authority"])


# ---- acceptance 3: injection (TODO 6) ----------------------------------------------------------------
@pytest.mark.parametrize("role", ["complaint_intake", "qa_specialist", "regulatory_affairs"])
def test_injected_instructions_cannot_trigger_privileged_tools(tmp_path, role):
    p, log = run(tmp_path, role, INJECTED_TRIAGE)
    privileged = {"set_mdr_assessment", "close_complaint", "send_customer_email"}
    assert not privileged & set(log.executed)
    assert p.complaints.outbox == []
    assert {k: p.complaints.records["CMP-3006"][k] for k in ("mdr_assessment", "status")} == \
        {"mdr_assessment": "pending", "status": "open"}
    assert p.enforcer.environment["tainted"] and p.enforcer.environment["injection_suspected"]
    assert any("SECURITY NOTICE" in s.context for s in log.steps)


def test_tainted_not_reportable_needs_a_human(tmp_path):
    script = [("get_complaint", {"complaint_id": "CMP-3003"}),
              ("set_mdr_assessment", {"complaint_id": "CMP-3003", "decision": "not_reportable",
                                      "rationale": "Battery shortfall, no therapy interruption, no injury."})]
    _, log = run(tmp_path / "a", "regulatory_affairs", script)
    assert log.steps[-1].outcome == "denied" and log.steps[-1].message.startswith("[INJ-001]")
    _, log = run(tmp_path / "b", "regulatory_affairs", script, approver=lambda d, a: True)
    assert log.steps[-1].outcome == "executed"


def test_ask_never_grants_a_tool_no_rule_allows(tmp_path):
    script = [("get_complaint", {"complaint_id": "CMP-3003"}),
              ("set_mdr_assessment", {"complaint_id": "CMP-3003", "decision": "not_reportable",
                                      "rationale": "Battery shortfall, no therapy interruption, no injury."})]
    p, log = run(tmp_path, "complaint_intake", script, approver=lambda d, a: True)   # a human would say yes
    assert log.steps[-1].outcome == "denied" and log.steps[-1].message.startswith("[DEFAULT-DENY]")
    assert p.complaints.records["CMP-3003"]["mdr_assessment"] == "pending"


# ---- TODOs 5 and 6: the other adapters ------------------------------------------------------------
def test_can_use_tool_adapter(tmp_path):
    p = build_pipeline(tmp_path, role="complaint_intake")
    ctx = SimpleNamespace(tool_use_id="toolu_900")
    deny = asyncio.run(p.enforcer.can_use_tool("mcp__complaints__close_complaint",
                                         {"complaint_id": "CMP-3001", "rationale": "x" * 25}, ctx))
    allow = asyncio.run(p.enforcer.can_use_tool("mcp__complaints__get_complaint", {"complaint_id": "CMP-3001"},
                                                SimpleNamespace(tool_use_id="toolu_901")))
    assert isinstance(deny, PermissionResultDeny) and RULE_ID.match(deny.message)
    assert isinstance(allow, PermissionResultAllow)


def test_pre_and_post_conditions(tmp_path):
    p = build_pipeline(tmp_path, role="regulatory_affairs")
    d = p.enforcer.decide("mcp__complaints__set_mdr_assessment", {"complaint_id": "3003", "decision": "maybe"})
    assert (d.effect, d.rule_id) == ("deny", "PRE-001")
    leaky = ComplaintStore(leaky_search=True)
    p.enforcer.resolver = leaky.resolve
    log = asyncio.run(run_script(build_complaint_tools(leaky), [("search_similar", {"complaint_id": "CMP-3001"})],
                                 enforcer=p.enforcer))
    assert log.steps[0].outcome == "error" and log.steps[0].message.startswith("[POST-001]")
    assert "@" not in log.steps[0].message
