---
description: Show the current session log (agent loop signals)
argument-hint: [lines]
allowed-tools: mcp__cbim__log_show
---

Call the `log_show` MCP tool with `lines=N` where N is `$ARGUMENTS` if provided, else 50. Print the returned `session_log` field to the user. The log interleaves all signal types (`[SESSION]`, `[USER]`, `[TOOL]`, `[RESULT]`, `[TURN]`, plus `[ENG]`/`[IMP]` when `.cbim/.debug` is on).

If the tool returns an empty `session_log`, tell the user: "no session log yet — the SessionStart hook hasn't fired in this Claude Code session, please restart Claude Code".
