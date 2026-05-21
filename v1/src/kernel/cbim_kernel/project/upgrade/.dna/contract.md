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

This module consumes the following stable entries from sibling modules. None are imported via Python except `cbim_kernel.context` (kernel-internal, kernel-local).

| From | Entry | Used by | How |
|------|-------|---------|-----|
| `installer.paths` | `install_root()` | `app_state.get_install_root` | Python import (kernel and installer co-exist on PYTHONPATH only during upgrade flows; the actual installer ops still go via subprocess) — **OPEN POINT, see below** |
| `installer.registry` | `list_installed()`, `get_default()`, `get_kernel_path(v)`, `versions_file()` | `app_state.*` | Python import (read-only API) |
| `installer` (CLI) | `python -m installer install <ver>` | `apply_flow.invoke_installer` | subprocess only |
| `cbim_kernel.context` | `project_root()`, `cbim_dir()` | `project_state.find_project_root` | Python import (kernel-internal) |
| `cbim_kernel.project.migrate` | (none — referenced only as a *command to recommend*) | diagnostic text | string only |

### OPEN POINT (for assistant): kernel-side import of `installer.paths` / `installer.registry`

The root-level architecture rule says "kernel never imports installer." This was preserved on the *write* side (subprocess for mutations). On the *read* side, `upgrade` needs to know what is installed and where. Two compliant options:

1. **Read via subprocess too.** `python -m installer versions --json` returns the registry. Slower; subprocess overhead on every `check` and every notifier wake-up. Simpler dependency graph.
2. **Promote the registry-read surface to a tiny shared module** (e.g. a new top-level `cbim_install_api/` that both `installer` and the kernel may import) — i.e. extract `installer.paths` and the read-only half of `installer.registry`. Cleaner conceptually; adds one module to the repo.

Current design above leans toward option 1 (subprocess) for purity — the contract row marked "Python import" should in fact be subprocess. I am calling this out because the answer affects implementation, not architecture: the contract surface (`Diagnosis` value, CLI commands, JSON schema) stays identical either way. **Recommend the assistant defer this to the programmer at implementation time** — both options preserve unidirectional dependency.

## Forbidden

- Writing to `<install_root>/` outside `apply_flow` (which itself goes through `invoke_installer` subprocess).
- Writing to `<project_root>/.cbim/` from this module — that belongs to `project.init` / `project.migrate`.
- Mutating `versions.json` from this module — installer subprocess only.
- Exposing a public `rollback` CLI command.
- 3-way merging `CLAUDE.md` — always overwrite, snapshot is the recovery path.
- Hard-coding `Path.home() / ".cbim"` or any install-root path. Always resolve via `installer.paths.install_root()` (whether by import or subprocess).
