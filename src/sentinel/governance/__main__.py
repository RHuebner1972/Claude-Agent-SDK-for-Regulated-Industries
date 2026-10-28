"""python -m sentinel.governance inventory|card|risks|validate|raci|brief  (M11)"""
import argparse
import os
import sys
from pathlib import Path

from .brief import agent_card, board_brief, confirmed_scorecard, lint_all, load_governance
from .raci import render_raci
from .risk import render_register
from .validation import summary_md


def _report(name: str, problems: list[str]) -> None:
    print(f"\n{name}: {'clean' if not problems else f'{len(problems)} problem(s)'}")
    for p in problems:
        print(f"  {p}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m sentinel.governance")
    ap.add_argument("--fleet", help="fleet manifest (default: FLEET_FILE or the production manifest)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory", help="lint the AI system inventory and list every system")
    c = sub.add_parser("card", help="print one agent card")
    c.add_argument("--agent", required=True)
    r = sub.add_parser("risks", help="the risk register (FMEA), severity-first")
    r.add_argument("--agent")
    sub.add_parser("validate", help="validation records: current, stale or missing")
    sub.add_parser("raci", help="the RACI and its independence checks")
    b = sub.add_parser("brief", help="run the compliance suite, then write a board brief for one organization")
    b.add_argument("--org", required=True)
    b.add_argument("--out", help="write the brief here (default: print)")
    b.add_argument("--prepared-by", default="")
    args = ap.parse_args()

    g = load_governance(args.fleet or os.getenv("FLEET_FILE"))
    if args.cmd == "inventory":
        for name, e in g.inventory.systems.items():
            print(f"  {name:<17} {e.decision_role:<10} {e.business_owner:<45} "
                  f"{', '.join(a.kind for a in e.assessments)}")
        problems = lint_all(g)["inventory"]
        _report("inventory", problems)
    elif args.cmd == "card":
        print(agent_card(g, args.agent))
        problems = []
    elif args.cmd == "risks":
        print(render_register(g.register.for_agent(args.agent)))
        problems = lint_all(g)["risks"]
        _report("risk register", problems)
    elif args.cmd == "validate":
        print(summary_md(g.validations, g.fleet))
        problems = lint_all(g)["validation"]
        _report("validation", problems)
    elif args.cmd == "raci":
        print(render_raci(g.raci))
        problems = lint_all(g)["raci"]
        _report("RACI", problems)
    else:
        results, confirmed = confirmed_scorecard(g)
        md, problems = board_brief(g, args.org, confirmed, results, prepared_by=args.prepared_by)
        if args.out:
            Path(args.out).write_text(md, encoding="utf-8")
            print(f"wrote {args.out}")
        else:
            print(md)
        _report("brief", problems)
    sys.exit(1 if problems and args.cmd != "brief" else 0)


if __name__ == "__main__":
    main()
