from pathlib import Path
from datetime import datetime

def _logs_dir() -> Path:
    d = Path(__file__).resolve().parent.parent / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d

def log_import(module_path: str, status: str, trigger: str) -> None:
    from .debug import is_debug
    if not is_debug():
        return
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[IMP]{ts}: trigger={trigger} | status={status} | module={module_path}\n"
        (_logs_dir() / "imports.txt").open("a", encoding="utf-8").write(line)
    except Exception:
        pass
