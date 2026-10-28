"""Offline tests for Module 11 code (no API key needed). Run: uv run pytest tests/test_m11_offline.py"""
import contextlib
import io
import runpy
import shutil
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

import sentinel.governance as gov
from sentinel.evidence import apply_reviews, load_session, score
from sentinel.governance import (BOARD_QUESTIONS, Claim, Inventory, Raci, RiskRegister, Section, ValidationRecord,
                                 ValidationSet, board_brief, evidence_index, lint_all, lint_brief, lint_inventory,
                                 lint_raci, lint_register, lint_validations, load_governance, priority,
                                 required_assessments)
from sentinel.governance.brief import PROD_REVIEW
from sentinel.monitoring.change import ChangeLog

REPO = Path(__file__).resolve().parents[1]
LESSONS = REPO / "lessons"
ATTESTED = {"2.1", "2.4", "2.5", "3.4", "4.4", "5.2", "5.6", "7.5", "7.6"}     # not proven by a test


def _results() -> dict:
    """What the production suite reports when every tested control passes (as in M10)."""
    ids = [f"{p}.{n}" for p, count in zip(range(1, 8), (6, 6, 5, 6, 6, 5, 6)) for n in range(1, count + 1)]
    return {"results": [{"test": f"compliance/test_x.py::test_{i.replace('.', '_')}", "controls": [i],
                         "agent": None, "outcome": "passed"} for i in ids if i not in ATTESTED]}


@pytest.fixture(scope="module")
def g():
    return load_governance()


@pytest.fixture(scope="module")
def confirmed():
    return apply_reviews(score(_results()), load_session(PROD_REVIEW))


def test_production_records_are_clean_and_one_risk_rests_on_a_challenged_control(g, confirmed):
    assert confirmed.score == 39 and confirmed.rating == "Audit-ready"
    assert lint_all(g) == {"inventory": [], "risks": [], "validation": [], "raci": []}
    lints = lint_all(g, confirmed)
    assert lints["risks"] == [("RISK-007 FM-AML-02: rated assuming control 7.5, which is challenged after review; "
                               "re-rate or fix the control")]
    assert lints["validation"] == []                    # aml-triage is 'fit_with_conditions', naming the 7.5 fix


def test_inventory_catches_unregistered_ai_owner_conflicts_and_self_review(g):
    regimes = g.rmap.applicability
    rogue = g.fleet.agents[0].model_copy(update={"name": "marketing-drafts"})
    assert lint_inventory(g.inventory, g.fleet.model_copy(update={"agents": [*g.fleet.agents, rogue]}), regimes) == [
        "GOV-001 marketing-drafts: runs in the fleet but isn't in the AI inventory (unregistered AI)"]
    data = g.inventory.model_dump(mode="json")
    e = data["systems"]["pa-reviewer"]
    e["business_owner"] = e["assessments"][0]["reviewer"] = e["technical_owner"]
    e["assessments"] = [a for a in e["assessments"] if a["kind"] != "HIPAA-SRA"]
    codes = [p.split()[0] for p in lint_inventory(Inventory.model_validate(data), g.fleet, regimes)]
    assert codes == ["GOV-003", "GOV-004", "GOV-006"]
    data["systems"]["ghost"] = data["systems"].pop("ledgerbot")
    assert any(p.startswith("GOV-002 ghost") for p in lint_inventory(Inventory.model_validate(data), g.fleet, regimes))
    data["systems"]["aml-triage"]["business_owner"] = "BSA Officer"          # a role is not an owner
    with pytest.raises(ValidationError):
        Inventory.model_validate(data)


