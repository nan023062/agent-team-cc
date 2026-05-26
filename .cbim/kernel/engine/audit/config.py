"""audit/config.py — threshold loading + bands resolver.

Reads the `audit` section of `.cbim/config.json` if present, merging on top of
hardcoded DEFAULTS. Never writes config. Resolves a measured value against a
threshold into one of {"info", "warn", "error"} using:

    info  = 0.80 * threshold <= v < threshold
    warn  = threshold        <= v < 1.50 * threshold
    error = 1.50 * threshold <= v
    (None when v < 0.80 * threshold)
"""

from __future__ import annotations

from copy import deepcopy

from engine.config import load_config

from .result import Severity

DEFAULTS: dict = {
    "memory": {
        "short_max_entries": 80,
        "short_max_age_days": 7,
        "short_max_total_kb": 512,
        "medium_max_entries": 40,
    },
    "agent_fission": {
        "max_body_lines": 250,
        "max_skill_count": 6,
    },
    "dna_fission": {
        "max_body_lines": 350,
        "max_workflow_count": 8,
    },
    "dna_tree": {
        "allow_undeclared_deps": False,
    },
}

_INFO_FACTOR = 0.80
_ERROR_FACTOR = 1.50


def load_audit_config() -> dict:
    """Return effective audit config = DEFAULTS deep-merged with config.json.audit."""
    cfg = load_config().get("audit") or {}
    merged = deepcopy(DEFAULTS)
    _deep_merge(merged, cfg)
    return merged


def _deep_merge(base: dict, overlay: dict) -> None:
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def resolve_bands(value: float, threshold: float) -> Severity | None:
    """Map a measured value against a threshold to a severity band.

    Returns None when value is below the info band (i.e. healthy).
    """
    if threshold <= 0:
        return None
    if value >= _ERROR_FACTOR * threshold:
        return "error"
    if value >= threshold:
        return "warn"
    if value >= _INFO_FACTOR * threshold:
        return "info"
    return None
