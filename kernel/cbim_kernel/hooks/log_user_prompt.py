"""
log_user_prompt.py — UserPromptSubmit hook.

Records "user spoke, assistant is about to think" — the start of a turn — into
the per-session log under [USER].
"""

import json
import sys

from cbim_kernel.context import cbim_dir


def main(event: dict | None = None) -> int:
    if event is None:
        raw = sys.stdin.buffer.read().decode("utf-8").strip()
        if not raw:
            return 0
        try:
            event = json.loads(raw)
        except json.JSONDecodeError:
            return 0

    prompt = event.get("prompt", "")
    summary = prompt.strip().replace("\n", " ")[:120] if prompt else ""

    try:
        from cbim_kernel.engine.session_log import append
        append("USER", f"prompt_chars={len(prompt)} preview={summary!r}", cbim=cbim_dir())
    except Exception:
        pass

    # Mark CC as busy — scheduler reads this when deciding whether to fire idle-sensitive tasks
    try:
        from datetime import datetime
        (cbim_dir() / ".cc-status").write_text(
            f"busy {datetime.now().isoformat()}\n", encoding="utf-8"
        )
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
