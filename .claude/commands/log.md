---
description: Tail recent CBIM tool-call log entries
argument-hint: [lines]
allowed-tools: Bash
---

Show the last N lines of `.cbim/logs/tools.txt` where N is `$ARGUMENTS` if provided, otherwise 30. If the file doesn't exist, tell the user debug logging isn't capturing (either `.cbim/.debug` flag is off or Claude Code wasn't restarted after enabling).
