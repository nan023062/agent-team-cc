---
description: Disable CBIM tool-call logging (removes .cbim/.debug flag)
allowed-tools: Bash
---

Run `python .cbim/engine debug off` and confirm the flag file was removed. The PreToolUse hook remains registered but becomes inert (no log writes).
