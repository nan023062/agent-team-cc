"""
Single source of truth for runtime path resolution.

project_root() reads CBIM_PROJECT_ROOT env var (set by the cbim launcher).
kernel_root() reads CBIM_KERNEL_ROOT env var (set by the cbim launcher).

Both fall back gracefully for backward-compat: if the env vars are not set,
walk up from cwd looking for .cbim/config.json (project_root) or use
__file__-relative path (kernel_root). This allows the kernel to work during
the transition period when the old `python .cbim/engine` invocation style is
still in use.
"""
import os
from pathlib import Path


def project_root() -> Path:
    """Return the project root directory (the directory containing .cbim/)."""
    if "CBIM_PROJECT_ROOT" in os.environ:
        return Path(os.environ["CBIM_PROJECT_ROOT"])
    # Fallback: walk up from cwd
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".cbim" / "config.json").exists():
            return candidate
        if (candidate / ".cbim").is_dir():
            return candidate
    return cwd


def kernel_root() -> Path:
    """Return the kernel installation root (the directory containing cbim_kernel/)."""
    if "CBIM_KERNEL_ROOT" in os.environ:
        return Path(os.environ["CBIM_KERNEL_ROOT"])
    # Fallback: derive from this file's location
    return Path(__file__).parent.parent


def cbim_dir() -> Path:
    """Return the .cbim/ state directory (always project_root() / '.cbim')."""
    return project_root() / ".cbim"
