"""Board-ready evidence (M11-L05): agent cards and a brief where every claim cites a hashed artifact.

The brief is generated from the same files the auditors get: the inventory, the risk register, the validation
records, the confirmed rubric score, the change log and the regulatory map. Nothing in it is typed by hand, so it
can't say more than the evidence does. lint_brief() catches the two ways a hand-edited brief goes wrong: a claim
with no evidence, and absolute language ("fully compliant") that no evidence can support.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from sentinel.deploy.deployment import (
    DEPLOYMENT_FILE,
    PROD_FLEET,
    Deployment,
    load_deployment,
)
from sentinel.evidence.mapping import MAP_PATH, RegulatoryMap, coverage, load_map, trace
from sentinel.evidence.review import POLICIES as EVIDENCE_POLICIES
from sentinel.evidence.rubric import load_rubric
from sentinel.monitoring.change import CHANGES_PATH, ChangeLog, load_changes
from sentinel.monitoring.fleet import Fleet, load_fleet

from .inventory import (
    INVENTORY_PATH,
    Inventory,
    lint_inventory,
    load_inventory,
    next_review,
    person,
)
from .raci import RACI_PATH, Raci, lint_raci, load_raci
from .risk import REGISTER_PATH, RiskRegister, lint_register, load_register
from .validation import (
    VALIDATIONS_PATH,
    ValidationSet,
    lint_validations,
    load_validations,
    status,
)

REPO = Path(__file__).resolve().parents[3]
PROD_REVIEW = EVIDENCE_POLICIES / "reviews" / "fleet-2026-q4-prod.yaml"

# The questions boards and risk committees actually ask, and the artifact that answers each one (the M11 quiz).
BOARD_QUESTIONS: list[tuple[str, str, str]] = [
    ("What AI do we run, and who owns each system?", "AI system inventory and agent cards", "inventory"),
    ("What could go wrong, and how bad would it be?", "Risk register (FMEA), severity-first priority", "risks"),
    ("How do we know it does what we intended?", "Validation record: intended use, activities, independent validator", "validation"),
    ("Who checked the controls, and did anyone disagree?", "Rubric review sign-off: proposed vs confirmed, every challenge", "review"),
    ("Which regulations apply, and where is the proof for each clause?", "Regulatory trace from the regulatory map", "map"),
    ("What changed since we last met, and was it re-validated?", "Change records with re-validation and approvals", "changes"),
    ("Where does our data go, and under which agreements?", "Deployment manifest: path, region, agreements, retention", "deployment"),
    ("Can a person stop it, and has anyone tried?", "Approval gate and kill-switch drill record (rubric 5.1, 5.6)", "review"),
    ("What happens when it goes wrong, and who tells the regulator?", "Incident runbook, notification clocks and tabletop record (rubric 7.5)", "review"),
    ("How do we know this evidence wasn't edited?", "Signed evidence-pack manifest (python -m sentinel.evidence verify)", "pack"),
]
ABSOLUTE = re.compile(r"\b(fully compliant|100% compliant|guarantee[sd]?|never (?:fails?|makes)|risk[- ]free|"
                      r"zero risk|cannot fail)\b", re.IGNORECASE)


@dataclass
class Governance:
    fleet: Fleet
    inventory: Inventory
    register: RiskRegister
    validations: ValidationSet
    raci: Raci
    rmap: RegulatoryMap
    changes: ChangeLog
    deployment: Deployment
    rubric_ids: set[str] = field(default_factory=set)
    paths: dict[str, Path] = field(default_factory=dict)       # where each record was loaded from (for hashing)

    def org_agents(self, org: str) -> list[str]:
        names = [a.name for a in self.fleet.agents if a.organization == org]
        if not names:
            raise KeyError(f"no fleet agent belongs to {org!r}; organizations: "
                           f"{sorted({a.organization for a in self.fleet.agents})}")
        return names


def load_governance(fleet: Fleet | str | Path | None = None, *, inventory: str | Path = INVENTORY_PATH,
                    register: str | Path = REGISTER_PATH, validations: str | Path = VALIDATIONS_PATH,
                    raci: str | Path = RACI_PATH, changes: str | Path = CHANGES_PATH,
                    deployment: str | Path = DEPLOYMENT_FILE, review: str | Path = PROD_REVIEW) -> Governance:
    """Everything governance reads, defaulting to the PRODUCTION fleet (M10). Pass paths to work on copies."""
    fleet = fleet if isinstance(fleet, Fleet) else load_fleet(fleet or PROD_FLEET)
    paths = {"inventory": Path(inventory), "risks": Path(register), "validation": Path(validations),
             "review": Path(review), "changes": Path(changes), "map": MAP_PATH, "deployment": Path(deployment),
             "fleet": Path(fleet.path), "raci": Path(raci)}
    return Governance(fleet, load_inventory(inventory), load_register(register), load_validations(validations),
                      load_raci(raci), load_map(), load_changes(changes), load_deployment(deployment),
                      {i["id"] for i in load_rubric()["items"]}, paths)


def confirmed_scorecard(g: Governance, results: dict | None = None, workdir: str | Path | None = None):
    """Run the compliance suite on g's fleet exactly as CI does (unless results are given), score the rubric and
    apply the review session. Returns (results, confirmed Scorecard)."""
    if results is None:
        import tempfile

        from sentinel.evidence.pack import run_suite
        work = Path(workdir or tempfile.mkdtemp())
        results = run_suite(work / "compliance-results.json", env={"FLEET_FILE": g.fleet.path})
    from sentinel.evidence.review import apply_reviews, load_session
    from sentinel.evidence.rubric import score
    return results, apply_reviews(score(results), load_session(g.paths.get("review", PROD_REVIEW)))


def lint_all(g: Governance, confirmed=None, as_of: date | None = None) -> dict[str, list[str]]:
    return {"inventory": lint_inventory(g.inventory, g.fleet, g.rmap.applicability, g.deployment, as_of, g.changes),
            "risks": lint_register(g.register, [a.name for a in g.fleet.agents], g.rubric_ids, confirmed, as_of),
            "validation": lint_validations(g.validations, g.fleet, g.rubric_ids, confirmed),
            "raci": lint_raci(g.raci)}


def agent_card(g: Governance, name: str) -> str:
    """One page per agent: the inventory entry joined with everything the code knows about it."""
    e, a = g.inventory.get(name), g.fleet.get(name)
    d = g.deployment.agents.get(name)
    v = g.validations.latest(name)
    change = next((c for c in reversed(g.changes.records) if c.agent == name and c.status == "approved"), None)
    risks = g.register.for_agent(name)
    lines = [f"# Agent card: {name}", "", (f"*{a.organization}* · risk tier {a.risk_tier} · {e.lifecycle} since "
              f"{e.in_production_since} · inventory v{g.inventory.version}"), "",
             f"**Purpose.** {e.purpose}", "",
             "| | |", "|---|---|",
             f"| Business owner | {e.business_owner} |", f"| Technical owner | {e.technical_owner} |",
             f"| Decision role | {e.decision_role} |", f"| Affected | {e.affected} |",
             f"| Human oversight | {e.human_oversight} |", f"| Data | {', '.join(e.data)} |",
             f"| Model and tools | {a.model}; {', '.join(a.tools)} |",
             f"| Configuration | {a.fingerprint()} (prompt {a.prompt_version}, mode {a.permission_mode}) |",
             f"| Runs on | {d.path}, {d.region} |" if d else "| Runs on | (no deployment entry) |",
             f"| Regimes | {', '.join(g.rmap.regimes_for(name))} |",
             f"| Latest change | {change.id}: {change.summary} |" if change else "| Latest change | (none) |",
             f"| Validation | {v.id}, {v.framework}, {v.conclusion.replace('_', ' ')} by {v.validator}: "
             f"**{status(v, g.fleet)}** |" if v else "| Validation | **missing** |", "",
             "## Classifications", ""]
    lines += [f"- **{c.scheme}:** {c.result} ({c.by})" for c in e.classifications] or ["- (none recorded)"]
    lines += ["", "## Assessments", "", "| Kind | ID | Date | Reviewer | Next review | Outcome |", "|---|---|---|---|---|---|"]
    lines += [f"| {s.kind} | {s.id} | {s.date} | {s.reviewer} | {next_review(s, a.risk_tier, g.inventory)} | {s.outcome} |"
              for s in e.assessments]
    lines += ["", "## Top risks", ""]
    lines += [f"- **{f.id} ({f.priority})** {f.failure_mode}: {f.treatment}" for f in risks[:3]] or ["- (none)"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------- the brief
@dataclass
class Claim:
    text: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Section:
    title: str
    claims: list[Claim] = field(default_factory=list)
    table: str = ""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def evidence_index(g: Governance, pack: str | Path | None = None) -> dict[str, tuple[str, str, str]]:
    """key -> (what it is, repo-relative path, sha256 prefix). The brief cites these keys."""
    labels = {"inventory": "AI system inventory", "risks": "Risk register (FMEA)", "validation": "Validation records",
              "review": "Rubric review sign-off", "changes": "Change records", "map": "Regulatory map",
              "deployment": "Deployment manifest", "fleet": "Production fleet manifest", "raci": "RACI"}
    files = {k: (labels[k], g.paths.get(k) or Path(g.fleet.path)) for k in labels}
    if pack:
        files["pack"] = ("Signed evidence-pack manifest", Path(pack) / "manifest.json")
    out = {}
    for key, (label, path) in files.items():
        rel = path.resolve().relative_to(REPO) if path.resolve().is_relative_to(REPO) else path
        out[key] = (label, str(rel), _sha(path) if path.exists() else "(not built)")
    return out


def lint_brief(sections: list[Section], index: dict | None = None) -> list[str]:
    problems = []
    for s in sections:
        for c in s.claims:
            if not c.evidence:
                problems.append(f"BRIEF-001 '{c.text[:60]}': a claim with no evidence")
            if m := ABSOLUTE.search(c.text):
                problems.append(f"BRIEF-002 '{m.group(0)}': absolute language no evidence can support; "
                                "say what was tested, by whom, and what is open")
            if index is not None and (unknown := [k for k in c.evidence if k not in index]):
                problems.append(f"BRIEF-003 '{c.text[:60]}': cites {unknown}, which aren't in the evidence index")
    return problems


def brief_sections(g: Governance, org: str, confirmed, results: dict | None = None,
                   period_start: date | None = None, as_of: date | None = None) -> list[Section]:
    as_of = as_of or g.inventory.as_of
    period_start = period_start or as_of - timedelta(days=90)
    names = g.org_agents(org)
    entries = {n: g.inventory.get(n) for n in names}
    risks = [f for n in names for f in g.register.for_agent(n)]
    risks.sort(key=lambda f: ({"High": 0, "Medium": 1, "Low": 2}[f.priority], -f.s, -f.rpn))
    vals = {n: g.validations.latest(n) for n in names}
    lints = lint_all(g, confirmed, as_of)
    mine = [p for k in ("inventory", "risks", "validation") for p in lints[k] if any(n in p for n in names)
            or any(f.id in p for f in risks) or any(v and v.id in p for v in vals.values())]
    challenged = [i for i in confirmed.items if not i.points]
    critical = [i for i in confirmed.items if i.critical]
    roles = {e.decision_role for e in entries.values()}

    bottom = [
        Claim(f"We run {len(names)} AI agent{'s' if len(names) > 1 else ''} in production ({', '.join(names)}). "
              + (("It recommends" if len(names) == 1 else "Each one informs or recommends")
                 + "; a person makes every decision." if roles <= {"informs", "recommends"}
                 else "At least one acts without a per-decision human approval: see section 1."), ["inventory"]),
        Claim(f"Controls: {confirmed.score} of 40 rubric points confirmed by reviewers who didn't build the evidence; "
              f"{sum(1 for i in critical if i.points)} of {len(critical)} critical items met; rating "
              f"{confirmed.rating}. The rubric is scored for the whole platform fleet; section 2 traces the "
              f"clauses that apply to {', '.join(names)} alone.", ["review"]),
    ]
    for n, v in vals.items():
        if v is None:
            bottom.append(Claim(f"{n} has no validation record.", ["validation"]))
        else:
            cond = f": {'; '.join(v.conditions)}" if v.conditions else ""
            bottom.append(Claim(f"{n} was validated on {v.date} by {v.validator} ({v.framework}): "
                                f"{v.conclusion.replace('_', ' ')}{cond}. The configuration in production is "
                                f"{'the one validated' if status(v, g.fleet) == 'current' else 'NOT the one validated'}.",
                                ["validation", "fleet"]))
    high = [f for f in risks if f.priority == "High"]
    bottom.append(Claim(f"Risk register: {len(high)} High, {sum(f.priority == 'Medium' for f in risks)} Medium, "
                        f"{sum(f.priority == 'Low' for f in risks)} Low failure modes"
                        + (f"; the High one{'s' if len(high) > 1 else ''}: "
                           + "; ".join(f"{f.id} {f.failure_mode.lower()} ({f.treatment})" for f in high) if high else "")
                        + ".", ["risks"]))

    what = Section("1. What we run", table="\n".join(
        ["| Agent | Purpose | Decision role | Human oversight | Tier | Runs on | Regimes |", "|---|---|---|---|---|---|---|"]
        + [f"| {n} | {e.purpose} | {e.decision_role} | {e.human_oversight} | {g.fleet.get(n).risk_tier} | "
           f"{g.deployment.agents[n].path}, {g.deployment.agents[n].region} | {', '.join(g.rmap.regimes_for(n))} |"
           for n, e in entries.items()]),
        claims=[Claim(f"Owners: {'; '.join(f'{n}: {e.business_owner}' for n, e in entries.items())}.", ["inventory"])]
        + [Claim(f"{n} runs on {g.deployment.agents[n].path} ({g.deployment.agents[n].region}) under: "
                 f"{'; '.join(g.deployment.agents[n].agreements)}. Audit records are kept "
                 f"{g.deployment.agents[n].audit_storage.retain_days / 365.25:.0f} years in write-once storage.",
                 ["deployment"])
           for n in names])

    working = Section("2. How we know it works")
    pillars = confirmed.by_pillar()
    working.claims.append(Claim("Confirmed rubric points by pillar: " + ", ".join(
        f"{p} {pts}/{n}" for p, (pts, n) in sorted(pillars.items())) + ".", ["review"]))
    for i in challenged:
        why = i.evidence[-1].split(": ", 1)[-1] if i.evidence else i.status
        if not any(n in why for n in names):          # another tenant's details stay out of this board's pack
            why = f"The reason concerns another agent on the platform, not {', '.join(names)}."
        working.claims.append(Claim(f"Point withheld: {i.id} {i.criterion} ({i.status}). {why}", ["review"]))
    if results is not None:
        for n in names:
            cov = coverage(trace(g.rmap, confirmed, results, agent=n))
            parts = [f"{reg} met {c['met']}, gaps {c['gap']}, failing {c['failing']}" for reg, c in cov.items()]
            working.claims.append(Claim(f"{n} regulatory trace (clauses with rubric evidence): {'; '.join(parts)}.",
                                        ["map", "review"]))

    top = Section("3. Top risks", table="| ID | Failure mode | Effect | S/O/D | Priority | Treatment |\n|---|---|---|---|---|---|\n"
                  + "\n".join(f"| {f.id} | {f.failure_mode} | {f.effect} | {f.s}/{f.o}/{f.d} | **{f.priority}** | "
                              f"{f.treatment} |" for f in risks if f.priority != "Low"),
                  claims=[Claim("Priority is severity-first: a rare failure that harms a person or breaks a legal "
                                "duty outranks a frequent nuisance, whatever S x O x D says.", ["risks"])])

    changed = [c for c in g.changes.records if c.agent in names and c.status == "approved"
               and date.fromisoformat(c.approvals[-1].date) >= period_start]
    changes = Section("4. What changed this period", claims=[
        Claim(f"{c.id} ({c.agent}, {c.category}): {c.summary}. Re-validation {c.revalidation.result} "
              f"({c.revalidation.suite}, red team {c.revalidation.redteam}); approved by "
              f"{', '.join(f'{x.name} ({x.role})' for x in c.approvals)}.", ["changes"]) for c in changed]
        or [Claim("No approved changes this period.", ["changes"])])

    asks = Section("5. Open items and decisions for the committee")
    for p in mine:
        asks.claims.append(Claim(p.split(" ", 1)[1], ["risks" if p.startswith("RISK") else
                                                     "validation" if p.startswith("VAL") else "inventory"]))
    for f in high:
        if f.action:
            asks.claims.append(Claim(f"Note: {f.id} stays High until '{f.action.what}' is done (owner "
                                     f"{person(f.action.owner)}, due {f.action.due}). Management will report "
                                     "closure with evidence at the next meeting.", ["risks"]))
        elif not f.acceptance:
            asks.claims.append(Claim(f"Decide: accept {f.id} or fund an action; it has neither.", ["risks"]))
    soon = [f for f in risks if f.acceptance and f.acceptance.expires <= as_of + timedelta(days=180)]
    for f in soon:
        asks.claims.append(Claim(f"Renew or retire the acceptance of {f.id} before {f.acceptance.expires}.", ["risks"]))
    if not asks.claims:
        asks.claims.append(Claim("No decisions requested this period.", ["review"]))

    return [Section("Bottom line", bottom), what, working, top, changes, asks]


def render_brief(g: Governance, org: str, sections: list[Section], *, audience: str = "Board Risk Committee",
                 prepared_by: str = "", index: dict | None = None, as_of: date | None = None) -> str:
    index = index or evidence_index(g)
    keys = list(index)
    lines = [f"# AI compliance brief: {org}", "",
             f"For: {audience} · As of {as_of or g.inventory.as_of}"
             + (f" · Prepared by {prepared_by}" if prepared_by else "")
             + " · Generated from versioned, hashed artifacts: every statement cites them [n].", ""]
    for s in sections:
        lines += [f"## {s.title}", ""]
        if s.table:
            lines += [s.table, ""]
        lines += [f"- {c.text} " + "".join(f"[{keys.index(k) + 1}]" for k in c.evidence if k in index)
                  for c in s.claims] + [""]
    lines += ["## Evidence index", "", "| # | Artifact | File | sha256 |", "|---|---|---|---|"]
    lines += [f"| [{n}] | {label} | `{path}` | {sha} |" for n, (label, path, sha) in enumerate(index.values(), 1)]
    lines += ["", "## If the committee asks", "", "| Question | The artifact that answers it |", "|---|---|"]
    lines += [f"| {q} | {a} [{keys.index(k) + 1}] |" if k in index else f"| {q} | {a} |" for q, a, k in BOARD_QUESTIONS]
    lines += ["", "*Synthetic course data. Not legal advice: confirm obligations with counsel and compliance.*", ""]
    return "\n".join(lines)


def board_brief(g: Governance, org: str, confirmed, results: dict | None = None, *, pack: str | Path | None = None,
                audience: str = "Board Risk Committee", prepared_by: str = "", as_of: date | None = None
                ) -> tuple[str, list[str]]:
    """Markdown brief for one organization, plus lint problems (an empty list means every claim is backed)."""
    index = evidence_index(g, pack)
    sections = brief_sections(g, org, confirmed, results, as_of=as_of)
    return (render_brief(g, org, sections, audience=audience, prepared_by=prepared_by, index=index, as_of=as_of),
            lint_brief(sections, index))
