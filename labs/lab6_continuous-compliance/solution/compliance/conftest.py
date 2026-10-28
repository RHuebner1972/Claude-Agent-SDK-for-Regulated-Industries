"""Lab 6: the fleet compliance suite (the same suite as course-repo/compliance, on assurance_kit).
The fleet compliance suite: every test evidences one or more rubric items for one agent (rubric 7.1).

    uv run pytest compliance                                  # writes compliance-results.json
    FLEET_FILE=proposed-fleet.yaml uv run pytest compliance   # test a proposed configuration before it ships
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]            # solution/ or starter/: assurance_kit lives here
REPO_SRC = HERE.parents[2] / "src"                     # the course toolkit (sentinel.audit, .privacy, ...)
for path in (REPO_SRC, HERE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

pytest_plugins = ["assurance_kit.pytest_plugin"]

from assurance_kit.fleet import load_fleet          # noqa: E402
from assurance_kit.redteam import run_redteam        # noqa: E402
from assurance_kit.runs import run_fleet             # noqa: E402



@pytest.fixture(scope="session")
def fleet():
    return load_fleet()


@pytest.fixture(scope="session")
def runs(fleet, tmp_path_factory):
    """Every agent, run once, offline, exactly as the manifest configures it."""
    return run_fleet(fleet, tmp_path_factory.mktemp("fleet"))


@pytest.fixture(scope="session")
def redteam(fleet):
    return run_redteam(fleet)
