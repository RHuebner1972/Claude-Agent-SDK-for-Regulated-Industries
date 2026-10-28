"""Where inference and storage happen, checked against what the data requires (rubric 6.4).

These are course-level checks that encode common requirements. They are not legal advice: confirm with your
contracting officer, export counsel and provider documentation (see the Regulatory Watchlist).
"""
from __future__ import annotations

from .cards import AgentCard, CardSet


def _us(region: str) -> bool:
    return region.lower().startswith(("us", "us-gov"))


def check_deployment(card: AgentCard) -> list[str]:
    d, findings = card.deployment, []
    handles_cui = any(m.startswith("CUI") for m in card.data_scope)
    if handles_cui and d.fedramp not in ("moderate", "moderate_equivalent", "high"):
        findings.append("RES-001 CUI processed by a cloud service without FedRAMP Moderate-equivalent controls "
                        "(DFARS 252.204-7012(b)(2)(ii)(D))")
    if handles_cui and not (_us(d.region) and _us(d.storage_region)):
        findings.append("RES-002 CUI inference or storage outside a U.S. region (company policy for this program)")
    if "ITAR" in card.export_authorizations and not d.us_persons_only:
        findings.append("RES-003 ITAR technical data: access must be limited to U.S. persons unless authorized")
    if "ITAR" in card.export_authorizations and not _us(d.storage_region):
        findings.append("RES-004 ITAR technical data stored outside the U.S.: allowed only under the end-to-end "
                        "encryption conditions of 22 CFR 120.54(a)(5); confirm with export counsel")
    return findings


def check_all(cards: CardSet) -> dict[str, list[str]]:
    return {c.name: check_deployment(c) for c in cards.agents}
