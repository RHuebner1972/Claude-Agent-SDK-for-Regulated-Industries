"""
M09-L07: score the fleet with engineering and compliance together.

Automation proposes a score from tests and attestations. The regulatory map scopes each agent and traces every
clause to its evidence. Then the review session: reviewers who didn't build the evidence confirm or challenge each
point, and the confirmed score, not the proposed one, sets the rating.

    uv run python lessons/M09-L07_the-40-point-rubric-scoring-an-agent/final/rubric_review_demo.py
    # the same steps from the CLI:
    uv run python -m sentinel.evidence trace --agent aml-triage
    uv run python -m sentinel.evidence review
"""
from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

from pydantic import ValidationError

from sentinel.evidence import (ReviewSession, apply_reviews, coverage, lint, load_map, load_session, render_trace,
                               run_suite, score, signoff_md, trace)
from sentinel.monitoring.fleet import load_fleet

AGENT = "aml-triage"


def show(rows, title: str) -> None:
    print(f"\n{title}")
    for r in rows:
        why = ", ".join(f"{i} {s}" for i, s in r.items if not s.startswith("met"))
        status = f"{r.how}: {why}" if why else r.how
        print(f"   {r.mapping.id:<18} {r.mapping.pillar}  {status:<28} {r.mapping.citation[:60]}")


def main() -> None:
    out = Path(tempfile.mkdtemp()) / "m09-review"
    out.mkdir(parents=True)

    print("1. PROPOSE: run the compliance suite exactly as CI does, then score the 40-point rubric")
    results = run_suite(out / "compliance-results.json")
    proposed = score(results)
    kinds = Counter(i.status for i in proposed.items)
    print(f"   {len(results['results'])} tests, exit {results['exit_status']} -> proposed {proposed.score}/40, "
          f"{proposed.rating}   {dict(kinds)}")

    print("\n2. SCOPE: which regimes apply to each agent is a decision you record with compliance")
    rmap = load_map()
    fleet = load_fleet()
    print(f"   map {rmap.name} v{rmap.version}: {len(rmap.mappings)} clauses across {len(rmap.regimes)} regimes; "
          f"lint: {lint(rmap, fleet_agents=[a.name for a in fleet.agents]) or 'clean'}")
    for a in fleet.agents:
        print(f"   {a.name:<17} {a.organization:<42} {', '.join(rmap.regimes_for(a.name))}")

    rows = trace(rmap, proposed, results, agent=AGENT)
    show(rows, f"3. TRACE {AGENT}: clause -> pillar -> control -> code -> tests -> evidence (proposed score)")
    print("   Note BANK-36H: 'met (attested)'. The runbook point was attested once, for the whole fleet.")

    print("\n4. REVIEW: people who didn't build the evidence confirm or challenge each point")
    session = load_session()
    by = Counter(f"{r.reviewer} ({r.role})" for r in session.reviews)
    for who, n in by.items():
        print(f"   {who:<38} {n} items")
    for r in session.reviews:
        if r.decision == "challenge":
            print(f"   CHALLENGE {r.item} by {r.reviewer}: {r.note}")

    confirmed = apply_reviews(proposed, session)
    print(f"\n5. CONFIRMED: {confirmed.score}/40, {confirmed.rating} (proposed was {proposed.score}/40, {proposed.rating})")
    show(trace(rmap, confirmed, results, agent=AGENT), f"   {AGENT} after review:")

    print("\n6. GUARDRAILS on the review itself")
    data = session.model_dump()
    for label, change in [
        ("author confirms their own evidence", lambda d: d["reviews"][0].update(reviewer=d["author"])),
        ("challenge without a reason", lambda d: d["reviews"][-1].update(decision="challenge", note="no")),
    ]:
        bad = ReviewSession.model_validate(data | {"reviews": [dict(r) for r in data["reviews"]]}).model_dump()
        change(bad)
        try:
            ReviewSession.model_validate(bad)
            print(f"   {label}: accepted (unexpected)")
        except ValidationError as exc:
            print(f"   {label}: refused -> {exc.errors()[0]['msg'][:90]}")

    (out / "signoff.md").write_text(signoff_md(proposed, confirmed, session), encoding="utf-8")
    (out / "regulatory-trace.md").write_text(render_trace(rmap, trace(rmap, confirmed, results)), encoding="utf-8")
    print(f"\n7. WRITTEN for the risk owner: {out / 'signoff.md'}\n   and the auditor: {out / 'regulatory-trace.md'}")
    print("   Coverage after review:", {k: f"{v['met']} met / {v['gap']} gap" for k, v in
                                       coverage(trace(rmap, confirmed, results, agent=AGENT)).items()})


if __name__ == "__main__":
    main()
