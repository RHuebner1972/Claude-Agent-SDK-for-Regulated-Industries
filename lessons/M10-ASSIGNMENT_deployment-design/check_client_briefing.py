"""M10 practice activity: check a sixth agent's production deployment without the fleet runners.

Reads your copies in <course-repo>/practice/ (deployment.yaml, fleet-prod.yaml, changes.yaml), never the course files.
Run from the root of course-repo:

    uv run python lessons/M10-ASSIGNMENT_deployment-design/check_client_briefing.py [practice-dir]
"""
import asyncio
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sentinel.audit import AuditStore, verify_log
from sentinel.audit.models import Actor, AgentInfo, AuditEvent
from sentinel.deploy import (CredentialError, CredentialInjector, EgressPolicy, FsGuard, RetentionLocked,
                             TokenBroker, TranscriptStore, WormStore, archive_audit_log, check_agent, docker_args,
                             load_catalog, load_deployment, preflight, scan_for_secrets, sweep)
from sentinel.monitoring.change import check_change_control, load_changes
from sentinel.monitoring.fleet import load_fleet

ROOT = Path(__file__).resolve().parents[2]                     # course-repo
HERE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "practice"
AGENT = "client-briefing"
T0 = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def main() -> None:
    fleet = load_fleet(HERE / "fleet-prod.yaml")
    dep = load_deployment(HERE / "deployment.yaml")
    d = dep.get(AGENT)
    work = Path(tempfile.mkdtemp())

    print("PRE-FLIGHT")
    for name, findings in preflight(fleet, dep).items():
        print(f"  {name:17} {'READY' if not findings else findings}")
    assert check_agent(AGENT, d, load_catalog()) == []

    print("CHANGE CONTROL")
    findings = check_change_control(fleet, load_changes(HERE / "changes.yaml"))
    for name, items in findings.items():
        print(f"  {name:17} {'OK' if not items else items[0]}")
    assert not any(findings.values())

    # 1.4: a synthetic audit log, archived write-once, can't be deleted early
    clock = Clock()
    log = work / "run" / "audit.jsonl"
    store = AuditStore(log, hmac_key=b"practice")
    store.append(AuditEvent(event_type="prompt.submitted", actor=Actor(kind="human", id="rm-042"),
                            on_behalf_of="rm-042", correlation_id="brief-1",
                            agent=AgentInfo(name=AGENT, version="1", model="claude-sonnet-5-5",
                                            prompt_version="sha256:7b1e4d0a9c3f", policy_version="deployment@1.1.0")))
    store.checkpoint()
    worm = WormStore(work / "worm", clock=clock)
    meta = archive_audit_log(worm, log, AGENT, d.rule("audit_log"))[0]
    try:
        worm.delete(meta.key)
        raise SystemExit("1.4 FAIL: deleted early")
    except RetentionLocked:
        print(f"1.4  audit log locked until {meta.retain_until[:10]} ({d.audit_storage.mode})")

    # 2.6: transcripts swept at max_days, holds respected, receipts verify
    tclock = Clock()
    ts = TranscriptStore(work / "transcripts", clock=tclock)
    for sid in ("brief-old", "brief-held"):
        asyncio.run(ts.append({"project_key": "p", "session_id": sid}, [{"uuid": sid}]))
    tclock.now = T0 + timedelta(days=d.rule("session_transcript").max_days + 1)
    audit = AuditStore(work / "deletions.jsonl", hmac_key=b"practice")
    receipts = sweep(ts, AGENT, d.rule("session_transcript"), holds={"brief-held"}, audit=audit)
    audit.checkpoint()
    assert [r.session_id for r in receipts] == ["brief-old"] and verify_log(work / "deletions.jsonl", b"practice").ok
    print(f"2.6  swept {[r.session_id for r in receipts]}, held session kept, receipts verify")

    # 3.3: scoped, short-lived, injected outside, nothing leaked
    bclock = Clock()
    broker = TokenBroker(b"practice", clock=bclock)
    tok = broker.issue(d.identity, d.identity.scopes[:1], 300, task="brief")
    for bad in (lambda: broker.issue(d.identity, ["clients:write"], 300, task="x"),
                lambda: broker.issue(d.identity, d.identity.scopes[:1], 3600, task="x")):
        try:
            bad()
            raise SystemExit("3.3 FAIL")
        except CredentialError:
            pass
    bclock.now = T0 + timedelta(seconds=301)
    try:
        broker.verify(tok.value, d.identity.scopes[0])
        raise SystemExit("3.3 FAIL: token didn't expire")
    except CredentialError:
        pass
    inj = CredentialInjector(broker, d.identity, {d.sandbox.egress_allowlist[-1]: d.identity.scopes[0]})
    bclock.now = T0
    assert inj.outbound(d.sandbox.egress_allowlist[-1], {}, task="t")["Authorization"].startswith("Bearer ")
    assert scan_for_secrets([log]) == []
    print("3.3  token scoped, 15-minute cap enforced, expired at 5 minutes, injected outside, log clean")

    # 3.5: sandboxed, one way out
    args = docker_args(d.sandbox)
    assert "--read-only" in args and args[args.index("--network") + 1] == "none"
    eg = EgressPolicy(d.sandbox.egress_allowlist)
    assert eg.check(f"https://{d.endpoint}/model/invoke").allowed
    assert not eg.check("https://bedrock-runtime.us-east-1.amazonaws.com/").allowed     # wrong region
    guard = FsGuard([d.sandbox.workspace], [d.sandbox.workspace])
    assert guard.decide("Read", {"file_path": "/workspace/.env"})[0] == "deny"
    print("3.5  no network but the proxy; US endpoint refused; credential files refused")
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    main()
