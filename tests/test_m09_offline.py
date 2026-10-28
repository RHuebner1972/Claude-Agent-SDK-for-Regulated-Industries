"""Offline tests for Module 9 code (no API key needed). Run: uv run pytest tests/test_m09_offline.py"""
import contextlib
import io
import runpy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from sentinel.evidence import (RegulatoryMap, ReviewSession, apply_reviews, coverage, lint, load_map,
                               load_session, matrix, render_trace, score, signoff_md, trace)
from sentinel.evidence.mapping import MAP_PATH
from sentinel.monitoring import load_fleet

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
# The rubric items the fleet compliance suite tests (M08); the rest are attested or planned.
TESTED = ["1.1", "1.2", "1.3", "1.5", "1.6", "2.2", "2.3", "3.1", "3.2", "4.1", "4.2", "4.3", "4.5", "4.6",
          "5.1", "5.3", "5.4", "5.5", "6.1", "6.2", "6.3", "6.4", "6.5", "7.1", "7.2", "7.3", "7.4"]


def _results(fail: str | None = None, drop: str | None = None) -> dict:
    return {"results": [{"test": f"compliance/test_x.py::test_{i.replace('.', '_')}", "controls": [i],
                         "agent": None, "outcome": "failed" if i == fail else "passed"}
                        for i in TESTED if i != drop]}


def _row(rows, id_):
    return next(r for r in rows if r.mapping.id == id_)


def test_the_map_loads_lints_clean_and_scopes_every_fleet_agent():
    rmap = load_map()
    assert len(rmap.mappings) >= 60 and len(rmap.regimes) >= 15
    assert lint(rmap, fleet_agents=[a.name for a in load_fleet().agents]) == []
    grid = matrix(rmap)
    assert all(grid[p] for p in grid), "every pillar has at least one clause"
    assert "BANKING" in rmap.regimes_for("aml-triage") and "FDA-AI" not in rmap.regimes_for("complaint-triage")
    with pytest.raises(KeyError):
        rmap.regimes_for("new-agent")                  # unscoped agents are a decision, not a default


def test_rows_must_say_who_answers_and_regimes_must_exist():
    data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
    row = next(m for m in data["mappings"] if not m["rubric"])
    row.pop("owner")
    with pytest.raises(ValidationError, match="must name an owner"):
        RegulatoryMap.model_validate(data)
    data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
    data["applicability"]["aml-triage"].append("BASEL-IV")
    with pytest.raises(ValidationError, match="undeclared regimes"):
        RegulatoryMap.model_validate(data)
    data = yaml.safe_load(MAP_PATH.read_text(encoding="utf-8"))
    data["mappings"][0]["code"] = ["src/sentinel/audit/renamed.py"]
    assert lint(RegulatoryMap.model_validate(data)) == [f"{data['mappings'][0]['id']}: code path not found: "
                                                        "src/sentinel/audit/renamed.py"]


def test_trace_status_is_the_weakest_link():
    rmap, res = load_map(), _results()
    rows = trace(rmap, score(res), res)
    assert _row(rows, "HIPAA-164.312(b)").how == "met (tested)"
    assert _row(rows, "HIPAA-164.316(b)(2)").status == "gap"            # 1.4 is planned for Module 10
    assert _row(rows, "PART11-11.10(e)").status == "gap"                # 1.1 and 1.3 met, 1.4 not: still a gap
    assert _row(rows, "GLBA-314.4(c)(3)").status == "owned elsewhere"
    assert _row(rows, "BANK-36H").how == "met (attested)"
    failing = trace(rmap, score(_results(fail="2.2")), _results(fail="2.2"))
    assert _row(failing, "GDPR-5(1)(c)-25").status == "failing"


def test_tests_come_from_results_so_a_deleted_test_becomes_a_gap():
    rmap = load_map()
    rows = trace(rmap, score(_results()), _results())
    assert _row(rows, "HIPAA-164.502(b)").tests == ["PASSED: compliance/test_x.py::test_2_3"]
    dropped = _results(drop="2.3")
    assert _row(trace(rmap, score(dropped), dropped), "HIPAA-164.502(b)").status == "gap"


def test_trace_for_an_agent_keeps_only_its_regimes_and_tests():
    rmap = load_map()
    res = {"results": [{"test": "t[aml-triage]", "controls": ["3.1"], "agent": "aml-triage", "outcome": "passed"},
                       {"test": "t[ledgerbot]", "controls": ["3.1"], "agent": "ledgerbot", "outcome": "passed"}]}
    rows = trace(rmap, score(_results()), res, agent="aml-triage")
    assert {r.mapping.regime for r in rows} == set(rmap.regimes_for("aml-triage"))
    assert _row(rows, "NYDFS-500.7").tests == ["PASSED: t[aml-triage]"]
    md = render_trace(rmap, rows)
    assert "## BANKING" in md and "## HIPAA" not in md
    assert coverage(rows)["BANKING"]["gap"] == 1


def test_review_confirms_challenges_and_withholds_unreviewed_points():
    proposed = score(_results())
    assert (proposed.score, proposed.rating) == (36, "Audit-ready")
    session = load_session()
    confirmed = apply_reviews(proposed, session)
    assert (confirmed.score, confirmed.rating) == (35, "Conditionally ready")
    assert next(i for i in confirmed.items if i.id == "7.5").status == "challenged"
    page = signoff_md(proposed, confirmed, session)
    assert "36/40" in page and "35/40" in page and "BANK-36H" in page and "remediation plan" in page
    partial = session.model_copy(update={"reviews": [r for r in session.reviews if r.item != "5.1"]})
    unreviewed = apply_reviews(proposed, partial)
    assert next(i for i in unreviewed.items if i.id == "5.1").status == "unconfirmed"
    assert unreviewed.rating == "Not production-ready"                  # 5.1 is critical: unconfirmed gates


def test_review_rules_independence_reasons_and_no_points_from_nothing():
    data = load_session().model_dump()
    own = {**data, "reviews": [{**data["reviews"][0], "reviewer": data["author"]}]}
    with pytest.raises(ValidationError, match="author can't review"):
        ReviewSession.model_validate(own)
    lazy = {**data, "reviews": [{**data["reviews"][0], "decision": "challenge", "note": "no"}]}
    with pytest.raises(ValidationError, match="must say what evidence is missing"):
        ReviewSession.model_validate(lazy)
    twice = {**data, "reviews": [data["reviews"][0], data["reviews"][0]]}
    with pytest.raises(ValidationError, match="one decision per item"):
        ReviewSession.model_validate(twice)
    planned = ReviewSession.model_validate({**data, "reviews": [{**data["reviews"][0], "item": "1.4"}]})
    assert next(i for i in apply_reviews(score(_results()), planned).items if i.id == "1.4").points == 0


def test_review_demo_runs():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(str(next(LESSONS.glob("M09-L07*")) / "final" / "rubric_review_demo.py"), run_name="__main__")
    out = buf.getvalue()
    assert "proposed 36/40, Audit-ready" in out and "CONFIRMED: 35/40, Conditionally ready" in out
    assert out.count("refused") == 2
