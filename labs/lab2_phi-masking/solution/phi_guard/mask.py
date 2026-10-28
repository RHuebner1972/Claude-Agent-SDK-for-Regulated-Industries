"""Masking strategies on top of Presidio's AnonymizerEngine.

    redact      [MRN]                       irreversible; loses linkage between mentions
    partial     ******9173                  keeps the last 4 for human matching
    pseudonym   PERSON_3f9a1c               keyed HMAC: same value -> same pseudonym; not reversible
    token       [[MRN_7f3a2c91]]            vault-backed: reversible, but only by authorized roles
    generalize  1961 / 021**                Safe Harbor style: keep year, 3-digit ZIP prefix
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from .detect import Finding, analyze

if TYPE_CHECKING:
    from .vault import TokenVault

Strategy = Literal["redact", "partial", "pseudonym", "token", "generalize"]
_engine = AnonymizerEngine()


def _pseudonym_key() -> bytes:
    return os.getenv("PSEUDONYM_KEY", "course-demo-pseudonym-key").encode()


def pseudonym(entity: str, value: str, key: bytes | None = None) -> str:
    digest = hmac.new(key or _pseudonym_key(), f"{entity}|{value}".encode(), hashlib.sha256).hexdigest()[:6]
    return f"{entity}_{digest}"


def _generalize(entity: str, value: str) -> str:
    if entity == "DATE_TIME":
        year = re.search(r"\b(19|20)\d{2}\b", value)
        return year.group(0) if year else "[DATE]"
    if entity == "US_ZIP":
        z = re.search(r"\d{5}", value)
        return f"{z.group(0)[:3]}**" if z else "[ZIP]"
    return f"[{entity}]"


def _operator(strategy: Strategy, entity: str, vault: "TokenVault | None") -> OperatorConfig:
    if strategy == "redact":
        return OperatorConfig("replace", {"new_value": f"[{entity}]"})
    if strategy == "partial":                         # last 4 only makes sense for numbers people match on
        if entity in {"MRN", "US_SSN", "PHONE_NUMBER", "MEMBER_ID", "US_BANK_NUMBER", "CREDIT_CARD", "NPI"}:
            return OperatorConfig("custom", {"lambda": lambda v: "*" * max(len(v) - 4, 0) + v[-4:]})
        return OperatorConfig("replace", {"new_value": f"[{entity}]"})
    if strategy == "pseudonym":
        return OperatorConfig("custom", {"lambda": lambda v: pseudonym(entity, v)})
    if strategy == "token":
        if vault is None:
            raise ValueError("token strategy needs a TokenVault")
        return OperatorConfig("custom", {"lambda": lambda v: vault.tokenize(v, entity)})
    if strategy == "generalize":
        return OperatorConfig("custom", {"lambda": lambda v: _generalize(entity, v)})
    raise ValueError(f"unknown strategy {strategy!r}")


@dataclass
class MaskResult:
    text: str
    findings: list[Finding]


def mask_text(text: str, strategy: Strategy = "redact", *, vault: "TokenVault | None" = None,
              known: dict[str, Iterable[str]] | None = None) -> MaskResult:
    results = analyze(text, known=known)
    if not results:
        return MaskResult(text, [])
    for r in results:                                 # KNOWN_IDENTIFIER: name it after what it is, if we can
        if r.entity_type == "KNOWN_IDENTIFIER" and known:
            span = text[r.start:r.end]
            r.entity_type = next((e for e, vals in known.items() if span in vals), "KNOWN_IDENTIFIER")
    operators = {r.entity_type: _operator(strategy, r.entity_type, vault) for r in results}
    out = _engine.anonymize(text=text, analyzer_results=results, operators=operators)
    findings = [Finding(r.entity_type, r.start, r.end, round(r.score, 2), text[r.start:r.end]) for r in results]
    return MaskResult(out.text, findings)


class PrivacyRedactor:
    """Drop-in redactor for AuditHooks(redactor=...): M03's key-based redaction, then detection on every string."""

    def __init__(self, strategy: Strategy = "redact", vault: "TokenVault | None" = None):
        self.strategy, self.vault = strategy, vault

    def __call__(self, value: Any) -> Any:
        from sentinel.audit.redact import redact as key_redact
        value = key_redact(value)
        return self._walk(value)

    def _walk(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._walk(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._walk(v) for v in value]
        if isinstance(value, str) and value.strip():
            return mask_text(value, self.strategy, vault=self.vault).text
        return value
