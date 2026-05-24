"""
compaction/health.py — HealthChecker.

Phase 4A: SKELETON. The contract (compaction/.dna/module.md Key Decision #3):
- Compaction owns health thresholds; audit must NOT re-implement them.
- audit reaches indicators via the parent facade's stats() and decides
  whether to surface a finding.
- HealthChecker.check() returns a HealthReport — does NOT emit, log, or
  notify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class HealthReport:
    indicators: dict = field(default_factory=dict)
    breaches: list[str] = field(default_factory=list)


class HealthChecker:

    def __init__(self, store_dir: Path) -> None:
        self._store = Path(store_dir)

    def check(self) -> HealthReport:
        """Skeleton stub. 4B will read stats and compare to thresholds."""
        # TODO 4B: pull stats, compare to thresholds, fill report.
        return HealthReport()
