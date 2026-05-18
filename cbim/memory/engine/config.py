"""
config.py — Load memory/config.json with built-in defaults.

Call load_config() from anywhere; missing keys fall back to _DEFAULTS.
"""

import copy
import json
from pathlib import Path

_DEFAULTS: dict = {
    "short_term": {
        "keep_days": 3,
        "max_request_chars": 300,
        "max_result_chars": 600,
        "max_slug_input_chars": 50,
        "max_slug_chars": 30,
    },
    "query": {
        "default_top_k": 5,
        "load_top_k": 3,
        "entry_preview_chars": 800,
    },
    "hooks": {
        "timeout_seconds": 30,
    },
    "signals": {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "timeout": 20,
        "max_files_in_prompt": 10,
    },
    "last_session": {
        "result_preview_chars": 120,
        "max_files": 10,
    },
    "distill": {
        "suggest_threshold": 5,
        "how_to_skill_threshold": 3,
        "how_to_workflow_threshold": 2,
        "must_review_threshold": 2,
    },
}


def load_config(cwd: Path | None = None) -> dict:
    """Return merged config: defaults overridden by memory/config.json if present."""
    cfg = copy.deepcopy(_DEFAULTS)
    path = (cwd or Path(".")) / "memory" / "config.json"
    if path.exists():
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
            for section, values in user.items():
                if section in cfg and isinstance(values, dict):
                    cfg[section].update(values)
        except Exception:
            pass
    return cfg
