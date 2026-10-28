"""Notification clocks for an agent incident (rubric 7.5). Course-level summary, not legal advice.

Each clock starts at a different moment (discovery, awareness, a determination), so the record keeps the start
event next to the deadline. Confirm every obligation with counsel; regulators and contracts can add others.

    clocks = notification_clocks(discovered_at, ["hipaa", "gdpr"], affected=12, max_in_one_state=12)
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta


@dataclass
class Deadline:
    regime: str
    audience: str
    due: str                 # ISO date/time, or a description when it depends on a later event
    starts: str              # what starts the clock
    citation: str
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _business_days(start: datetime, n: int) -> datetime:
    d = start
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:          # Mon-Fri; holidays not modeled
            n -= 1
    return d


def notification_clocks(discovered: datetime, regimes: list[str], *, affected: int = 0,
                        max_in_one_state: int = 0, determined: datetime | None = None) -> list[Deadline]:
    """discovered: when the incident was discovered / you became aware. determined: when it was determined to be a
    reportable incident or material (NYDFS, SEC), if different."""
    out: list[Deadline] = []
    determined = determined or discovered
    if "hipaa" in regimes:
        d60 = (discovered + timedelta(days=60)).date().isoformat()
        out.append(Deadline("HIPAA", "Affected individuals", f"without unreasonable delay; no later than {d60}",
                            "discovery of the breach", "45 CFR 164.404(b)"))
        if affected >= 500:
            out.append(Deadline("HIPAA", "HHS Secretary", f"with individual notice; no later than {d60}",
                                "discovery of the breach", "45 CFR 164.408(b)"))
        else:
            year_end = date(discovered.year, 12, 31) + timedelta(days=60)
            out.append(Deadline("HIPAA", "HHS Secretary", f"annual log, no later than {year_end.isoformat()}",
                                "end of the calendar year", "45 CFR 164.408(c)", "fewer than 500 individuals"))
        if max_in_one_state > 500:
            out.append(Deadline("HIPAA", "Prominent media in the state", f"no later than {d60}",
                                "discovery of the breach", "45 CFR 164.406"))
        out.append(Deadline("HIPAA", "Covered entity (if you are its business associate)", f"no later than {d60}",
                            "discovery of the breach", "45 CFR 164.410", "the contract (BAA) may set a shorter time"))
    if "gdpr" in regimes:
        out.append(Deadline("GDPR", "Supervisory authority", (discovered + timedelta(hours=72)).isoformat(),
                            "becoming aware of a personal data breach", "GDPR Art. 33(1)",
                            "unless unlikely to result in a risk to rights and freedoms; give reasons if late"))
        out.append(Deadline("GDPR", "Data subjects", "without undue delay", "high risk to rights and freedoms",
                            "GDPR Art. 34"))
    if "dfars" in regimes:
        out.append(Deadline("DFARS", "DoD (DIBNet)", (discovered + timedelta(hours=72)).isoformat(),
                            "discovery of a cyber incident affecting covered defense information",
                            "DFARS 252.204-7012(c)", "preserve images and data for 90 days"))
    if "nydfs" in regimes:
        out.append(Deadline("NYDFS", "Superintendent", (determined + timedelta(hours=72)).isoformat(),
                            "determining a cybersecurity incident occurred", "23 NYCRR 500.17(a)"))
    if "sec" in regimes:
        out.append(Deadline("SEC", "Form 8-K Item 1.05", _business_days(determined, 4).date().isoformat(),
                            "determining the incident is material", "Form 8-K Item 1.05",
                            "public companies; holidays not modeled"))
    return out
