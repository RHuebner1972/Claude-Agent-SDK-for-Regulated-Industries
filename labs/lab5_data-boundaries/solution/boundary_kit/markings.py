"""Find controlled content in text: CUI banner markings, drawing numbers, tolerances, precise dimensions,
material specifications, and known canary values. Used on handoffs, contexts and logs.

Pattern matching is a tripwire with known blind spots. The primary control is structural: restricted data
never reaches an agent whose card doesn't allow it, and handoffs are typed. Scanning catches what slips through.
"""
from __future__ import annotations

import re
from typing import Iterable

PATTERNS: dict[str, re.Pattern] = {
    "CUI banner marking": re.compile(r"\bCUI(//[A-Z][A-Z-]*)*\b"),
    "drawing number": re.compile(r"\bD-\d{5}-\d\b"),
    "tolerance value": re.compile(r"±\s*\d*\.?\d+"),
    "precise dimension": re.compile(r"\b\d+\.\d{3,4}\s*in\b"),
    "material specification": re.compile(r"\b(?:AMS|MIL-PRF|MIL-STD)[- ]?\d+"),
}


def scan(text: str, canaries: Iterable[str] = ()) -> list[str]:
    """Return what was found, by kind (never the matched value, so findings are safe to log)."""
    found = [kind for kind, rx in PATTERNS.items() if rx.search(text or "")]
    found += [f"known controlled value ({c[:10]}...)" for c in canaries if c and c in (text or "")]
    return found


def canaries_from(records: Iterable[dict]) -> list[str]:
    """Canary strings planted in the synthetic data's controlled fields."""
    return sorted(set(re.findall(r"CANARY-CUI-[A-Z0-9]{4}", str(list(records)))))
