"""
install.py — Legacy script-based installer entry point.

Prefer the bootstrap install documented in README.md at the repo root.
This script is kept for users who want a one-command install:

    python install/install.py
"""

import sys
from pathlib import Path

# Don't drop __pycache__ next to source files.
sys.dont_write_bytecode = True

_here = Path(__file__).resolve().parent      # install/
_root = _here.parent                          # repo root
_cbim = _root / ".cbim"                       # .cbim/ (for engine.cli inline command builder)

sys.path.insert(0, str(_root))   # so 'install' package is importable
sys.path.insert(0, str(_cbim))   # so settings.py can import engine.cli

from install.cli import main

sys.exit(main())
