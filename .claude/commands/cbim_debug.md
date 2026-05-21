---
description: Toggle/inspect the .cbim/.debug flag (extra engine-internal log detail)
argument-hint: on | off | status
allowed-tools: Bash
---

Dispatch on `$ARGUMENTS`:

- `on` → run `cbim debug on`; enables extra `[ENG]` and `[IMP]` lines (engine CLI invocations + skill/soul import events) in the session log. Base session signals (`[SESSION]`/`[USER]`/`[TOOL]`/`[RESULT]`/`[TURN]`) always log — no flag needed.
- `off` → run `cbim debug off`; turns off the extra detail.
- `status` (or empty) → run `cbim debug status` and report the flag state.
- Anything else → print usage: `/cbim_debug on | off | status`.
