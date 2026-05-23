"""
mcp_server/tools/hook.py — MCP tools called by Claude Code hooks.

Phase 1 surface: these tools are REGISTERED here so the MCP `tools/list`
surface includes them. The hook client (UDS sidecar) and the wiring that
makes hooks call them are Phase 2/3a — not in this phase.

Six tools:
  snapshot_for_session_start(session_id, cwd) -> {additionalContext: str}
  memory_distill_session(transcript_path, cwd) -> {entry_path: str | null}
  cc_status_set(state, cwd) -> {ok: bool}
  session_log_append(kind, payload, transcript_path, cwd) -> {ok: bool}
  tool_call_log(phase, tool, tool_input, tool_response, transcript_path, cwd) -> {ok: bool}
  dashboard_ensure_running(cwd) -> {pid: int, started: bool}
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def _cbim_dir(cwd: str) -> Path:
    """Resolve `<project>/.cbim/` for the given `cwd`, walking up to find it."""
    p = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    cur = p
    for _ in range(6):
        if (cur / ".cbim").is_dir():
            return cur / ".cbim"
        if cur.parent == cur:
            break
        cur = cur.parent
    return p / ".cbim"


def _project_root_from_cwd(cwd: str) -> Path:
    return _cbim_dir(cwd).parent


def register(mcp) -> None:
    @mcp.tool()
    def snapshot_for_session_start(session_id: str, cwd: str) -> dict:
        """Build the combined session-start additionalContext payload.

        Server-side aggregation of: (1) opening a fresh session log,
        (2) load_context from the memory engine, (3) build_snapshot of the
        project knowledge tree, (4) a short-term memory threshold banner.

        Args:
            session_id: Claude Code session id (from SessionStart event).
            cwd:        Project directory.

        Returns:
            {"additionalContext": str} — the same payload the legacy
            `load_memory.py` hook used to emit. Empty string when nothing
            to surface.
        """
        cbim = _cbim_dir(cwd)
        root = cbim.parent

        try:
            from engine.session_log import start_session
            start_session(session_id=session_id, cwd=str(root), cbim=cbim)
        except Exception:
            pass

        memory_out = ""
        try:
            from memory.engine.config import load_config
            from memory.engine.engine import MemoryEngine
            from memory.engine.file_backend import FileBackend
            from memory.engine.loader import load_context

            store_dir = cbim / "memory"
            engine = MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)
            cfg = load_config()
            memory_out = load_context(store_dir, engine, cfg) or ""
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
            from memory.engine.config import load_config
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
        combined = "\n\n---\n\n".join(parts) if parts else ""
        return {"additionalContext": combined}

    @mcp.tool()
    def memory_distill_session(transcript_path: str, cwd: str) -> dict:
        """Distill the current session transcript into a short-term memory entry.

        Wraps `memory.engine.writer.write_session`. The server reads the
        transcript file from the path supplied by the client.

        Args:
            transcript_path: Absolute path to the Claude Code transcript JSONL.
            cwd:             Project directory.

        Returns:
            {"entry_path": str | null} — absolute path of the written entry,
            or null when nothing was written (empty transcript, distill skip
            heuristic, etc.).
        """
        cbim = _cbim_dir(cwd)
        try:
            from memory.engine.config import load_config
            from memory.engine.engine import MemoryEngine
            from memory.engine.file_backend import FileBackend
            from memory.engine.writer import write_session

            store_dir = cbim / "memory"
            engine = MemoryEngine(backend=FileBackend(store_dir), store_dir=store_dir)
            cfg = load_config()
            path = write_session(transcript_path, store_dir, engine, cfg)
            return {"entry_path": str(path) if path else None}
        except Exception as e:
            return {"entry_path": None, "error": str(e)}

    @mcp.tool()
    def cc_status_set(state: str, cwd: str) -> dict:
        """Write `<cbim>/.cc-status` with the given state and an ISO timestamp.

        Args:
            state: "busy" or "idle".
            cwd:   Project directory.
        """
        if state not in ("busy", "idle"):
            return {"ok": False, "error": f"state must be 'busy' or 'idle', got {state!r}"}
        cbim = _cbim_dir(cwd)
        try:
            from datetime import datetime
            cbim.mkdir(parents=True, exist_ok=True)
            (cbim / ".cc-status").write_text(
                f"{state} {datetime.now().isoformat()}\n", encoding="utf-8"
            )
            return {"ok": True}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    def session_log_append(
        kind: str,
        payload: dict,
        transcript_path: str,
        cwd: str,
    ) -> dict:
        """Append a structured entry to the current session log.

        Args:
            kind:            "user" | "session_end".
                             "user"        -> payload {"prompt": str}
                             "session_end" -> payload {"session_id": str, "reason": str}
            payload:         Per-kind dict (see above).
            transcript_path: Claude Code transcript path (used for [agent] label).
            cwd:             Project directory.
        """
        cbim = _cbim_dir(cwd)
        try:
            if kind == "user":
                from engine.logger import log_user
                log_user(
                    payload.get("prompt", ""),
                    cbim=cbim,
                    transcript_path=transcript_path or "",
                )
            elif kind == "session_end":
                from engine.logger import end_session
                end_session(
                    session_id=payload.get("session_id", ""),
                    reason=payload.get("reason", "") or "unknown",
                    cbim=cbim,
                )
            else:
                return {"ok": False, "error": f"unknown kind: {kind!r}"}
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    def tool_call_log(
        phase: str,
        tool: str,
        tool_input: dict,
        tool_response: dict | None,
        transcript_path: str,
        cwd: str,
    ) -> dict:
        """Log a pre-tool or post-tool entry to the session log.

        Debug-only [ENG]/[IMP] lines are gated on `<cbim>/.debug`; the gate
        is read server-side, no flag in the call.

        Args:
            phase:           "pre" | "post".
            tool:            Tool name (e.g. "Read", "Bash").
            tool_input:      Tool input dict from the hook event.
            tool_response:   Tool response dict (post only; None for pre).
            transcript_path: Claude Code transcript path.
            cwd:             Project directory.
        """
        cbim = _cbim_dir(cwd)
        try:
            if phase == "pre":
                from engine.logger import log_call
                log_call(tool, tool_input or {}, cbim=cbim, transcript_path=transcript_path or "")
            elif phase == "post":
                from engine.logger import log_ret
                log_ret(
                    tool,
                    tool_input or {},
                    tool_response or {},
                    cbim=cbim,
                    transcript_path=transcript_path or "",
                )
            else:
                return {"ok": False, "error": f"unknown phase: {phase!r}"}
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @mcp.tool()
    def dashboard_ensure_running(cwd: str) -> dict:
        """Ensure the dashboard HTTP server is running; spawn detached if not.

        Reads `<cbim>/dashboard/.run/.preview.pid` to detect an existing
        instance. If the pid file is missing or the recorded process is
        dead, spawns a fresh detached server (no browser, no terminal).

        Args:
            cwd: Project directory.

        Returns:
            {"pid": int, "started": bool, "port": int}
              started=True  -> this call spawned the server.
              started=False -> it was already running.
        """
        import subprocess
        import sys as _sys

        cbim = _cbim_dir(cwd)
        root = cbim.parent
        pid_path = cbim / "dashboard" / ".run" / ".preview.pid"

        if pid_path.exists():
            try:
                data = json.loads(pid_path.read_text(encoding="utf-8"))
                pid = int(data.get("pid", 0))
                port = int(data.get("port", 0))
                if pid > 0 and _process_alive(pid):
                    return {"pid": pid, "started": False, "port": port}
            except (json.JSONDecodeError, OSError, ValueError):
                pass

        # Spawn detached server. Uses the same `.cbim/run dashboard` entry
        # point as the user-facing CLI, with --no-browser so it stays
        # headless. stdout/stderr to DEVNULL — we read the pid file instead.
        run_script = root / ".cbim" / "run"
        if not run_script.exists():
            return {"pid": 0, "started": False, "error": f"missing {run_script}"}

        try:
            proc = subprocess.Popen(
                [_sys.executable, str(run_script), "dashboard", "--no-browser"],
                cwd=str(root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as e:
            return {"pid": 0, "started": False, "error": str(e)}

        # Best-effort: wait briefly for the child to write the pid file so
        # the caller gets the actual bound port; fall back to returning the
        # spawned-process pid if the file never appears.
        import time as _time
        port = 0
        for _ in range(20):
            if pid_path.exists():
                try:
                    data = json.loads(pid_path.read_text(encoding="utf-8"))
                    return {
                        "pid": int(data.get("pid", proc.pid)),
                        "started": True,
                        "port": int(data.get("port", 0)),
                    }
                except (json.JSONDecodeError, OSError, ValueError):
                    pass
            _time.sleep(0.1)
        return {"pid": proc.pid, "started": True, "port": port}


def _process_alive(pid: int) -> bool:
    """POSIX-only liveness check; treat Windows as 'assume alive' for now.

    Phase 1 sees darwin/linux. Windows support is a known Phase 3 follow-up.
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False
