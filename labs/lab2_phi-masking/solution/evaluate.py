"""
Lab 2: measure detection recall against the annotated notes (acceptance threshold: 95%).

    uv run python evaluate.py
"""
from __future__ import annotations

from course_data import patients, phi_annotations, prior_auth_requests

from phi_guard.detect import detect, known_values

TARGET = 0.95            # the pipeline (patterns + NLP + known values from the record)
GENERIC_TARGET = 0.90    # patterns + NLP alone: free text you hold no record for


def recall(use_known: bool = True) -> tuple[float, list[str]]:
    pts = {p["patient_id"]: p for p in patients()}
    hit = total = 0
    missed: list[str] = []
    for r in prior_auth_requests():
        text = r["clinical_notes"]
        found = detect(text, known=known_values(pts[r["patient_id"]]) if use_known else None)
        for a in phi_annotations()[r["request_id"]]:
            total += 1
            i = text.find(a["value"])
            if any(f.start <= i and f.end >= i + len(a["value"]) for f in found):
                hit += 1
            else:
                missed.append(f"{r['request_id']} {a['type']}: {a['value']}")
    return hit / total, missed


if __name__ == "__main__":
    for label, use_known, target in [("patterns + NLP", False, GENERIC_TARGET),
                                     ("+ known values (the pipeline)", True, TARGET)]:
        score, missed = recall(use_known)
        verdict = "PASS" if score >= target else "below target"
        print(f"{label:<32} recall {score:.1%} (target {target:.0%}) {verdict}  missed: {missed[:3]}")
