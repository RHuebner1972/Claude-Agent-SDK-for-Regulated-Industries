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
    # TODO 5: return what was found, BY KIND, never the matched value (findings get logged).
    # For each (kind, regex) in PATTERNS: if regex.search(text or "") -> append kind.
    # Then for each canary c in canaries: if c and c in text -> append f"known controlled value ({c[:10]}...)".
    # Return the list (empty = nothing found).
    raise NotImplementedError("Lab 5: scan")


def canaries_from(records: Iterable[dict]) -> list[str]:
    """Canary strings planted in the synthetic data's controlled fields."""
    return sorted(set(re.findall(r"CANARY-CUI-[A-Z0-9]{4}", str(list(records)))))
