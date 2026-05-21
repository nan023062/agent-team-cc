"""
dashboard.py — Double-click to start / stop the CBIM dashboard server.

Reads dashboard/.run/.preview.pid to decide current state:
  - PID file exists + process alive  →  stop
  - otherwise                        →  start (new console window on Windows)

The PID file used to live under .cbim/memory/store/ — that directory is
now governance-only (Kernel-Only Writes), so the PID was moved here.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CBIM = Path(__file__).resolve().parent.parent  # dashboard → .cbim
ROOT = CBIM.parent                              # project root (where .venv lives)
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
    print(f"  已停止 (PID {pid})")


def start() -> None:
    python = _python()
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    kwargs = dict(cwd=str(CBIM))  # cwd=.cbim/ so `engine` package is importable
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    else:
        kwargs["start_new_session"] = True

    # `dashboard` is the primary command; `preview` is a deprecated alias.
    proc = subprocess.Popen(
        [python, "-m", "engine", "dashboard"],
        **kwargs,
    )
    print(f"  已启动 (PID {proc.pid})")
    print("  浏览器将自动打开（实际端口见服务窗口输出）")
    print("  再次双击本脚本可停止服务")


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
