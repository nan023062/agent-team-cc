"""Hook-side bridge: bootstrap kernel sys.path; never raise."""

from __future__ import annotations

import sys
from pathlib import Path


def bootstrap_kernel(project_root: Path) -> bool:
    """Insert `<project>/.cbim/kernel/` at sys.path[0] so kernel modules become importable.

    Returns True when the kernel directory exists and was inserted (or
    already present on sys.path); False when the kernel is missing. Never
    raises.
    """
    kernel = Path(project_root) / ".cbim" / "kernel"
    if not kernel.exists():
        print(
            f"[CBIM:hook] bootstrap: kernel missing at {kernel}",
            file=sys.stderr,
        )
        return False
    p = str(kernel)
    if p not in sys.path:
        sys.path.insert(0, p)
    return True


def safe_run(callable, *, on_error_label: str):
    """Run `callable`; on any exception print `[CBIM:hook] <label>: <err>` to stderr and swallow."""
    try:
        return callable()
    except Exception as e:
        print(
            f"[CBIM:hook] {on_error_label}: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return None
