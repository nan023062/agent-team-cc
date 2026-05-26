#!/usr/bin/env python3
"""SessionStart hook — in-process bridge to kernel.

Phase 4 (memory v2) redesign:

The v1 responsibility was to query short-tier memory and inject the top-K
entries into Claude Code's `additionalContext`. That role moved out: the
execution behaviour tree now has a ContextRetrieval node that runs the
same retrieval against `engine.retrieval` on every tick.

What this hook does in v2:

  1. **Index quick-sync for git-shared sources** (.dna/ and .claude/agents/):
     - `engine.retrieval.verify_consistency(source, mode="fast")` detects
       modified files (mtime/size mismatch — re-indexed) and deleted files
       (source_path gone — removed from index).
     - A manual scan picks up *new* files (present on disk but not in the
       retrieval `meta.json`) and indexes them.

  2. **Transcript backlog indexing**: scan
     ~/.claude/projects/<slug>/*.jsonl, compare against the
     `transcript` source's known doc_ids, and `index_upsert` anything new.
     The stop hook normally takes care of this for the just-ended session,
     but a session that crashed before Stop fired (or a fresh install on
     an existing project) leaves un-indexed transcripts on disk; this is
     the catch-up path.

  3. **Dream tick banner** (unchanged): nudge the main agent to run
     `dream_tick(reason="catchup")` when the 20-hour window has elapsed,
     or to abort a stale RUNNING tick.

This hook MUST NOT block CC startup. Every retrieval call is wrapped in
safe_run; an empty additionalContext is preferable to a broken hook.
"""
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


# ---------------------------------------------------------------------------
# Retrieval index sync — .dna / .claude/agents / transcripts
# ---------------------------------------------------------------------------


def _iter_dna_modules(root: Path) -> list[tuple[str, Path]]:
    """Walk the project tree for .dna/module.md files.

    Returns (doc_id, source_path) tuples where doc_id is the module path
    relative to the project root (matching `cbim dna list` and how MCP
    callers reference modules), and source_path is the absolute
    .dna/module.md path used both as the file we read and as the
    retrieval metadata.source_path.

    Skips heavy / vendored directories so the scan stays fast even on
    repos with thousands of files.
    """
    out: list[tuple[str, Path]] = []
    skip_dirs = {
        ".git", "node_modules", "__pycache__", ".venv", "venv", ".tox",
        "dist", "build", ".idea", ".vscode", ".cbim",
    }

    # The .dna/ marker is one level below the module dir, so we look for
    # any directory named ".dna" containing a module.md.
    def _walk(d: Path) -> None:
        try:
            children = list(d.iterdir())
        except OSError:
            return
        for child in children:
            name = child.name
            if name in skip_dirs:
                continue
            if not child.is_dir():
                continue
            if name == ".dna":
                module_md = child / "module.md"
                if module_md.is_file():
                    module_dir = child.parent
                    try:
                        rel = module_dir.resolve().relative_to(root.resolve())
                    except ValueError:
                        continue
                    doc_id = rel.as_posix() or "."
                    out.append((doc_id, module_md.resolve()))
                # Do NOT descend into .dna/ itself.
                continue
            _walk(child)

    _walk(root)
    return out


def _iter_agents(root: Path) -> list[tuple[str, Path]]:
    """List `.claude/agents/<name>/<name>.md` agent files.

    doc_id  = agent name (the directory basename) — matches what
              `agent_*` MCP tools key on.
    """
    out: list[tuple[str, Path]] = []
    agents_dir = root / ".claude" / "agents"
    if not agents_dir.is_dir():
        return out
    for child in agents_dir.iterdir():
        if not child.is_dir():
            continue
        agent_md = child / f"{child.name}.md"
        if agent_md.is_file():
            out.append((child.name, agent_md.resolve()))
    return out


