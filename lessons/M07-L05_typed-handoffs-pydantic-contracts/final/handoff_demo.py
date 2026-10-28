"""
M07-L05: typed handoffs. Six things a cleared subagent might send back, and what the contract does with each.

    uv run python lessons/M07-L05_typed-handoffs-pydantic-contracts/final/handoff_demo.py
"""
from __future__ import annotations

import json

from course_data import ecrs
from sentinel.boundaries import ChangeImpactSummary, canaries_from, enforce_contract
from sentinel.boundaries.simulate import CHATTY_SUMMARY, FREE_TEXT, GOOD_SUMMARY, LEAKY_SUMMARY

CLEAN = json.dumps({k: v for k, v in json.loads(GOOD_SUMMARY).items() if k in ChangeImpactSummary.model_fields})
WRONG_BAND = CLEAN.replace('"10k-100k"', '"about 60 thousand"')

CASES = [
    ("clean ENG-FORM-7", CLEAN),
    ("extra fields (drawing, tolerance)", GOOD_SUMMARY),
    ("extra field carrying test data", CHATTY_SUMMARY),
    ("CUI smuggled into the rationale", LEAKY_SUMMARY),
    ("free text, no JSON", FREE_TEXT),
    ("value outside the allowed set", WRONG_BAND),
]


def main() -> None:
    canaries = canaries_from(ecrs())
    print("CONTRACT  ChangeImpactSummary (ENG-FORM-7), extra='forbid'")
    for name, prop in ChangeImpactSummary.model_json_schema()["properties"].items():
        rule = prop.get("enum") or prop.get("const") or prop.get("pattern") or prop.get("type")
        limits = {k: prop[k] for k in ("minimum", "maximum", "minLength", "maxLength") if k in prop}
        print(f"  {name:28} {rule}  {limits or ''}"[:110])
    for label, raw in CASES:
        r = enforce_contract(raw, ChangeImpactSummary, canaries)
        print(f"\n{label.upper()}")
        print(f"  ok={r.ok}  stripped={r.stripped or '-'}  findings={r.findings or '-'}")
        print(f"  orchestrator receives: {' '.join(r.text().split())[:170]}")


if __name__ == "__main__":
    main()
