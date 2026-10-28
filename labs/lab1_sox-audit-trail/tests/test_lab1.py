"""Lab 1 acceptance tests: one test per acceptance criterion, plus the guard rails that make the log usable.

Criteria: every prompt / tool call / result / final answer is logged; the chain verifies; tampering with
one line is detected; a reviewer can reconstruct a decision from the logs alone.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from audit_trail import GENESIS, Actor, AgentInfo, AuditEvent, AuditHooks, AuditStore, canonical, record_hash, replay_decision, verify_log
from audit_trail.simulate import DEMO_AGENT, fixed_clock, simulate_ledger_review

KEY = b"test-key"
AGENT = DEMO_AGENT
DATA = Path(__file__).resolve().parents[1] / "data"
SENSITIVE = ["84-2917365", "4417002291", "47-1180942", "9921880034", "91-5532018", "3300418872", "33-7741206", "7712049931"]


@pytest.fixture
def run(tmp_path) -> AuditStore:
    store = AuditStore(tmp_path / "audit.jsonl", hmac_key=KEY, checkpoint_every=10)
    hooks = AuditHooks(store, agent=AGENT, on_behalf_of="j.chen", clock=fixed_clock())
    asyncio.run(simulate_ledger_review(hooks))
    return store


def rewrite(path: Path, records: list[dict]) -> None:
    path.write_bytes(b"".join(canonical(r) + b"\n" for r in records))


# --- Criterion 1: everything is logged --------------------------------------------------------
def test_every_kind_of_event_is_logged(run):
    types = {r["event_type"] for r in run.records()}
    assert {"prompt.submitted", "tool.requested", "tool.completed", "tool.denied",
            "decision.recorded", "agent.stopped", "run.completed"} <= types


def test_every_request_has_an_outcome(run):
    records = run.records()
    requested = {r["tool_use_id"] for r in records if r["event_type"] == "tool.requested"}
    ended = {r["tool_use_id"] for r in records if r["event_type"] in ("tool.completed", "tool.denied", "tool.failed")}
    assert requested == ended


def test_one_decision_per_entry_with_authority(run):
    decisions = [r for r in run.records() if r["event_type"] == "decision.recorded"]
    assert len({d["detail"]["entry_id"] for d in decisions}) == 10
    assert all(d["authority"] and d["reason"] for d in decisions)


def test_who_and_which_agent_on_every_event(run):
    for r in run.records():
        assert r["on_behalf_of"] == "j.chen" and r["correlation_id"] and r["timestamp"].endswith("Z")
        assert all(r["agent"][k] for k in ("name", "version", "model", "prompt_version", "policy_version"))


def test_no_sensitive_numbers_in_the_log(run):
    text = run.path.read_text()
    assert not [s for s in SENSITIVE if s in text]


# --- Criterion 2: the chain verifies ------------------------------------------------------------
def test_clean_log_verifies(run):
    report = verify_log(run.path, KEY)
    assert report.ok, report.render()
    assert report.events == len(run.records()) and report.checkpoints_checked >= 1


def test_chain_links(run):
    records = run.records()
    assert records[0]["prev_hash"] == GENESIS
    assert all(b["prev_hash"] == a["hash"] for a, b in zip(records, records[1:]))
    assert [r["seq"] for r in records] == list(range(1, len(records) + 1))


def test_store_resumes_an_existing_chain(run):
    reopened = AuditStore(run.path, hmac_key=KEY)
    hooks = AuditHooks(reopened, agent=AGENT, on_behalf_of="a.patel")
    asyncio.run(simulate_ledger_review(hooks, entries=["JE-1001"]))
    assert verify_log(run.path, KEY).ok


# --- Criterion 3: tampering is detected --------------------------------------------------------
def _decision_index(records, entry_id="JE-1003"):
    return next(i for i, r in enumerate(records) if r["event_type"] == "decision.recorded" and r["detail"]["entry_id"] == entry_id)


def test_editing_one_line_is_detected(run):
    records = run.records()
    i = _decision_index(records)
    records[i]["detail"]["recommendation"] = "approve"
    rewrite(run.path, records)
    report = verify_log(run.path, KEY)
    assert not report.ok and any(f"seq {records[i]['seq']}" in p for p in report.problems)


def test_edit_and_rehash_breaks_the_next_link(run):
    records = run.records()
    i = _decision_index(records)
    records[i]["detail"]["recommendation"] = "approve"
    records[i]["hash"] = record_hash(records[i])
    rewrite(run.path, records)
    assert any("broken link" in p for p in verify_log(run.path).problems)


def test_deleting_a_middle_event_is_detected(run):
    records = run.records()
    del records[5]
    rewrite(run.path, records)
    assert not verify_log(run.path, KEY).ok


def test_rewritten_chain_needs_the_key_to_catch(run):
    records = run.records()
    records[_decision_index(records)]["detail"]["recommendation"] = "approve"
    prev = GENESIS
    for r in records:
        r["prev_hash"] = prev
        r["hash"] = record_hash(r)
        prev = r["hash"]
    rewrite(run.path, records)
    assert any("rewritten" in p for p in verify_log(run.path, KEY).problems)


def test_truncation_is_detected_with_the_key(run):
    rewrite(run.path, run.records()[:-3])
    assert any("truncated" in p for p in verify_log(run.path, KEY).problems)


def test_suspicious_sample_log_fails(monkeypatch):
    report = verify_log(DATA / "suspicious" / "audit.jsonl", b"course-demo-key")
    assert not report.ok
    assert verify_log(DATA / "sample_run" / "audit.jsonl", b"course-demo-key").ok


# --- Criterion 4: a reviewer can reconstruct a decision from the log alone ------------------------
def test_replay_reconstructs_the_decision(run):
    report = verify_log(run.path, KEY)
    text = replay_decision(run.records(), "JE-1003", report)
    for must in ("VERIFIED", "j.chen", "LedgerBot", "claude-sonnet-5-5", "escalate", "Controller", "Policy rule 1", "get_journal_entry"):
        assert must in text, must


def test_replay_shows_the_denied_request(run):
    text = replay_decision(run.records(), "JE-1010", verify_log(run.path, KEY))
    assert "get_vendor_banking" in text and "denied" in text


def test_replay_warns_when_chain_fails():
    path = DATA / "suspicious" / "audit.jsonl"
    records = [json.loads(l) for l in path.read_text().splitlines()]
    text = replay_decision(records, "JE-1006", verify_log(path, b"course-demo-key"))
    assert "FAILED" in text.split("|")[0]


# --- Guard rails ----------------------------------------------------------------------------------
def test_fail_closed_when_the_log_cannot_be_written(tmp_path):
    class BrokenStore(AuditStore):
        def append(self, event):
            raise OSError("disk full")
    hooks = AuditHooks(BrokenStore(tmp_path / "a.jsonl"), agent=AGENT, on_behalf_of="j.chen")
    out = asyncio.run(hooks.on_pre_tool({"session_id": "s", "tool_name": "mcp__ledger__get_journal_entry",
                                         "tool_input": {"entry_id": "JE-1001"}, "tool_use_id": "t1"}, "t1", {"signal": None}))
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("fields", [
    dict(event_type="prompt.submitted", timestamp=datetime(2026, 10, 1, 9, 0)),
    dict(event_type="tool.completed", tool_name="mcp__ledger__get_journal_entry"),
    dict(event_type="decision.recorded", reason="looks fine"),
    dict(event_type="agent.stopped", note="extra field"),
])
def test_unusable_events_are_rejected(fields):
    with pytest.raises(ValidationError):
        AuditEvent(actor=Actor(kind="agent", id="LedgerBot@1.3.0"), on_behalf_of="j.chen", agent=AGENT,
                   correlation_id="run-x", **fields)
