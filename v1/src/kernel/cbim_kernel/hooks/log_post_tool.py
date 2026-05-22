"""
log_post_tool.py — PostToolUse hook.

Tool results are visible in the Claude Code conversation itself, so this
hook is intentionally silent. The PreToolUse hook already records CBIM
call entries; no additional result logging is needed here.
"""

import sys


def main(event: dict | None = None) -> int:
    # Consume stdin so the hook doesn't leave a dangling pipe.
    if event is None:
        try:
            sys.stdin.buffer.read()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
