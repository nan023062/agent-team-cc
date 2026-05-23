"""Task C — add new validator module + test."""

from __future__ import annotations

from pathlib import Path

from ._common import base_arch_metrics

NAME = "task_c"

PROMPT = """\
The project at the current working directory is a tiny Python calculator (see README.md).

Please add a new module `src/validator.py` that exposes a single function:

```python
def validate_number(s: str) -> bool:
    ...
```

`validate_number` returns True iff `s` (after stripping whitespace) is a valid Python
float literal (e.g. "12", "-3.14", "0.5"); and False otherwise (e.g. "", "abc", "1.2.3").

Also add `tests/test_validator.py` with at least two test cases: one for a valid number
and one for an invalid string.

Do not modify any existing files except to add the two new ones.
"""


def success_check(project_root: Path) -> bool:
    vpath = project_root / "src" / "validator.py"
    tpath = project_root / "tests" / "test_validator.py"
    if not vpath.exists() or not tpath.exists():
        return False
    vsrc = vpath.read_text(encoding="utf-8", errors="replace")
    tsrc = tpath.read_text(encoding="utf-8", errors="replace")
    if "def validate_number" not in vsrc:
        return False
    return "validate_number" in tsrc and tsrc.count("assert") >= 2


def arch_metrics_extract(result, project_root: Path, baseline_root: Path) -> dict:
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
