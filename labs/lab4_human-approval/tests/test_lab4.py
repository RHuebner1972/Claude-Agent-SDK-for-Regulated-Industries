"""Lab 4 acceptance tests. Run: uv run pytest labs/lab4_human-approval   (LAB_IMPL=starter to check your work)

Acceptance criteria:
  1. No account action or SAR recommendation executes without approval by someone other than the requester
  2. Timeouts escalate and never auto-approve
  3. Approval records include signer, meaning and time
"""
import asyncio
import json
from types import SimpleNamespace

import pytest

from claude_agent_sdk import PermissionResultDeny
from sentinel.audit import AuditStore, verify_log

from aml_pipeline import build_pipeline
from approval_desk.aml_tools import staff_signer
from approval_desk.models import Signer
from approval_desk.queue import ApprovalError, ApprovalQueue
from approval_desk.records import input_digest
from approval_desk.simulate import TRIAGE, FixedClock, run_script
from approval_desk.sod import SegregationOfDutiesError, check_segregation

REASON = "Reviewed the alert evidence and the customer's history."
PRIVILEGED = {"close_alert", "recommend_sar", "restrict_account"}


def pipeline(tmp_path, mode="deny", clock=None):
    return build_pipeline(tmp_path, clock=clock or FixedClock(), mode=mode)


def triage(p, **kw):
    return asyncio.run(run_script(p.tools, TRIAGE, gate=[p.kill, p.gate], audit=p.audit, **kw))


def ids(p):
    return {r.tool: r.request_id for r in p.queue.requests.values()}


def queued(p):
    """Put TRIAGE's three held actions in the queue directly (no gate needed): for the TODO 1-5 tests."""
    for name, args in TRIAGE:
        rule = p.queue.policy.rule_for(name)
        if rule and rule.oversight == "in_the_loop":
            p.queue.submit(name, args, requested_by="j.rivera", requester_role="aml_analyst", agent="AML-Triage@1.0.0",
                           rationale=str(args.get("rationale") or args.get("narrative") or args.get("reason")),
                           evidence=p.alerts.evidence(name, args))
    return ids(p)


# ---- TODOs 1-5 (+8): segregation of duties and signing, no agent needed ------------------------------------------------------------------
def test_requester_and_agent_cannot_approve(tmp_path):
    p = pipeline(tmp_path); queued(p)
    r = p.queue.get(ids(p)["close_alert"])
    assert any(v.startswith("SOD-001") for v in check_segregation(r, staff_signer("j.rivera")))
    agent = Signer(user="AML-Triage", name="AML Triage Assistant", role="aml_senior_analyst")
    assert any(v.startswith("SOD-002") for v in check_segregation(r, agent, agent_ids={"AML-Triage"}))
    with pytest.raises(SegregationOfDutiesError):
        p.queue.sign(r.request_id, staff_signer("j.rivera"), "approve", REASON)
    assert p.queue.get(r.request_id).status == "pending"


def test_sar_needs_two_people_one_of_them_the_bsa_officer(tmp_path):
    p = pipeline(tmp_path); queued(p)
    sar = ids(p)["recommend_sar"]
    p.queue.sign(sar, staff_signer("m.chen"), "approve", REASON)
    assert p.queue.get(sar).status == "pending"
    for user in ("m.chen", "a.brooks"):
        signer = staff_signer(user) if user == "m.chen" else Signer(user=user, name="Alex Brooks", role="aml_senior_analyst")
        with pytest.raises(SegregationOfDutiesError) as exc:
            p.queue.sign(sar, signer, "approve", REASON)
        assert any(v.startswith("SOD-005") for v in exc.value.violations)
    p.queue.sign(sar, staff_signer("d.okafor"), "approve", REASON)
    assert p.queue.get(sar).status == "approved"


def test_conflict_of_interest_and_wrong_role_are_refused(tmp_path):
    p = pipeline(tmp_path); queued(p)
    with pytest.raises(SegregationOfDutiesError) as exc:
        p.queue.sign(ids(p)["recommend_sar"], staff_signer("t.nguyen"), "approve", REASON)   # RM of CUS-2101
    assert exc.value.violations[0].startswith("SOD-006")
    with pytest.raises(SegregationOfDutiesError) as exc:
        p.queue.sign(ids(p)["restrict_account"], staff_signer("m.chen"), "approve", REASON)  # BSA Officer only
    assert exc.value.violations[0].startswith("SOD-004")


