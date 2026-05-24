#!/usr/bin/env python3
"""SessionStart hook — in-process bridge to kernel."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event, write_additional_context
from _lib.paths import project_root_from_cwd
from _lib.bridge import bootstrap_kernel, safe_run


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

    parts = [p for p in [threshold_banner, snapshot_out, mem_text] if p]
    return "\n\n---\n\n".join(parts) if parts else ""


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
