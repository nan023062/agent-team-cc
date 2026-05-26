"""checks/memory_threshold.py — memory store volume / candidate-backlog drift.

Thin metrics consumer over kernel/memory's compaction.HealthChecker.

Per memory/compaction/.dna Key Decision #3: compaction owns the
thresholds; audit reaches indicators via HealthChecker.check() and
decides whether to surface a finding. Both audit findings mirror the
two HealthReport.breaches codes verbatim so callers that branch on the
codes have a single vocabulary.

v2 surfaces (no short tier, no MEMORY_STALE):

  Audit code              Breach trigger
  ----------------------- -----------------------------------------------
  MEMORY_VOLUME           medium_bytes / 1024 >= medium_max_total_kb
  MEMORY_CANDIDATE_BACKLOG candidate_count >= candidate_max

Severities are deterministic — the thresholds are absolute caps, so
hitting one is always at least a "warn"; doubling the cap escalates to
"error". This mirrors v1's overflow severity band logic, just on v2
indicators.

Audit MUST NOT read .cbim/memory/* directly. Source-grep test
test_audit_does_not_read_memory_files_directly enforces that.
"""
from __future__ import annotations

from pathlib import Path

from ..result import AuditFinding


_SUGGEST_GOVERNANCE = (
    "Run `dream_tick(reason=\"catchup\")` so the governance loop compacts "
    "the medium tier and promotes / drops backlogged candidates."
)


def check(project_root: Path, config: dict) -> list[AuditFinding]:
    """Surface medium-volume / candidate-backlog HealthChecker breaches.

    `config` is accepted for API symmetry but is not consulted; the
    thresholds live in compaction/health._load_thresholds (memory
    config -> hard-coded defaults). Keeping the thresholds inside the
    memory module is the v2 architectural rule.
    """
    findings: list[AuditFinding] = []

    try:
        from memory.compaction.health import HealthChecker
    except ImportError:
        # Memory module not bootstrapped on this sys.path — leave clean
        # findings (caller will just see no memory rules ran).
        return findings

    store_dir = project_root / ".cbim" / "memory"
    if not store_dir.exists():
        return findings

    try:
        report = HealthChecker(store_dir).check()
    except Exception as e:  # pragma: no cover — defensive
        return [
            AuditFinding(
                check="memory_threshold",
                severity="warn",
                target=str(store_dir),
                message=f"HealthChecker raised {type(e).__name__}: {e}",
                code="MEMORY_HEALTH_ERROR",
            )
        ]

    indicators = report.indicators or {}
    thresholds = indicators.get("thresholds") or {}

    if "MEDIUM_VOLUME" in report.breaches:
        medium_bytes = int(indicators.get("medium_bytes", 0))
        threshold_kb = int(thresholds.get("medium_max_total_kb", 0))
        ratio = (medium_bytes / 1024.0) / max(threshold_kb, 1)
        severity = "error" if ratio >= 2.0 else "warn"
        findings.append(AuditFinding(
            check="memory_threshold",
            severity=severity,
            target="medium",
            message=(
                f"medium tier volume {medium_bytes // 1024} KiB exceeds "
                f"threshold {threshold_kb} KiB "
                f"({int(ratio * 100)}% of cap)"
            ),
            suggestion=_SUGGEST_GOVERNANCE,
            code="MEMORY_VOLUME",
            metadata={
                "medium_bytes": medium_bytes,
                "threshold_kb": threshold_kb,
                "ratio": round(ratio, 2),
            },
        ))

    if "CANDIDATES_BACKLOG" in report.breaches:
        candidate_count = int(indicators.get("candidate_count", 0))
        threshold = int(thresholds.get("candidate_max", 0))
        ratio = candidate_count / max(threshold, 1)
        severity = "error" if ratio >= 2.0 else "warn"
        findings.append(AuditFinding(
            check="memory_threshold",
            severity=severity,
            target="candidates",
            message=(
                f"candidates backlog {candidate_count} >= "
                f"threshold {threshold}"
            ),
            suggestion=_SUGGEST_GOVERNANCE,
            code="MEMORY_CANDIDATE_BACKLOG",
            metadata={
                "candidate_count": candidate_count,
                "threshold": threshold,
                "ratio": round(ratio, 2),
            },
        ))

    return findings
