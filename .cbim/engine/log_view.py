from pathlib import Path
import time

def _logs_dir() -> Path:
    # Walk upward from cwd looking for .cbim/
    p = Path.cwd()
    for _ in range(6):
        candidate = p / ".cbim" / "logs"
        if candidate.parent.exists():
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        p = p.parent
    fallback = Path.cwd() / ".cbim" / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback

_LOGS = [("ENG", "engine.txt"), ("IMP", "imports.txt"), ("TOL", "tools.txt")]

def cmd_log_show(args) -> int:
    lines = getattr(args, "lines", 50)
    logs_dir = _logs_dir()
    all_lines = []
    for tag, fname in _LOGS:
        f = logs_dir / fname
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                all_lines.append(line)
    all_lines.sort(key=lambda l: l[5:24])  # sort by timestamp after "[TAG]"
    for l in all_lines[-lines:]:
        print(l)
    return 0

def cmd_log_tail(args) -> int:
    interval = getattr(args, "interval", 1.0)
    logs_dir = _logs_dir()
    handles = []
    for tag, fname in _LOGS:
        f = logs_dir / fname
        f.touch()
        fh = f.open("r", encoding="utf-8", errors="replace")
        fh.seek(0, 2)  # seek to end
        handles.append((tag, fh))
    print("Tailing logs (Ctrl+C to stop)...")
    try:
        while True:
            for tag, fh in handles:
                for line in fh:
                    line = line.rstrip()
                    if line:
                        print(line, flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        for _, fh in handles:
            fh.close()
    return 0
