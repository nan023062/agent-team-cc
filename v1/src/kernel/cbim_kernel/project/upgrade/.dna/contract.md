# Upgrade Contract

This contract is what other modules (kernel CLI dispatcher, `hooks.load_memory`, future MCP tool, future dashboard widget) depend on. Breaking changes here ripple to every surface.

## CLI Surface

### `cbim upgrade check`

Run a holistic diagnosis. Always exit 0 unless the kernel itself is broken; "nothing to upgrade" is success, not failure.

```
cbim upgrade check [--json] [--no-network]
```

| Flag | Meaning |
|------|---------|
| `--json` | Emit the `Diagnosis` value as JSON to stdout (machine-readable). Default is human-readable text. |
| `--no-network` | Skip remote ls-remote; only inspect local install + project state. Used by SessionStart notifier path. |

**Stdout (human-readable)** — three sections:

```
[cbim upgrade check]
  app    : 1.2.0 installed (default), 1.2.3 available locally
  project: pinned to 1.2.0  (at <project_root>)
  remote : 1.2.5 (https://github.com/nan023062/cbim.git, tag pattern v*)

Scenario 5: both-stale
  App is older than remote; project pin is older than app.
  Run in order:
    1) cbim upgrade apply --to 1.2.5
    2) cbim migrate --to 1.2.5
```

**Stdout (`--json`)** — see "Diagnosis schema" below.

### `cbim upgrade apply`

Upgrade the app-side install in place. Internal-only snapshot + auto-rollback on failure. No interactive prompts (unless `--confirm` semantics added later); CI-safe.

```
cbim upgrade apply --to <version> [--source local|git|github] [--from <path-or-url>] [--dry-run]
```

| Flag | Meaning |
|------|---------|
| `--to <version>` | Required. Target version. Must be reachable via `--source`. |
| `--source` | `local` (already-staged kernel dir), `git` (clone+tag-checkout), `github` (release tarball). Default: `github`. |
| `--from` | Override source location (path for `local`, URL for `git`/`github`). |
| `--dry-run` | Print the plan; do not mutate anything. |

**Exit codes:**
- `0` — applied successfully, registry updated, `active_default` advanced to target
- `2` — preflight refused (e.g. project pin requires a manual migrate first)
- `3` — network or download failure (no mutation occurred)
- `4` — apply failed mid-flight and rolled back automatically (stderr contains the cause)
- `1` — any other unexpected error

**No `rollback` subcommand.** Failed upgrades are rolled back automatically and silently from the in-memory snapshot. Successful upgrades cannot be undone via this module — users wanting to revert install `<old-ver>` explicitly.

## Diagnosis Schema (`--json`)

```json
{
  "scenario": 5,
  "scenario_name": "both-stale",
  "app": {
    "install_root": "C:/Users/u/AppData/Local/Cbim-CC",
    "installed_versions": ["1.2.0", "1.2.3"],
    "active_default": "1.2.0",
    "latest_local": "1.2.3"
  },
  "project": {
    "root": "C:/work/myproj",
    "pin": "1.2.0",
    "upgrade_config": {
      "remote": "https://github.com/nan023062/cbim.git",
      "branch_or_tag_pattern": "v*",
      "auto_check": true,
      "check_interval_hours": 24,
      "channel": "stable"
    }
  },
  "remote": {
    "url": "https://github.com/nan023062/cbim.git",
    "latest": "1.2.5",
    "reachable": true
  },
  "recommendation": "App is older than remote; project pin is older than app.",
  "commands": [
    {"shell": "cbim upgrade apply --to 1.2.5", "description": "Upgrade app to remote latest"},
    {"shell": "cbim migrate --to 1.2.5", "description": "Migrate project schema to 1.2.5"}
  ],
  "ordered": true
}
```

Schema is additive — new fields may be added; existing field names and meanings are stable.

## SessionStart Notifier Hook (consumed by `hooks.load_memory`)

`hooks.load_memory` calls into `upgrade.notify.session_start_line()` once per session. The function:

1. Reads `<project_root>/.cbim/.upgrade_cache.json` (or wherever `notify.cache_path` resolves).
2. If cache is missing or older than `check_interval_hours`, fires `cbim upgrade check --json --no-network` in the background to refresh the cache.
3. Returns either:
   - `None` — no banner to print
   - `"[cbim] update available: 1.2.0 → 1.2.5  (run `cbim upgrade check` for details)"` — one stdout line

