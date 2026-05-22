---
description: Show the current session log (agent loop signals)
argument-hint: [lines]
allowed-tools: Bash
---

Run `cbim log show --lines N` where N is `$ARGUMENTS` if provided, otherwise 50. This prints the most recent N entries from the current per-session log under `.cbim/logs/session_*.log` — all signal types interleaved (`[SESSION]`, `[USER]`, `[TOOL]`, `[RESULT]`, `[TURN]`, plus `[ENG]`/`[IMP]` when `.cbim/.debug` is on).

If the output says "no session log yet", the SessionStart hook hasn't fired in this Claude Code session — restart Claude Code.