def test_assessments_follow_regimes_review_dates_and_model_changes(g):
    assert required_assessments(["HIPAA", "NIST-AI-RMF"]) == ["AIIA", "FMEA", "HIPAA-SRA"]
    assert required_assessments(["GDPR"]) == ["AIIA", "FMEA", "DPIA"]
    late = lint_inventory(g.inventory, g.fleet, g.rmap.applicability, as_of=date(2027, 10, 20))
    assert {p.split()[1] for p in late} == {"pa-reviewer:", "complaint-triage:", "aml-triage:", "ccb-assistant:"}
    assert all(p.startswith("GOV-005") for p in late)    # tier 4 is annual; ledgerbot (tier 3) is every two years
    # The M10 deployment changes (controls, configs) don't change what the agent is; a model change does.
    assert lint_inventory(g.inventory, g.fleet, g.rmap.applicability, changes=g.changes) == []
    rec = g.changes.records[-2].model_dump(mode="json")
    rec.update(id="CHG-0012", changed=["model"], approvals=[{"name": "D. Okafor", "role": "BSA Officer", "date": "2026-11-12"}])
    log = ChangeLog.model_validate({**g.changes.model_dump(mode="json"), "records": [rec]})
    assert [p[:28] for p in lint_inventory(g.inventory, g.fleet, g.rmap.applicability, changes=log)] == \
        ["GOV-009 aml-triage: CHG-0012"]


def test_priority_is_severity_first_not_rpn(g):
    assert priority(10, 3, 3) == "Medium" and priority(3, 7, 6) == "Low"          # RPN 90 vs 126
    assert priority(9, 4, 7) == "High" and priority(7, 6, 2) == "High" and priority(10, 1, 1) == "Low"
    rows = {f.id: f for f in g.register.for_agent("complaint-triage")}
    assert rows["FM-CT-04"].rpn > rows["FM-CT-01"].rpn
    assert [f.id for f in g.register.for_agent("complaint-triage")][0] == "FM-CT-01"


def test_register_rules_for_treatment_acceptance_and_controls(g):
    agents, ids = [a.name for a in g.fleet.agents], g.rubric_ids
    data = g.register.model_dump(mode="json")
    fm = {f["id"]: f for f in data["failure_modes"]}
    fm["FM-AML-02"]["action"] = None
    assert lint_register(RiskRegister.model_validate(data), agents, ids) == [
        "RISK-001 FM-AML-02: High priority with no action and no acceptance"]
    fm["FM-AML-02"]["acceptance"] = {"by": "D. Okafor, BSA Officer", "date": "2026-10-28", "expires": "2026-10-01",
                                     "rationale": "for the test only"}
    fm["FM-PA-01"]["acceptance"]["by"] = fm["FM-PA-01"]["owner"]
    fm["FM-LB-01"]["action"] = {"what": "Fuzzy-match vendor names", "owner": "D. Alvarez, Platform Engineering",
                                "due": "2026-09-30"}
    fm["FM-CT-01"]["controls"] = [{"rubric": "3.6", "how": "a rubric item that doesn't exist (P3 has five)"}]
    fm["FM-CCB-01"]["controls"] = []
    fm["FM-CT-03"]["acceptance"] = None
    codes = sorted(p.split()[0] + " " + p.split()[1] for p in lint_register(RiskRegister.model_validate(data), agents, ids))
    assert codes == sorted(["RISK-002 FM-AML-02:", "RISK-004 FM-AML-02:", "RISK-003 FM-PA-01:",
                            "RISK-005 FM-LB-01:", "RISK-006 FM-CT-01:", "RISK-009 FM-CCB-01:",
                            "RISK-010 FM-CT-03:"])
    data["failure_modes"].append(dict(fm["FM-PA-01"]))
    with pytest.raises(ValidationError, match="unique"):
        RiskRegister.model_validate(data)


def test_control_pattern_rejects_unknown_rubric_shapes():
    with pytest.raises(ValidationError):
        gov.risk.Control(rubric="9.9", how="a control that doesn't exist")


def test_validation_rules(g, confirmed):
    ids = g.rubric_ids
    data = g.validations.model_dump(mode="json")
    rec = {r["agent"]: r for r in data["records"]}
    rec["complaint-triage"]["activities"] = [a for a in rec["complaint-triage"]["activities"] if a["method"] != "scripted"]
    rec["complaint-triage"]["validator"] = rec["complaint-triage"]["developer"]
    rec["aml-triage"]["activities"] = [a for a in rec["aml-triage"]["activities"] if a["method"] != "effective_challenge"]
    rec["ledgerbot"]["activities"][0]["evidence"] = "rubric:8.1"
    data["records"] = [r for r in data["records"] if r["agent"] != "ccb-assistant"]
    codes = sorted(p.split()[0] for p in lint_validations(ValidationSet.model_validate(data), g.fleet, ids))
    assert codes == ["VAL-001", "VAL-002", "VAL-003", "VAL-006", "VAL-007"]
    data = g.validations.model_dump(mode="json")
    aml = next(r for r in data["records"] if r["agent"] == "aml-triage")
    aml["conclusion"], aml["conditions"] = "fit", []
    assert [p.split()[0] for p in lint_validations(ValidationSet.model_validate(data), g.fleet, ids, confirmed)] == ["VAL-005"]
    aml["conclusion"] = "fit_with_conditions"
    with pytest.raises(ValidationError, match="must list the conditions"):
        ValidationRecord.model_validate(aml)


