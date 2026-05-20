"""import_log.py — skill/soul import logger (writes [IMP] lines to session log)."""


def log_import(module_path: str, status: str, trigger: str) -> None:
    from .debug import is_debug
    if not is_debug():
        return
    try:
        from .session_log import append
        append("IMP", f"trigger={trigger} | status={status} | module={module_path}")
    except Exception:
        pass
