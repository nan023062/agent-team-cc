"""Pytest config for v1 kernel tests.

Adds v1/src/kernel/ to sys.path so `import cbi`, `import engine`, etc. resolve
without requiring an editable install.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent       # v1/src/tests/
_SRC = _HERE.parent                            # v1/src/
_KERNEL_SRC = _SRC / "kernel"                  # v1/src/kernel/

for p in (_KERNEL_SRC,):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