def _sync_source_with_disk(source: str,
                           on_disk: list[tuple[str, Path]],
                           ) -> None:
    """Reconcile a retrieval source with the current on-disk files.

    Strategy:
      1. Pull current meta.json doc_ids via stats() / facade internals.
      2. `verify_consistency(source, "fast")` handles modified-via-mtime
         and deleted-on-disk drift for ids we already know about.
      3. For ids that exist on disk but not in meta.json yet, read and
         index_upsert them.

    Both `verify_consistency` and `index_upsert` already swallow / handle
    embedding failures internally; we only need to guard against the
    retrieval module not being importable.
    """
    try:
        from engine.retrieval import index_upsert, verify_consistency
        from engine.retrieval.facade import _facade  # internal but stable
    except Exception:
        return

    # Step 1+2: drift fix for known ids.
    try:
        verify_consistency(source, "fast")
    except Exception:
        # Failure here just means we re-check on the next session.
        pass

    # Step 3: pick up brand-new files. We peek at the facade's records
    # to know which doc_ids exist; this is the cheapest way to compute
    # set difference without re-reading every meta.json from disk.
    try:
        state = _facade()._get(source)
        known = set(state.records.keys())
    except Exception:
        known = set()

    for doc_id, src_path in on_disk:
        if doc_id in known:
            continue
        try:
            content = src_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not content:
            continue
        try:
            index_upsert(
                source,
                doc_id,
                content,
                {"source_path": str(src_path)},
            )
        except Exception:
            # Single-file failure must not stop the rest of the scan.
            continue


def _sync_transcripts(root: Path) -> None:
    """Catch-up index of any ~/.claude/projects/<slug>/*.jsonl missing
    from the `transcript` retrieval source.

    The stop hook handles per-session indexing on a clean exit. This
    runs at session start to handle the not-clean-exit case (CC
    crashed, machine rebooted, project freshly cloned to a new box).

    Slug derivation is shared via ``memory._lib.paths.cc_transcripts_dir``.
    """
    try:
        from memory._lib.paths import cc_transcripts_dir
    except Exception:
        return
    try:
        tdir = cc_transcripts_dir(root)
    except (RuntimeError, OSError):
        return
    if not tdir.is_dir():
        return

    try:
        from engine.retrieval import index_upsert
        from engine.retrieval.facade import _facade
    except Exception:
        return

    try:
        state = _facade()._get("transcript")
        known = set(state.records.keys())
    except Exception:
        known = set()

    for p in tdir.glob("*.jsonl"):
        try:
            if not p.is_file():
                continue
        except OSError:
            continue
        abs_path = str(p.resolve())
        if abs_path in known:
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not content:
            continue
        try:
            index_upsert(
                "transcript",
                abs_path,
                content,
                {"source_path": abs_path},
            )
        except Exception:
            continue


def _refresh_indexes(root: Path) -> None:
    """Run the three index sync passes; each is independently guarded."""
    safe_run(
        lambda: _sync_source_with_disk("dna", _iter_dna_modules(root)),
        on_error_label="session_start.sync_dna",
    )
    safe_run(
        lambda: _sync_source_with_disk("agents", _iter_agents(root)),
        on_error_label="session_start.sync_agents",
    )
    safe_run(
        lambda: _sync_transcripts(root),
        on_error_label="session_start.sync_transcripts",
    )


# ---------------------------------------------------------------------------
# additionalContext payload — banners and snapshot only
# ---------------------------------------------------------------------------


def _build_context(root: Path, session_id: str) -> str:
    cbim = root / ".cbim"

    try:
        from engine.session_log import start_session
        start_session(session_id=session_id, cwd=str(root), cbim=cbim)
    except Exception:
        pass

    # Run the retrieval index sync passes before composing context — this
    # is the per-session refresh of all four retrieval sources except
    # memory_medium (which memory.crud keeps in sync at write time).
    _refresh_indexes(root)

    snapshot_out = ""
    try:
        from cbi._primitives.snapshot import build_snapshot
        snapshot_out = build_snapshot(root.resolve()) or ""
    except Exception:
        snapshot_out = ""

    dream_banner, dream_summary = _dream_signals(cbim)

    parts = [p for p in [dream_banner, dream_summary, snapshot_out] if p]
    return "\n\n---\n\n".join(parts) if parts else ""


def _dream_signals(cbim: Path) -> tuple[str | None, str | None]:
    """Return (dream_banner, dream_summary) tuple, either may be None.

    dream_banner — short prompt nudging the main agent to run dream_tick when:
      - no last_success.json exists at all (never run), OR
      - last success >= 20 hours ago, OR
      - current.json shows a stale running tick (heartbeat > 30 min)
    dream_summary — one-line context line from the most recent successful tick.

    Catchup wording reflects the v2 governance memory step: when overdue,
    the loop will dispatch the main agent to distill un-distilled
    transcripts before running the architect / HR governance passes.
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
            f"the last {_DREAM_WINDOW_HOURS}h). When you have a quiet "
            "moment, run `dream_tick(reason=\"catchup\")`. The memory step "
            "will dispatch the main agent first to distill any pending "
            "transcripts, then run the architect / HR governance passes."
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
