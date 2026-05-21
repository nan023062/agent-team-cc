"""
auto_preview.py - SessionStart hook that launches the dashboard server
in the background if the user has it enabled.

Idempotent: an existing live PID short-circuits the launch. CI is
detected via the `CI` env var (set by GitHub Actions / GitLab / etc.)
and forces --no-browser; the server still starts so the UI is reachable
over port-forward.

Reads `.cbim/config.json` -> `dashboard.auto_open` (default true) and
`dashboard.open_browser` (default true).

(Filename kept as `auto_preview.py` for historical reasons - the
SessionStart hook entry is registered in `.claude/settings.json`.
The server it launches is now the renamed `dashboard` package.)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cbim_kernel.context import cbim_dir, project_root


def _read_cfg(cbim: Path) -> dict:
    p = cbim / "config.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _python() -> str:
    """Prefer the project's .venv interpreter; fall back to whatever
    invoked us. Same lookup order as load_memory.py for consistency."""
    for root in [project_root(), cbim_dir()]:
        for candidate in [
            root / ".venv" / "Scripts" / "python.exe",
            root / ".venv" / "bin" / "python",
        ]:
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _pid_file() -> Path:
    """PID lives under the project's .cbim/ state directory."""
    return cbim_dir() / "dashboard" / ".run" / ".preview.pid"


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


def _already_running() -> bool:
    pid_path = _pid_file()
    if not pid_path.exists():
        return False
    try:
        raw = pid_path.read_text().strip()
        try:
            data = json.loads(raw)
            pid = data["pid"]
        except (json.JSONDecodeError, KeyError):
            pid = int(raw)
    except (ValueError, OSError):
        pid_path.unlink(missing_ok=True)
        return False
    if _pid_alive(pid):
        return True
    pid_path.unlink(missing_ok=True)
    return False


def _launch(cwd: Path, no_browser: bool) -> int:
    """Spawn `python -m cbim_kernel dashboard` detached. Returns the child PID."""
    python = _python()
    args = [python, "-m", "cbim_kernel", "dashboard"]
    if no_browser:
        args.append("--no-browser")

    kwargs: dict = dict(cwd=str(cwd))
    if sys.platform == "win32":
        # DETACHED_PROCESS keeps the server alive after CC's hook exits
        # without flashing a console window.
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
        # Detach stdio so closing the hook's pipe doesn't SIGPIPE the server.
        kwargs["stdin"] = subprocess.DEVNULL
        kwargs["stdout"] = subprocess.DEVNULL
        kwargs["stderr"] = subprocess.DEVNULL

    proc = subprocess.Popen(args, **kwargs)
    return proc.pid


def main(event: dict | None = None) -> int:
    # auto_preview ignores the event payload; signature kept for dispatcher symmetry.
    _ = event
    cbim = cbim_dir()
    cfg = _read_cfg(cbim).get("dashboard", {})

    # auto_open defaults to True - the user explicitly wants the UI ready
    # on every session start. Set to false in config.json to opt out.
    if not cfg.get("auto_open", True):
        return 0
    if _already_running():
        return 0

    # CI mode: the server must still come up so test harnesses can curl
    # /api/* over port-forwarding, but no browser should be spawned.
    in_ci = bool(os.environ.get("CI"))
    open_browser = cfg.get("open_browser", True) and not in_ci

    try:
        _launch(project_root(), no_browser=not open_browser)
    except Exception:
        # Hooks must never break session start. Swallow and move on.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
