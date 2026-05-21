"""Pytest config for v1 kernel tests.

Adds the kernel source directory to sys.path so `import cbim_kernel` and
`import cbim_launcher` resolve without an installed package.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_V1 = _HERE.parent
_KERNEL_SRC = _V1 / "src" / "kernel"
_BIN_SRC = _V1 / "src" / "bin"
_SRC = _V1 / "src"  # for `import installer.*`

for p in (_KERNEL_SRC, _BIN_SRC, _SRC):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)
