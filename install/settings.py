"""
install/settings.py — Static template for .claude/settings.json.

Five hooks are registered unconditionally:
  SessionStart   .cbim/hooks/load_memory.py       opens per-session log + injects context
  Stop           .cbim/hooks/write_memory.py      appends [TURN] end + distills session memory
  UserPromptSubmit .cbim/hooks/log_user_prompt.py appends [USER] (turn-start signal)
  PreToolUse     .cbim/hooks/log_pre_tool.py      appends [TOOL] (action point)
  PostToolUse    .cbim/hooks/log_post_tool.py     appends [RESULT] (reflection point)

All five always log to .cbim/logs/session_<ts>_<id>.log — one file per session.
The .cbim/.debug flag (toggled via `python .cbim/engine debug on/off`) only
controls extra [ENG]/[IMP] engine-internal lines, not the session signals.
"""


def _hook_cmd(script: str) -> dict:
    return {
        "hooks": [
            {
                "type": "command",
                "command": f"python .cbim/hooks/{script}",
            }
        ]
    }


SETTINGS: dict = {
    "hooks": {
        "SessionStart":     [_hook_cmd("load_memory.py")],
        "Stop":             [_hook_cmd("write_memory.py")],
        "UserPromptSubmit": [_hook_cmd("log_user_prompt.py")],
        "PreToolUse":       [_hook_cmd("log_pre_tool.py")],
        "PostToolUse":      [_hook_cmd("log_post_tool.py")],
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
