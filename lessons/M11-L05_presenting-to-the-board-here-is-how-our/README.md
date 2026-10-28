# M11-L05: Presenting to the board: here is how our agent stays compliant, and here is the evidence

Module: M11 Governance, Validation & Board-Ready Evidence · Type: Lecture with demo

`final/board_brief_demo.py` runs the compliance suite on the production fleet, applies the rubric review, and
writes a brief for Bayside Community Bank's Board Risk Committee (`out/m11/brief-bayside.md`) plus the
aml-triage agent card. Every statement cites a hashed artifact. Then it shows what the brief lint catches when
someone edits the brief by hand: a claim with no evidence (BRIEF-001), absolute language (BRIEF-002) and evidence
that isn't in the index (BRIEF-003). It ends with the board questions and the artifact that answers each.

```bash
uv run python lessons/M11-L05_presenting-to-the-board-here-is-how-our/final/board_brief_demo.py
uv run python -m sentinel.governance brief --org "Bayside Community Bank" --out brief.md
```
Code walked through on screen: `src/sentinel/governance/brief.py` (`board_brief`, `lint_brief`, `BOARD_QUESTIONS`).

Regulatory references are paraphrased and current as of 2026-10-28 (see `00_Course-Plan/Regulatory_Watchlist.md`). Not legal advice.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
