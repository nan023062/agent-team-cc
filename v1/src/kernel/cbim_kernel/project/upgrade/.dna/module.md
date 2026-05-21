---
name: upgrade
owner: architect
description: cbim upgrade: holistic version-state inspector (check) + app-side install repointer (apply); 7-scenario diagnostic across app install vs project pin
keywords: []
dependencies: []
---

## Positioning

`cbim upgrade` — a holistic version-state inspector and app-side install repointer. `check` diagnoses the joint state of the global app install and the per-project pin and prints exact next-step commands. `apply` upgrades the app-side install in place. Project-side schema migration is delegated to `cbim migrate`; rollback is internal-only and automatic on failure.

## Class Diagram

```mermaid
classDiagram
    class cli {
        +cmd_check(args) int
        +cmd_apply(args) int
        +build_parser(subparsers)
    }
    class diagnose {
        +diagnose() Diagnosis
        +scenario_id(app_state, project_state) int
    }
    class Diagnosis {
        +scenario : 1..7
        +app_installed_versions : list~str~
        +app_latest_local : str | None
        +app_remote_latest : str | None
        +project_pin : str | None
        +project_root : Path | None
        +recommendation : str
        +commands : list~Command~
        +ordered : bool  // true when commands MUST run in given order
    }
    class Command {
        +shell : str
        +description : str
    }
    class app_state {
        +list_installed() list~str~  // wraps installer.registry.list_installed
        +active_default() str | None
        +get_install_root() Path     // wraps installer.paths.install_root
    }
    class project_state {
        +find_project_root(start) Path | None
        +read_pin(project_root) str | None
        +read_upgrade_config(project_root) UpgradeConfig
    }
    class remote {
        +latest_tag(remote_url, pattern) str | None
        +ls_remote_tags(remote_url) list~str~
        +network_available() bool
    }
    class apply_flow {
        +preflight(target_version) PreflightResult
        +snapshot_app(install_root, current_versions) Path
        +invoke_installer(target_version, source) int
        +verify_post_install(target_version) bool
        +rollback_from_snapshot(snapshot_path) None
    }
    class notify {
        +session_start_line() str | None  // for hooks.load_memory
        +cache_path(project_root) Path
        +read_cache(project_root) NotifyCache | None
        +write_cache(project_root, cache) None
    }
    class config {
        +DEFAULT_REMOTE = "https://github.com/nan023062/cbim.git"
        +DEFAULT_PATTERN = "v*"
        +DEFAULT_CHANNEL = "stable"
        +DEFAULT_AUTO_CHECK = true
        +DEFAULT_INTERVAL_HOURS = 24
        +load_from_project(project_root) UpgradeConfig
    }

    cli --> diagnose
    cli --> apply_flow
    diagnose --> app_state
    diagnose --> project_state
    diagnose --> remote
    apply_flow --> app_state
    apply_flow --> remote
    notify --> diagnose
    project_state --> config
```

## Key Decisions

### 7-scenario diagnostic matrix

`check` MUST classify the joint state into one of the following scenarios and emit the corresponding recommendation + ordered commands. This matrix is the externally-visible contract of the module — see `contract.md`.

| # | App (Cbim-CC install) | Project (`.cbim/`)                          | Scenario name              | Recommended commands (in order)                                                            |
|---|------------------------|---------------------------------------------|----------------------------|---------------------------------------------------------------------------------------------|
| 1 | not installed          | not initialized                             | `cold-start`               | `python install.py` (or download installer), then `cbim init` inside the target project dir |
| 2 | installed, current     | not initialized                             | `app-ready-project-new`    | `cbim init` (run in project dir)                                                            |
| 3 | installed, outdated    | not initialized                             | `app-stale-project-new`    | `cbim upgrade apply --to <latest>`, then `cbim init`                                        |
| 4 | installed, current     | pinned to an older installed version        | `project-stale-vs-app`     | EITHER `cbim migrate --version <app-current>` (recommended) OR explicit `cbim pin <X>`      |
| 5 | installed, outdated    | pinned older than app, app older than remote| `both-stale`               | `cbim upgrade apply --to <remote-latest>`, then `cbim migrate --version <remote-latest>`    |
| 6 | installed, outdated    | pin equals current app version              | `app-stale-project-aligned`| `cbim upgrade apply --to <remote-latest>`; project pin stays at `<X>` unless the user opts to also migrate |
| 7 | installed, current     | pin equals app current                      | `all-aligned`              | (nothing to do; print "All aligned at version <X>.")                                        |

Each row, when emitted, includes:
- A one-line **state description** ("App is at 1.2.3 (latest local), project pins 1.2.0, remote latest is 1.2.3.")
- The exact **commands** in execution order
- An **order flag** — `ordered=true` for #3 and #5 (must run sequentially) — to suppress parallel-execution hints by the assistant

### Module-level decisions

- **Subprocess to installer, never import.** `apply_flow.invoke_installer` shells out to `python -m installer install <ver>` (resolved via `<install_root>/installer/`). This keeps the root-level "kernel never imports installer" rule intact even though upgrade orchestrates an install-root mutation.
- **Snapshot + automatic rollback are internal-only.** Before `apply` overwrites `<install_root>/installer/`, `<install_root>/bin/`, and stages a new kernel under `<install_root>/kernel/<new-ver>/`, it captures a tar snapshot of those paths. On any failure (network mid-download, checksum mismatch, post-install verification failure), the snapshot is restored automatically. There is NO `cbim upgrade rollback` subcommand — users only ever see success or "rolled back to <prev-ver> due to <reason>". (Decision #5.)
- **CLAUDE.md is always overwritten on a kernel upgrade; snapshot is the safety net.** No 3-way merge attempt. User customizations to CLAUDE.md are not preserved; users are expected to keep custom prompt content in their own project-side files. (Decision #4.)
- **Default `upgrade.remote` is hard-coded in the template** to `https://github.com/nan023062/cbim.git`. (Decision #3.) Users can override per-project in `.cbim/config.json`.
- **`upgrade.auto_check` is true by default**, with a 24-hour interval. The notifier in `hooks.load_memory` reads `notify.cache_path(project_root)`; if older than the interval, it runs a fresh `diagnose` in a fire-and-forget subprocess and updates the cache. The user-visible cost is at most one stdout line per session start when an update is available.
- **Network failures are silent on `check` and fatal on `apply`.** `check` degrades gracefully (omits the `app_remote_latest` field; scenarios 5/6 may fall back to 4/7 if remote is unreachable, with a "remote unreachable" note). `apply` refuses to proceed without network confirmation of the target's existence.
- **Version-incompatibility preflight.** Before `apply`, `apply_flow.preflight` checks whether jumping from current pin to target requires a schema migration in `.cbim/`. If so, it refuses and instructs the user to run `cbim migrate --version <ver>` first. The upgrade module never touches `.cbim/` directly.
- **Only the app side is upgraded by this module.** Project-side schema migration belongs to `project.migrate`; the user invokes it explicitly. This is a hard split: `upgrade.apply` mutates `<install_root>/`; `migrate` mutates `<cwd>/.cbim/`. No flag combines them — they remain two steps, surfaced as two commands.
- **Diagnosis is pure and side-effect-free.** `diagnose.diagnose()` returns a `Diagnosis` value; CLI / notifier / future MCP tool all share it. Testability and reuse hinge on this.
