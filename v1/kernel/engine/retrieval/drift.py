"""DriftChecker — two-stage consistency verification.

fast (mtime+size): for entries whose meta.source_path exists, stat the
file and compare. Mismatches go into the drift list. Required to finish
sub-second per arch decision (SessionStart hook).

full (sha256): re-hash content for every meta entry. Slow path used by
the dream loop's MemRebuildIndex. Catches the same-mtime/same-size edge
case that fast misses, plus index-file corruption.

In Phase 1 the *repair* path here is intentionally minimal: drift items
without a known source_path are reported but not auto-fixed — repair
requires re-reading the original content which only the data-owning
module (memory.crud, hooks, etc.) knows how to do. When source_path *is*
recorded and the file is readable, we re-upsert (mtime/size/hash
refreshed); when the file is missing, we delete the doc.

The caller-facing repair contract: DriftReport.repaired / failed list
the doc_ids that were attempted; everything else is in drifted (caller
must arrange re-upsert through its own write path).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional


# Caller-supplied callbacks: facade injects the actual upsert/delete that
# wire through to the live indexes. Drift module itself stays pure.
ReadDocFn = Callable[[str], Optional[str]]   # doc_id -> content (or None)
UpsertFn = Callable[[str, str, dict], None]  # doc_id, content, metadata
DeleteFn = Callable[[str], None]             # doc_id


@dataclass
class DriftReport:
    source: str
    mode: str
    checked: int = 0
    drifted: List[str] = field(default_factory=list)
    repaired: List[str] = field(default_factory=list)
    failed: List[dict] = field(default_factory=list)  # [{doc_id, error}]
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "mode": self.mode,
            "checked": self.checked,
            "drifted": list(self.drifted),
            "repaired": list(self.repaired),
            "failed": list(self.failed),
            "duration_ms": self.duration_ms,
        }


def fast_check(
    records: Dict[str, "object"],
    read_doc: ReadDocFn,
    upsert: UpsertFn,
    delete: DeleteFn,
) -> DriftReport:
    """records: {doc_id: DocRecord}. Uses DocRecord.mtime/size/source_path."""
    return _check(records, mode="fast", read_doc=read_doc, upsert=upsert, delete=delete)


def full_check(
    records: Dict[str, "object"],
    read_doc: ReadDocFn,
    upsert: UpsertFn,
    delete: DeleteFn,
) -> DriftReport:
    return _check(records, mode="full", read_doc=read_doc, upsert=upsert, delete=delete)


def _check(records, mode, read_doc, upsert, delete) -> DriftReport:
    t0 = time.perf_counter()
    # Caller has the source name; we expect records' first record to carry it
    # via metadata or we accept that the facade fills it in. To keep this
    # module pure, source is unknown here and the facade overrides it later.
    report = DriftReport(source="", mode=mode)
    for doc_id, rec in records.items():
        report.checked += 1
        src_path_str = getattr(rec, "source_path", None)
        snapshot_content = read_doc(doc_id)  # the docs/<doc_id>.txt snapshot we hold

        if src_path_str:
            src_path = Path(src_path_str)
            if not src_path.exists():
                # Original file deleted — try to remove from index.
                try:
                    delete(doc_id)
                    report.drifted.append(doc_id)
                    report.repaired.append(doc_id)
                except Exception as e:  # pragma: no cover — defensive
                    report.failed.append({"doc_id": doc_id, "error": str(e)})
                continue
            try:
                st = src_path.stat()
            except OSError as e:
                report.failed.append({"doc_id": doc_id, "error": f"stat: {e}"})
                continue

            if mode == "fast":
                if st.st_mtime != rec.mtime or st.st_size != rec.size:
                    _attempt_reindex(
                        doc_id, src_path, rec, upsert, report
                    )
            else:  # full
                try:
                    file_hash = _hash_file(src_path)
                except OSError as e:
                    report.failed.append({"doc_id": doc_id, "error": f"hash: {e}"})
                    continue
                if file_hash != rec.sha256:
                    _attempt_reindex(doc_id, src_path, rec, upsert, report)
        else:
            # No known source_path. fast-check has no signal; full-check can
            # still validate the snapshot against its recorded hash.
            if mode == "full":
                if snapshot_content is None:
                    report.drifted.append(doc_id)
                    report.failed.append(
                        {"doc_id": doc_id, "error": "snapshot missing and no source_path"}
                    )
                else:
                    snap_hash = hashlib.sha256(snapshot_content.encode("utf-8")).hexdigest()
                    if snap_hash != rec.sha256:
                        report.drifted.append(doc_id)
                        report.failed.append(
                            {"doc_id": doc_id, "error": "snapshot hash mismatch; no source to refetch"}
                        )

    report.duration_ms = (time.perf_counter() - t0) * 1000.0
    return report


def _attempt_reindex(doc_id, src_path: Path, rec, upsert, report) -> None:
    report.drifted.append(doc_id)
    try:
        content = src_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        report.failed.append({"doc_id": doc_id, "error": f"read: {e}"})
        return
    try:
        upsert(doc_id, content, dict(rec.metadata or {}))
        report.repaired.append(doc_id)
    except Exception as e:  # pragma: no cover — defensive
        report.failed.append({"doc_id": doc_id, "error": f"reindex: {e}"})


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
