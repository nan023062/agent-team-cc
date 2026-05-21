#!/usr/bin/env python3
"""One-shot CBIM kernel installer.

Run once per machine::

    python install.py

This is the machine-level installer that places the CBIM kernel into
``<install_root>/kernel/<version>/`` and provisions the shared venv at
``<install_root>/venv/``. The install root resolves to
``%LOCALAPPDATA%\\Cbim-CC\\`` on Windows and
``$XDG_DATA_HOME/Cbim-CC/`` (default ``~/.local/share/Cbim-CC``) on POSIX,
and can be overridden via the ``CBIM_INSTALL_ROOT`` env var.

NOTE: The previous project-level installer (``python install/install.py``)
still lives in the ``install/`` package. It is preserved as the migration
path used by ``cbim migrate`` for projects laid out under the old layout.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from installer.bootstrap import copy_installer, print_path_instructions, write_launcher  # noqa: E402
from installer.install import install_from_local  # noqa: E402
from installer.venv_mgr import ensure_venv  # noqa: E402


def main() -> int:
    kernel_src = HERE / "kernel"
    print("[cbim] Installing CBIM kernel...")

    # 1. Install kernel
    install_from_local(kernel_src)

    # 2. Provision shared venv
    req = kernel_src / "requirements.txt"
    if req.is_file():
        print("[cbim] Setting up Python environment...")
        ensure_venv(req)

    # 3. Write launcher
    launcher_src = HERE / "bin" / "cbim_launcher.py"
    bin_dir = write_launcher(launcher_src)

    # 4. Copy installer package so launcher can run cbim upgrade/install/use
    copy_installer(HERE / "installer")

    print("")
    print("[cbim] Installation complete!")
    print_path_instructions(bin_dir)
    print("")
    print("Next: cd your-project && cbim init")
    return 0


if __name__ == "__main__":
    sys.exit(main())
