"""memory.compaction — identify/compact + candidates/ work area + health.

Phase 4A: most operations are skeletons; only archiver.sweep_expired and
rebuilder.rebuild are wired. Both route through crud.primitives.delete /
.write to keep the store-mutation surface single-sourced.
"""

from .archiver import sweep_expired
from .candidates import CANDIDATES_SUBDIR, CandidatesArea
from .compactor import CompactionReport, compact
from .health import HealthChecker, HealthReport
from .identifier import identify
from .promote_builder import scan_for_promote_candidates
from .rebuilder import rebuild

__all__ = [
    "CANDIDATES_SUBDIR",
    "CandidatesArea",
    "CompactionReport",
    "HealthChecker",
    "HealthReport",
    "compact",
    "identify",
    "rebuild",
    "scan_for_promote_candidates",
    "sweep_expired",
]
