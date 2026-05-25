#!/usr/bin/env python3
"""SessionStart hook — in-process bridge to kernel."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event, write_additional_context
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run

# Dream readiness detection constants — kept in sync with
# engine.dream.api.dream_tick (cannot import here because the hook runs
# before kernel bootstrap completes on every event).
_DREAM_WINDOW_HOURS = 20
_DREAM_HEARTBEAT_STALE_MINUTES = 30


def _build_context(root: Path, session_id: str) -> str:
    cbim = root / ".cbim"

    try:
        from engine.session_log import start_session
        start_session(session_id=session_id, cwd=str(root), cbim=cbim)
    except Exception:
        pass

    memory_out = ""
    try:
        from memory._config import load_config
        from memory.crud.file_backend import FileBackend
        from memory.session_loader import load_context

        store_dir = cbim / "memory"
        backend = FileBackend(store_dir)
        cfg = load_config()
        memory_out = load_context(store_dir, backend, cfg) or ""
    except Exception:
        memory_out = ""

    snapshot_out = ""
    try:
        from cbi._primitives.snapshot import build_snapshot
        snapshot_out = build_snapshot(root.resolve()) or ""
    except Exception:
        snapshot_out = ""

    threshold_banner = None
    try:
        from memory._config import load_config
        short_dir = cbim / "memory" / "short"
        if short_dir.exists():
            count = sum(1 for p in short_dir.glob("*.md") if p.is_file())
            cfg = load_config()
            threshold = int(cfg.get("distill", {}).get("suggest_threshold", 5))
            if count >= threshold:
                threshold_banner = (
                    f"[CBIM] Short-term memory has {count} entries "
                    f"(threshold {threshold}). Consider running "
                    f"`cbim skill show memory_distill` to consolidate."
                )
    except Exception:
        pass

    mem_text = memory_out
    if memory_out.startswith("{"):
        try:
            mem_data = json.loads(memory_out)
            mem_text = mem_data.get("additionalContext", memory_out)
        except json.JSONDecodeError:
            pass

    dream_banner, dream_summary = _dream_signals(cbim)

    parts = [p for p in [dream_banner, dream_summary, threshold_banner,
                         snapshot_out, mem_text] if p]
    return "\n\n---\n\n".join(parts) if parts else ""


def _dream_signals(cbim: Path) -> tuple[str | None, str | None]:
    """Return (dream_banner, dream_summary) tuple, either may be None.

    dream_banner — short prompt nudging the main agent to run dream_tick when:
      - no last_success.json exists at all (never run), OR
      - last success ≥ 20 hours ago, OR
      - current.json shows a stale running tick (heartbeat > 30 min)
    dream_summary — one-line context line from the most recent successful tick.
    """
    dream_dir = cbim / "scheduler" / "dream"
    if not dream_dir.exists():
        return None, None

    last_success_path = dream_dir / "last_success.json"
    current_path = dream_dir / "current.json"

    last_finished_at: datetime | None = None
    last_summary: str | None = None
    last_report_path: str | None = None
    if last_success_path.exists():
        try:
            raw = json.loads(last_success_path.read_text(encoding="utf-8"))
            ts = raw.get("finished_at") or ""
            if ts:
                last_finished_at = _parse_iso(ts)
            last_report_path = raw.get("summary_path")
            step_results = raw.get("step_results") or {}
            if step_results:
                steps_str = " ".join(f"{k}={v}" for k, v in step_results.items())
                last_summary = (
                    f"[CBIM dream] last run {raw.get('run_id','?')} "
                    f"({raw.get('trigger_reason','?')}): {steps_str}"
                )
                if last_report_path:
                    last_summary += f"  · report: {last_report_path}"
        except (OSError, ValueError):
            pass

    now = datetime.now(timezone.utc)
    catchup_overdue = (
        last_finished_at is None
        or (now - last_finished_at) >= timedelta(hours=_DREAM_WINDOW_HOURS)
    )

    stale_running: str | None = None
    if current_path.exists():
        try:
            cur = json.loads(current_path.read_text(encoding="utf-8")) or {}
            if cur.get("status") == "running":
                hb = _parse_iso(cur.get("last_heartbeat", "") or "")
                if hb is None or (now - hb) >= timedelta(minutes=_DREAM_HEARTBEAT_STALE_MINUTES):
                    stale_running = cur.get("run_id") or "?"
        except (OSError, ValueError):
            pass

    banner_lines: list[str] = []
    if stale_running:
        banner_lines.append(
            f"[CBIM dream] stale RUNNING tick `{stale_running}` "
            f"(heartbeat > {_DREAM_HEARTBEAT_STALE_MINUTES} min). Consider "
            f"`dream_abort` to clear it before starting a new tick."
        )
    if catchup_overdue and not stale_running:
        banner_lines.append(
            "[CBIM dream] governance tick is overdue (no successful run in "
            f"the last {_DREAM_WINDOW_HOURS}h). When you have a quiet moment, "
            "run `dream_tick(reason=\"catchup\")` to drive the governance loop."
        )

    dream_banner = "\n".join(banner_lines) if banner_lines else None
    return dream_banner, last_summary


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    session_id = event.get("session_id", "") or ""
    root = project_root_from_cwd(cwd)

    if not bootstrap_kernel(root):
        return 0

    text = safe_run(
        lambda: _build_context(root, session_id),
        on_error_label="session_start",
    )
    if text:
        write_additional_context(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
