"""P7 Continuous Assurance: the 40-point rubric as data, scoring, and a signed evidence pack (M08, M09, Capstone).

    python -m sentinel.evidence build --out out/evidence-pack
    python -m sentinel.evidence verify out/evidence-pack
    python -m sentinel.evidence trace --agent aml-triage       # M09: clause-level regulatory trace
    python -m sentinel.evidence review                         # M09: proposed vs confirmed score
"""
from .mapping import (Mapping, RegulatoryMap, TraceRow, coverage, lint, load_map, matrix, render_trace,
                      trace)
from .pack import build_pack, run_suite, sign_manifest, verify_pack
from .review import Review, ReviewSession, apply_reviews, load_session, signoff_md
from .rubric import ItemScore, Scorecard, load_attestations, load_rubric, score

__all__ = ["ItemScore", "Mapping", "RegulatoryMap", "Review", "ReviewSession", "Scorecard", "TraceRow",
           "apply_reviews", "build_pack", "coverage", "lint", "load_attestations", "load_map", "load_rubric",
           "load_session", "matrix", "render_trace", "run_suite", "score", "sign_manifest", "signoff_md", "trace",
           "verify_pack"]
