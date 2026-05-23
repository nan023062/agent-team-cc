"""audit/registry.py — name -> check callable map.

Single source of truth for available check names. CLI flag validation and
`list_checks()` read this dict.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .checks import (
    agent_fission,
    dna_fission,
    dna_tree,
    index_consistency,
    memory_threshold,
)
from .result import AuditFinding

CheckFn = Callable[[Path, dict], list[AuditFinding]]

CHECKS: dict[str, CheckFn] = {
    "index_consistency": index_consistency.check,
    "memory_threshold": memory_threshold.check,
    "agent_fission": agent_fission.check,
    "dna_fission": dna_fission.check,
    "dna_tree": dna_tree.check,
}


def list_check_names() -> list[str]:
    return list(CHECKS.keys())
