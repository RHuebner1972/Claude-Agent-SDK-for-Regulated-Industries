"""
M11-L05: the board brief, generated from the evidence.

Run the compliance suite as CI does, apply the review, and generate a brief for one organization's risk
committee: bottom line, what we run, how we know it works, top risks, what changed, open items and asks. Every
statement cites a hashed artifact. Then the lint shows what goes wrong when someone "improves" the brief by hand.

    uv run python lessons/M11-L05_presenting-to-the-board-here-is-how-our/final/board_brief_demo.py
    uv run python -m sentinel.governance brief --org "Bayside Community Bank" --out brief.md
"""
from __future__ import annotations

from pathlib import Path

from sentinel.governance import (BOARD_QUESTIONS, Claim, Section, agent_card, board_brief, brief_sections,
                                 confirmed_scorecard, evidence_index, lint_brief, load_governance)

ORG = "Bayside Community Bank"
OUT = Path("out/m11")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    g = load_governance()
    print("1. EVIDENCE FIRST: run the compliance suite on the production fleet, score it, apply the review")
    results, confirmed = confirmed_scorecard(g, workdir=OUT)
    print(f"   {len(results['results'])} tests -> confirmed {confirmed.score}/40, {confirmed.rating}")

    print(f"\n2. THE BRIEF for {ORG}'s Board Risk Committee")
    md, problems = board_brief(g, ORG, confirmed, results, prepared_by="S. Patel, Chief Compliance Officer")
    (OUT / "brief-bayside.md").write_text(md, encoding="utf-8")
    (OUT / "card-aml-triage.md").write_text(agent_card(g, "aml-triage"), encoding="utf-8")
    bottom = md.split("## Bottom line", 1)[1].split("## 1.", 1)[0].strip()
    print("   " + bottom.replace("\n", "\n   "))
    print(f"   wrote {OUT / 'brief-bayside.md'} and {OUT / 'card-aml-triage.md'}; lint: {problems or 'every claim cited'}")

    print("\n3. SOMEONE EDITS THE BRIEF BY HAND before the meeting")
    sections = brief_sections(g, ORG, confirmed, results)
    sections[0].claims.insert(0, Claim("Our AML agent is fully compliant and never makes a wrong call."))
    sections.append(Section("Extra", [Claim("Validated by the vendor.", ["vendor-letter"])]))
    for p in lint_brief(sections, evidence_index(g)):
        print(f"   {p}")

    print("\n4. IF THE COMMITTEE ASKS: each question has one artifact that answers it")
    for q, artifact, _ in BOARD_QUESTIONS:
        print(f"   {q:<66} {artifact}")


if __name__ == "__main__":
    main()
