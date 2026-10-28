"""
M10-L03: retention and deletion. Keep the audit trail where nobody can shorten it; delete transcripts on schedule,
provably, unless a legal hold applies.

    uv run python lessons/M10-L03_retention-and-deletion-session/final/retention_demo.py
"""
from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sentinel.audit import AuditStore, verify_log
from sentinel.deploy import (RetentionLocked, TranscriptStore, WormStore, archive_audit_log, load_deployment,
                             session_options, sweep)
from sentinel.monitoring.fleet import load_fleet
from sentinel.monitoring.runs import KEY, run_agent

AGENT = "pa-reviewer"


class Clock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw) -> None:
        self.now += timedelta(**kw)


def main() -> None:
    work = Path(tempfile.mkdtemp())
    dep = load_deployment().get(AGENT)
    print(f"1. THE RULES for {AGENT} (deploy/policies/deployment.yaml)")
    for r in dep.retention:
        span = f"keep >= {r.min_days} d" if r.min_days else f"delete <= {r.max_days} d"
        print(f"   {r.data_class:22} {span:16} {'WORM ' if r.worm else '     '} {r.basis[:70]}")

    print("\n2. KEEP: ship the audit log to write-once storage under the audit_log rule")
    clock = Clock(datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc))
    run = run_agent(load_fleet().get(AGENT), work / "run")
    worm = WormStore(work / "worm", clock=clock)
    rule = dep.rule("audit_log")
    meta = archive_audit_log(worm, run.general_log, AGENT, rule)[0]
    print(f"   {meta.key}  {meta.sha256[:23]}...  retained until {meta.retain_until[:10]}  "
          f"({dep.audit_storage.service}, {dep.audit_storage.mode} mode)")
    for label, attempt in [("delete it", lambda: worm.delete(meta.key)),
                           ("overwrite it", lambda: worm.overwrite(meta.key, b"{}")),
                           ("shorten the lock", lambda: worm.extend(meta.key, clock.now + timedelta(days=30)))]:
        try:
            attempt()
            print(f"   {label}: allowed (unexpected)")
        except RetentionLocked as exc:
            print(f"   {label}: refused -> {exc}")
    worm.set_legal_hold(meta.key, True)
    clock.advance(days=rule.min_days + 1)
    try:
        worm.delete(meta.key)
    except RetentionLocked as exc:
        print(f"   six years later, under legal hold: refused -> {exc}")
    worm.set_legal_hold(meta.key, False)
    worm.delete(meta.key)
    print("   hold released, retention expired: deleted (the only time deletion succeeds)")

    print("\n3. DELETE: transcripts go to a store you govern, and a sweep enforces max_days")
    clock = Clock(datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc))
    store = TranscriptStore(work / "transcripts", clock=clock)
    opts = session_options(store, work / "session-config")
    print(f"   ClaudeAgentOptions(session_store=TranscriptStore(...), env={opts['env']}, setting_sources=[])")
    project = "-workspace-pa-reviewer"
    for sid in ("case-PA-1001", "case-PA-1002"):
        asyncio.run(store.append({"project_key": project, "session_id": sid},
                                 [{"uuid": f"{sid}-u1", "type": "user", "message": "Review case <MEMBER_ID_1>"},
                                  {"uuid": f"{sid}-a1", "type": "assistant", "message": "Criteria 4.2 met..."}]))
    asyncio.run(store.append({"project_key": project, "session_id": "case-PA-1001",
                              "subpath": "subagents/agent-criteria"}, [{"uuid": "s1", "type": "assistant"}]))
    clock.advance(days=8)
    asyncio.run(store.append({"project_key": project, "session_id": "case-PA-1003"},
                             [{"uuid": "c3-u1", "type": "user", "message": "Review case <MEMBER_ID_2>"}]))
    audit = AuditStore(work / "deletions.jsonl", hmac_key=KEY)
    receipts = sweep(store, AGENT, dep.rule("session_transcript"), holds={"case-PA-1002"}, audit=audit)
    audit.checkpoint()
    for r in receipts:
        print(f"   deleted {r.session_id} (age {r.age_days} d, incl. subagent transcripts)  content {r.content_sha256[:23]}...")
    left = sorted(e["session_id"] for e in asyncio.run(store.list_sessions(project)))
    print(f"   kept: {left}  (PA-1002 is under legal hold; PA-1003 was created today)")
    report = verify_log(work / "deletions.jsonl", KEY)
    print(f"   deletion receipts in the audit trail: {report.events} event(s), verifies: {report.ok}")

    print("\n4. THE PROVIDER SIDE is a contract and a setting, not your code")
    print(f"   {dep.rule('provider_prompt_cache').basis}")
    print(f"   path {dep.path}: {', '.join(dep.agreements)}")


if __name__ == "__main__":
    main()
