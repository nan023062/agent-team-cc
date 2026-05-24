"""actions/emit_report.py — write report.md + summary_for_session.

Even when all three steps failed, EmitReport still runs (it lives OUTSIDE
the SequenceTolerant container). The report records partial results / errors
so the next SessionStart has something to surface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.bt.core.node import Node, Status


class EmitReport(Node):
    def __init__(self, *, scheduler_root: Path, name: str = "EmitReport") -> None:
        self.name = name
        self._scheduler_root = Path(scheduler_root)

    def tick(self, bb) -> Status:
        try:
            run_id = bb.run_id or "_unset"
            tick_dir = self._scheduler_root / "dream" / run_id
            tick_dir.mkdir(parents=True, exist_ok=True)
            md = _render_report(bb)
            report_path = tick_dir / "report.md"
            tmp = tick_dir / "report.md.tmp"
            tmp.write_text(md, encoding="utf-8")
            tmp.replace(report_path)
            bb.report_path = str(report_path)
            bb.summary_for_session = _render_summary(bb)
        except Exception as e:
            # Failing to write the report should not kill Finalize — record
            # the error on bb and let the downstream Finalize still rotate
            # the 20h window.
            bb.summary_for_session = f"[CBIM dream] report emit failed: {e}"
            return Status.FAILURE
        return Status.SUCCESS


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_report(bb) -> str:
    lines: list[str] = []
    lines.append(f"# Dream Tick Report — {bb.run_id}")
    lines.append("")
    lines.append(f"- trigger_reason: `{bb.trigger_reason or '?'}`")
    lines.append(f"- started_at: `{bb.started_at or '?'}`")
    lines.append(f"- generated_at: `{_now_iso()}`")
    lines.append("")
    lines.append("## Step results")
    results = bb.step_results or {}
    if not results:
        lines.append("- (no steps recorded)")
    else:
        for step, status in results.items():
            lines.append(f"- `{step}`: **{status}**")
    lines.append("")
    lines.append("## Memory governance")
    lines.append(_yaml_block({
        "mem_health": bb.mem_health,
        "mem_compact_result": bb.mem_compact_result,
        "mem_sweep_result": bb.mem_sweep_result,
        "mem_index_result": bb.mem_index_result,
    }))
    lines.append("## Knowledge governance (Architect)")
    lines.append(_yaml_block(bb.arch_governance_report or {}))
    lines.append("## Capability governance (HR)")
    lines.append(_yaml_block(bb.hr_governance_report or {}))
    return "\n".join(lines) + "\n"


def _render_summary(bb) -> str:
    results = bb.step_results or {}
    parts = [f"{k}={v}" for k, v in results.items()]
    return f"[CBIM dream {bb.run_id}] {' '.join(parts) if parts else 'no steps recorded'}"


def _yaml_block(payload: Any) -> str:
    import json
    body = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    return "```json\n" + body + "\n```\n"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
