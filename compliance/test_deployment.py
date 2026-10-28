"""Production deployment (Module 10): retention locks, deletion, identity and the sandbox, per deployed agent."""
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sentinel.audit import AuditStore, verify_log
from sentinel.deploy import (CredentialError, CredentialInjector, EgressPolicy, FsGuard, RetentionLocked,
                             TokenBroker, TranscriptStore, WormStore, archive_audit_log, check_agent, docker_args,
                             load_catalog, scan_for_secrets, session_options, sweep)
from sentinel.monitoring.fleet import load_fleet

DEPLOYED = [a.name for a in load_fleet().agents if a.controls.get("deployment")]
T0 = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)
KEY = b"compliance-suite-key"


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


@pytest.mark.parametrize("name", DEPLOYED)
@pytest.mark.control("1.4")
def test_audit_logs_are_write_once_and_retention_locked(runs, deployment, name, tmp_path):
    d = deployment.get(name)
    rule = d.rule("audit_log")
    assert rule and rule.worm, f"{name}: no WORM retention rule for the audit log"
    assert d.audit_storage.mode == "COMPLIANCE", "governance-mode locks can be lifted by a privileged admin"
    assert d.audit_storage.retain_days >= rule.min_days
    clock = Clock()
    store = WormStore(tmp_path / "worm", clock=clock)
    archived = [m for log in runs[name].logs.values() for m in archive_audit_log(store, Path(log), name, rule)]
    assert archived, f"{name}: nothing archived"
    key = archived[0].key
    with pytest.raises(RetentionLocked):
        store.delete(key)
    with pytest.raises(RetentionLocked):
        store.overwrite(key, b"edited")
    clock.now = T0 + timedelta(days=rule.min_days - 1)
    with pytest.raises(RetentionLocked):
        store.delete(key)                                    # still locked the day before it expires
    assert store.verify() == []


@pytest.mark.parametrize("name", DEPLOYED)
@pytest.mark.control("2.6")
def test_transcripts_are_deleted_on_schedule_with_receipts(deployment, name, tmp_path):
    d = deployment.get(name)
    rule = d.rule("session_transcript")
    assert rule is not None and rule.max_days <= 30, f"{name}: transcripts need a short maximum retention"
    for r in d.retention:
        if r.data_class in ("session_transcript", "tool_cache", "provider_prompt_cache", "vault_entry"):
            assert r.max_days is not None, f"{name}: {r.data_class} has no deletion deadline"
    clock = Clock()
    store = TranscriptStore(tmp_path / "transcripts", clock=clock)
    for sid in ("old", "held"):
        asyncio.run(store.append({"project_key": "proj", "session_id": sid}, [{"uuid": f"{sid}-1", "type": "user"}]))
    asyncio.run(store.append({"project_key": "proj", "session_id": "old", "subpath": "subagents/agent-1"},
                             [{"uuid": "sub-1", "type": "assistant"}]))
    clock.now = T0 + timedelta(days=rule.max_days + 1)
    asyncio.run(store.append({"project_key": "proj", "session_id": "new"}, [{"uuid": "new-1", "type": "user"}]))
    audit = AuditStore(tmp_path / "deletions.jsonl", hmac_key=KEY)
    receipts = sweep(store, name, rule, holds={"held"}, audit=audit)
    audit.checkpoint()
    assert [r.session_id for r in receipts] == ["old"]
    assert asyncio.run(store.load({"project_key": "proj", "session_id": "old"})) is None
    assert asyncio.run(store.list_subkeys({"project_key": "proj", "session_id": "old"})) == []
    kept = {e["session_id"] for e in asyncio.run(store.list_sessions("proj"))}
    assert kept == {"held", "new"}, "legal holds and young transcripts must survive the sweep"
    assert verify_log(tmp_path / "deletions.jsonl", KEY).ok
    opts = session_options(store, tmp_path / "cfg")
    assert opts["setting_sources"] == [] and opts["env"]["CLAUDE_CONFIG_DIR"].startswith(str(tmp_path))


@pytest.mark.parametrize("name", DEPLOYED)
@pytest.mark.control("3.3")
def test_agent_credentials_are_scoped_short_lived_and_never_logged(runs, deployment, name):
    d = deployment.get(name)
    ident = d.identity
    assert ident.principal.startswith("svc:") and name in ident.principal
    assert ident.max_ttl_s <= 900, "agent credentials should expire within 15 minutes"
    clock = Clock()
    broker = TokenBroker(KEY, clock=clock)
    token = broker.issue(ident, ident.scopes[:1], 300, task="compliance-check")
    assert broker.verify(token.value, ident.scopes[0])["sub"] == ident.principal
    with pytest.raises(CredentialError):
        broker.issue(ident, ["admin:*"], 300, task="escalation")
    with pytest.raises(CredentialError):
        broker.issue(ident, ident.scopes[:1], ident.max_ttl_s + 1, task="too long")
    clock.now = T0 + timedelta(seconds=301)
    with pytest.raises(CredentialError, match="expired"):
        broker.verify(token.value, ident.scopes[0])
    tool_host = d.sandbox.egress_allowlist[-1]
    injector = CredentialInjector(broker, ident, {tool_host: ident.scopes[0]})
    assert injector.outbound(tool_host, {}, task="t")["Authorization"].startswith("Bearer ")
    with pytest.raises(CredentialError):
        injector.outbound(tool_host, {"Authorization": "Bearer agent-supplied"}, task="t")
    assert scan_for_secrets(list(runs[name].logs.values())) == []


@pytest.mark.parametrize("name", DEPLOYED)
@pytest.mark.control("3.5")
def test_runtime_is_sandboxed_with_an_egress_allowlist(deployment, name):
    d = deployment.get(name)
    assert check_agent(name, d, load_catalog()) == [], "deployment pre-flight must be clean"
    args = docker_args(d.sandbox)
    assert "--read-only" in args and args[args.index("--network") + 1] == "none"
    egress = EgressPolicy(d.sandbox.egress_allowlist)
    assert egress.check(f"https://{d.endpoint}/v1/messages").allowed
    for url in ("https://exfil.example.net/upload", f"http://{d.endpoint}/", "https://203.0.113.7/collect",
                f"https://{d.endpoint}.attacker.example/"):
        assert not egress.check(url).allowed, url
    ws = d.sandbox.workspace
    guard = FsGuard([ws], [ws])
    assert guard.decide("Read", {"file_path": f"{ws}/case.json"})[0] == "allow"
    for tool, path in (("Read", f"{ws}/.env"), ("Read", "/etc/passwd"), ("Write", f"{ws}/../etc/cron.d/x"),
                       ("Read", "/home/agent/.aws/credentials")):
        assert guard.decide(tool, {"file_path": path})[0] == "deny", path