# ---- acceptance 1: nothing privileged runs without approval (TODOs 6, 7) -----------------------------
def test_nothing_privileged_runs_without_approval(tmp_path):
    p = pipeline(tmp_path)
    log = triage(p)
    assert not PRIVILEGED & {s.tool for s in log.steps if s.outcome == "executed"}
    assert p.alerts.changes == ["ALR-5007: note added"]
    assert all(r.status == "pending" for r in p.queue.requests.values()) and len(p.queue.requests) == 3
    denied = [s for s in log.steps if s.outcome == "denied"]
    assert all(s.message.startswith("[APPROVAL-PENDING] APR-") for s in denied)


def test_defer_pauses_then_resume_runs_the_approved_call_exactly_once(tmp_path):
    clock = FixedClock()
    p = pipeline(tmp_path, mode="defer", clock=clock)
    log = triage(p)
    assert log.paused_at == 2 and log.deferred.name == "mcp__aml__close_alert" and p.alerts.changes == []
    p.queue.sign("APR-000001", staff_signer("m.chen"), "approve", REASON)
    p2 = pipeline(tmp_path, mode="defer", clock=clock)            # new process, same queue file
    log2 = asyncio.run(run_script(p2.tools, TRIAGE, gate=p2.gate, audit=p2.audit, start=log.paused_at))
    assert log2.steps[0].tool == "close_alert" and log2.steps[0].outcome == "executed"
    assert p2.queue.get("APR-000001").status == "consumed"
    again = asyncio.run(run_script(p2.tools, TRIAGE[2:3], gate=p2.gate))   # same call again: needs a NEW approval
    assert again.steps[0].outcome == "deferred" and "APR-000001" not in again.steps[0].message


def test_approval_is_bound_to_the_exact_input(tmp_path):
    p = pipeline(tmp_path); triage(p)
    p.queue.sign(ids(p)["close_alert"], staff_signer("m.chen"), "approve", REASON)
    changed = dict(TRIAGE[2][1], disposition="not_suspicious")
    assert p.queue.approved_for("close_alert", changed, "j.rivera") is None
    assert p.queue.approved_for("close_alert", TRIAGE[2][1], "j.rivera") is not None
    assert input_digest("close_alert", changed) != input_digest("close_alert", TRIAGE[2][1])


def test_rejection_blocks_the_action(tmp_path):
    p = pipeline(tmp_path); triage(p)
    p.queue.sign(ids(p)["close_alert"], staff_signer("m.chen"), "reject", "Payroll amounts jumped 40% this cycle; investigate.")
    log = triage(p, session_id="sess-aml-6b21")
    step = next(s for s in log.steps if s.tool == "close_alert")
    assert step.outcome == "denied" and step.message.startswith("[APPROVAL-REJECTED]")


# ---- acceptance 2: timeouts escalate, never approve (TODO 4) -----------------------------------------
def test_timeout_escalates_then_expires_and_never_approves(tmp_path):
    clock = FixedClock()
    p = pipeline(tmp_path, clock=clock); triage(p)
    rid = ids(p)["restrict_account"]
    clock.advance(61)
    assert (rid, "escalated") in p.queue.sweep()
    r = p.queue.get(rid)
    assert "chief_compliance_officer" in r.allowed_roles() and not r.signatures
    clock.advance(61)
    assert (rid, "expired") in p.queue.sweep()
    with pytest.raises(ApprovalError):
        p.queue.sign(rid, staff_signer("d.okafor"), "approve", REASON)
    log = triage(p, session_id="sess-aml-6b21")
    step = next(s for s in log.steps if s.tool == "restrict_account")
    assert step.outcome == "denied" and step.message.startswith("[APPROVAL-EXPIRED]")
    assert not p.alerts.restrictions
    assert all(r.status != "approved" for r in p.queue.requests.values() if not r.signatures)


def test_can_use_tool_timeout_is_a_deny(tmp_path):
    p = pipeline(tmp_path)
    result = asyncio.run(p.gate.can_use_tool("mcp__aml__close_alert", TRIAGE[2][1], SimpleNamespace(tool_use_id="t9"),
                                             max_wait_s=0.2, poll_s=0.05))
    assert isinstance(result, PermissionResultDeny) and "APPROVAL-TIMEOUT" in result.message


