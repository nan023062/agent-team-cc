---
description: Enable CBIM tool-call logging (creates .cbim/.debug flag)
allowed-tools: Bash
---

Run `python .cbim/engine debug on` and confirm the flag file was created. Remind the user that Claude Code must be restarted for the PreToolUse hook to start firing in the current session.
