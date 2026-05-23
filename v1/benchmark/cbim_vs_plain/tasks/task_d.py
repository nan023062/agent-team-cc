"""Task D — cross-module refactor: extract common error hierarchy."""

from __future__ import annotations

from pathlib import Path

from ._common import base_arch_metrics

NAME = "task_d"

PROMPT = """\
The project at the current working directory is a tiny Python calculator (see README.md).

Currently `src/calculator.py` and `src/parser.py` both raise bare `ValueError`. Please
introduce a common error hierarchy:

1. Create `src/errors.py` with:
   - `class CalculatorError(Exception)` — base class
   - `class DivisionError(CalculatorError)` — for divide-by-zero
   - `class ParseError(CalculatorError)` — for parser failures
2. Update `src/calculator.py` so `divide(x, 0)` raises `DivisionError` (still a subclass
   of `Exception`, but no longer a bare `ValueError`).
3. Update `src/parser.py` so `parse_binary` raises `ParseError` instead of `ValueError`
   when no operator is found.
4. Update `tests/test_calculator.py` so any existing divide-by-zero test imports and
   asserts on `DivisionError` (or on `CalculatorError`, since the new class is a subclass).
   If no such test exists yet, add one.

Make sure every file is consistent: nothing in `src/` should still raise bare `ValueError`
for these two specific cases.
"""


def success_check(project_root: Path) -> bool:
    errors_path = project_root / "src" / "errors.py"
    calc_path = project_root / "src" / "calculator.py"
    parser_path = project_root / "src" / "parser.py"
    test_path = project_root / "tests" / "test_calculator.py"
    for p in (errors_path, calc_path, parser_path, test_path):
        if not p.exists():
            return False
    errors_src = errors_path.read_text(encoding="utf-8", errors="replace")
    calc_src = calc_path.read_text(encoding="utf-8", errors="replace")
    parser_src = parser_path.read_text(encoding="utf-8", errors="replace")
    test_src = test_path.read_text(encoding="utf-8", errors="replace")
    if "class CalculatorError" not in errors_src:
        return False
    if "class DivisionError" not in errors_src:
        return False
    if "class ParseError" not in errors_src:
        return False
    if "DivisionError" not in calc_src:
        return False
    if "ParseError" not in parser_src:
        return False
    return "DivisionError" in test_src or "CalculatorError" in test_src


def arch_metrics_extract(result, project_root: Path, baseline_root: Path) -> dict:
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
