"""Offline tests for Module 6 code (no API key needed). Run: uv run pytest tests/test_m06_offline.py"""
import asyncio
import importlib.util
import sys
import tempfile
from pathlib import Path

from sentinel.approvals import ApprovalQueue, FixedClock, review_quality
from sentinel.approvals.aml_tools import AlertStore, oversight_policy, staff_signer

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
LAB = REPO / "labs" / "lab4_human-approval"


def load(path: Path, name: str):
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(path.parent))


def test_lab_solution_matches_the_toolkit():
    for name in ("models.py", "records.py", "sod.py", "queue.py", "gate.py", "aml_tools.py", "simulate.py",
                 "metrics.py", "killswitch.py", "policies/oversight.yaml"):
        assert (LAB / "solution/approval_desk" / name).read_text() == (REPO / "src/sentinel/approvals" / name).read_text(), name


def test_oversight_policy_loads_and_classifies_every_tool():
    policy, version = oversight_policy()
    assert version.startswith("sha256:")
    assert {r.tool: r.oversight for r in policy.rules}["recommend_sar"] == "in_the_loop"
    assert policy.rule_for("recommend_sar").approvals_required == 2


def test_l03_can_use_tool_waits_and_never_defaults_to_yes(capsys):
    asyncio.run(load(LESSONS / "M06-L03_implementing-approvals-with-can-use/final/gate_demo.py", "m06_gate").main())
    out = capsys.readouterr().out
    assert "PermissionResultAllow" in out and "APPROVAL-REJECTED" in out and "APPROVAL-TIMEOUT" in out
    assert "Record changes so far: ['ALR-5007: note added']" in out


def test_l04_defer_persist_resume(capsys):
    asyncio.run(load(LESSONS / "M06-L04_async-approval-queues-pause-persist-and/final/async_queue_demo.py", "m06_async").main())
    out = capsys.readouterr().out
    assert "stop_reason=tool_deferred" in out and "['pending', 'approved', 'consumed']" in out


def test_l05_sod_refusals(capsys):
    load(LESSONS / "M06-L05_segregation-of-duties-and-the-four-eyes/final/sod_demo.py", "m06_sod").main()
    out = capsys.readouterr().out
    for code in ("SOD-001", "SOD-002", "SOD-003", "SOD-004", "SOD-005", "SOD-006"):
        assert code in out
    assert "2/2, status approved" in out


def test_review_quality_flags_rubber_stamping():
    clock = FixedClock(step_seconds=2)
    q = ApprovalQueue(Path(tempfile.mkdtemp()) / "q.json", policy=oversight_policy()[0], signing_key=b"k", clock=clock)
    store = AlertStore()
    for i in range(6):
        args = {"alert_id": "ALR-5002", "disposition": "false_positive", "rationale": f"Payroll run number {i} matches."}
        r = q.submit("close_alert", args, requested_by="j.rivera", requester_role="aml_analyst", agent="AML-Triage@1.0.0",
                     evidence=store.evidence("close_alert", args))
        q.sign(r.request_id, staff_signer("m.chen"), "approve", "Looks fine, approved.")
    flags = review_quality(q)["m.chen"]["flags"]
    assert "approves everything" in flags and "repeats the same reason" in flags and any("median" in f for f in flags)
