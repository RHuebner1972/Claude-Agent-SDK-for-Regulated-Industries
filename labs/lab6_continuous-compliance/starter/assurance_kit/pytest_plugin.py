"""pytest plugin: compliance tests as executable controls (rubric 7.1).

Tag each test with the rubric item(s) it evidences and the agent it checks:

    @pytest.mark.control("2.2", agent="pa-reviewer")
    def test_no_phi_in_audit_log(fleet_runs): ...

At the end of the run the plugin writes compliance-results.json: which controls were tested, against which
agent fingerprints, with what outcome. CI keeps that file as evidence; the evidence pack scores the rubric from it.

    pytest compliance --compliance-results=compliance-results.json     (compliance/conftest.py loads the plugin)
"""
from __future__ import annotations

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

import pytest

RESULTS: list[dict] = []


def pytest_addoption(parser):
    parser.addoption("--compliance-results", default="compliance-results.json",
                     help="where to write the control-by-control results (JSON)")


def pytest_configure(config):
    config.addinivalue_line("markers", "control(*ids, agent=None): rubric item(s) this test evidences")
    config._compliance_started = datetime.now(timezone.utc)
    RESULTS.clear()


def _controls(item) -> tuple[list[str], str | None]:
    ids, agent = [], None
    for mark in item.iter_markers(name="control"):
        ids += [str(i) for i in mark.args]
        agent = agent or mark.kwargs.get("agent")
    if agent is None and hasattr(item, "callspec"):          # parametrized over agents: use the agent's name
        agent = item.callspec.params.get("name")
    return ids, agent


def _message(report) -> str:
    crash = getattr(report.longrepr, "reprcrash", None)
    text = crash.message if crash is not None else str(report.longrepr).splitlines()[-1]
    return " ".join(text.split())[:300]


def result_for(item, report) -> dict | None:
    # TODO 1: turn one test report into a control result (or None).
    # ids, agent = _controls(item)  (rubric items from @pytest.mark.control, agent from the marker or the
    # parametrized "name"). Return None if the test has no control ids.
    # Record the CALL phase; also record a failed SETUP (a broken fixture means the control wasn't tested):
    #     report.when == "call" or (report.when == "setup" and report.outcome != "passed")   otherwise None.
    # Return {"test": item.nodeid, "controls": sorted(set(ids)), "agent": agent, "outcome": report.outcome,
    #         "duration_s": round(report.duration, 3), "message": _message(report) if report.failed else ""}
    raise NotImplementedError("Lab 6: result_for")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    entry = result_for(item, outcome.get_result())
    if entry:
        RESULTS.append(entry)


def pytest_sessionfinish(session, exitstatus):
    config = session.config
    if getattr(config, "workerinput", None) is not None:      # xdist worker: the controller writes the file
        return
    try:
        from .fleet import load_fleet
        fleet = load_fleet()
        fingerprints, manifest = fleet.fingerprints(), fleet.path
    except Exception as exc:                                  # a broken manifest is itself a finding
        fingerprints, manifest = {}, f"unloadable: {exc}"
    doc = {"schema": "sentinel.compliance-results/1",
           "started": config._compliance_started.isoformat(), "finished": datetime.now(timezone.utc).isoformat(),
           "commit": os.getenv("GITHUB_SHA", "local"), "ref": os.getenv("GITHUB_REF", "local"),
           "python": platform.python_version(), "fleet_manifest": manifest, "fingerprints": fingerprints,
           "exit_status": int(exitstatus), "results": RESULTS}
    path = Path(config.getoption("--compliance-results"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1), encoding="utf-8")
