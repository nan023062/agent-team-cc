"""Pytest config for v1 kernel tests.

Adds v1/kernel/ to sys.path so `import cbi`, `import engine`, etc. resolve
without requiring an editable install.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent       # v1/tests/
_V1 = _HERE.parent                             # v1/
_KERNEL_SRC = _V1 / "kernel"                   # v1/kernel/

for p in (_KERNEL_SRC,):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


def pytest_configure(config):
    """Register custom markers used by the suite."""
    config.addinivalue_line(
        "markers",
        "requires_api_key: integration test needs ANTHROPIC_API_KEY (skipped by default)",
    )
