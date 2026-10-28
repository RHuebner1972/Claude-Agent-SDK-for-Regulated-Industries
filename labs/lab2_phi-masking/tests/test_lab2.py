"""Lab 2 acceptance tests.

Criteria: zero PHI in logs on the synthetic test set; detection recall at or above the target threshold;
re-identification is access-controlled and audited. Plus minimum necessary at the tool boundary.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from course_data import patients, prior_auth_requests
from sentinel.audit import verify_log

from evaluate import GENERIC_TARGET, TARGET, recall
from phi_guard.detect import detect, known_values
from phi_guard.leakscan import canaries_from, scan_text
from phi_guard.minimize import minimize
from phi_guard.pa_tools import case_record, simulate_pa_review
from phi_guard.recognizers import npi_is_valid
from phi_guard.vault import ReidentificationDenied, TokenVault
from pipeline import DEMO_ENC_KEY, build_pipeline

CANARIES = canaries_from(patients())


@pytest.fixture
def vault(tmp_path) -> TokenVault:
    from sentinel.audit import AuditStore
    return TokenVault(tmp_path / "vault.json", enc_key=DEMO_ENC_KEY.encode(), hmac_key=b"test-hmac",
                      audit=AuditStore(tmp_path / "vault_audit.jsonl"))


@pytest.fixture
def run(tmp_path):
    p = build_pipeline(tmp_path)
    seen = asyncio.run(simulate_pa_review(p.hooks, p.tools))
    return p, seen, tmp_path


# --- TODOs 1-3: recognizers ------------------------------------------------------------------------
def test_mrn_needs_context():
    assert any(f.entity == "MRN" for f in detect("Patient MRN 4829173 seen today."))
    assert not any(f.entity == "MRN" for f in detect("Lot number 4829173 shipped today."))


def test_npi_luhn():
    assert npi_is_valid("1245319599") and not npi_is_valid("1245319598")
    assert any(f.entity == "NPI" for f in detect("Ordering provider NPI 1672938028."))
    assert not any(f.entity == "NPI" for f in detect("Ordering provider NPI 1672938029."))


def test_member_id():
    assert any(f.entity == "MEMBER_ID" for f in detect("Subscriber ID NEH221964730 on file."))


def test_recall_meets_targets():
    generic, missed = recall(use_known=False)
    assert generic >= GENERIC_TARGET, missed
    pipeline, missed = recall(use_known=True)
    assert pipeline >= TARGET, missed


def test_durations_are_not_masked():
    text = "Failed 6 weeks of physical therapy; symptoms for 9 weeks."
    assert not any(f.entity == "DATE_TIME" for f in detect(text))


# --- TODOs 4-5: the vault --------------------------------------------------------------------------
def test_tokens_are_deterministic_and_encrypted(vault):
    t1, t2 = vault.tokenize("Maria Delgado", "PERSON"), vault.tokenize("Maria Delgado", "PERSON")
    assert t1 == t2 and t1.startswith("[[PERSON_") and t1.endswith("]]")
    assert "Maria" not in vault.path.read_text()


def test_reidentification_is_access_controlled(vault):
    token = vault.tokenize("4829173", "MRN")
    assert vault.detokenize(token, requester="k.osei", role="care_manager", purpose="treatment") == "4829173"
    with pytest.raises(ReidentificationDenied):
        vault.detokenize(token, requester="d.ruiz", role="data_analyst", purpose="analytics")
    with pytest.raises(ReidentificationDenied):
        vault.detokenize(token, requester="m.chen", role="utilization_reviewer", purpose="treatment")


def test_reidentification_is_audited_without_the_value(vault):
    token = vault.tokenize("4829173", "MRN")
    vault.detokenize(token, requester="k.osei", role="care_manager", purpose="treatment")
    with pytest.raises(ReidentificationDenied):
        vault.detokenize(token, requester="d.ruiz", role="data_analyst", purpose="analytics")
    log = vault.audit.path.read_text()
    types = [json.loads(line)["event_type"] for line in log.splitlines()]
    assert types.count("tool.completed") == 1 and types.count("tool.denied") == 1
    assert "d.ruiz" in log and "4829173" not in log
    assert verify_log(vault.audit.path).ok


# --- TODOs 6-7: minimum necessary at the tool boundary ----------------------------------------------
def test_minimize_allowlist():
    patient = patients()[0]
    out = minimize({**patient, "age": 65}, "patient", "prior_auth_review")
    assert set(out) == {"age", "sex", "plan"}
    with pytest.raises(PermissionError):
        minimize(patient, "patient", "marketing")


def test_tool_returns_no_identifiers_but_keeps_clinical_meaning(vault):
    for r in prior_auth_requests():
        case = case_record(r["request_id"], minimized=True, vault=vault)
        assert not scan_text(json.dumps(case), CANARIES), r["request_id"]
    case = case_record("PA-2001", minimized=True, vault=vault)
    assert "6 weeks of physical therapy" in case["clinical_notes"] and case["patient"]["age"] == 65


# --- TODO 8 + acceptance: the whole pipeline ---------------------------------------------------------
def test_zero_phi_anywhere_after_a_full_run(run):
    p, seen, work = run
    assert not scan_text(json.dumps(seen), CANARIES)                       # what the model saw
    for f in ("audit.jsonl", "vault.json"):
        assert not scan_text((work / f).read_text(), CANARIES), f
    assert not scan_text(json.dumps(p.recorded), CANARIES)                  # downstream records


def test_pipeline_audit_log_is_complete_and_verifies(run):
    p, _, work = run
    types = {json.loads(line)["event_type"] for line in p.store.path.read_text().splitlines()}
    assert {"prompt.submitted", "tool.requested", "tool.completed", "decision.recorded", "agent.stopped"} <= types
    assert verify_log(p.store.path, b"course-demo-key").ok


def test_reviewer_can_reidentify_the_recommendation(run):
    p, _, _ = run
    rationale = p.recorded[0]["rationale"]
    assert "[[PERSON_" in rationale
    text = p.vault.reidentify_text(rationale, requester="k.osei", role="care_manager", purpose="treatment")
    assert "Maria Delgado" in text
