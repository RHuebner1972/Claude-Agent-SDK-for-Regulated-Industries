"""Custom Presidio recognizers for identifiers the defaults don't know: MRN, NPI, member ID, street address, ZIP.

Out of the box, Presidio labels a 7-digit MRN as a date and a 10-digit NPI as a phone number. Labels
matter: they decide the masking strategy, the data class and what the leak report says.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from presidio_analyzer import Pattern, PatternRecognizer


def npi_is_valid(npi: str) -> bool:
    """CMS rule: Luhn check over '80840' + the 10-digit NPI."""
    digits = [int(d) for d in "80840" + npi]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return total % 10 == 0


class NpiRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entity="NPI", name="NpiRecognizer",
                         patterns=[Pattern("npi_10_digits", r"\b\d{10}\b", 0.6)],
                         context=["npi", "provider", "prescriber", "dr", "ordering"])

    def validate_result(self, pattern_text: str) -> bool:      # drops 10-digit numbers that fail Luhn
        return npi_is_valid(pattern_text)


def mrn_recognizer() -> PatternRecognizer:
    # A bare 7-digit number is weak evidence (score 0.2). The word "MRN" or "medical record" nearby lifts
    # it above the threshold: that's Presidio's context enhancement.
    return PatternRecognizer(supported_entity="MRN", name="MrnRecognizer",
                             patterns=[Pattern("mrn_7_digits", r"\b\d{7}\b", 0.2)],
                             context=["mrn", "medical", "record", "chart"])


def member_id_recognizer() -> PatternRecognizer:
    return PatternRecognizer(supported_entity="MEMBER_ID", name="MemberIdRecognizer",
                             patterns=[Pattern("payer_member_id", r"\b[A-Z]{3}\d{9}\b", 0.6)],
                             context=["member", "subscriber", "id", "policy"])


def street_address_recognizer() -> PatternRecognizer:
    suffix = r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Ln|Lane|Dr|Drive|Way|Ct|Court|Pl|Place)"
    return PatternRecognizer(supported_entity="STREET_ADDRESS", name="StreetAddressRecognizer",
                             patterns=[Pattern("street_address", rf"\b\d{{1,5}}\s+(?:[A-Z][a-z]+\s){{1,3}}{suffix}\b\.?", 0.9)])


def us_zip_recognizer() -> PatternRecognizer:
    return PatternRecognizer(supported_entity="US_ZIP", name="UsZipRecognizer",
                             patterns=[Pattern("state_zip", r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b", 0.6)])


def us_phone_recognizer() -> PatternRecognizer:
    # Presidio's phone recognizer scores US numbers 0.4 without context; this pattern is unambiguous.
    return PatternRecognizer(supported_entity="PHONE_NUMBER", name="UsPhoneRecognizer",
                             patterns=[Pattern("us_phone", r"\(?\b\d{3}\)?[-.\s]\d{3}[-.]\d{4}\b", 0.7)])


# Cities in the plan's service area. A gazetteer (deny list) catches what the NLP model misses;
# Safe Harbor treats any geographic unit smaller than a state as an identifier.
SERVICE_AREA_CITIES = ["Quincy", "Braintree", "Hull", "Weymouth", "Milton", "Cohasset", "Hingham", "Boston"]


def city_recognizer(cities: Iterable[str] = SERVICE_AREA_CITIES) -> PatternRecognizer:
    return PatternRecognizer(supported_entity="LOCATION", name="ServiceAreaCityRecognizer", deny_list=list(cities))


def known_values_recognizer(values: dict[str, Iterable[str]]) -> PatternRecognizer | None:
    """Exact-match recognizer for identifiers you already hold in the structured record.

    If the tool fetched patient P-008, you know his name, MRN and phone: look for exactly those in the
    free text. It catches what models miss ("Marcus Hill works night shifts") at near-zero false-positive cost.
    """
    patterns = [Pattern(f"known_{entity.lower()}", r"\b" + re.escape(v) + r"\b", 0.95)
                for entity, vals in values.items() for v in vals if v]
    if not patterns:
        return None
    return PatternRecognizer(supported_entity="KNOWN_IDENTIFIER", name="KnownValuesRecognizer", patterns=patterns)


def custom_recognizers() -> list[PatternRecognizer]:
    return [mrn_recognizer(), NpiRecognizer(), member_id_recognizer(), street_address_recognizer(),
            us_zip_recognizer(), us_phone_recognizer(), city_recognizer()]
