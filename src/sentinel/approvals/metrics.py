"""Is anyone actually reviewing? Signals of rubber-stamping, computed from the approval queue."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import median

from .queue import ApprovalQueue


def review_quality(queue: ApprovalQueue, *, fast_seconds: int = 60, min_decisions: int = 5) -> dict[str, dict]:
    by_user: dict[str, list] = defaultdict(list)
    for r in queue.requests.values():
        for s in r.signatures:
            by_user[s.user].append((r, s))
    report = {}
    for user, items in by_user.items():
        secs = [(s.signed_at - r.created_at).total_seconds() for r, s in items]
        reasons = Counter(s.reason.strip().lower() for _, s in items)
        approve_rate = sum(s.meaning == "approve" for _, s in items) / len(items)
        flags = []
        if len(items) >= min_decisions and approve_rate == 1.0:
            flags.append("approves everything")
        if median(secs) < fast_seconds:
            flags.append(f"median decision under {fast_seconds}s")
        if reasons and reasons.most_common(1)[0][1] > 1:
            flags.append("repeats the same reason")
        report[user] = {"decisions": len(items), "approve_rate": round(approve_rate, 2),
                        "median_seconds": round(median(secs)), "flags": flags}
    return report
