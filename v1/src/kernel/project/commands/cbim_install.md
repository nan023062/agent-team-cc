---
description: Install or refresh the CBIM cc-prompt-pack in this project
---
# /cbim_install

Bootstrap (or refresh) CBIM in the current project directory. This downloads the kernel into `<project>/.cbim/kernel/`, generates the `.cbim/run` launcher shim, and registers Claude Code hooks + the MCP server.

## What it does

1. Confirms cwd is the intended project root.
2. Downloads the kernel from https://github.com/nan023062/cbim into `<project>/.cbim/kernel/` (flat layout — `engine/`, `cbi/`, `memory/`, `project/`, etc. are direct children; no `cbim_kernel/` wrapper directory). (Claude performs this download via bash; the kernel has no built-in installer.)
3. Runs `PYTHONPATH=<project>/.cbim/kernel python -m engine init` to:
   - Create `.cbim/config.json`, `.cbim/logs/`, `.cbim/memory/{short,medium}/`
   - Write `.cbim/run` (POSIX, mode 0755) and `.cbim/run.cmd` (Windows). Both export `PYTHONPATH=<project>/.cbim/kernel` and `exec python -m engine "$@"`.
   - Install the 4 kernel agents to `.claude/agents/<name>/<name>.md`
   - Install the 6 kernel slash commands to `.claude/commands/*.md`
   - Merge kernel hooks + `mcpServer.cbim` into `.claude/settings.json` (hooks invoke `.cbim/run hook <event>`; mcpServer.cbim runs `.cbim/run mcp`)
   - Write `CLAUDE.md` from template; append CBIM entries to `.gitignore`.

## When this runs

This command runs in two situations:

- **First-time install** — the slash command isn't registered yet (no `.claude/commands/cbim_install.md` exists in the project). In this case, the user pastes the "first-time bootstrap paragraph" from the repo-root README into Claude, which performs the same download + `python3 -m engine init` steps this file specifies. Once `init` completes, `.claude/commands/cbim_install.md` exists and `/cbim_install` is available for all subsequent invocations.
- **Refresh** — the slash command is registered. Typing `/cbim_install` re-runs the same flow against the same kernel source. Re-running is the only refresh / upgrade path; there is no `cbim update` CLI.

In both cases the entry point is `python3 -m engine init` with `PYTHONPATH=<project>/.cbim/kernel`. The launcher shim at `.cbim/run` is regenerated every time (it encodes the absolute Python interpreter path and the kernel install path, both of which can change between machines / installs).

## Idempotency

Re-running `/cbim_install` is safe. Existing project files are preserved unless `--force` is passed. `.cbim/run` and `.cbim/run.cmd` are always rewritten (they encode the kernel install path).

## After install

Restart Claude Code in the project root. The SessionStart hook will load short-term memory and the project knowledge snapshot.

## Uninstall

Delete `.cbim/`, `.claude/agents/{architect,auditor,hr,programmer}/`, the 6 `.claude/commands/cbim_*.md` entries, and any CBIM-specific lines in `CLAUDE.md` / `.gitignore` / `.claude/settings.json`.

## Migration from pre-rename layout

If a previous `/cbim_install` placed the kernel at `<project>/cbim-cc/`, simply `rm -rf <project>/cbim-cc/` and re-run `/cbim_install`. The shim under `.cbim/run` is always regenerated, so it will point at the new `.cbim/kernel/` location automatically.
