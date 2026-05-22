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
    """Return the project root directory (the directory containing .cbim/).

    Resolution order:
      1. CBIM_PROJECT_ROOT env var (set by the launcher) wins.
      2. Walk up from cwd looking for `.cbim/config.json` (or `.cbim/` dir).

    Hard boundaries during the fallback walk:
      - Never accept `Path.home()` as a project root. The user home commonly
        contains a global `~/.cbim/` for kernel installation state; treating
        it as a project root has caused `cbim init` to silently overwrite
        user-global files. Raise instead.
      - Never silently return the filesystem root. If the walk reaches it
        without finding a project marker, fall back to cwd (which may itself
        not be a project — callers that need a real project must check).
    """
    if "CBIM_PROJECT_ROOT" in os.environ:
        return Path(os.environ["CBIM_PROJECT_ROOT"])
    # Fallback: walk up from cwd, stopping hard at the user's home directory.
    cwd = Path.cwd().resolve()
    try:
        home = Path.home().resolve()
    except (RuntimeError, OSError):
        home = None
    for candidate in [cwd, *cwd.parents]:
        if home is not None and candidate == home:
            raise RuntimeError(
                "refusing to treat user home as a CBIM project root "
                f"({candidate}); run from inside a project directory or set "
                "CBIM_PROJECT_ROOT explicitly"
            )
        if (candidate / ".cbim" / "config.json").exists():
            return candidate
        if (candidate / ".cbim").is_dir():
            return candidate
    # Reached filesystem root without finding a project marker. Degrade to cwd
    # so read-only callers still work; write callers must validate themselves.
    return cwd


def kernel_root() -> Path:
    """Return the kernel installation root (the directory containing engine/, cbi/, ...)."""
    if "CBIM_KERNEL_ROOT" in os.environ:
        return Path(os.environ["CBIM_KERNEL_ROOT"])
    # Fallback: derive from this file's location
    return Path(__file__).parent


def cbim_dir() -> Path:
    """Return the .cbim/ state directory (always project_root() / '.cbim')."""
    return project_root() / ".cbim"
