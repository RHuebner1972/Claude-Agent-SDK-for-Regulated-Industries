"""Scoring together (M09-L07): automation PROPOSES a rubric score, people outside engineering CONFIRM it.

Rubric rule: award a point only when the evidence exists AND someone other than the author has checked it.
A review session records, item by item, who looked at the evidence and what they decided:

    confirm      the evidence shows the criterion is met: the point stands
    challenge    the evidence doesn't hold up for this agent (a reason is required): the point is withheld

Points nobody reviewed are not confirmed either. The confirmed score, not the proposed one, sets the rating.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .rubric import POLICIES, Scorecard

REVIEW_PATH = POLICIES / "reviews" / "fleet-2026-q4.yaml"


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    item: str
    decision: Literal["confirm", "challenge"]
    reviewer: str = Field(min_length=3)
    role: str = Field(min_length=3)
    date: date
    note: str = ""

    @model_validator(mode="after")
    def _challenge_needs_a_reason(self) -> "Review":
        if self.decision == "challenge" and len(self.note) < 15:
            raise ValueError(f"item {self.item}: a challenge must say what evidence is missing")
        return self


class ReviewSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    agent: str
    author: str = Field(min_length=3)             # who built the evidence: can't confirm it
    held: date
    reviews: list[Review]

    @model_validator(mode="after")
    def _independent(self) -> "ReviewSession":
        own = [r.item for r in self.reviews if r.reviewer.strip().lower() == self.author.strip().lower()]
        if own:
            raise ValueError(f"the author can't review their own evidence: items {own}")
        seen: set[str] = set()
        twice = [r.item for r in self.reviews if r.item in seen or seen.add(r.item)]
        if twice:
            raise ValueError(f"one decision per item; repeated: {twice}")
        return self


def load_session(path: str | Path = REVIEW_PATH) -> ReviewSession:
    return ReviewSession.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def apply_reviews(card: Scorecard, session: ReviewSession) -> Scorecard:
    """Return the CONFIRMED scorecard: proposed points survive only where a reviewer confirmed them."""
    by_item = {r.item: r for r in session.reviews}
    unknown = sorted(set(by_item) - {i.id for i in card.items})
    if unknown:
        raise ValueError(f"reviews for items not on the scorecard: {unknown}")
    items = []
    for i in card.items:
        r = by_item.get(i.id)
        if not i.points:                                      # nothing to confirm; a review can't add a point
            items.append(i)
        elif r is None:
            items.append(replace(i, status="unconfirmed", points=0, evidence=i.evidence + ["not yet reviewed"]))
        elif r.decision == "confirm":
            items.append(replace(i, evidence=i.evidence + [f"confirmed by {r.reviewer} ({r.role}), {r.date}"]))
        else:
            items.append(replace(i, status="challenged", points=0,
                                 evidence=i.evidence + [f"challenged by {r.reviewer} ({r.role}), {r.date}: {r.note}"]))
    return Scorecard(items)


def signoff_md(proposed: Scorecard, confirmed: Scorecard, session: ReviewSession) -> str:
    """The page the risk owner signs: proposed vs confirmed, every challenge with its reason."""
    challenged = [i for i in confirmed.items if i.status == "challenged"]
    unconfirmed = [i for i in confirmed.items if i.status == "unconfirmed"]
    missing = [i for i in confirmed.items if i.status in ("missing", "failing")]
    reviewers = sorted({f"{r.reviewer} ({r.role})" for r in session.reviews})
    lines = [f"# Rubric review: {session.agent}", "",
             f"Held {session.held} · evidence author {session.author} · reviewers: {'; '.join(reviewers)}", "",
             "| | Score | Critical items | Rating |", "|---|---|---|---|",
             f"| Proposed by automation | {proposed.score}/40 | {'all met' if proposed.critical_met else 'NOT all met'}"
             f" | {proposed.rating} |",
             f"| Confirmed by review | {confirmed.score}/40 | {'all met' if confirmed.critical_met else 'NOT all met'}"
             f" | **{confirmed.rating}** |", ""]
    if challenged:
        lines += ["## Challenged (point withheld until the evidence is fixed)", ""]
        lines += [f"- **{i.id}** {i.criterion} {i.evidence[-1].split(': ', 1)[-1]}" for i in challenged] + [""]
    if unconfirmed:
        lines += ["## Not yet reviewed", ""] + [f"- {i.id} {i.criterion}" for i in unconfirmed] + [""]
    if missing:
        lines += ["## Missing or failing (no point proposed)", ""]
        lines += [f"- {i.id} {i.criterion} ({i.evidence[0]})" for i in missing] + [""]
    if confirmed.rating == "Conditionally ready":
        lines += ["Conditionally ready means: deploy only with a dated remediation plan approved by the risk owner.", ""]
    return "\n".join(lines)