# ---- acceptance 3: signed records (TODOs 2, 3, 5) ------------------------------------------------------
def test_records_carry_signer_meaning_and_time_and_verify(tmp_path):
    p = pipeline(tmp_path); queued(p)
    rid = ids(p)["recommend_sar"]
    p.queue.sign(rid, staff_signer("m.chen"), "approve", REASON)
    p.queue.sign(rid, staff_signer("d.okafor"), "approve", REASON)
    r = p.queue.get(rid)
    for s in r.signatures:
        assert s.name and s.role and s.meaning == "approve" and s.signed_at.tzinfo is not None
        assert s.meaning_text.startswith("I reviewed the investigation") and s.record_sha256.startswith("sha256:")
    assert p.queue.verify(rid) == [("m.chen", True), ("d.okafor", True)]


def test_editing_a_signed_record_breaks_the_signature(tmp_path):
    p = pipeline(tmp_path); queued(p)
    rid = ids(p)["recommend_sar"]
    p.queue.sign(rid, staff_signer("m.chen"), "approve", REASON)
    path = tmp_path / "approvals.json"
    data = json.loads(path.read_text())
    data["requests"][rid]["tool_input"]["suspicious_amount"] = 5780            # someone "fixes" a typo later
    path.write_text(json.dumps(data))
    reloaded = ApprovalQueue(path, policy=p.queue.policy, signing_key=p.queue.signing_key)
    assert reloaded.verify(rid) == [("m.chen", False)]


def test_queue_persists_across_processes(tmp_path):
    p = pipeline(tmp_path); queued(p)
    p.queue.sign(ids(p)["close_alert"], staff_signer("m.chen"), "approve", REASON)
    again = pipeline(tmp_path)
    assert {r.request_id: r.status for r in again.queue.requests.values()} == \
        {"APR-000001": "approved", "APR-000002": "pending", "APR-000003": "pending"}


def test_audit_log_records_every_request_decision_and_escalation(tmp_path):
    clock = FixedClock()
    p = pipeline(tmp_path, clock=clock); triage(p)                  # needs TODO 7: the gate holds 3 calls
    p.queue.sign(ids(p)["close_alert"], staff_signer("m.chen"), "approve", REASON)
    with pytest.raises(SegregationOfDutiesError):
        p.queue.sign(ids(p)["recommend_sar"], staff_signer("j.rivera"), "approve", REASON)
    clock.advance(61); p.queue.sweep()
    records = AuditStore(p.store.path).records()
    kinds = [r["event_type"] for r in records]
    assert kinds.count("approval.requested") == 3 and kinds.count("approval.escalated") == 1
    decided = [r for r in records if r["event_type"] == "approval.decided"]
    assert len(decided) == 1 and decided[0]["actor"] == {"kind": "human", "id": "m.chen"}
    assert "APR-000001 approved by Morgan Chen" in decided[0]["authority"]
    held = [r for r in records if r["event_type"] == "tool.denied" and r["actor"]["id"] == "approval-gate"]
    assert len(held) == 3 and all("pending" in r["authority"] for r in held)
    assert verify_log(p.store.path, b"course-demo-key").ok


def test_on_the_loop_actions_are_logged_for_review(tmp_path):
    p = pipeline(tmp_path); triage(p)
    assert [r["tool"] for r in p.queue.reviews] == ["add_case_note"]


def test_kill_switch_drill(tmp_path):
    p = pipeline(tmp_path)
    with pytest.raises(PermissionError):
        p.kill.engage(staff_signer("m.chen"), "Not authorized to stop the assistant.")
    p.kill.engage(staff_signer("d.okafor"), "Drill: confirm the assistant stops on demand.")
    log = triage(p)
    assert len(log.steps) == 1 and log.steps[0].outcome == "stopped" and "[KILL-SWITCH]" in log.steps[0].message
    assert p.alerts.changes == [] and not p.queue.requests
    p.kill.release(staff_signer("d.okafor"), "Drill complete.")
    assert triage(p, session_id="sess-aml-6b21").steps[0].outcome == "executed"
