"""python -m sentinel.evidence build|verify|trace|review  (rubric 7.6, M09)"""
import argparse
import json
from pathlib import Path

from .mapping import coverage, lint, load_map, render_trace, trace
from .pack import SUITE, build_pack, run_suite, verify_pack
from .review import apply_reviews, load_session, signoff_md
from .rubric import score


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m sentinel.evidence")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="run what's missing and build a signed evidence pack")
    b.add_argument("--out", default="out/evidence-pack")
    b.add_argument("--results", help="compliance-results.json from CI (otherwise the suite runs now)")
    b.add_argument("--redteam", help="redteam-report.json (otherwise the corpus runs now)")
    v = sub.add_parser("verify", help="check every file against the signed manifest")
    v.add_argument("pack")
    t = sub.add_parser("trace", help="clause -> pillar -> control -> code -> test -> evidence, with live status")
    t.add_argument("--regime", help="one regime, e.g. HIPAA (default: all)")
    t.add_argument("--agent", help="only the regimes that apply to this fleet agent")
    t.add_argument("--results", help="compliance-results.json (otherwise the suite runs now)")
    t.add_argument("--brief", action="store_true", help="one line per clause instead of Markdown tables")
    r = sub.add_parser("review", help="apply a review session to the proposed score and print the sign-off page")
    r.add_argument("--session", help="review YAML (default: policies/reviews/fleet-2026-q4.yaml)")
    r.add_argument("--results", help="compliance-results.json (otherwise the suite runs now)")
    args = ap.parse_args()
    load = lambda p: json.loads(Path(p).read_text(encoding="utf-8")) if p and Path(p).exists() else None
    if args.cmd in ("trace", "review"):
        results = load(args.results) or run_suite(Path("compliance-results.json"), SUITE)
        card = score(results)
        if args.cmd == "trace":
            rmap = load_map()
            for problem in lint(rmap):
                print("MAP LINT:", problem)
            rows = trace(rmap, card, results, regime=args.regime, agent=args.agent)
            if args.brief:
                for row in rows:
                    why = ", ".join(f"{i} {s}" for i, s in row.items if not s.startswith("met"))
                    n = len(row.tests)
                    print(f"{row.mapping.id:<27} {row.mapping.pillar}  {row.how + (': ' + why if why else ''):<30} "
                          f"{n} test{'' if n == 1 else 's'}")
            else:
                print(render_trace(rmap, rows, args.regime))
            print(json.dumps(coverage(rows)))
        else:
            session = load_session(args.session) if args.session else load_session()
            print(signoff_md(card, apply_reviews(card, session), session))
        return
    if args.cmd == "build":
        summary = build_pack(args.out, results=load(args.results), redteam=load(args.redteam))
        print(json.dumps(summary, indent=1))
    else:
        problems = verify_pack(args.pack)
        print("VERIFIED" if not problems else "FAILED\n  " + "\n  ".join(problems))
        raise SystemExit(1 if problems else 0)


main()
