"""
log_user_prompt.py — UserPromptSubmit hook.

Logs the full user prompt [USER] and marks .cc-status as "busy".
"""

import json
import sys

from context import cbim_dir


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
    transcript_path = event.get("transcript_path", "") or ""

    try:
        from engine.logger import log_user
        log_user(prompt, cbim=cbim_dir(), transcript_path=transcript_path)
    except Exception:
        pass

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