def test_a_model_change_makes_the_validation_stale(g):
    upgraded = [a.model_copy(update={"model": "claude-opus-5-5"}) if a.name == "pa-reviewer" else a
                for a in g.fleet.agents]
    fleet = g.fleet.model_copy(update={"agents": upgraded})
    assert gov.status(g.validations.latest("pa-reviewer"), fleet) == "stale"
    assert [p[:20] for p in lint_validations(g.validations, fleet, g.rubric_ids)] == ["VAL-004 VAL-PA-001: "]


def test_raci_has_one_accountable_role_and_real_independence(g):
    assert lint_raci(g.raci) == []
    data = g.raci.model_dump(mode="json")
    acts = {a["id"]: a for a in data["activities"]}
    acts["validate"]["cells"]["eng"] = "R"
    acts["fmea"]["cells"]["comp"] = "A"
    acts["report"]["cells"]["audit"] = "R"
    acts["scope"]["cells"] = {"comp": "A"}
    acts["change"]["cells"]["legal"] = "C"
    codes = sorted(p.split()[0] + " " + p.split()[1] for p in lint_raci(Raci.model_validate(data)))
    assert codes == ["RACI-001 fmea:", "RACI-002 scope:", "RACI-003 validate:", "RACI-004 report:", "RACI-005 change:"]


def test_brief_cites_everything_and_keeps_other_tenants_out(g, confirmed):
    md, problems = board_brief(g, "Bayside Community Bank", confirmed, _results())
    assert problems == []
    assert "FM-AML-02" in md and "36-hour" in md and "39 of 40" in md and "Harborline" not in md
    assert md.count("| [") == len(evidence_index(g)) and "## If the committee asks" in md
    md, problems = board_brief(g, "Harborline Medical", confirmed, _results())
    assert problems == [] and "Bayside" not in md and "aml-triage" not in md
    assert "The reason concerns another agent on the platform" in md
    with pytest.raises(KeyError):
        board_brief(g, "Nobody Inc", confirmed)


def test_brief_lint_rejects_unbacked_and_absolute_claims(g):
    bad = [Section("x", [Claim("The agent is fully compliant."), Claim("Validated by the vendor.", ["vendor"]),
                         Claim("Risk is guaranteed to be low.", ["risks"])])]
    codes = [p.split()[0] for p in lint_brief(bad, evidence_index(g))]
    assert codes == ["BRIEF-001", "BRIEF-002", "BRIEF-003", "BRIEF-002"]
    assert {k for _, _, k in BOARD_QUESTIONS} - {"pack"} <= set(evidence_index(g))


def _run(path: Path, monkeypatch, argv=()) -> str:
    monkeypatch.setattr(gov, "confirmed_scorecard",
                        lambda g, results=None, workdir=None: (_results(), apply_reviews(score(_results()), load_session(PROD_REVIEW))))
    monkeypatch.setattr(sys, "argv", [str(path), *argv])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(str(path), run_name="__main__")
    return buf.getvalue()


