"""The fleet compliance suite: every test evidences one or more rubric items for one agent (rubric 7.1).

    uv run pytest compliance                                  # writes compliance-results.json
    FLEET_FILE=proposed-fleet.yaml uv run pytest compliance   # test a proposed configuration before it ships

test_deployment.py (rubric 1.4, 2.6, 3.3, 3.5, Module 10) is collected only when the manifest declares production
deployments (fleet-prod.yaml). Without a declared deployment there is nothing to test, so those rubric items stay
"missing": absence of a deployment can never score as a pass.
"""
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

pytest_plugins = ["sentinel.monitoring.pytest_plugin"]

from sentinel.monitoring.fleet import load_fleet          # noqa: E402
from sentinel.monitoring.redteam import run_redteam        # noqa: E402
from sentinel.monitoring.runs import run_fleet             # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _declares_deployment() -> bool:
    try:
        return any(a.controls.get("deployment") for a in load_fleet().agents)
    except Exception:                      # an unloadable manifest fails loudly in the other tests
        return False


collect_ignore = [] if _declares_deployment() else ["test_deployment.py"]


@pytest.fixture(scope="session")
def fleet():
    return load_fleet()


@pytest.fixture(scope="session")
def runs(fleet, tmp_path_factory):
    """Every agent, run once, offline, exactly as the manifest configures it."""
    return run_fleet(fleet, tmp_path_factory.mktemp("fleet"))


@pytest.fixture(scope="session")
def deployment():
    from sentinel.deploy import load_deployment
    return load_deployment()


@pytest.fixture(scope="session")
def redteam(fleet):
    return run_redteam(fleet)
