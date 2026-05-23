---
description: Toggle/inspect the .cbim/.debug flag (extra engine-internal log detail)
argument-hint: on | off | status
allowed-tools: mcp__cbim__debug_get, mcp__cbim__debug_set
---

Dispatch on `$ARGUMENTS`:

- `on` → call `debug_set` with `state="on"`; report the new state. Enables extra `[ENG]`/`[IMP]` lines (engine CLI invocations + skill/soul import events) in the session log. Base session signals (`[SESSION]`/`[USER]`/`[TOOL]`/`[RESULT]`/`[TURN]`) always log — no flag needed.
- `off` → call `debug_set` with `state="off"`; report the new state.
- `status` (or empty) → call `debug_get`; report the current state.
- Anything else → print usage: `/cbim_debug on | off | status`.