@pytest.mark.parametrize("demo, expect", [
    ("M11-L01_ai-system-inventory-and-agent-cards/final/inventory_demo.py", ["GOV-001", "GOV-009", "# Agent card"]),
    ("M11-L02_risk-and-impact-assessments-dpia-ai/final/fmea_demo.py", ["RISK-007 FM-AML-02", "RISK-002", "DPIA"]),
    ("M11-L03_validation-in-gxp-and-quality-systems/final/validation_demo.py", ["VAL-002", "VAL-003", "VAL-004", "VAL-005"]),
    ("M11-L05_presenting-to-the-board-here-is-how-our/final/board_brief_demo.py", ["BRIEF-001", "every claim cited"]),
])
def test_lesson_demos_run(demo, expect, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    out = _run(LESSONS / demo, monkeypatch)
    for e in expect:
        assert e in out, e


SOLUTION = {
    "changes.yaml": '''  - id: CHG-0012
    agent: pa-reviewer
    summary: "Model upgrade: claude-sonnet-5-5 to claude-opus-5-5"
    category: significant
    changed: [model]
    to_fingerprint: "{fp}"
    revalidation: {{suite: compliance@m11, result: passed, redteam: 13/13 defended, date: "2026-11-04"}}
    approvals:
      - {{name: D. Reyes, role: Utilization Management director, date: "2026-11-05"}}
      - {{name: L. Brandt, role: Privacy Officer, date: "2026-11-05"}}
    status: approved
''',
    "validations.yaml": '''
  - id: VAL-PA-002
    agent: pa-reviewer
    framework: RISK-BASED
    intended_use: "Summarize a prior authorization request against published criteria for a clinician."
    process_risk: high
    developer: "D. Alvarez, Platform Engineering"
    validator: "K. Ito, Clinical AI Governance"
    validated_fingerprint: "{fp}"
    date: "2026-11-04"
    activities:
      - {{method: scripted, what: "Compliance suite incl. PHI masking", evidence: "rubric:2.2", result: pass}}
    conclusion: fit_with_conditions
    conditions: ["Fix FM-PA-03 by 2026-12-15"]
''',
    "risk_register.yaml": '''  - id: FM-PA-03
    agent: pa-reviewer
    step: "Summarize the request"
    failure_mode: "Summarizes another open request for the same member"
    effect: "The clinician reviews the wrong clinical picture"
    cause: "Several open requests for one member"
    controls:
      - {{rubric: "5.2", how: "The reviewer sees the request ID next to the summary"}}
    s: 8
    o: 4
    d: 5
    owner: "D. Reyes, Utilization Management director"
    action: {{what: "Make the tool take the request ID", owner: "D. Alvarez, Platform Engineering", due: "2026-12-15"}}
''',
}


def test_assignment_checker_passes_only_when_every_task_is_done(monkeypatch, tmp_path):
    practice = tmp_path / "m11"
    practice.mkdir()
    src = REPO / "src" / "sentinel"
    for f in ("monitoring/policies/fleet-prod.yaml", "monitoring/policies/changes.yaml",
              "governance/policies/inventory.yaml", "governance/policies/risk_register.yaml",
              "governance/policies/validations.yaml"):
        shutil.copy(src / f, practice)
    checker = LESSONS / "M11-ASSIGNMENT_board-brief/check_board_brief.py"
    assert "4 check(s) to fix" in _run(checker, monkeypatch, [str(practice)])
    fleet = practice / "fleet-prod.yaml"
    text = fleet.read_text()
    head, tail = text.split("name: pa-reviewer", 1)
    fleet.write_text(head + "name: pa-reviewer" + tail.replace("claude-sonnet-5-5", "claude-opus-5-5", 1))
    fp = gov.load_governance(fleet).fleet.get("pa-reviewer").fingerprint()
    out = _run(checker, monkeypatch, [str(practice)])
    assert "VAL-004" in out and "no approved change record" in out
    for name, snippet in SOLUTION.items():
        with open(practice / name, "a", encoding="utf-8") as fh:
            fh.write(snippet.format(fp=fp))
    out = _run(checker, monkeypatch, [str(practice)])
    assert "GOV-009 pa-reviewer: CHG-0012" in out             # the impact assessment predates the model change
    inv = practice / "inventory.yaml"
    inv.write_text(inv.read_text().replace(
        "      - {kind: FMEA, id: FMEA-PA-001",
        '      - {kind: AIIA, id: AIIA-PA-002, date: "2026-11-05", reviewer: "L. Brandt, Privacy Officer", '
        'outcome: "Re-assessed for the model upgrade"}\n      - {kind: FMEA, id: FMEA-PA-001', 1))
    out = _run(checker, monkeypatch, [str(practice)])
    assert out.rstrip().endswith("ALL CHECKS PASS"), out
    assert "CHG-0012" in (practice / "brief-northshore.md").read_text()
