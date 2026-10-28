"""Red-team suite: an attack corpus and a runner that replays it against the fleet's controls (rubric 7.2).

    python -m assurance_kit.redteam [--out redteam-report.json]
"""
from .runner import CORPUS_PATH, Case, CaseResult, RedTeamReport, load_corpus, run_case, run_redteam

__all__ = ["CORPUS_PATH", "Case", "CaseResult", "RedTeamReport", "load_corpus", "run_case", "run_redteam"]
