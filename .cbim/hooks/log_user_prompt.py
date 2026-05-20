"""
log_user_prompt.py — UserPromptSubmit hook.

Records "user spoke, assistant is about to think" — the start of a turn — into
the per-session log under [USER].
"""

import json
import sys
from pathlib import Path


def _cbim_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(0)

    prompt = event.get("prompt", "")
    summary = prompt.strip().replace("\n", " ")[:120] if prompt else ""

    try:
        sys.path.insert(0, str(_cbim_root()))
        from engine.session_log import append
        append("USER", f"prompt_chars={len(prompt)} preview={summary!r}", cbim=_cbim_root())
    except Exception:
        pass

    # Mark CC as busy — scheduler reads this when deciding whether to fire idle-sensitive tasks
    try:
        from datetime import datetime
        (_cbim_root() / ".cc-status").write_text(
            f"busy {datetime.now().isoformat()}\n", encoding="utf-8"
        )
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
