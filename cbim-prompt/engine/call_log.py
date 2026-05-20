from pathlib import Path
from datetime import datetime

def _logs_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def log_call(argv: list, exit_code: int) -> None:
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cmd = " ".join(str(a) for a in argv)
        line = f"[ENG]{ts}: argv={cmd} | cwd={Path.cwd()} | exit={exit_code}\n"
        (_logs_dir() / "engine.txt").open("a", encoding="utf-8").write(line)
    except Exception:
        pass
