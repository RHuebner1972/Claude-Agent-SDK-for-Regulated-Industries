"""P1 Traceability: every agent's audit trail is complete, attributable, tamper-evident and replayable."""
import pytest

from sentinel.audit import AuditEvent, replay_decision, verify_log
from assurance_kit.runs import KEY

AGENTS = ["ledgerbot", "pa-reviewer", "complaint-triage", "aml-triage", "ccb-assistant"]


@pytest.mark.parametrize("name", AGENTS)
@pytest.mark.control("1.1")
def test_every_tool_call_is_logged_with_its_outcome(runs, name):
    events = runs[name].events()
    for e in events:
        AuditEvent.model_validate(e)                               # schema-valid, every line
    requested = {e["tool_use_id"] for e in events if e["event_type"] == "tool.requested"}
    finished = {e["tool_use_id"] for e in events if e["event_type"] in ("tool.completed", "tool.denied", "tool.failed")}
    assert requested and requested <= finished, f"{name}: tool calls with no outcome: {sorted(requested - finished)}"
    assert {"prompt.submitted", "run.completed"} <= {e["event_type"] for e in events}


@pytest.mark.parametrize("name", AGENTS)
@pytest.mark.control("1.2")
def test_every_event_is_attributable(runs, name):
    for e in runs[name].events():
        assert e["on_behalf_of"] and e["agent"]["name"] and e["session_id"] and e["correlation_id"], e["event_type"]


@pytest.mark.parametrize("name", AGENTS)
@pytest.mark.control("1.3")
def test_audit_logs_verify_with_signed_checkpoints(runs, name):
    for which, path in runs[name].logs.items():
        report = verify_log(path, KEY)
        assert report.ok, f"{name} {which}: {report.problems}"
        assert report.checkpoints_checked > 0, f"{name} {which}: no signed checkpoints (is audit_hmac off?)"


@pytest.mark.parametrize("name", AGENTS)
@pytest.mark.control("1.5")
def test_model_prompt_and_policy_versions_are_recorded(runs, fleet, name):
    agent = fleet.get(name)
    for e in runs[name].events():
        assert e["agent"]["model"] == agent.model and e["agent"]["prompt_version"] == agent.prompt_version
        assert e["agent"]["policy_version"]


@pytest.mark.control("1.6", agent="ledgerbot")
def test_a_decision_can_be_replayed_from_the_log_alone(runs):
    run = runs["ledgerbot"]
    report = replay_decision(run.events(), "JE-1006", verify_log(run.general_log, KEY))
    assert "VERIFIED" in report and "reject" in report.lower() and "Policy rule 3" in report
