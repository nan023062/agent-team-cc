"""actions/finalize.py — close out a dream tick.

Writes `.cbim/scheduler/dream/last_success.json` with the canonical fields
{run_id, finished_at, summary_path} per WORKFLOW-DREAM §四. Also stamps
bb.finished_at.

Even if upstream steps all failed, FinalizeDreamTick still runs — this is
deliberate (the 20-hour window must roll forward; retrying a perpetually
failing tick every session is worse than letting it lapse and try again
tomorrow).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from engine.core.node import Node, Status


class FinalizeDreamTick(Node):
    def __init__(self, *, scheduler_root: Path, name: str = "FinalizeDreamTick") -> None:
        self.name = name
        self._scheduler_root = Path(scheduler_root)

    def tick(self, bb) -> Status:
        try:
            finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            bb.finished_at = finished_at
            dream_dir = self._scheduler_root / "dream"
            dream_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "run_id": bb.run_id,
                "finished_at": finished_at,
                "summary_path": bb.report_path,
                "step_results": bb.step_results or {},
                "trigger_reason": bb.trigger_reason,
            }
            target = dream_dir / "last_success.json"
            tmp = dream_dir / "last_success.json.tmp"
            tmp.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            os.replace(tmp, target)
            # Best-effort: clear current.json so SessionStart sees no in-flight tick.
            current = dream_dir / "current.json"
            if current.exists():
                try:
                    current.unlink()
                except OSError:
                    pass
        except Exception:
            # Don't propagate — finalize is best-effort by design.
            return Status.FAILURE
        return Status.SUCCESS
