"""Point the Lab 5 tests at your work (starter/) or the reference solution (solution/, the default).

    LAB_IMPL=starter uv run pytest labs/lab5_data-boundaries     # check your work
    uv run pytest labs/lab5_data-boundaries                      # check the reference solution
"""
import os
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parents[1]
IMPL = os.getenv("LAB_IMPL", "solution")
for path in (REPO / "src", LAB / IMPL):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
