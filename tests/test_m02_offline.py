"""Offline tests for Module 2 code: no API key or network needed. Run: uv run pytest tests/test_m02_offline.py"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
SIBLINGS = ("models", "typed_tools", "ledger_tools", "tools")


def load(path: Path, name: str):
    """Import a lesson file with its own folder first on sys.path (lesson folders stand alone)."""
    for m in SIBLINGS:
        sys.modules.pop(m, None)
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod          # needed for Pydantic forward references
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(path.parent))


def run(coro):
    return asyncio.run(coro)


def text(result) -> str:
    return result["content"][0]["text"]


# ---------------------------------------------------------------- L03 options
def test_locked_down_options_are_least_privilege():
    m = load(LESSONS / "M02-L03_claudeagentoptions-as-your-first/final/options_tour.py", "options_tour")
    o = m.LOCKED_DOWN
    assert o.tools == [] and o.allowed_tools == [] and o.setting_sources == []
    assert o.permission_mode == "dontAsk" and o.strict_mcp_config is True
    assert o.max_turns and o.max_budget_usd


# ---------------------------------------------------------------- L04 tools
def test_ledger_tools_read_only_and_named():
    m = load(LESSONS / "M02-L04_custom-tools-with-tool-and-in-process/final/ledger_tools.py", "ledger_tools_l04")
    assert m.LEDGER_TOOL_NAMES == ["mcp__ledger__list_pending_entries", "mcp__ledger__get_journal_entry", "mcp__ledger__get_gl_account"]
    rows = json.loads(text(run(m.list_pending_entries.handler({}))))
    assert len(rows) == 10 and set(rows[0]) == {"entry_id", "date", "amount", "description"}
    missing = run(m.get_journal_entry.handler({"entry_id": "JE-9999"}))
    assert missing["is_error"] is True
    assert all(t.annotations.read_only_hint for t in m.TOOLS)


# ---------------------------------------------------------------- L05 models + typed tool
def test_all_synthetic_entries_validate():
    m = load(LESSONS / "M02-L05_pydantic-everywhere-typed-tool-inputs/final/models.py", "models_l05")
    from course_data import journal_entries
    for raw in journal_entries():
        m.JournalEntry.model_validate(raw)


def test_models_reject_bad_data():
    m = load(LESSONS / "M02-L05_pydantic-everywhere-typed-tool-inputs/final/models.py", "models_l05b")
    from course_data import journal_entries
    bad = dict(journal_entries()[0])
    bad["lines"] = [{"account": "6200", "debit": 100, "credit": 0}, {"account": "2100", "debit": 0, "credit": 99}]
    with pytest.raises(ValidationError):
        m.JournalEntry.model_validate(bad)
    with pytest.raises(ValidationError):
        m.EntryLookup.model_validate({"entry_id": "1003"})
    with pytest.raises(ValidationError):
        m.EntryLookup.model_validate({"entry_id": "JE-1003", "extra": "x"})
    with pytest.raises(ValidationError):
        m.ReviewDecision.model_validate({"entry_id": "JE-1003", "decision": "approve", "required_approver": "none",
                                         "policy_rules_applied": [1], "reasons": ["  "]})


def test_typed_tool_validates_input():
    m = load(LESSONS / "M02-L05_pydantic-everywhere-typed-tool-inputs/final/typed_tools.py", "typed_tools_l05")
    ok = run(m.get_journal_entry.handler({"entry_id": "JE-1003"}))
    assert not ok.get("is_error") and "JE-1003" in text(ok)
    for bad in ({"entry_id": "1003"}, {"entry_id": "JE-1003; DROP TABLE"}, {"entry_id": "JE-9999"}):
        assert run(m.get_journal_entry.handler(bad))["is_error"] is True


# ---------------------------------------------------------------- L06 structured output checks
def test_business_checks_fail_closed():
    m = load(LESSONS / "M02-L06_structured-outputs-and-validation-on/final/structured_review.py", "structured_review")
    D = m.ReviewDecision
    assert m.business_checks(D(entry_id="JE-1003", decision="approve", required_approver="none",
                               policy_rules_applied=[1], reasons=["looks fine"]))
    assert m.business_checks(D(entry_id="JE-1009", decision="approve", required_approver="none",
                               policy_rules_applied=[2], reasons=["small"]))
    assert not m.business_checks(D(entry_id="JE-1003", decision="escalate", required_approver="controller",
                                   policy_rules_applied=[1], reasons=["over threshold"]))
    schema = m.options.output_format["schema"]
    assert schema["type"] == "object" and "decision" in schema["properties"]


# ---------------------------------------------------------------- baseline
def test_naive_baseline_has_its_documented_flaws(tmp_path, monkeypatch):
    t = load(REPO / "baseline/naive_ledger_agent/tools.py", "naive_tools")
    for name in ("WORKSPACE",):
        monkeypatch.setattr(t, name, tmp_path)
    monkeypatch.setattr(t, "DEBUG_LOG", tmp_path / "naive_debug.log")
    monkeypatch.setattr(t, "DECISIONS", tmp_path / "decisions.jsonl")
    monkeypatch.setattr(t, "OUTBOX", tmp_path / "outbox.jsonl")
    vendor = json.loads(text(run(t.get_vendor.handler({"vendor_id": "V-201"}))))
    assert "bank_account" in vendor                         # flaw: returns bank details
    run(t.approve_entry.handler({"entry_id": "JE-1010", "comment": "controller cleared by phone"}))
    assert "JE-1010" in (tmp_path / "decisions.jsonl").read_text()   # flaw: no policy check
    assert "4417002291" in (tmp_path / "naive_debug.log").read_text()  # flaw: bank number in the log
    a = load(REPO / "baseline/naive_ledger_agent/agent.py", "naive_agent")
    assert a.options.permission_mode == "bypassPermissions" and a.options.max_turns is None


def test_inspect_run_flags_violations(tmp_path, monkeypatch, capsys):
    i = load(REPO / "baseline/naive_ledger_agent/inspect_run.py", "inspect_run")
    d = tmp_path / "decisions.jsonl"
    d.write_text("\n".join(json.dumps({"entry_id": e, "decision": "approve"}) for e in ("JE-1001", "JE-1003", "JE-1010")))
    monkeypatch.setattr(i, "DECISIONS", d)
    monkeypatch.setattr(i, "OUTBOX", tmp_path / "none.jsonl")
    monkeypatch.setattr(i, "DEBUG_LOG", tmp_path / "none.log")
    i.main()
    out = capsys.readouterr().out
    assert "Policy violations (approved when it shouldn't): 2" in out
