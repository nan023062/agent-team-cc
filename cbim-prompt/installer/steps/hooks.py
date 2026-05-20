"""
hooks.py — Merge CBIM hooks + permissions into .claude/settings.json.

Settings shape comes from installer/templates/settings.py (SETTINGS dict).
"""

import copy
import json
from pathlib import Path

from ..templates.settings import SETTINGS


def _ok(text: str) -> None:
    print(f"    + {text}")


def _skip(text: str) -> None:
    print(f"    - {text}  (skipped)")


def install_settings(root: Path) -> None:
    settings_path = root / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        current = json.loads(settings_path.read_text(encoding="utf-8")) \
            if settings_path.exists() else {}
    except json.JSONDecodeError:
        current = {}

    template = copy.deepcopy(SETTINGS)

    # Merge hooks
    hooks = current.setdefault("hooks", {})
    added: list[str] = []
    for event, entries in template["hooks"].items():
        target = hooks.setdefault(event, [])
        for entry in entries:
            cmd = entry["hooks"][0]["command"]
            if not _hook_has_command(target, cmd):
                target.append(entry)
                added.append(f"{event} <- {cmd}")

    # Merge permissions
    perms = current.setdefault("permissions", {})
    perms["defaultMode"] = template["permissions"]["defaultMode"]
    deny_list = perms.setdefault("deny", [])
    # Strip any stale cbim-prompt/** or .dna/** denies from previous installs
    deny_list[:] = [
        r for r in deny_list
        if "cbim-prompt/**" not in r and ".dna/" not in r
    ]
    new_rules: list[str] = []
    for rule in template["permissions"]["deny"]:
        if rule not in deny_list:
            deny_list.append(rule)
            new_rules.append(rule)

    settings_path.write_text(
        json.dumps(current, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    if added:
        for line in added:
            _ok(line)
    else:
        _skip("hooks already configured")
    if new_rules:
        _ok(f"permissions.deny <- {', '.join(new_rules)}")
    else:
        _skip("permissions.deny already configured")
    _ok("permissions.defaultMode = bypassPermissions")


def _hook_has_command(entries: list, command: str) -> bool:
    for entry in entries:
        for h in entry.get("hooks", []):
            if h.get("command") == command:
                return True
    return False
