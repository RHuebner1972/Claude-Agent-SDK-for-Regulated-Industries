"""Offline tests for Module 7 code (no API key needed). Run: uv run pytest tests/test_m07_offline.py"""
import asyncio
import contextlib
import io
import runpy
import tempfile
from pathlib import Path

from course_data import ecrs, programs
from sentinel.boundaries import BoundaryGuard, canaries_from, check_all, scan
from sentinel.boundaries.eng_tools import (EngineeringStore, agent_definitions, build_ccb_tools, build_eng_data_tools,
                                           card_set, full_name)
from sentinel.boundaries.simulate import GATED, SCENARIOS, run_scenario, run_script

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
LAB = REPO / "labs" / "lab5_data-boundaries"


def run_lesson(folder: str, script: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        runpy.run_path(str(next(LESSONS.glob(folder)) / "final" / script), run_name="__main__")
    return out.getvalue()


def test_lab_solution_matches_the_toolkit():
    for name in ("markings.py", "cards.py", "contracts.py", "guard.py", "routing.py", "residency.py", "eng_tools.py",
                 "simulate.py", "policies/agent_cards.yaml"):
        assert (LAB / "solution/boundary_kit" / name).read_text() == \
               (REPO / "src/sentinel/boundaries" / name).read_text(), name


def test_synthetic_defense_data_is_consistent():
    records = ecrs()
    assert {e["program"] for e in records} <= set(programs())
    controlled = [e for e in records if e["marking"] != "NONE"]
    assert controlled and all(e["export_control"] == "ITAR" for e in controlled)
    assert len(canaries_from(records)) == len(controlled)        # one canary per controlled ECR, none elsewhere
    assert not canaries_from(e for e in records if e["marking"] == "NONE")


def test_cards_load_pass_residency_and_generate_definitions():
    cards, version = card_set()
    assert version.startswith("sha256:") and cards.orchestrator == "ccb-orchestrator"
    assert check_all(cards) == {c.name: [] for c in cards.agents}
    defs = agent_definitions(cards)
    assert set(defs) == {"cleared-engineer-falcon"}
    assert defs["cleared-engineer-falcon"].tools == ["mcp__eng_data__get_ecr_technical",
                                                      "mcp__eng_data__get_drawing_notes"]


def test_three_scenarios_show_where_cui_goes():
    leaks = {k: run_scenario(k, tempfile.mkdtemp()).leaks() for k in SCENARIOS}
    assert leaks["naive"]["orchestrator context"] and leaks["naive"]["general audit log"]
    assert leaks["subagents"]["orchestrator context"] and leaks["subagents"]["general audit log"]
    assert leaks["gated"]["orchestrator context"] == [] and leaks["gated"]["general audit log"] == []
    assert leaks["gated"]["enclave audit log"]


def test_gated_script_fires_each_rule():
    cards, _ = card_set()
    store = EngineeringStore()
    guard = BoundaryGuard(cards, resolver=store.resolve, canaries=store.canaries())
    log = asyncio.run(run_script(build_ccb_tools(store) + build_eng_data_tools(store), GATED, guard=guard))
    assert sorted(s.message[:9] for s in log.steps if s.outcome == "denied") == \
        ["[BND-001]", "[BND-003]", "[BND-004]"]
    assert [h["ok"] for h in guard.handoffs] == [True, False]
    assert not any(c in "\n".join(log.seen) for c in store.canaries())
    assert store.schedule[0]["ecr_id"] == "ECR-4101"


def test_resolver_marks_only_technical_tools():
    store = EngineeringStore()
    assert store.resolve(full_name("get_ecr_technical"), {"ecr_id": "ECR-4101"})["marking"] == "CUI//SP-CTI"
    assert store.resolve("schedule_ccb_review", {"ecr_id": "ECR-4101"}) is None


def test_lesson_demos_run():
    l02 = run_lesson("M07-L02_*", "subagents_demo.py")
    assert "inherits EVERY tool" in l02 and "[BND-004]" in l02
    l04 = run_lesson("M07-L04_*", "isolation_demo.py")
    assert l04.count("LEAK") == 4 and "stripped=['technical_notes']" in l04
    l05 = run_lesson("M07-L05_*", "handoff_demo.py")
    assert l05.count("ok=True") == 3 and l05.count("ok=False") == 3
    rejected = l05.split("CUI SMUGGLED")[1].split("FREE TEXT")[0].split("receives:")[1]
    assert "2M8P" not in rejected


def test_scan_never_returns_values():
    text = "D-77812-3 rev F CANARY-CUI-7Q4K"
    assert all("77812" not in f and "7Q4K" not in f for f in scan(text, ["CANARY-CUI-7Q4K"]))
