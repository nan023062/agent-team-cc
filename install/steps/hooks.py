"""
hooks.py — Overwrite CBIM hooks + permissions in .claude/settings.json.

Settings shape comes from install/settings.py (SETTINGS dict).
hooks and permissions are always fully replaced; other keys are preserved.
"""

import copy
import json
from pathlib import Path

from ..settings import SETTINGS


def _ok(text: str) -> None:
    print(f"    + {text}")


def install_settings(root: Path) -> None:
    settings_path = root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        current = json.loads(settings_path.read_text(encoding="utf-8")) \
            if settings_path.exists() else {}
    except json.JSONDecodeError:
        current = {}

    template = copy.deepcopy(SETTINGS)

    current["hooks"] = template["hooks"]
    current["permissions"] = template["permissions"]

    settings_path.write_text(
        json.dumps(current, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    for event, entries in template["hooks"].items():
        for entry in entries:
            cmd = entry["hooks"][0]["command"]
            _ok(f"{event} <- {cmd}")
    _ok(f"permissions.deny <- {', '.join(template['permissions']['deny'])}")
    _ok(f"permissions.defaultMode = {template['permissions']['defaultMode']}")
