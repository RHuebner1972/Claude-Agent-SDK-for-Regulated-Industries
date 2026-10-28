"""Minimum necessary, by design: each purpose gets only the fields it needs, decided in code."""
from __future__ import annotations

from datetime import date
from typing import Any

# Purpose -> fields allowed from each record type. Anything not listed never leaves the tool.
PURPOSE_FIELDS: dict[str, dict[str, list[str]]] = {
    "prior_auth_review": {
        "request": ["request_id", "service_code", "service", "icd10", "diagnosis", "submitted", "clinical_notes"],
        "patient": ["age", "sex", "plan"],          # derived: age, not date of birth
    },
    "member_outreach": {
        "request": ["request_id", "status"],
        "patient": ["first_name", "phone", "plan"],
    },
}


def age_on(dob: str, on: str) -> int | str:
    """Age in years on a date. HIPAA Safe Harbor aggregates ages over 89 into one category."""
    b, d = date.fromisoformat(dob), date.fromisoformat(on)
    years = d.year - b.year - ((d.month, d.day) < (b.month, b.day))
    return "90+" if years >= 90 else years


def derive(patient: dict[str, Any], as_of: str) -> dict[str, Any]:
    return {**patient, "age": age_on(patient["dob"], as_of)}


def minimize(record: dict[str, Any], kind: str, purpose: str) -> dict[str, Any]:
    try:
        allowed = PURPOSE_FIELDS[purpose][kind]
    except KeyError:
        raise PermissionError(f"no field allowlist for purpose {purpose!r} and record type {kind!r}") from None
    return {k: record[k] for k in allowed if k in record}
