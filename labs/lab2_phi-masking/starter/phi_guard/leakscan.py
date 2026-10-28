"""Leak scanning: prove that logs, traces and transcripts contain no PHI.

Two complementary checks:
  canaries  exact identifier values you planted or already know (names, MRNs, SSNs...). No false negatives
            for those values, no false positives. This is the acceptance test.
  detector  the Presidio pipeline, for identifiers you didn't know about. Noisier; triage the hits.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .detect import detect
from .vault import TOKEN_RE


def canaries_from(patients: Iterable[dict]) -> dict[str, str]:
    """value -> label, for every identifier in the synthetic patient file (several date formats for DOB)."""
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]
    out: dict[str, str] = {}
    for p in patients:
        y, m, d = p["dob"].split("-")
        pid = p["patient_id"]
        for label, value in [("name", f"{p['first_name']} {p['last_name']}"), ("last_name", p["last_name"]),
                             ("mrn", p["mrn"]), ("member_id", p["member_id"]), ("ssn", p["ssn"]),
                             ("phone", p["phone"]), ("email", p["email"]), ("street", p["address"]["street"]),
                             ("dob", p["dob"]), ("dob", f"{m}/{d}/{y}"), ("dob", f"{months[int(m) - 1]} {int(d)}, {y}")]:
            out[value] = f"{pid}.{label}"
    return out


@dataclass
class LeakReport:
    canary_hits: dict[str, list[str]] = field(default_factory=dict)     # file -> labels found
    detector_hits: dict[str, list[str]] = field(default_factory=dict)   # file -> "ENTITY: text"

    @property
    def clean(self) -> bool:
        return not any(self.canary_hits.values())

    def render(self) -> str:
        lines = [f"{'File':<44} {'Canaries':>8} {'Detector':>8}"]
        for f in sorted(set(self.canary_hits) | set(self.detector_hits)):
            lines.append(f"{f[-44:]:<44} {len(self.canary_hits.get(f, [])):>8} {len(self.detector_hits.get(f, [])):>8}")
        lines.append("CLEAN: no known identifiers found" if self.clean else "LEAKS FOUND")
        return "\n".join(lines)


def scan_text(text: str, canaries: dict[str, str]) -> list[str]:
    return sorted({label for value, label in canaries.items() if value and value in text})


def scan_paths(paths: Iterable[str | Path], canaries: dict[str, str], *, use_detector: bool = True) -> LeakReport:
    report = LeakReport()
    for path in map(Path, paths):
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        report.canary_hits[str(path)] = scan_text(text, canaries)
        if use_detector:
            cleaned = TOKEN_RE.sub(" ", text)                    # vault tokens are fine by design
            hits = [f for chunk in cleaned.splitlines() for f in detect(chunk[:5000])
                    if f.entity in {"PERSON", "US_SSN", "EMAIL_ADDRESS", "PHONE_NUMBER", "MRN", "MEMBER_ID", "STREET_ADDRESS"}]
            report.detector_hits[str(path)] = [f"{f.entity}: {f.text}" for f in hits]
    return report
