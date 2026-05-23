"""Task A — fix divide-by-zero bug + add test."""

from __future__ import annotations

from pathlib import Path

from ._common import base_arch_metrics

NAME = "task_a"

PROMPT = """\
The project at the current working directory is a tiny Python calculator (see README.md).

The function `divide` in `src/calculator.py` does not handle a zero divisor — it currently
lets Python raise a bare `ZeroDivisionError`. Please:

1. Modify `divide` so that calling it with `b == 0` raises a `ValueError` with a
   clear message (e.g. "cannot divide by zero").
2. Add at least one test in `tests/test_calculator.py` that calls `divide` with a zero
   divisor and asserts the `ValueError` is raised. Use `pytest.raises(ValueError)`.

Edit only those two files. Do not change the behavior of `add`, `subtract`, `multiply`.
"""


def success_check(project_root: Path) -> bool:
    calc_path = project_root / "src" / "calculator.py"
    test_path = project_root / "tests" / "test_calculator.py"
    if not calc_path.exists() or not test_path.exists():
        return False
    calc = calc_path.read_text(encoding="utf-8", errors="replace")
    test = test_path.read_text(encoding="utf-8", errors="replace")
    if "ValueError" not in calc:
        return False
    if "divide" not in test:
        return False
    if "raises" not in test:
        return False
    # Look for a zero arg in a divide call inside the test file.
    lower = test.lower()
    return "divide(" in test and ("0)" in test.replace(" ", "") or "zero" in lower)


def arch_metrics_extract(result, project_root: Path, baseline_root: Path) -> dict:
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
