"""
dashboard.py — Double-click to start / stop the CBIM dashboard server.

Reads dashboard/.run/.preview.pid under the project's .cbim/ state dir to
decide current state:
  - PID file exists + process alive  ->  stop
  - otherwise                        ->  start (new console window on Windows)
"""
import json
import os
import subprocess
import sys
import time

from cbim_kernel.context import cbim_dir, project_root


ROOT = project_root()
CBIM = cbim_dir()
PID_FILE = CBIM / "dashboard" / ".run" / ".preview.pid"


def _python() -> str:
    for p in [ROOT / ".venv/Scripts/python.exe", ROOT / ".venv/bin/python"]:
        if p.exists():
            return str(p)
    return sys.executable


def _alive(pid: int) -> bool:
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


def stop(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                       capture_output=True)
    else:
        import signal
        os.kill(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)
    print(f"  Stopped (PID {pid})")


def start() -> None:
    python = _python()
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    kwargs = dict(cwd=str(ROOT))
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        [python, "-m", "cbim_kernel", "dashboard"],
        **kwargs,
    )
    print(f"  Started (PID {proc.pid})")
    print("  A browser tab will open shortly (actual port shown in server window).")
    print("  Re-run this script to stop the service.")


# ---------------------------------------------------------------------------

print("=" * 42)
print("   CBIM Dashboard")
print("=" * 42)

if PID_FILE.exists():
    try:
        raw = PID_FILE.read_text().strip()
        try:
            data = json.loads(raw)
            pid = data["pid"]
        except (json.JSONDecodeError, KeyError):
            pid = int(raw)
        if _alive(pid):
            print(f"  Running (PID {pid}); stopping...")
            stop(pid)
        else:
            PID_FILE.unlink(missing_ok=True)
            print("  Stale PID, starting...")
            start()
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        start()
else:
    print("  Starting...")
    start()

print("=" * 42)
time.sleep(3)
