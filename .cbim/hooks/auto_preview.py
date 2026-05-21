"""
auto_preview.py — SessionStart hook that launches the preview server
in the background if the user has it enabled.

Idempotent: an existing live PID short-circuits the launch. CI is
detected via the `CI` env var (set by GitHub Actions / GitLab / etc.)
and forces --no-browser; the server still starts so the UI is reachable
over port-forward.

Reads `.cbim/config.json` → `preview.auto_open` (default true) and
`preview.open_browser` (default true).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _cbim_root() -> Path:
    return Path(__file__).resolve().parent.parent


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
    cbim = _cbim_root()
    for root in [cbim, cbim.parent]:
        for candidate in [
            root / ".venv" / "Scripts" / "python.exe",
            root / ".venv" / "bin" / "python",
        ]:
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _pid_file() -> Path:
    """PID lives under the preview package itself — never under
    .cbim/memory/store/ (governed dir; PID is not memory state)."""
    return _cbim_root() / "preview" / ".run" / ".preview.pid"


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
        pid = int(pid_path.read_text().strip())
    except (ValueError, OSError):
        pid_path.unlink(missing_ok=True)
        return False
    if _pid_alive(pid):
        return True
    pid_path.unlink(missing_ok=True)
    return False


def _launch(cbim: Path, no_browser: bool) -> int:
    """Spawn `python -m engine preview` detached. Returns the child PID."""
    python = _python()
    args = [python, "-m", "engine", "preview"]
    if no_browser:
        args.append("--no-browser")

    kwargs: dict = dict(cwd=str(cbim))
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

    pid_path = _pid_file()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(proc.pid))
    return proc.pid


def main() -> None:
    cbim = _cbim_root()
    cfg = _read_cfg(cbim).get("preview", {})

    # auto_open defaults to True — the user explicitly wants the UI ready
    # on every session start. Set to false in config.json to opt out.
    if not cfg.get("auto_open", True):
        return
    if _already_running():
        return

    # CI mode: the server must still come up so test harnesses can curl
    # /api/* over port-forwarding, but no browser should be spawned.
    in_ci = bool(os.environ.get("CI"))
    open_browser = cfg.get("open_browser", True) and not in_ci

    try:
        _launch(cbim, no_browser=not open_browser)
    except Exception:
        # Hooks must never break session start. Swallow and move on.
        pass


if __name__ == "__main__":
    main()
