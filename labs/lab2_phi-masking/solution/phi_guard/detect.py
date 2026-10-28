"""Detection: a Presidio AnalyzerEngine with our custom recognizers, a threshold and overlap resolution."""
from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .classes import ENTITY_CLASS
from .recognizers import custom_recognizers, known_values_recognizer

# Entities we act on. ORGANIZATION, NRP and others are left out: too noisy to mask everywhere.
ENTITIES = ["PERSON", "DATE_TIME", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN", "LOCATION", "US_BANK_NUMBER",
            "CREDIT_CARD", "IP_ADDRESS", "MRN", "NPI", "MEMBER_ID", "STREET_ADDRESS", "US_ZIP", "KNOWN_IDENTIFIER"]
# A date that identifies a moment (03/14/1961, March 14, 1961, 2026-06-02), not a duration ("6 weeks").
DATE_LIKE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2}|"
                       r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}")
THRESHOLD = 0.5
SPACY_MODEL = os.getenv("PRIVACY_SPACY_MODEL", "en_core_web_sm")   # en_core_web_lg finds more names


@dataclass(frozen=True)
class Finding:
    entity: str
    start: int
    end: int
    score: float
    text: str

    @property
    def data_class(self) -> str:
        return ENTITY_CLASS.get(self.entity, "PII")


@lru_cache(maxsize=2)
def build_analyzer(model: str = SPACY_MODEL) -> AnalyzerEngine:
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": model}]})
    analyzer = AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])
    for recognizer in custom_recognizers():
        analyzer.registry.add_recognizer(recognizer)
    return analyzer


def resolve_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """Keep the highest-scoring (then longest) result wherever spans overlap."""
    kept: list[RecognizerResult] = []
    for r in sorted(results, key=lambda r: (-r.score, -(r.end - r.start), r.start)):
        if all(r.end <= k.start or r.start >= k.end for k in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: r.start)


def plausible(r: RecognizerResult, text: str) -> bool:
    """Post-filters that keep clinical meaning: over-masking ("[DATE] of PT") destroys the summary."""
    span = text[r.start:r.end]
    if r.entity_type == "DATE_TIME":
        return bool(DATE_LIKE.search(span))           # durations, frequencies and ages aren't identifiers
    if r.entity_type == "PERSON":
        return not any(c.isdigit() for c in span)     # "Grade 2/6" is a murmur, not a person
    if r.entity_type == "LOCATION":
        return not (span.isupper() and len(span) <= 3)  # "RA" is rheumatoid arthritis
    return True


def analyze(text: str, threshold: float = THRESHOLD,
            known: dict[str, Iterable[str]] | None = None) -> list[RecognizerResult]:
    ad_hoc = [rec] if known and (rec := known_values_recognizer(known)) else []
    raw = build_analyzer().analyze(text=text, language="en", entities=ENTITIES, score_threshold=threshold,
                                   ad_hoc_recognizers=ad_hoc or None)
    return resolve_overlaps([r for r in raw if plausible(r, text)])


def detect(text: str, threshold: float = THRESHOLD, known: dict[str, Iterable[str]] | None = None) -> list[Finding]:
    return [Finding(r.entity_type, r.start, r.end, round(r.score, 2), text[r.start:r.end])
            for r in analyze(text, threshold, known)]


def known_values(record: dict) -> dict[str, list[str]]:
    """Identifiers from a structured patient record, for known_values_recognizer."""
    first, last = record.get("first_name", ""), record.get("last_name", "")
    addr = record.get("address", {})
    return {"PERSON": [f"{first} {last}".strip(), first, last], "MRN": [record.get("mrn", "")],
            "MEMBER_ID": [record.get("member_id", "")], "PHONE_NUMBER": [record.get("phone", "")],
            "EMAIL_ADDRESS": [record.get("email", "")], "US_SSN": [record.get("ssn", "")],
            "STREET_ADDRESS": [addr.get("street", "")]}
