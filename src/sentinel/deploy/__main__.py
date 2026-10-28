"""python -m sentinel.deploy paths|preflight|docker  (M10)"""
import argparse
import json
import os
import sys

from sentinel.monitoring.fleet import load_fleet

from .deployment import DEPLOYMENT_FILE, PROD_FLEET, check_reference, load_deployment, preflight
from .paths import Requirements, load_catalog, shortlist
from .sandbox import docker_args, sdk_sandbox_settings


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m sentinel.deploy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("paths", help="shortlist deployment paths for a set of requirements")
    for flag in ("phi", "itar", "eu-residency", "us-residency", "private-network", "cloud-processor"):
        p.add_argument(f"--{flag}", action="store_true")
    p.add_argument("--fedramp", choices=["none", "moderate", "high"], default="none")
    p.add_argument("--il", type=int, default=0)
    f = sub.add_parser("preflight", help="check the deployment manifest against the fleet (default: fleet-prod.yaml)")
    f.add_argument("--fleet", help="fleet manifest (default: FLEET_FILE or the production manifest)")
    d = sub.add_parser("docker", help="print the hardened docker run command and SDK sandbox settings for an agent")
    d.add_argument("agent")
    r = sub.add_parser("reference", help="static checks on a compose-based reference deployment")
    r.add_argument("folder")
    r.add_argument("--agent", required=True)
    args = ap.parse_args()

    if args.cmd == "paths":
        req = Requirements(phi=args.phi, itar=args.itar, eu_residency=args.eu_residency, us_residency=args.us_residency,
                           private_network=args.private_network, cloud_processor=args.cloud_processor,
                           fedramp=args.fedramp, il=args.il)
        print(f"Path catalog as of {load_catalog().as_of}: re-check every fact with the provider.")
        for fit in shortlist(req):
            print(f"  {'OK ' if fit.ok else 'no '} {fit.path:22} {'; '.join(fit.reasons)}")
            for item in fit.to_confirm:
                print(f"       confirm: {item}")
    elif args.cmd == "preflight":
        fleet = load_fleet(args.fleet or os.getenv("FLEET_FILE") or PROD_FLEET)
        dep = load_deployment()
        print(f"fleet {fleet.name}@{fleet.version} · deployment {dep.name}@{dep.version} ({DEPLOYMENT_FILE.name})")
        findings = preflight(fleet, dep)
        for name, items in findings.items():
            print(f"  {name:17} {'READY' if not items else items[0]}")
            for extra in items[1:]:
                print(f"  {'':17} {extra}")
        sys.exit(1 if any(findings.values()) else 0)
    elif args.cmd == "reference":
        findings = check_reference(args.folder, args.agent)
        print(f"{args.folder} for {args.agent}: {'PASS' if not findings else 'FINDINGS'}")
        for x in findings:
            print("  " + x)
        sys.exit(1 if findings else 0)
    else:
        prof = load_deployment().get(args.agent).sandbox
        print(" \\\n  ".join(docker_args(prof, args.agent)))
        print(json.dumps({"sandbox": sdk_sandbox_settings(prof)}, indent=1))


main()
