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
   - Build a managed venv at `.cbim/.venv/` using the bootstrap `python3` and install the `mcp` SDK into it. (Your system Python is not touched.)
   - Write `.cbim/run` (POSIX, mode 0755) and `.cbim/run.cmd` (Windows). Each shim resolves its own directory and execs `.cbim/.venv/bin/python -m engine "$@"` with `PYTHONPATH=<project>/.cbim/kernel`.
   - Install the 4 kernel agents to `.claude/agents/<name>/<name>.md`
   - Install the 6 kernel slash commands to `.claude/commands/*.md`
   - Merge kernel hooks into `.claude/settings.json` (hooks invoke `.claude/hooks/cbim_*.py` in-process)
   - Write `mcpServers.cbim` into project-root `.mcp.json` (Claude Code reads MCP server registrations from `<project>/.mcp.json`, NOT from `.claude/settings.json`); the entry runs `.cbim/run mcp`
   - Write `CLAUDE.md` from template; append CBIM entries to `.gitignore`.

## When this runs

This command runs in two situations:

- **First-time install** — the slash command isn't registered yet (no `.claude/commands/cbim_install.md` exists in the project). In this case the user runs `curl -sSL https://raw.githubusercontent.com/nan023062/cbim/master/install.sh | bash` from the project root; that script clones the repo, copies `v1/src/kernel/` into `.cbim/kernel/`, and runs the same `python3 -m engine init` flow this file specifies. Once `init` completes, `.claude/commands/cbim_install.md` exists and `/cbim_install` is available for all subsequent invocations.
- **Refresh** — the slash command is registered. Typing `/cbim_install` re-runs the same flow against the same kernel source. This (and re-running `install.sh`) are the two valid refresh / upgrade paths; there is no `cbim update` CLI.

In both cases the entry point is `python3 -m engine init` with `PYTHONPATH=<project>/.cbim/kernel`. The launcher shim at `.cbim/run` is regenerated every time. The shim itself is portable (it resolves its own directory and execs the venv-managed python next to it); rebuilding it is cheap and keeps the install repeatable.

**After `init` completes, do NOT re-read anything under `.cbim/`** — not `cat .cbim/config.json`, not `ls -la .cbim/...`, not `Read` on any `.cbim/*` path. The install writes `permissions.deny` entries that block LLM access to `.cbim/`, and `.claudeignore` hides it from indexing. Attempting to verify install state by reading inside `.cbim/` will trigger permission-denial prompts and confuse the user. To confirm a successful install, check only the artefacts outside `.cbim/`: the seven files under `.claude/hooks/cbim_*.py`, the `mcpServers.cbim` block in project-root `.mcp.json`, and the four agents under `.claude/agents/{architect,auditor,hr,programmer}/`. Anything you need to know about kernel state goes through `cbim` MCP tools, not raw file reads.

## Idempotency

Re-running `/cbim_install` is safe. Existing project files are preserved unless `--force` is passed. `.cbim/run` and `.cbim/run.cmd` are always rewritten (they encode the kernel install path).

## After install

Restart Claude Code in the project root. The SessionStart hook will load short-term memory and the project knowledge snapshot.

## Uninstall

Delete `.cbim/`, `.claude/agents/{architect,auditor,hr,programmer}/`, the 6 `.claude/commands/cbim_*.md` entries, project-root `.mcp.json` (or just the `mcpServers.cbim` entry), and any CBIM-specific lines in `CLAUDE.md` / `.gitignore` / `.claude/settings.json`.

## Migration from pre-rename layout

If a previous `/cbim_install` placed the kernel at `<project>/cbim-cc/`, simply `rm -rf <project>/cbim-cc/` and re-run `/cbim_install`. The shim under `.cbim/run` is always regenerated, so it will point at the new `.cbim/kernel/` location automatically.
