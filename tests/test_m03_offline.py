"""Offline tests for Module 3 code (no API key needed). Run: uv run pytest tests/test_m03_offline.py"""
import asyncio
import os
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
LAB = REPO / "labs" / "lab1_sox-audit-trail"
SIBLINGS = ("audit_models", "audit_hooks", "ledger_tools", "models", "tools")
L02 = LESSONS / "M03-L02_anatomy-of-an-agent-audit-event-the" / "final"
L03 = LESSONS / "M03-L03_hooks-as-the-audit-backbone" / "final"
L04 = LESSONS / "M03-L04_correlation-ids-sessions-and" / "final"
L05 = LESSONS / "M03-L05_tamper-evidence-hash-chaining-signing" / "final"


def load(path: Path, name: str):
    for m in SIBLINGS:
        sys.modules.pop(m, None)
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(path.parent))


def test_lesson_model_copies_match_the_toolkit():
    reference = (REPO / "src/sentinel/audit/models.py").read_text()
    assert (L02 / "audit_models.py").read_text() == reference
    assert (L03 / "audit_models.py").read_text() == reference


def test_lab_solution_matches_the_toolkit():
    for name in ("models", "hashing", "redact", "store", "hooks", "simulate"):
        assert (LAB / "solution/audit_trail" / f"{name}.py").read_text() == (REPO / "src/sentinel/audit" / f"{name}.py").read_text(), name


def test_l02_demo_rejects_every_bad_event(capsys):
    load(L02 / "demo_events.py", "m03_demo_events").main()
    out = capsys.readouterr().out
    assert out.count("REJECTED") == 4 and "ACCEPTED" not in out and '"authority": "Policy rule 1"' in out


def test_l03_simple_hooks_log_a_full_run(tmp_path):
    hooks_mod = load(L03 / "audit_hooks.py", "m03_audit_hooks")
    models = sys.modules["audit_models"]
    from sentinel.audit.simulate import simulate_ledger_review
    log = hooks_mod.SimpleAuditLog(tmp_path / "audit.jsonl", agent=models.AgentInfo(name="LedgerBot", version="1.3.0", model="m",
                                                                                                  prompt_version="p1", policy_version="q1"),
                                   on_behalf_of="j.chen", correlation_id="run-1")
    asyncio.run(simulate_ledger_review(log, entries=["JE-1003", "JE-1010"]))
    types = [json.loads(l)["event_type"] for l in log.path.read_text().splitlines()]
    assert types[0] == "prompt.submitted" and types[-1] == "run.completed"
    assert {"tool.requested", "tool.completed", "tool.denied", "agent.stopped"} <= set(types)
    assert set(log.sdk_hooks()) == {"UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}


def test_l03_record_recommendation_propagates_correlation_id(tmp_path, monkeypatch):
    tools = load(L03 / "ledger_tools.py", "m03_ledger_tools")
    monkeypatch.setattr(tools, "WORKSPACE", tmp_path)
    monkeypatch.setattr(tools, "RECOMMENDATIONS", tmp_path / "recommendations.jsonl")
    tools.RUN["correlation_id"] = "run-abc"
    args = {"entry_id": "JE-1003", "recommendation": "escalate", "approver_required": "Controller",
            "rationale": "At or above $50,000", "policy_rule": "Policy rule 1"}
    asyncio.run(tools.record_recommendation.handler(args))
    row = json.loads((tmp_path / "recommendations.jsonl").read_text())
    assert row["correlation_id"] == "run-abc"
    assert "mcp__ledger__get_vendor_banking" not in tools.LEDGERBOT_ALLOWED


def test_l04_pairs_requests_with_outcomes(tmp_path, capsys):
    mod = load(L04 / "correlate.py", "m03_correlate")
    path = tmp_path / "audit.jsonl"
    asyncio.run(mod.make_sample(path))
    calls = mod.pair_tool_calls(mod.load(path))
    denied = [tid for tid, pair in calls.items() if "tool.denied" in pair]
    assert len(denied) == 1 and calls[denied[0]]["tool.requested"]["tool_name"].endswith("get_vendor_banking")
    mod.report(mod.load(path))
    assert "DENIED" in capsys.readouterr().out


def test_l05_tamper_lab_shows_which_defence_catches_what(capsys):
    load(L05 / "tamper_lab.py", "m03_tamper_lab").main()
    rows = {line[:28].strip(): line for line in capsys.readouterr().out.splitlines() if line[:2] in ("1.", "2.", "3.", "4.")}
    assert "CAUGHT         CAUGHT" in rows["1. edit a field"]
    assert "CAUGHT         CAUGHT" in rows["2. edit + rehash"]
    assert "missed         CAUGHT" in rows["3. rewrite whole chain"]
    assert "missed         CAUGHT" in rows["4. delete the tail"]


def test_cli_exit_codes():
    env = {**os.environ, "PYTHONPATH": str(REPO / "src"), "AUDIT_HMAC_KEY": "course-demo-key"}
    ok = subprocess.run([sys.executable, "-m", "sentinel.audit", "verify", str(LAB / "data/sample_run/audit.jsonl")],
                        env=env, capture_output=True, text=True)
    bad = subprocess.run([sys.executable, "-m", "sentinel.audit", "verify", str(LAB / "data/suspicious/audit.jsonl")],
                         env=env, capture_output=True, text=True)
    assert ok.returncode == 0 and "VERIFIED" in ok.stdout
    assert bad.returncode == 1 and "rewritten" in bad.stdout
