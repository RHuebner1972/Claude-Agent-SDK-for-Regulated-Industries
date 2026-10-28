"""Offline tests for Module 10 code (no API key needed). Run: uv run pytest tests/test_m10_offline.py"""
import asyncio
import contextlib
import io
import json
import os
import runpy
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sentinel.audit import AuditStore, verify_log
from sentinel.deploy import (CredentialError, CredentialInjector, EgressPolicy, FsGuard, Requirements,
                             RetentionLocked, RetentionRule, SandboxProfile, TokenBroker, TranscriptStore,
                             WorkloadIdentity, WormStore, check_reference, lint_profile, load_deployment, preflight,
                             scan_for_secrets, shortlist, sweep)
from sentinel.deploy.deployment import PROD_FLEET
from sentinel.evidence import apply_reviews, load_session, run_suite, score
from sentinel.evidence.review import REVIEW_PATH
from sentinel.monitoring.change import check_change_control, load_changes
from sentinel.monitoring.fleet import load_fleet

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
T0 = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def _ok(req: Requirements) -> set[str]:
    return {f.path for f in shortlist(req) if f.ok}


def test_path_shortlists_match_the_documented_facts():
    assert "claude-platform-aws" not in _ok(Requirements(phi=True))
    assert _ok(Requirements(fedramp="high")) == {"bedrock-govcloud", "google-agent-platform", "claude-for-government"}
    assert _ok(Requirements(itar=True)) == {"bedrock-govcloud"}
    assert _ok(Requirements(phi=True, eu_residency=True)) == {"bedrock", "google-agent-platform"}
    assert _ok(Requirements(eu_residency=True, fedramp="high")) == set()       # FedRAMP environments are US
    assert "microsoft-foundry" not in _ok(Requirements(cloud_processor=True))


def test_retention_rules_refuse_incoherent_settings():
    with pytest.raises(ValidationError, match="max_days"):
        RetentionRule(data_class="session_transcript", basis="policy text")
    with pytest.raises(ValidationError, match="WORM"):
        RetentionRule(data_class="audit_log", worm=True, basis="policy text")
    with pytest.raises(ValidationError):
        RetentionRule(data_class="tool_cache", min_days=10, max_days=5, basis="policy text")


def test_worm_store_is_write_once_and_locked(tmp_path):
    clock = Clock()
    store = WormStore(tmp_path, clock=clock)
    store.put("a/log.jsonl", b"line\n", retain_days=30)
    for attempt in (lambda: store.put("a/log.jsonl", b"x", 30), lambda: store.delete("a/log.jsonl"),
                    lambda: store.overwrite("a/log.jsonl", b"x"),
                    lambda: store.extend("a/log.jsonl", T0 + timedelta(days=1))):
        with pytest.raises(RetentionLocked):
            attempt()
    (tmp_path / "a/log.jsonl").write_bytes(b"edited\n")                       # tampering outside the API
    assert store.verify() and "no longer matches" in store.verify()[0]
    (tmp_path / "a/log.jsonl").write_bytes(b"line\n")
    store.set_legal_hold("a/log.jsonl", True)
    clock.now = T0 + timedelta(days=31)
    with pytest.raises(RetentionLocked, match="legal hold"):
        store.delete("a/log.jsonl")
    store.set_legal_hold("a/log.jsonl", False)
    store.delete("a/log.jsonl")
    assert store.keys() == []


def test_transcript_store_follows_the_session_store_contract(tmp_path):
    store = TranscriptStore(tmp_path)
    key = {"project_key": "p", "session_id": "s1"}
    asyncio.run(store.append(key, [{"uuid": "1", "type": "user"}]))
    asyncio.run(store.append(key, [{"uuid": "1", "type": "user"}, {"uuid": "2", "type": "assistant"}]))  # retry
    assert [e["uuid"] for e in asyncio.run(store.load(key))] == ["1", "2"]
    asyncio.run(store.append({**key, "subpath": "subagents/agent-x"}, [{"uuid": "3"}]))
    assert asyncio.run(store.list_subkeys(key)) == ["subagents/agent-x"]
    asyncio.run(store.delete(key))
    assert asyncio.run(store.load(key)) is None and asyncio.run(store.list_subkeys(key)) == []
    assert asyncio.run(store.list_sessions("p")) == []
    assert asyncio.run(store.load({"project_key": "p", "session_id": "nope"})) is None


def test_sweep_deletes_old_transcripts_keeps_holds_and_logs_receipts(tmp_path):
    clock = Clock()
    store = TranscriptStore(tmp_path / "t", clock=clock)
    for sid in ("a", "b"):
        asyncio.run(store.append({"project_key": "p", "session_id": sid}, [{"uuid": sid}]))
    clock.now = T0 + timedelta(days=8)
    rule = RetentionRule(data_class="session_transcript", max_days=7, basis="minimum necessary policy")
    audit = AuditStore(tmp_path / "d.jsonl", hmac_key=b"k")
    receipts = sweep(store, "pa-reviewer", rule, holds={"b"}, audit=audit)
    audit.checkpoint()
    assert [r.session_id for r in receipts] == ["a"] and receipts[0].content_sha256.startswith("sha256:")
    event = json.loads((tmp_path / "d.jsonl").read_text().splitlines()[0])
    assert event["detail"]["action"] == "deleted" and event["authority"] == "minimum necessary policy"
    assert verify_log(tmp_path / "d.jsonl", b"k").ok


