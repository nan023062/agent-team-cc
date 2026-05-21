"""CBIM machine-level installer.

Installs kernel versions into ``<install_root>/kernel/<version>/`` and
provisions the shared Python virtual environment at ``<install_root>/venv/``.
The install root defaults to ``%LOCALAPPDATA%\\Cbim-CC\\`` on Windows and
``$XDG_DATA_HOME/Cbim-CC/`` (or ``~/.local/share/Cbim-CC``) on POSIX; it
can be overridden via the ``CBIM_INSTALL_ROOT`` env var. See
``installer.paths.install_root()`` for the full resolution order.

Stdlib only — no third-party dependencies.
"""

__all__ = ["install", "registry", "venv_mgr", "bootstrap", "cli", "paths"]
