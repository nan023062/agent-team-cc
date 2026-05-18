"""
preview.py — Double-click to start / stop the memory preview server.

Reads store/.preview.pid to decide current state:
  - PID file exists + process alive  →  stop
  - otherwise                        →  start (new console window on Windows)
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # engine/preview → engine → memory → project root
PID_FILE = ROOT / "memory" / "store" / ".preview.pid"


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
    print(f"  已停止 (PID {pid})")


def start() -> None:
    python = _python()
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    kwargs = dict(cwd=str(ROOT))
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(
        [python, "-m", "memory.engine.cli", "preview"],
        **kwargs,
    )
    PID_FILE.write_text(str(proc.pid))
    print(f"  已启动 (PID {proc.pid})")
    print("  浏览器将自动打开  http://127.0.0.1:8765")
    print("  再次双击本脚本可停止服务")


# ---------------------------------------------------------------------------

print("=" * 42)
print("   Memory Preview")
print("=" * 42)

if PID_FILE.exists():
    try:
        pid = int(PID_FILE.read_text().strip())
        if _alive(pid):
            print(f"  服务运行中 (PID {pid})，正在停止…")
            stop(pid)
        else:
            PID_FILE.unlink(missing_ok=True)
            print("  服务未运行（PID 已失效），正在启动…")
            start()
    except (ValueError, OSError):
        PID_FILE.unlink(missing_ok=True)
        start()
else:
    print("  正在启动…")
    start()

print("=" * 42)
time.sleep(3)
