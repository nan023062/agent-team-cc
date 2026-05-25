#!/usr/bin/env python3
"""SessionStart phase 2 — ensure dashboard server is running (in-process bridge)."""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _lib.event_io import read_event
from _lib.paths import project_root_from_cwd, kernel_path
from _lib.bridge import bootstrap_kernel, safe_run


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


def _already_running(pid_path: Path) -> bool:
    if not pid_path.exists():
        return False
    try:
        raw = pid_path.read_text().strip()
        try:
            pid = int(json.loads(raw)["pid"])
        except (json.JSONDecodeError, KeyError, TypeError):
            pid = int(raw)
    except (ValueError, OSError):
        pid_path.unlink(missing_ok=True)
        return False
    if _pid_alive(pid):
        return True
    pid_path.unlink(missing_ok=True)
    return False


def _launch(root: Path, cbim: Path, no_browser: bool) -> None:
    python = _python_exe(root, cbim)
    args = [python, "-m", "engine", "dashboard"]
    if no_browser:
        args.append("--no-browser")

    env = os.environ.copy()
    kp = str(kernel_path(root))
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


def _maybe_launch(root: Path) -> None:
    cbim = root / ".cbim"
    cfg = _read_dashboard_cfg(cbim)
    if not cfg.get("auto_open", True):
        return
    pid_path = cbim / "dashboard" / ".run" / ".preview.pid"
    if _already_running(pid_path):
        return
    in_ci = bool(os.environ.get("CI"))
    open_browser = cfg.get("open_browser", True) and not in_ci
    _launch(root, cbim, no_browser=not open_browser)


def main() -> int:
    event = read_event()
    cwd = event.get("cwd") or "."
    root = project_root_from_cwd(cwd)

    # auto_preview does not strictly need kernel on sys.path (it shells out),
    # but bootstrap establishes the missing-kernel warning and keeps behaviour
    # consistent across hooks.
    if not bootstrap_kernel(root):
        return 0

    safe_run(lambda: _maybe_launch(root), on_error_label="auto_preview")
    return 0


if __name__ == "__main__":
    sys.exit(main())
