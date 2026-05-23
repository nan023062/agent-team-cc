"""Task B — add eval() function to parser.py + a test."""

from __future__ import annotations

from pathlib import Path

from ._common import base_arch_metrics

NAME = "task_b"

PROMPT = """\
The project at the current working directory is a tiny Python calculator (see README.md).

`src/parser.py` currently has `parse_number` and `parse_binary` but no way to actually
compute a result. Please:

1. Add a function `eval(s: str) -> float` to `src/parser.py` that:
   - calls `parse_binary(s)` to obtain `(left, op, right)`
   - returns the numeric result of applying `op` to `left` and `right`
   - supports all four operators: `+`, `-`, `*`, `/`
   - raises `ValueError` for any other operator
2. Add a new test file `tests/test_parser.py` with at least one test that calls `eval`
   on a non-trivial expression (e.g. `"6 * 7"`) and asserts the expected result.

Do not modify `src/calculator.py`.
"""


def success_check(project_root: Path) -> bool:
    parser_path = project_root / "src" / "parser.py"
    test_path = project_root / "tests" / "test_parser.py"
    if not parser_path.exists() or not test_path.exists():
        return False
    parser_src = parser_path.read_text(encoding="utf-8", errors="replace")
    test_src = test_path.read_text(encoding="utf-8", errors="replace")
    if "def eval" not in parser_src:
        return False
    if "eval" not in test_src or "assert" not in test_src:
        return False
    # All four operators must appear in eval's body region.
    eval_idx = parser_src.find("def eval")
    body = parser_src[eval_idx:]
    return all(op in body for op in ('"+"', '"-"', '"*"', '"/"')) or all(
        op in body for op in ("'+'", "'-'", "'*'", "'/'")
    ) or all(op in body for op in ("+", "-", "*", "/"))


def arch_metrics_extract(result, project_root: Path, baseline_root: Path) -> dict:
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
