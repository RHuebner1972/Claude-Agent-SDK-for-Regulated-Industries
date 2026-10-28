"""Offline tests for Module 8 code (no API key needed). Run: uv run pytest tests/test_m08_offline.py"""
import contextlib
import io
import json
import runpy
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sentinel.evidence import build_pack, score, verify_pack
from sentinel.monitoring import (FleetMetrics, check_change_control, evaluate, load_changes, load_fleet,
                                 notification_clocks, run_fleet, total)
from sentinel.monitoring.redteam import run_redteam
from sentinel.monitoring.runs import KEY

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"


def _fleet_with(name, **controls):
    fleet = load_fleet()
    return fleet.model_copy(update={"agents": [
        a.model_copy(update={"controls": {**a.controls, **controls}}) if a.name == name else a for a in fleet.agents]})


def test_fleet_manifest_and_change_control_agree():
    fleet = load_fleet()
    assert len(fleet.agents) == 5 and all(fp.startswith("fp:") for fp in fleet.fingerprints().values())
    assert not any(check_change_control(fleet, load_changes()).values())
    swapped = fleet.model_copy(update={"agents": [a.model_copy(update={"model": "claude-sonnet-9-9"})
                                                  if a.name == "aml-triage" else a for a in fleet.agents]})
    assert check_change_control(swapped, load_changes())["aml-triage"][0].startswith("CHG-001")


def test_red_team_defends_everything_and_notices_weakening():
    assert run_redteam().ok
    weak = run_redteam(_fleet_with("ccb-assistant", handoff_contracts=False))
    assert {r.id for r in weak.results if not r.defended} == {"RT-EXF-002", "RT-EXF-004"}


def test_metrics_and_alerts_from_audit_logs():
    metrics = FleetMetrics()
    for run in run_fleet(load_fleet(), tempfile.mkdtemp()).values():
        metrics.ingest(run, KEY)
    snap = metrics.snapshot()
    assert total(snap, "agent.policy.denials") >= 3 and total(snap, "agent.pii.masked") > 0
    assert total(snap, "agent.restricted_data.leaks") == 0 and metrics.p95_latency("aml-triage") > 0
    assert {a.rule for a in evaluate(snap, metrics=metrics)} == {"ALR-APPROVAL-EXPIRED", "ALR-DENY-RATE"}


def test_leak_regression_pages():
    metrics = FleetMetrics()
    for run in run_fleet(_fleet_with("ccb-assistant", handoff_contracts=False), tempfile.mkdtemp()).values():
        metrics.ingest(run, KEY)
    pages = [a for a in evaluate(metrics.snapshot(), metrics=metrics) if a.severity == "page"]
    assert [(a.rule, a.agent) for a in pages] == [("ALR-LEAK", "ccb-assistant")]


def test_scorecard_rules():
    passing = {"results": [{"test": "t", "controls": ["1.2"], "agent": None, "outcome": "passed"}]}
    failing = {"results": [{"test": "t", "controls": ["1.2"], "agent": None, "outcome": "failed"}]}
    assert score(passing).items[1].status == "met (tested)"
    card = score(failing)
    assert card.items[1].status == "failing" and not card.critical_met and card.rating == "Not production-ready"


def test_notification_clocks():
    found = datetime(2026, 10, 28, 15, 40, tzinfo=timezone.utc)
    clocks = {(d.regime, d.audience): d for d in notification_clocks(found, ["hipaa", "gdpr", "sec"], affected=600)}
    assert "2026-12-27" in clocks[("HIPAA", "Affected individuals")].due
    assert ("HIPAA", "HHS Secretary") in clocks and clocks[("GDPR", "Supervisory authority")].due.startswith("2026-10-31T15:40")
    assert clocks[("SEC", "Form 8-K Item 1.05")].due == "2026-11-03"          # Wed + 4 business days


def test_evidence_pack_builds_verifies_and_detects_tampering():
    out = Path(tempfile.mkdtemp()) / "pack"
    summary = build_pack(out)
    assert summary["suite_passed"] and summary["score"] == 36 and summary["rating"] == "Audit-ready"
    assert not verify_pack(out)
    (out / "alerts.json").write_text("[]", encoding="utf-8")
    (out / "extra.txt").write_text("x", encoding="utf-8")
    assert set(verify_pack(out)) == {"modified: alerts.json", "added after signing: extra.txt"}


def test_lesson_demos_run():
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runpy.run_path(str(next(LESSONS.glob("M08-L03_*")) / "final" / "redteam_demo.py"), run_name="__main__")
    assert "AS DEPLOYED: 13/13 defended" in out.getvalue() and "WEAKENED" in out.getvalue()
