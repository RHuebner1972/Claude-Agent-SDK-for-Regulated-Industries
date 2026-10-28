"""Where inference and storage happen, checked against what the data requires (rubric 6.4).

These are course-level checks that encode common requirements. They are not legal advice: confirm with your
contracting officer, export counsel and provider documentation (see the Regulatory Watchlist).
"""
from __future__ import annotations

from .cards import AgentCard, CardSet


def _us(region: str) -> bool:
    return region.lower().startswith(("us", "us-gov"))


def check_deployment(card: AgentCard) -> list[str]:
    # TODO 1: where this agent runs vs. what its data requires. Return a list of findings.
    # d = card.deployment; handles_cui = any data_scope entry starting with "CUI".
    # RES-001 handles_cui and d.fedramp not in ("moderate", "moderate_equivalent", "high")   (DFARS 252.204-7012(b)(2)(ii)(D))
    # RES-002 handles_cui and not (_us(d.region) and _us(d.storage_region))
    # RES-003 "ITAR" in card.export_authorizations and not d.us_persons_only
    # RES-004 "ITAR" in card.export_authorizations and not _us(d.storage_region)   (22 CFR 120.54(a)(5) carve-out: ask counsel)
    # Start each finding with its code.
    raise NotImplementedError("Lab 5: check_deployment")


def check_all(cards: CardSet) -> dict[str, list[str]]:
    return {c.name: check_deployment(c) for c in cards.agents}