The hook prints the line to stdout (NOT `additionalContext`), so it appears in the user's terminal without polluting the LLM's context.

## Project Config Surface

`.cbim/config.json` carries an `upgrade` block. `project.init` writes the default; users may edit it.

```json
{
  "cbim_version": "1.2.0",
  "upgrade": {
    "remote": "https://github.com/nan023062/cbim.git",
    "branch_or_tag_pattern": "v*",
    "auto_check": true,
    "check_interval_hours": 24,
    "channel": "stable"
  }
}
```

| Field | Default | Meaning |
|-------|---------|---------|
| `remote` | `https://github.com/nan023062/cbim.git` | git URL polled for new tags |
| `branch_or_tag_pattern` | `v*` | glob applied to `git ls-remote --tags` output |
| `auto_check` | `true` | whether `hooks.load_memory` runs the notifier at all |
| `check_interval_hours` | `24` | minimum gap between notifier-triggered remote checks |
| `channel` | `"stable"` | currently informational; reserved for future `beta`/`nightly` channels |

## Dependencies (incoming entrypoints used)

This module consumes the following stable entries from sibling modules. **None are imported via Python except `cbim_kernel.context`** (kernel-internal, kernel-local). All access to `installer` state — both reads and writes — goes through subprocess invocation of the installer CLI, preserving the unidirectional rule "kernel never imports installer".

| From | Entry | Used by | How |
|------|-------|---------|-----|
| `installer` (CLI, read surface) | `python -m installer version --json` | `app_state.get_install_root`, `app_state.list_installed`, `app_state.get_default`, `app_state.get_kernel_path` | subprocess (JSON parse). Stable machine-readable read surface — see `installer/.dna/module.md` Key Decision. |
| `installer` (CLI, write surface) | `python -m installer install <ver>` | `apply_flow.invoke_installer` | subprocess only |
| `cbim_kernel.context` | `project_root()`, `cbim_dir()` | `project_state.find_project_root` | Python import (kernel-internal) |
| `cbim_kernel.project.migrate` | (none — referenced only as a *command to recommend*) | diagnostic text | string only |

**Explicitly forbidden:** Python `import installer.paths` or `import installer.registry` from anywhere inside this module. Both modules are installer-internal implementation details; the contract is the `version --json` JSON surface, not the Python API.

### OPEN POINT (for assistant): kernel-side import of `installer.paths` / `installer.registry`

**RESOLVED: Option A (subprocess).** `app_state.py` reads installer state by spawning `python -m installer version --json` and parsing the resulting JSON. The kernel **does not import** `installer.paths` or `installer.registry` at the Python level — preserving the "kernel never imports installer" unidirectional dependency rule end-to-end (both read and write sides).

The `cbim version --json` subcommand is the **stable machine-readable read surface** for all external consumers (see `installer/.dna/module.md` Key Decision "`cbim version --json` is the stable machine-readable read surface"). Schema is additive; consumers must tolerate unknown keys.

Implementation note: subprocess overhead is paid on each `cbim upgrade check` and each notifier wake-up. This is acceptable because (a) `check` is interactive/diagnostic, not hot-path, and (b) the notifier already gates remote checks behind `check_interval_hours` (24h default), so subprocess cost is bounded. If profiling later shows the overhead matters, the answer is to add a short-lived in-process JSON cache inside `app_state` — **not** to bypass the contract via direct import.

Option 2 (extracting a shared `cbim_install_api/` module) is rejected for this revision: it adds a new top-level module to the repo for a single consumer, and the subprocess path is already clean. Revisit only if a second external consumer emerges with hard latency requirements.

## Forbidden

- Writing to `<install_root>/` outside `apply_flow` (which itself goes through `invoke_installer` subprocess).
- Writing to `<project_root>/.cbim/` from this module — that belongs to `project.init` / `project.migrate`.
- Mutating `versions.json` from this module — installer subprocess only.
- Exposing a public `rollback` CLI command.
- 3-way merging `CLAUDE.md` — always overwrite, snapshot is the recovery path.
- Hard-coding `Path.home() / ".cbim"` or any install-root path. Always resolve via `installer.paths.install_root()` (whether by import or subprocess).
