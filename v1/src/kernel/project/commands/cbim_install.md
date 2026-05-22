---
description: Install or refresh the CBIM cc-prompt-pack in this project
---
# /cbim_install

Bootstrap (or refresh) CBIM in the current project directory. This downloads the kernel into `<project>/cbim-cc/`, generates the `.cbim/run` launcher shim, and registers Claude Code hooks + the MCP server.

## What it does

1. Confirms cwd is the intended project root.
2. Downloads the kernel from GitHub into `<project>/cbim-cc/` (flat layout — `engine/`, `cbi/`, `memory/`, `project/`, etc. are direct children; no `cbim_kernel/` wrapper directory). (Claude performs this download via bash; the kernel has no built-in installer.)
3. Runs `PYTHONPATH=<project>/cbim-cc python -m engine init` to:
   - Create `.cbim/config.json`, `.cbim/logs/`, `.cbim/memory/{short,medium}/`
   - Write `.cbim/run` (POSIX, mode 0755) and `.cbim/run.cmd` (Windows). Both export `PYTHONPATH=<project>/cbim-cc` and `exec python -m engine "$@"`.
   - Install the 4 kernel agents to `.claude/agents/<name>/<name>.md`
   - Install the 6 kernel slash commands to `.claude/commands/*.md`
   - Merge kernel hooks + `mcpServer.cbim` into `.claude/settings.json` (hooks invoke `.cbim/run hook <event>`; mcpServer.cbim runs `.cbim/run mcp`)
   - Write `CLAUDE.md` from template; append CBIM entries to `.gitignore`.

## Idempotency

Re-running `/cbim_install` is safe. Existing project files are preserved unless `--force` is passed. `.cbim/run` and `.cbim/run.cmd` are always rewritten (they encode the kernel install path).

## After install

Restart Claude Code in the project root. The SessionStart hook will load short-term memory and the project knowledge snapshot.

## Uninstall

Delete `<project>/cbim-cc/`, `.cbim/`, `.claude/agents/{architect,auditor,hr,programmer}/`, the 6 `.claude/commands/cbim_*.md` entries, and any CBIM-specific lines in `CLAUDE.md` / `.gitignore` / `.claude/settings.json`.
