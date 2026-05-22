"""Pytest config for v1 kernel tests.

Adds the kernel source directory to sys.path so `import cbim_kernel` resolves
without an installed package.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_V1 = _HERE.parent
_KERNEL_SRC = _V1 / "src" / "kernel"

for p in (_KERNEL_SRC,):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
