"""
mcp_server/tools/runtime.py — Runtime/ops MCP tools for slash commands.

Exposes:
  dashboard_ensure_running(cwd)  — start dashboard if not running; idempotent
  debug_get(cwd)                  — read .cbim/.debug flag
  debug_set(state, cwd)           — toggle .cbim/.debug
  log_show(lines, cwd)            — tail of current session log

These tools are the LLM-side back-end for the
/cbim_dashboard, /cbim_debug, /cbim_log slash commands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Project root resolution (same convention as memory/dna tools)
# ---------------------------------------------------------------------------

def _project_root(cwd: str) -> Path:
    p = (Path(cwd) if cwd else Path.cwd()).resolve()
    for _ in range(6):
        if (p / ".cbim").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    raise RuntimeError(
        f"No .cbim/ directory found walking up from {cwd or Path.cwd()}; "
        f"cannot locate project root."
    )


# ---------------------------------------------------------------------------
# Dashboard spawn — mirrors project/hooks_src/cbim_auto_preview.py
#
# Kept as a parallel implementation rather than imported from the hook
# script because the hook lives under project/hooks_src/ (an install-time
# artefact copied into <project>/.claude/hooks/), and its parent dir is
# NOT on sys.path inside the MCP server process. Both paths use the
# same kernel CLI entry (`python -m engine dashboard`), so the spawn
# command itself is the single source of truth — divergence would mean
# someone changed the CLI shape, which is detectable.
# ---------------------------------------------------------------------------

def _read_dashboard_cfg(cbim: Path) -> dict:
    p = cbim / "config.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("dashboard", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _python_exe(root: Path, cbim: Path) -> str:
    for base in (root, cbim):
        for candidate in (
            base / ".venv" / "Scripts" / "python.exe",
            base / ".venv" / "bin" / "python",
        ):
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True,
        )
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_pid_file(pid_path: Path) -> tuple[int, int] | None:
    """Return (pid, port) from the dashboard pid file, or None."""
    if not pid_path.exists():
        return None
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        data = json.loads(raw)
        return int(data["pid"]), int(data.get("port") or 0)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        try:
            return int(raw), 0
        except ValueError:
            return None


def _kernel_root() -> Path:
    """Resolve the kernel root from this module's location.

    runtime.py lives at <kernel>/mcp_server/tools/runtime.py — go up two.
    """
    return Path(__file__).resolve().parent.parent.parent


def _launch_dashboard(root: Path, cbim: Path, no_browser: bool) -> None:
    python = _python_exe(root, cbim)
    args = [python, "-m", "engine", "dashboard"]
    if no_browser:
        args.append("--no-browser")

    env = os.environ.copy()
    kp = str(_kernel_root())
    env["PYTHONPATH"] = kp + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    kwargs: dict = dict(cwd=str(root), env=env)
    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
        kwargs["stdin"] = subprocess.DEVNULL
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    subprocess.Popen(args, **kwargs)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------

def register(mcp) -> None:
    @mcp.tool()
    def dashboard_ensure_running(cwd: str = "") -> str:
        """Ensure the CBIM dashboard server is running; return its URL.

        Idempotent: if a live server is already recorded in
        `.cbim/dashboard/.run/.preview.pid`, returns that endpoint
        without spawning. Otherwise launches `python -m engine dashboard`
        as a detached subprocess and returns the configured URL.

        Args:
            cwd: Project directory (default: current working dir).

        Returns:
            JSON dict {pid, port, started, url}. `started` is True if this
            call spawned a new process. `port` may be 0 when a freshly-
            spawned server has not yet written its pid file — caller can
            use the `url` field directly (it falls back to the configured
            port).
        """
        try:
            root = _project_root(cwd)
        except RuntimeError as e:
            return json.dumps({"error": str(e)})

        cbim = root / ".cbim"
        pid_path = cbim / "dashboard" / ".run" / ".preview.pid"
        cfg = _read_dashboard_cfg(cbim)
        cfg_port = int(cfg.get("port") or 8765)

        existing = _read_pid_file(pid_path)
        if existing is not None and _pid_alive(existing[0]):
            pid, port = existing
            port = port or cfg_port
            return json.dumps({
                "pid": pid,
                "port": port,
                "started": False,
                "url": f"http://127.0.0.1:{port}",
            })

        # Stale pid file (process dead) — clean it up so the new server
        # can re-write atomically without confusing concurrent readers.
        if existing is not None:
            pid_path.unlink(missing_ok=True)

        in_ci = bool(os.environ.get("CI"))
        open_browser = cfg.get("open_browser", True) and not in_ci
        _launch_dashboard(root, cbim, no_browser=not open_browser)

        # The just-spawned server writes its pid file asynchronously.
        # We don't block waiting for it — slash command will display the
        # url, and the live port will be reflected on next call.
        return json.dumps({
            "pid": 0,
            "port": cfg_port,
            "started": True,
            "url": f"http://127.0.0.1:{cfg_port}",
        })

    @mcp.tool()
    def debug_get(cwd: str = "") -> str:
        """Return current state of the .cbim/.debug flag.

        Args:
            cwd: Project directory (default: current working dir).

        Returns:
            JSON dict {enabled: bool}.
        """
        try:
            root = _project_root(cwd)
        except RuntimeError as e:
            return json.dumps({"error": str(e)})
        flag = root / ".cbim" / ".debug"
        return json.dumps({"enabled": flag.exists()})

    @mcp.tool()
    def debug_set(state: str, cwd: str = "") -> str:
        """Toggle the .cbim/.debug flag.

        Args:
            state: "on" creates the flag file; "off" deletes it.
            cwd:   Project directory (default: current working dir).

        Returns:
            JSON dict {ok: bool, enabled: bool} reflecting the final state,
            or {error: str} on invalid input.
        """
        if state not in ("on", "off"):
            return json.dumps({"error": f"state must be 'on' or 'off', got {state!r}"})
        try:
            root = _project_root(cwd)
        except RuntimeError as e:
            return json.dumps({"error": str(e)})
        flag = root / ".cbim" / ".debug"
        if state == "on":
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch(exist_ok=True)
        else:
            flag.unlink(missing_ok=True)
        return json.dumps({"ok": True, "enabled": flag.exists()})

    @mcp.tool()
    def log_show(lines: int = 50, cwd: str = "") -> str:
        """Return the last N lines of the current session log.

        Args:
            lines: Tail length (default 50, clamped to >=1).
            cwd:   Project directory (default: current working dir).

        Returns:
            JSON dict {session_log: str, session_file: str}. Both empty
            when no session log exists yet (SessionStart hook hasn't run).
        """
        try:
            root = _project_root(cwd)
        except RuntimeError as e:
            return json.dumps({"error": str(e)})

        n = max(1, int(lines))
        logs_dir = root / ".cbim" / "logs"
        if not logs_dir.is_dir():
            return json.dumps({"session_log": "", "session_file": ""})

        # Prefer the active-session pointer; fall back to most-recent file.
        target: Path | None = None
        pointer = logs_dir / ".current"
        if pointer.exists():
            try:
                p = Path(pointer.read_text(encoding="utf-8").strip())
                if p.exists():
                    target = p
            except OSError:
                target = None
        if target is None:
            candidates = sorted(logs_dir.glob("session_*.log"))
            target = candidates[-1] if candidates else None

        if target is None or not target.exists():
            return json.dumps({"session_log": "", "session_file": ""})

        try:
            with target.open("r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except OSError as e:
            return json.dumps({"error": f"read failed: {e}"})

        tail = "".join(all_lines[-n:])
        return json.dumps({
            "session_log": tail,
            "session_file": target.name,
        })
