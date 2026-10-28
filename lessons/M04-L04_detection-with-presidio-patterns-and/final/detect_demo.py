"""
M04-L04: detection in three stages, measured against ground truth.

    uv run python lessons/M04-L04_detection-with-presidio-patterns-and/final/detect_demo.py

Stage 1  Presidio defaults                    (NLP + built-in patterns)
Stage 2  + custom recognizers and filters      (MRN, NPI, member ID, address, ZIP, phone, city gazetteer)
Stage 3  + known values from the record        (exact match on identifiers the tool already holds)
"""
from __future__ import annotations

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from course_data import patients, phi_annotations, prior_auth_requests
from sentinel.privacy import detect, known_values
from sentinel.privacy.detect import SPACY_MODEL


def default_analyzer() -> AnalyzerEngine:
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": SPACY_MODEL}]})
    return AnalyzerEngine(nlp_engine=provider.create_engine(), supported_languages=["en"])


def covered(spans: list[tuple[int, int]], text: str, value: str) -> bool:
    i = text.find(value)
    return any(s <= i and e >= i + len(value) for s, e in spans)


def main() -> None:
    reqs, truth = prior_auth_requests(), phi_annotations()
    pts = {p["patient_id"]: p for p in patients()}
    sample = reqs[0]["clinical_notes"]
    base = default_analyzer()

    print("PA-2001 notes:\n ", sample, "\n")
    print("Stage 1, Presidio defaults:")
    for r in sorted(base.analyze(sample, language="en", score_threshold=0.5), key=lambda r: r.start):
        print(f"  {r.entity_type:<15} {sample[r.start:r.end]!r:<22} {r.score:.2f}")
    print("Stage 2, custom recognizers + filters:")
    for f in detect(sample):
        print(f"  {f.entity:<15} {f.text!r:<22} {f.score:.2f}")

    stages = {
        "1 defaults": lambda r: [(x.start, x.end) for x in base.analyze(r["clinical_notes"], language="en", score_threshold=0.5)],
        "2 + custom": lambda r: [(f.start, f.end) for f in detect(r["clinical_notes"])],
        "3 + known values": lambda r: [(f.start, f.end) for f in detect(r["clinical_notes"], known=known_values(pts[r["patient_id"]]))],
    }
    print(f"\n{'Stage':<18} {'Recall':>7}  Missed")
    for name, run in stages.items():
        hit = total = 0
        missed = []
        for r in reqs:
            spans = run(r)
            for a in truth[r["request_id"]]:
                total += 1
                if covered(spans, r["clinical_notes"], a["value"]):
                    hit += 1
                else:
                    missed.append(f"{a['type']}:{a['value']}")
        print(f"{name:<18} {hit / total:>7.1%}  {', '.join(missed[:4])}{' ...' if len(missed) > 4 else ''}")


if __name__ == "__main__":
    main()
