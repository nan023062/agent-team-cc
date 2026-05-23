"""Task E — pure explanation task (no code change expected)."""

from __future__ import annotations

from pathlib import Path

from ._common import base_arch_metrics

NAME = "task_e"

PROMPT = """\
The project at the current working directory is a tiny Python calculator (see README.md).

Please read `src/parser.py` and write a 3 to 5 sentence explanation of:

- what the module does
- what its limitations are
- how someone might extend it

Reply with the explanation only — do not modify any files.
"""


def success_check(project_root: Path) -> bool:
    """For task_e, the answer is in stdout; success is checked by runner using stdout."""
    # success_check sees the project, but the actual content is in stdout — checked
    # by the runner via the stdout_check hook below.
    return True


def stdout_check(stdout: str) -> bool:
    """Inspect the model's textual answer."""
    if stdout is None:
        return False
    text = stdout.strip()
    # Strip JSON wrapper if present (claude -p --output-format json).
    import json

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            text = obj.get("result") or obj.get("output") or obj.get("text") or text
            if not isinstance(text, str):
                text = str(text)
    except Exception:
        pass
    if len(text) < 100:
        return False
    lower = text.lower()
    keywords = ("parser", "binary", "operator")
    return all(k in lower for k in keywords)


def arch_metrics_extract(result, project_root: Path, baseline_root: Path) -> dict:
    return base_arch_metrics(result.session_log, result.stdout, project_root, baseline_root)
