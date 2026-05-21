"""Pytest config for v1 kernel-side tests under v1/src/kernel/tests.

Adds the kernel source and installer source to sys.path so `import
cbim_kernel` and `import installer` resolve without an installed package.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent           # v1/src/kernel/tests
_KERNEL_SRC = _HERE.parent                        # v1/src/kernel
_SRC = _KERNEL_SRC.parent                         # v1/src

for p in (_KERNEL_SRC, _SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
