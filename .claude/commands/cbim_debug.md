---
description: Toggle/inspect CBIM tool-call logging (on|off|status)
argument-hint: on | off | status
allowed-tools: Bash
---

Dispatch on `$ARGUMENTS`:

- `on` → run `python .cbim/engine debug on`; remind the user that Claude Code must be restarted before the PreToolUse hook starts firing.
- `off` → run `python .cbim/engine debug off`; the hook stays registered but becomes inert.
- `status` (or empty) → run `python .cbim/engine debug status`, then show the last 5 lines of `.cbim/logs/tools.txt` if it exists.
- Anything else → print usage: `/cbim_debug on | off | status`.
