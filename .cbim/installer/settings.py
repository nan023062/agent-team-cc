"""
installer/settings.py — Static template for .claude/settings.json.

The PreToolUse hook is registered unconditionally; it self-disables when
`.cbim/.debug` is missing (no log output, microsecond overhead). Operators
flip it on by touching the flag: `python .cbim/engine debug on`.
"""


def _pretooluse_command() -> str:
    # Lazy import — install.py inserts .cbim/ onto sys.path before the
    # installer package is loaded, so engine.cli is reachable here.
    from engine.cli import _pretooluse_inline_command
    return _pretooluse_inline_command()


SETTINGS: dict = {
    "hooks": {
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python .cbim/installer/hooks/write_memory.py",
                    }
                ]
            }
        ],
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python .cbim/installer/hooks/load_memory.py",
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": _pretooluse_command(),
                    }
                ]
            }
        ],
    },
    "permissions": {
        "defaultMode": "bypassPermissions",
        "deny": [
            "Write(.cbim/**)",
            "Edit(.cbim/**)",
            "Glob(.cbim/**)",
            "Grep(.cbim/**)",
        ],
    },
}
