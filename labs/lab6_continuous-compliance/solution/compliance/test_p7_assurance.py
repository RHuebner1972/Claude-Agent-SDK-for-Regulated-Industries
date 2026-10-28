"""P7 Continuous Assurance: the pipeline itself is under test."""
from pathlib import Path

import pytest
import yaml

from assurance_kit.alerts import load_rules
from assurance_kit.change import check_change_control, load_changes

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "compliance.yml"


@pytest.mark.control("7.1")
def test_ci_runs_the_suite_on_every_relevant_change():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = wf.get("on") or wf.get(True)                 # PyYAML reads a bare `on:` key as True
    for event in ("pull_request", "push"):
        assert "src/**" in triggers[event]["paths"], f"{event} must trigger on src/** (code, prompts, policies)"
    steps = " ".join(str(s.get("run", "")) for s in wf["jobs"]["compliance"]["steps"])
    assert "pytest compliance" in steps


@pytest.mark.control("7.2")
def test_red_team_runs_on_a_schedule_and_every_case_is_defended(redteam):
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert (wf.get("on") or wf.get(True)).get("schedule"), "no scheduled run"
    assert redteam.ok, [(r.id, r.observed) for r in redteam.results if not r.defended]
    assert set(redteam.by_category()) == {"injection", "exfiltration", "policy_evasion"}


@pytest.mark.control("7.3")
def test_alert_rules_cover_the_required_signals():
    metrics = {r.metric for r in load_rules()}
    for needed in ("agent.tool.calls", "agent.restricted_data.leaks", "agent.approval.latency", "agent.cost.usd",
                   "agent.errors"):
        assert needed in metrics, f"no alert on {needed}"


@pytest.mark.control("7.4", "4.6")
def test_every_running_configuration_is_an_approved_revalidated_change(fleet):
    findings = check_change_control(fleet, load_changes())
    assert not any(findings.values()), {k: v for k, v in findings.items() if v}
