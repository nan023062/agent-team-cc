"""
config.py — Load memory config from memory/config.py with built-in defaults.

Call load_config() from anywhere; missing keys fall back to _DEFAULTS.
"""

import copy

from ..config import CONFIG as _USER_CONFIG

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
    # Per-session LLM distillation written into each short entry body.
    # Distinct from the "distill" section above (which governs short→medium
    # promotion thresholds). This one runs at Stop hook time.
    "session_distill": {
        "enabled": True,
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "timeout": 30,
        "input_max_chars": 12000,
        # Skip the LLM call when there was no real work (no agent calls AND
        # no file changes) — those sessions are chit-chat and not worth the
        # latency or cost.
        "skip_if_no_work": True,
    },
}


def load_config(cwd=None) -> dict:
    """Return merged config: defaults overridden by memory/config.py CONFIG."""
    cfg = copy.deepcopy(_DEFAULTS)
    user = copy.deepcopy(_USER_CONFIG)
    for section, values in user.items():
        if section in cfg and isinstance(values, dict):
            cfg[section].update(values)
        else:
            cfg[section] = values
    return cfg
