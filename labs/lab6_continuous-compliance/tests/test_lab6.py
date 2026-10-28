"""Lab 6 acceptance tests. Run: uv run pytest labs/lab6_continuous-compliance   (LAB_IMPL=starter to check your work)

Acceptance criteria:
  1. The suite runs in CI and fails the build on a seeded regression
  2. The dashboard shows deny, PII and approval metrics
  3. The evidence pack generates in one command
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from assurance_kit.alerts import evaluate, load_rules
from assurance_kit.change import ChangeLog, check_change_control, load_changes
from assurance_kit.dashboard import render_dashboard
from assurance_kit.fleet import load_fleet
from assurance_kit.metrics import FleetMetrics, total
from assurance_kit.pack import sign_manifest, verify_pack
from assurance_kit.redteam import load_corpus, run_case, run_redteam
from assurance_kit.rubric import load_attestations, load_rubric, score
from assurance_kit.runs import KEY, run_fleet

LAB = Path(__file__).resolve().parents[1]
IMPL = LAB / os.getenv("LAB_IMPL", "solution")
REPO_SRC = LAB.parents[1] / "src"
ENV = {**os.environ, "PYTHONPATH": os.pathsep.join([str(REPO_SRC), str(IMPL)])}


def weakened(**by_agent):
    fleet = load_fleet()
    return fleet.model_copy(update={"agents": [
        a.model_copy(update={"controls": {**a.controls, **by_agent[a.name]}}) if a.name in by_agent else a
        for a in fleet.agents]})


def pytest_run(*args, env=None):
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                          cwd=IMPL, env={**ENV, **(env or {})}, capture_output=True, text=True)


def seeded(name, tmp_path):
    sys.path.insert(0, str(IMPL))
    try:
        spec = importlib.util.spec_from_file_location("seed_regression", IMPL / "seed_regression.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.seed(name, tmp_path / f"{name}-fleet.yaml")
    finally:
        sys.path.remove(str(IMPL))


@pytest.fixture(scope="module")
def fleet_metrics():
    m = FleetMetrics()
    for run in run_fleet(load_fleet(), tempfile.mkdtemp()).values():
        m.ingest(run, KEY)
    return m


# ---- Part 1, TODOs 1-4: the CI suite and the red-team run -----------------------------------------------------------
def test_plugin_records_each_control_result(tmp_path):
    (tmp_path / "conftest.py").write_text('pytest_plugins = ["assurance_kit.pytest_plugin"]\n')
    (tmp_path / "test_demo.py").write_text(textwrap.dedent('''
        import pytest
        @pytest.mark.control("2.2", agent="pa-reviewer")
        def test_ok(): pass
        @pytest.mark.parametrize("name", ["aml-triage"])
        @pytest.mark.control("5.1")
        def test_bad(name): assert False, "approval missing"
        def test_untagged(): pass
    '''))
    out = tmp_path / "results.json"
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path),
                           f"--compliance-results={out}"], env=ENV, capture_output=True, text=True, cwd=tmp_path)
    doc = json.loads(out.read_text())
    assert proc.returncode == 1 and doc["exit_status"] == 1
    got = {(r["controls"][0], r["agent"], r["outcome"]) for r in doc["results"]}
    assert got == {("2.2", "pa-reviewer", "passed"), ("5.1", "aml-triage", "failed")}
    assert "approval missing" in next(r["message"] for r in doc["results"] if r["outcome"] == "failed")


def test_phi_control_test_catches_a_leak(tmp_path):
    spec = importlib.util.spec_from_file_location("t_p2", IMPL / "compliance" / "test_p2_data_protection.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    log = tmp_path / "audit.jsonl"
    run = SimpleNamespace(general_log=log, canaries=["Maria Delgado", "4829173", "Lee"], seen="")
    log.write_text('{"detail": "[[PERSON_1a2b3c4d]] MRN [[MRN_9f8e7d6c]]"}\n')
    mod.test_no_phi_in_the_audit_log({"pa-reviewer": run})             # clean: passes
    log.write_text('{"detail": "Maria Delgado, MRN 4829173"}\n')
    with pytest.raises(AssertionError):
        mod.test_no_phi_in_the_audit_log({"pa-reviewer": run})


def test_red_team_defends_every_case():
    report = run_redteam()
    assert report.ok and len(report.results) == 13
    assert report.by_category() == {"exfiltration": {"cases": 4, "defended": 4}, "injection": {"cases": 3, "defended": 3},
                                    "policy_evasion": {"cases": 6, "defended": 6}}


def test_red_team_reports_weakened_controls_and_probe_errors():
    report = run_redteam(weakened(**{"pa-reviewer": {"log_masking": None}, "aml-triage": {"approval_gate": None}}))
    assert {r.id for r in report.results if not r.defended} == {"RT-INJ-003", "RT-EVA-004"}
    case = next(c for c in load_corpus()[0] if c.id == "RT-EVA-002")
    broken = case.model_copy(update={"input": {"tool": "no_such_tool", "signer": "j.rivera"}})
    result = run_case(broken, load_fleet())
    assert not result.defended and result.observed.startswith("probe error")


def test_change_control_is_clean_for_the_deployed_fleet():
    assert check_change_control(load_fleet(), load_changes()) == {a.name: [] for a in load_fleet().agents}


def test_change_control_flags_unrecorded_and_underapproved_changes():
    fleet = load_fleet()
    swapped = fleet.model_copy(update={"agents": [a.model_copy(update={"model": "claude-sonnet-5-6"})
                                                  if a.name == "ledgerbot" else a for a in fleet.agents]})
    assert check_change_control(swapped, load_changes())["ledgerbot"][0].startswith("CHG-001")
    log = load_changes().model_dump()
    fp = fleet.get("aml-triage").fingerprint()
    rec = next(r for r in log["records"] if r["to_fingerprint"] == fp)
    rec.update(approvals=rec["approvals"][:1], category="predetermined", changed=["model"],
               revalidation={**rec["revalidation"], "result": "failed"})
    codes = {f[:7] for f in check_change_control(fleet, ChangeLog.model_validate(log))["aml-triage"]}
    assert codes == {"CHG-002", "CHG-003", "CHG-004"}


# ---- Part 2, TODOs 5-8: metrics, alerts, scorecard, evidence pack ---------------------------------------------------
def test_metrics_come_from_the_audit_logs(fleet_metrics):
    snap = fleet_metrics.snapshot()
    assert total(snap, "agent.policy.denials", agent="complaint-triage") == 3
    assert {p["attributes"]["rule"] for p in snap["agent.policy.denials"] if p["attributes"]["agent"] == "complaint-triage"} \
        == {"INJ-003", "MDR-001", "COM-001"}
    assert total(snap, "agent.pii.masked", agent="pa-reviewer") > 20 and total(snap, "agent.restricted_data.leaks") == 0
    assert total(snap, "agent.approvals", agent="aml-triage", status="approved") == 2
    assert 3600 < fleet_metrics.p95_latency("aml-triage") < 4 * 3600
    assert total(snap, "agent.boundary.handoffs", result="accepted") == 1 and total(snap, "agent.runs") == 6


def test_alerts_fire_on_the_right_agents(fleet_metrics):
    base = {(a.rule, a.agent) for a in evaluate(fleet_metrics.snapshot(), metrics=fleet_metrics)}
    assert base == {("ALR-APPROVAL-EXPIRED", "aml-triage"), ("ALR-DENY-RATE", "complaint-triage")}
    m = FleetMetrics()
    for run in run_fleet(weakened(**{"ccb-assistant": {"handoff_contracts": False}}), tempfile.mkdtemp()).values():
        m.ingest(run, KEY)
    pages = [(a.rule, a.agent) for a in evaluate(m.snapshot(), metrics=m) if a.severity == "page"]
    assert pages == [("ALR-LEAK", "ccb-assistant")]


def test_alert_aggregations():
    snap = {"agent.tool.calls": [{"attributes": {"agent": "x", "outcome": "allowed"}, "value": 6},
                                 {"attributes": {"agent": "x", "outcome": "denied"}, "value": 4}],
            "agent.cost.usd": [{"attributes": {"agent": "x"}, "value": 1.5}],
            "agent.runs": [{"attributes": {"agent": "x"}, "value": 2}],
            "agent.approvals": [{"attributes": {"agent": "x", "status": "approved"}, "value": 3}]}
    fired = {a.rule: a.value for a in evaluate(snap, load_rules())}
    assert fired == {"ALR-DENY-RATE": 0.4, "ALR-COST": 0.75}


def test_scorecard_proposes_a_score_and_gates_on_critical_items():
    tested = {i["id"] for i in load_rubric()["items"]} - {"1.4", "2.1", "2.4", "2.5", "2.6", "3.3", "3.4", "3.5",
                                                          "4.4", "5.2", "5.6", "7.5", "7.6"}
    results = {"results": [{"test": f"t{c}", "controls": [c], "agent": None, "outcome": "passed"} for c in tested]}
    card = score(results)
    assert (card.score, card.rating, card.critical_met) == (36, "Audit-ready", True)
    assert {i.id for i in card.items if i.status == "missing"} == {"1.4", "2.6", "3.3", "3.5"}
    unsigned = {k: ({**v, "reviewer": ""} if k == "2.1" else v) for k, v in load_attestations().items()}
    assert next(i for i in score(results, unsigned).items if i.id == "2.1").status == "missing"   # no reviewer: not evidence
    results["results"][0]["outcome"] = "failed"
    worse = score({"results": [r if r["controls"] != ["2.2"] else {**r, "outcome": "failed"} for r in results["results"]]})
    assert worse.rating == "Not production-ready" and not worse.critical_met


def test_manifest_detects_edits_additions_and_deletions(tmp_path):
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.md").write_text("# b")
    manifest = sign_manifest(tmp_path, b"k")
    assert set(manifest["files"]) == {"a.json", "sub/b.md"} and verify_pack(tmp_path, b"k") == []
    assert verify_pack(tmp_path, b"wrong")[0].startswith("manifest signature does not verify")
    (tmp_path / "a.json").write_text('{"edited": true}')
    (tmp_path / "sub" / "b.md").unlink()
    (tmp_path / "c.txt").write_text("late")
    assert set(verify_pack(tmp_path, b"k")) == {"modified: a.json", "missing: sub/b.md", "added after signing: c.txt"}


# ---- Acceptance criteria ----------------------------------------------------------------------------------------
def test_ac1_suite_passes_and_a_seeded_regression_fails_the_build(tmp_path):
    ok = pytest_run("compliance", f"--compliance-results={tmp_path / 'ok.json'}")
    assert ok.returncode == 0, ok.stdout[-800:]
    doc = json.loads((tmp_path / "ok.json").read_text())
    assert len({c for r in doc["results"] for c in r["controls"]}) >= 25 and doc["fingerprints"]
    bad = pytest_run("compliance", f"--compliance-results={tmp_path / 'bad.json'}",
                     env={"FLEET_FILE": str(seeded("masking", tmp_path))})
    assert bad.returncode == 1
    failed = {c for r in json.loads((tmp_path / "bad.json").read_text())["results"] if r["outcome"] == "failed"
              for c in r["controls"]}
    assert {"2.2", "2.3", "7.4"} <= failed


def test_ac2_dashboard_shows_deny_pii_and_approval_metrics(fleet_metrics):
    snap = fleet_metrics.snapshot()
    page = render_dashboard(snap, evaluate(snap, metrics=fleet_metrics), metrics=fleet_metrics,
                            agents=[a.name for a in load_fleet().agents])
    for label in ("Policy denials", "PII masked before logging", "Approvals decided / expired", "Deny rate",
                  "Approval p95 (h)", "ALR-DENY-RATE", "COM-001"):
        assert label in page, label


def test_ac3_evidence_pack_in_one_command(tmp_path):
    out = tmp_path / "pack"
    proc = subprocess.run([sys.executable, "assure.py", "--out", str(out)], cwd=IMPL, env=ENV, capture_output=True,
                          text=True)
    assert proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-800:]
    summary = json.loads(proc.stdout[:proc.stdout.rindex("}") + 1])
    assert summary["verified"] and summary["suite_passed"] and summary["rating"] == "Audit-ready"
    for name in ("scorecard.md", "control-crosswalk.md", "dashboard.html", "compliance-results.json",
                 "redteam-report.json", "change-control.json", "audit-verification.json", "manifest.sig"):
        assert (out / name).exists(), name
    assert verify_pack(out, KEY) == []


def test_ac3_strict_mode_blocks_a_regressed_fleet(tmp_path):
    proc = subprocess.run([sys.executable, "assure.py", "--out", str(tmp_path / "pack"), "--strict",
                           "--fleet", str(seeded("contract", tmp_path))], cwd=IMPL, env=ENV, capture_output=True, text=True)
    assert proc.returncode == 1
    alerts = json.loads((tmp_path / "pack" / "alerts.json").read_text())
    assert ("ALR-LEAK", "ccb-assistant", "page") in {(a["rule"], a["agent"], a["severity"]) for a in alerts}
