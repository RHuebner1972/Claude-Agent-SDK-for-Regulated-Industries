"""Offline checks for the M02 assignment solution (no API key needed).

    uv run pytest tests/test_m02_assignment.py
"""
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOLUTION = REPO / "lessons/M02-ASSIGNMENT_lock-down-ledgerbot/solution/locked_agent.py"


def load():
    spec = importlib.util.spec_from_file_location("locked_agent_solution", SOLUTION)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["locked_agent_solution"] = mod
    spec.loader.exec_module(mod)
    return mod


def payload(result):
    return json.loads(result["content"][0]["text"])


def test_options_are_least_privilege():
    from course_data import MODEL
    o = load().options
    assert o.model == MODEL
    assert o.tools == []
    assert o.setting_sources == []
    assert o.strict_mcp_config is True
    assert o.permission_mode == "dontAsk"
    assert o.max_turns and o.max_budget_usd
    assert set(o.mcp_servers) == {"ledger"}


def test_only_read_only_tools_are_exposed_and_allowed():
    m = load()
    names = {t.name for t in m.TOOLS}
    assert not names & {"approve_entry", "reject_entry", "send_email"}
    assert all(t.annotations.read_only_hint for t in m.TOOLS)
    assert set(m.options.allowed_tools) == {f"mcp__ledger__{n}" for n in names}


def test_vendor_tool_returns_minimum_necessary():
    m = load()
    v = payload(asyncio.run(m.get_vendor_summary.handler({"vendor_id": "V-201"})))
    assert set(v) == {"vendor_id", "name"}
    missing = asyncio.run(m.get_vendor_summary.handler({"vendor_id": "V-999"}))
    assert missing["is_error"] is True


def test_listing_has_no_vendor_bank_data():
    m = load()
    text = json.dumps(payload(asyncio.run(m.list_pending_entries.handler({}))))
    for secret in ("4417002291", "84-2917365", "bank_account", "tax_id"):
        assert secret not in text
