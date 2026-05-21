"""CBIM machine-level installer.

Installs kernel versions into ``~/.cbim/kernel/<version>/`` and provisions
the shared Python virtual environment at ``~/.cbim/venv/``.

Stdlib only — no third-party dependencies.
"""

__all__ = ["install", "registry", "venv_mgr", "bootstrap", "cli"]
