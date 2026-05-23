---
name: kernel-cli
owner: architect
description: Unified CLI dispatcher: routes python -m engine <domain> to memory/dna/agent/skill/hook/mcp/dashboard/init/project/log/config/debug
keywords: []
dependencies: []
---

## Positioning

The unified CLI dispatcher for the kernel. Single user-facing entry — `python -m engine <domain> [<command>] [args]`, invoked via the project's shim `.cbim/run`. `__main__.py` calls `engine.cli.main()`, which builds an argparse tree and dispatches each domain to the matching delegate.

Engine contains zero business logic. It is a router: parse arguments, resolve config, dispatch, log, return. Every domain delegates outward to a sub-engine that owns the actual work.

## Sub-module Relationships

```mermaid
classDiagram
    class cli {
        +main() int
        +_build_parser()
        +_handle_dna_* / _handle_agent_*
        +_cmd_init / _cmd_project / cmd_dashboard
    }
    class __main__ {
        forwards sys.argv to cli.main
    }
    class logger
    class session_log
    class call_log
    class import_log
    class log_view {
        +cmd_log_show / cmd_log_tail
    }
    class debug {
        +.cbim/.debug flag toggle
    }
    class config {
        +cmd_config_get / set / show
    }

    cli ..> project_init : init
    cli ..> project_sync : project sync
    cli ..> cbi_resources : dna / agent / skill / soul / snapshot
    cli ..> memory_engine : memory create/add/query/delete/reindex/cleanup
    cli ..> hooks_dispatch : hook <event>
    cli ..> mcp_server : mcp (stdio)
    cli ..> dashboard_server : dashboard (HTTP)
    cli --> logger
    cli --> session_log
    cli --> import_log
    cli --> log_view
    cli --> debug
    cli --> config
```

Dispatched domains (current surface, mirrors `engine/cli.py:main`):

- `memory` → `memory.engine.cli` (create / add / query / delete / reindex / cleanup)
- `dna` → in-process handlers driving `cbi.resources.DNAModule` and `cbi._primitives.modules` (list / show / init / reindex / edit / write-doc[deprecated] / write-section[deprecated] / split)
- `agent` → in-process handlers driving `cbi.resources.Agent` (list / show / scaffold / archive / update / add-skill)
- `snapshot` → `cbi._primitives.snapshot.build_snapshot`
- `skill` → `cbi.resources.Skill` (list / show)
- `soul` → walks `cbi.agents.*.agent` modules
- `config` → `engine.config` (get / set / show on `.cbim/config.json`)
- `dashboard` → `dashboard.server.start_server`
- `preview` → `dashboard` (deprecated alias)
- `debug` → toggles `.cbim/.debug` flag (on / off / status)
- `log` → `engine.log_view` (show / tail per-session logs)
- `hook <event>` → `hooks.dispatch` (session-start / session-end / stop / log-prompt / log-pre-tool / log-post-tool)
- `mcp` → `mcp_server.server.mcp.run()` (stdio)
- `init` → `project.init.init_project` (bootstrap cwd)
- `project sync` → `project.sync.sync_templates` (refresh templated files)

Internal cross-cutting modules: `logger` + `session_log` (per-session text logs), `call_log` + `import_log` (PreToolUse/PostToolUse + import telemetry), `log_view` (read-back surface for `log show` / `log tail`), `debug` (.debug flag toggle), `config` (config get/set/show).

## Origin Context

Every CBIM operation that an LLM or human types is one CLI invocation. The kernel needs exactly one routing surface because:

1. **Single discoverability point.** `python -m engine --help` lists every available domain. No second binary, no second entry point.
2. **One logging seam.** Every invocation flows through `cli.main()`, so per-session call logging is uniform across all domains without each sub-engine reinventing the wheel.
3. **Domain isolation.** Each domain's real implementation lives in a sibling sub-module (`memory/`, `cbi/`, `hooks/`, etc.). Engine merely parses and dispatches. A domain can be refactored, removed, or added without touching the other domains.

The cross-cutting log/debug/config trio lives inside `engine/` because they describe *the engine's own runtime* (per-invocation logging, the debug flag that gates extra `[ENG]/[IMP]` records, the engine-level config keys). They are not "memory" or "cbi" concerns — they belong to the dispatcher.

## Key Decisions

- **Thin dispatcher, no business logic.** Every domain handler is a few lines: parse args, call delegate, return exit code. Anything more substantial belongs in the delegate module. This keeps `engine/cli.py` legible and prevents it from accumulating cross-domain knowledge.
- **`dna` and `agent` handlers live inline in `engine/cli.py`.** Historically they delegated to `cbi/_primitives/cli.py`; that thin wrapper layer was deleted in P3 Wave 1. The handlers now drive `cbi.resources.{DNAModule, Agent}` directly. Reason: a one-level dispatch (engine → resource model) is cheaper to read and modify than two-level dispatch (engine → cbi/cli → resource model), and the resource model is the de-facto public API.
- **`init` targets `Path.cwd()`, NOT `project_root()`.** `project_root()` walks up to find an existing `.cbim/`, which is the wrong semantics for bootstrap and historically caused init to clobber a parent project when run from a non-project subdirectory. Bootstrap always targets cwd.
- **`hook` is one subcommand with an event arg, not one subcommand per event.** Hook handlers are dispatched by `hooks.dispatch(event_name)` after reading stdin JSON — engine just passes the event name through. Note: as of Phase 3a/3b the runtime hook path no longer flows through `cli` — `.claude/settings.json` invokes `.claude/hooks/cbim_*.py` directly (thin MCP clients). The `cli` `hook` subcommand and the `hooks/` package remain as a deprecated rollback surface.
- **`init` does more than scaffold `.cbim/`.** Since Phase 3b, `init` also: (1) copies the 7 `cbim_*.py` hook scripts plus `_lib/` into `.claude/hooks/` with 0755 on the scripts; (2) rewrites the `hooks` section of `.claude/settings.json` to invoke those scripts directly (no more `.cbim/run hook ...` indirection); (3) extends `permissions.deny` to four entries (Write/Edit/Read on `.cbim/**`, plus `Bash(.cbim/run *)`); (4) appends missing kernel entries to `.claudeignore` (merge-only, never clobber); (5) probes the install-time Python for the `mcp` SDK and emits a stderr warning with the exact `pip install` command if absent (detect-only — never auto-installs, never creates a venv, to preserve the "no virtualenv, no pip install step" README contract).
- **`preview` is a deprecated alias for `dashboard`.** Kept for one release cycle. Emits a stderr deprecation line and forwards to `cmd_dashboard`.
- **Debug flag is engine-scoped, not memory-scoped.** `.cbim/.debug` (a zero-byte file at the project root's `.cbim/` directory) gates the extra `[ENG]/[IMP]` log lines from `call_log` and `import_log`. Session-level signals (`[SESSION]/[USER]/[TOOL]/[RESULT]/[TURN]`) always log regardless of the flag.

## Non-Goals

- No `cbim_kernel.*` import paths. The kernel root is now the package root (after flatten); imports are `from engine ...`, `from memory.engine ...`, `from cbi.resources ...`, never `from cbim_kernel.engine ...`.
- No `migrate` or `upgrade` subcommands. Project lifecycle = `init` + `project sync` only.
- No `pin` subcommand, no `versions.json` reader, no installer-side subprocess.