def test_sandbox_lint_egress_and_filesystem_guard():
    p = load_deployment().get("aml-triage").sandbox
    assert lint_profile(p, "bedrock-runtime.us-east-1.amazonaws.com") == []
    weak = SandboxProfile.model_validate({**p.model_dump(), "user": "root", "cap_drop_all": False,
                                          "mounts": [{"source": "/var/run/docker.sock", "target": "/d"}]})
    codes = {f.split()[0] for f in lint_profile(weak)}
    assert {"SBX-001", "SBX-003", "SBX-006"} <= codes
    egress = EgressPolicy(["api.anthropic.com", "*.bayside.example"])
    assert egress.check("https://api.anthropic.com/v1/messages").allowed
    assert egress.check("https://core.bayside.example/x").allowed
    for url in ("https://bayside.example/", "https://api.anthropic.com.evil.example/", "https://10.0.0.5/",
                "ftp://api.anthropic.com/"):
        assert not egress.check(url).allowed, url
    guard = FsGuard(["/workspace", "/data"], ["/workspace"])
    assert guard.decide("Read", {"file_path": "/data/x.csv"})[0] == "allow"
    assert guard.decide("Write", {"file_path": "/data/x.csv"})[0] == "deny"
    assert guard.decide("Read", {"file_path": "/workspace/keys/server.pem"})[0] == "deny"
    assert guard.decide("Bash", {"command": "ls"})[0] == "allow"                # Bash belongs to the SDK sandbox


def test_identity_tokens_are_scoped_short_lived_and_injected_outside():
    ident = load_deployment().get("pa-reviewer").identity
    with pytest.raises(ValidationError):
        WorkloadIdentity.model_validate({**ident.model_dump(), "principal": "user:dreyes"})
    with pytest.raises(ValidationError):
        WorkloadIdentity.model_validate({**ident.model_dump(), "max_ttl_s": 86400})
    clock = Clock()
    broker = TokenBroker(b"k", clock=clock)
    tok = broker.issue(ident, ["criteria:read"], 120, task="t")
    other = TokenBroker(b"different-key", clock=clock)
    with pytest.raises(CredentialError, match="signature"):
        other.verify(tok.value, "criteria:read")
    clock.now = T0 + timedelta(seconds=121)
    with pytest.raises(CredentialError, match="expired"):
        broker.verify(tok.value, "criteria:read")
    inj = CredentialInjector(broker, ident, {"um-api.northshore.example": "criteria:read"})
    with pytest.raises(CredentialError, match="no credential route"):
        inj.outbound("evil.example", {}, task="t")


def test_secret_scanner_finds_credentials(tmp_path):
    (tmp_path / "ok.log").write_text("member <MEMBER_ID_1> approved\n")
    (tmp_path / "bad.log").write_text("key=sk-ant-api03-abcdefghijklmnop\n-----BEGIN RSA PRIVATE KEY-----\n")
    found = scan_for_secrets([tmp_path])
    assert len(found) == 2 and all("bad.log" in f for f in found)


def test_preflight_and_change_control_for_both_manifests():
    base, prod = load_fleet(), load_fleet(PROD_FLEET)
    assert all(f and f[0].startswith("DEP-000") for f in preflight(base).values())
    assert not any(preflight(prod).values())
    assert not any(check_change_control(prod, load_changes()).values())
    assert not any(check_change_control(base, load_changes()).values())
    assert {a.name: a.fingerprint() for a in base.agents} != {a.name: a.fingerprint() for a in prod.agents}


def test_reference_architecture_passes_and_catches_a_quick_fix(tmp_path):
    ref = REPO / "deploy" / "reference"
    assert check_reference(ref, "aml-triage") == []
    copy = tmp_path / "ref"
    shutil.copytree(ref, copy)
    doc = yaml.safe_load((copy / "compose.yaml").read_text())
    doc["services"]["agent"].update(read_only=False, user="0")
    doc["services"]["agent"]["environment"]["ANTHROPIC_API_KEY"] = "x"
    (copy / "compose.yaml").write_text(yaml.safe_dump(doc))
    (copy / "egress-proxy" / "squid.conf").write_text("acl allowed_hosts dstdomain pastebin.com\n")
    codes = {f.split()[0] for f in check_reference(copy, "aml-triage")}
    assert {"REF-001", "REF-002", "REF-007", "REF-010", "REF-011"} <= codes


def test_production_suite_scores_40_and_review_confirms_39(tmp_path):
    base = run_suite(tmp_path / "base.json")
    assert len(base["results"]) == 53 and score(base).score == 36            # Modules 8-9 baseline unchanged
    prod = run_suite(tmp_path / "prod.json", env={"FLEET_FILE": str(PROD_FLEET)})
    assert prod["exit_status"] == 0 and len(prod["results"]) == 73
    card = score(prod)
    assert (card.score, card.rating) == (40, "Audit-ready")
    confirmed = apply_reviews(card, load_session(REVIEW_PATH.with_name("fleet-2026-q4-prod.yaml")))
    assert (confirmed.score, confirmed.rating) == (39, "Audit-ready")


@pytest.mark.parametrize("lesson,needle", [
    ("M10-L03*", "deletion receipts in the audit trail: 1 event(s), verifies: True"),
    ("M10-L04*", "SBX-005 network 'bridge'"),
    ("M10-L05*", "six minutes later: token expired"),
    ("M10-L08*", "confirmed 39/40, Audit-ready"),
])
def test_lesson_demos_run(lesson, needle):
    script = next(next(LESSONS.glob(lesson)).glob("final/*.py"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(str(script), run_name="__main__")
    assert needle in buf.getvalue()
