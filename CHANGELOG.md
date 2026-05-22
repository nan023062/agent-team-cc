# Changelog

[English](CHANGELOG.md) | [中文](CHANGELOG.zh-CN.md)

All notable changes to CBIM are recorded here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project follows semantic versioning at the kernel level.

---

## [2.3.0] - 2026-05-22

### Architecture — Unified Resource Object Model

Closes the long-standing Kernel-Only Writes gap for `.dna/` and `.claude/agents/`. A new `cbi/resources/` package exposes five resource façades — `Agent`, `DNAModule`, `Skill`, `Workflow`, `Memory` — each with consistent `.load() / .save() / .delete()` lifecycle and `.frontmatter` / `.body` / sub-collection accessors. The CLI is now a thin (~120 LOC) dispatch layer over these objects; resource logic lives in exactly one place.

Dependency direction is strictly unidirectional: `cli → resources → _primitives → services/_fm`.

### Added

- `cbi/resources/` package — 10 modules: `Resource` base, `Frontmatter`, `Body`, `atomic_write_text`, plus `Agent` / `DNAModule` / `Skill` / `Workflow` / `Memory` façades.
- `cbim dna edit --target {frontmatter|body|section|contract|contract-section|workflow}` — unified DNA edit entry; supports `--dry-run`, `--content` / `--content-file` / `--stdin`, and `--create-if-missing`.
- `--value-list` flag for list-typed frontmatter fields (`keywords`, `dependencies`, `includeDirs`); writes block-style YAML lists. Scalar `--value` on a list-typed field is now rejected explicitly.
- `cbim update --reinstall` (with `--force` alias) — forces snapshot redeploy of the current pin even when the version number is unchanged. Supports `--reinstall --local <path>` for developer hot-path refresh.
- `Skill.list_builtin()` / `Skill.load_builtin(key)` — built-in skill discovery exposed as resource methods.

### Changed

- `cbi/engine/` renamed to `cbi/_primitives/` to signal "internal primitives, do not import directly". External callers should use `cbi.resources` instead.
- `cbi/_primitives/cli.py` collapsed from ~350 LOC of `cmd_*` wrappers to a 17-line stub; dispatch moved into `engine/cli.py` as private `_handle_*` handlers calling `cbi.resources` directly.
- `services/_fm.py` gains `render_frontmatter` and becomes the sole frontmatter parser/renderer; duplicate `_parse_frontmatter` / `_strip_frontmatter` / `_parse_yaml_block` removed from `agents.py` and `modules.py`.
- Hooks (`write_memory`, `load_memory`) switch from subprocess to in-process imports of `memory.engine.{writer,loader}` and `cbi._primitives.snapshot`, eliminating per-event Python startup cost.
- MCP tools (`agent.py`, `dna.py`, `memory.py`, `skill.py`, `snapshot.py`) switch to `cbi.resources`, eliminating direct `MemoryEngine` / engine-primitive imports.

### Deprecated

- `cbim dna write-doc` / `write-section` — kept as deprecated aliases that print a stderr warning and forward to the legacy path. Migrate to `cbim dna edit --target body|section`.

### Removed

- `cbim memory write-session` / `load-context` / `preview` — replaced by in-process hook calls; `preview` superseded by `cbim dashboard`. These were hook-implementation surfaces; typical user workflows are unaffected.

### Fixed

- `cbim dna edit` argparse registration now correctly enumerates all `--target` choices and validates list-typed fields.
- Architect agent definition (`architect.md`) no longer falsely lists `index.md` as a `.dna/` core file (the registry lives at `.cbim/index.md` and is auto-maintained).

## [2.2.3] - 2026-05-22

### Added
- Agent tagging in session log: all subagent log entries are tagged with `[agent:<name>]` between the signal tag and the message; main-session lines remain untagged. Identity is resolved from `transcript_path` via the sibling `.meta.json` (`agentType` field).
- Rich session log: full conversation flow recorded with `[CALL]`/`[RET]` signals for all tool invocations.

### Fixed
- Reconfigure stdout/stderr to UTF-8 at cbim entry point to avoid codec errors on Windows.
- `config set/get` now correctly handles nested key paths; `cbim install` writes Claude deny rules on first install.
- `cbim_update` skill: removed stray `--no-additional-flags` argument from `release-notes` call.

### Changed
- Trim `cbim_update` prompt (removed verbose step 5); loosen `settings.json` deny rules to only cover `.cbim/**` paths.

## [2.2.0] - 2026-05-22

### Added
- `cbim release-notes <version>` command — prints GitHub release notes for any installed kernel version; fails soft on network errors (prints fallback URL, exits 0).
- `cbim_update` skill now auto-prints release notes at the end of a successful update (Step 5); skipped when no version change occurred (scenario 7).

### Changed
- Session log refactored as a dedicated logger module.

### Fixed
- `cbim release-notes` output was garbled on Windows consoles using GBK codepage; stdout is now explicitly reconfigured to UTF-8.

## [2.1.0] - 2026-05-22

### Built-in Slash Commands — OWNED Kernel Assets

`cbim init` now installs six built-in slash commands into `.claude/commands/`. These commands are kernel-owned (OWNED strategy): `cbim migrate` and `cbim update` overwrite them on upgrade so their content stays in sync with the kernel version. User-created commands outside the built-in set are never touched.

### Added

- `v1/src/kernel/cbim_kernel/project/commands/` — new template directory holding the 6 built-in slash commands: `cbim_dashboard`, `cbim_debug`, `cbim_help`, `cbim_log`, `cbim_sched`, `cbim_update`.
- `KERNEL_COMMAND_NAMES` constant in `sync.py` — explicit enumeration of built-in commands, parallel to `KERNEL_AGENT_NAMES`.
- `sync_command()` / `sync_commands()` in `sync.py` — OWNED sync functions for built-in commands, mirroring `sync_agent` / `sync_agents` semantics.
- `_update_commands()` in `migrate.py` — built-in commands are now overwritten on every `cbim migrate` / `cbim update`.

### Changed

- `sync_templates()` now includes `sync_commands()` between `sync_agents()` and `sync_settings()`.
- `cbim init` installs `.claude/commands/` alongside `.claude/agents/`; existing files skipped unless `--force`.
- UPDATE-FLOW docs: OWNED row extended to include 6 built-in commands; UNTOUCHED row now reads `.claude/commands/<user-owned>` (non-built-in commands are still never touched).
- Upgrade notify text: distinguishes `.claude/commands/ (6 built-in)` in overwrites from `.claude/commands/<user-owned>` in preserves.

---

## [2.0.0] - 2026-05-22

### Architecture — Updater / Kernel Sibling Split

This is a major architectural release. The updater and kernel are now **siblings**, not a single monolith. Cross-version operations (install, upgrade, migrate, pin) live exclusively in the new `updater` package; the kernel is a pure single-version runtime with no knowledge of how it is installed or upgraded.

### Added

- `v1/src/updater/` — new machine-level updater package extracted from `installer/` and the kernel's upgrade sub-module. Owns all cross-version operations.
- `cbim pin <version>` subcommand — pins the current project to any locally installed version (Bug C fix).
- `cbim migrate` subcommand in updater CLI — project schema migration now accessible directly via `python -m updater migrate`.
- `cbim self-update` routed through launcher to updater.
- `.claudeignore` project template (OWNED strategy) — generated by `cbim init` and refreshed on `cbim migrate`. Default content: `.cbim/`, `**/.dna/`, `.venv/`, `__pycache__/`, `*.pyc`.
- `sync.read_template(name)` — public accessor for kernel-managed template files; used by `cbim soul show assistant`.
- `v1/docs/UPDATE-FLOW.md` / `UPDATE-FLOW.zh-CN.md` — complete update loop diagram and component boundary reference.

### Changed

- `installer/` demoted to a deprecated reexport shim; all logic lives in `updater/`. Will be removed in a future release.
- Launcher `INSTALLER_COMMANDS` → `UPDATER_COMMANDS`, extended with `update`, `upgrade`, `migrate`, `check`, `apply`, `self-update`; launcher now spawns `python -m updater` instead of `python -m installer`.
- `write_pin` removed from `kernel/project/pin.py`; kernel is now read-only for `.cbim/.pin`. Only updater writes the pin file.
- `kernel/project/upgrade/cli.py` replaced with a subprocess facade that forwards `cbim upgrade check|apply` and `cbim update` to `python -m updater`.
- `kernel/project/migrate.py` moved to `updater/migrate.py`; kernel's `_cmd_migrate` is now a subprocess facade.
- Snapshot scope narrowed to `versions.json` + `kernel/<ver>/` only — `updater/`, `bin/`, `venv/` excluded.
- `cbim soul show assistant` now reads `project/templates/CLAUDE.md.tmpl` instead of the stale `cbi/claude_md.py` constant.

### Fixed

- **Bug A** — `upgrade apply` preflight now detects legacy schema (`cbim_version` in `config.json`, no `.pin` file) and refuses with a clear message directing users to run `cbim migrate` first.
- **Bug B** — `cbim update` now automatically triggers `cbim migrate` after a successful kernel upgrade, ensuring project config is brought forward in the same operation.
- **Bug C** — `cbim pin <version>` subcommand is now implemented (previously recommended by `cbim upgrade check` output but missing from the CLI).

### Removed

- `v1/src/install/` legacy installer directory (superseded by `v1/src/installer/` and now `v1/src/updater/`).
- `v1/src/kernel/cbim_kernel/cbi/claude_md.py` dead code (stale CLAUDE_MD constant, no live references).
- `kernel/project/upgrade/{app_state,apply_flow,config,diagnose,notify,project_state,remote}.py` — all moved to `updater/upgrade/`.

---

## [1.3.5] - 2026-05-22

### Fixed

- Launcher now reads the project pin from `.cbim/.pin` (post-1.3.3 location) before falling back to the legacy `cbim_version` field in `.cbim/config.json`. Before 1.3.5, fresh installs failed with `no kernel version resolved` because the post-1.3.3 `cbim init` template no longer writes `cbim_version` into `config.json`. **Existing 1.3.4 installs are broken until re-installed**: rerun `python install.py` (re-bootstrap or pull tarball) to pick up the patched launcher. `cbim install 1.3.5` alone will NOT refresh `<install_root>/bin/cbim_launcher.py`.
- Launcher now falls back to `versions.json[active_default]` when neither project pin nor `CBIM_DEFAULT_VERSION` is set, instead of dying.

### Changed

- Docs: README scheduler section reflects reality (tasks ship inside the kernel package `cbim_kernel.mcp_server.tasks`; there is no `.cbim/mcp_server/` in target projects; no project-local task drop-in path yet).
- Internal: stale `INSTALL.md` references in `ARCHITECTURE.md`/`ARCHITECTURE.zh-CN.md`, `install/cli.py`, `install/install.py`, `install/settings.py`, `cbi/claude_md.py`, and the `CLAUDE.md.tmpl` banner all now point to `README.md`.

---

## [1.3.4] - 2026-05-22

### Added

- `bootstrap.sh` / `bootstrap.py`: one-line install from the repo, no `git clone` required. Honors `CBIM_VERSION` / `CBIM_REF` env vars and supports `CBIM_BOOTSTRAP_DRY_RUN` for verification.

### Changed

- README quickstart now leads with the one-line bootstrap; the historical `git clone` + `python v1/src/install.py` path still works but is no longer the primary recommendation.

### Removed

- `v1/INSTALL.md` and `v1/INSTALL.zh-CN.md` — the manual SOP had drifted from repo layout (referenced a top-level `.cbim/mcp_server/`, manually overwrote `.claude/settings.json` that `cbim init` already merges safely). The bootstrap script + `install.py` + `cbim init` now own the install surface end-to-end.

---

## [1.3.3] - 2026-05-22

### Motivation

The project schema pin — the per-project version number that tells the kernel "this project is on schema X" — is the single most frequently written piece of project state. It moves every time you run `cbim update`, `cbim upgrade apply`, or `cbim migrate`. Living inside `.cbim/config.json` meant every pin bump:

- polluted `git diff` with a full JSON re-serialization of the whole config file, even when no user-visible setting changed;
- forced a JSON load-modify-dump round-trip just to flip one integer;
- mixed a machine-owned cursor with user-owned configuration in the same file, making "what should I commit?" ambiguous.

### Changed

- Project schema pin extracted from `.cbim/config.json` to a dedicated plain-text file `.cbim/.pin`.
  - One line: the version string, terminated with a single newline. No JSON, no fields, no comments.
  - The file is added to `.gitignore` — pin is local project state, not source.
- All reads and writes of the pin now go through a single accessor module `project/pin.py` (hard rule — no other code may touch `.cbim/.pin` directly).
- `cbim_version` is removed from `.cbim/config.json`. The kernel no longer reads or writes that key.

### Migration

Run either of the following once per project; both are idempotent:

```bash
cbim update -y
# or, if you only want to migrate without fetching a new kernel:
cbim migrate --version 1.3.3
```

The migrator will:

1. Read the legacy `cbim_version` from `.cbim/config.json`.
2. Write it into `.cbim/.pin` (single line, trailing newline).
3. Delete `cbim_version` from `.cbim/config.json`.
4. Append `.cbim/.pin` to `.gitignore` if not already present.

After migration, `git diff` no longer shows churn on every pin bump.

---

## [1.3.2] - 2026-05-22

### Fixed

- `cbim migrate` always advanced the project pin, even when the project layout was already on the latest schema. It now no-ops when there is nothing to migrate.
- `cbim upgrade apply` preflight error messages referenced a `--to` flag that no longer exists. They now correctly point users to `--version`.
- `diagnose.py` and the `/cbim_update` slash command had inconsistent flag names. Both now use `--version` everywhere.

---

## [1.3.1] - 2026-05-22

### Fixed

- `cbim upgrade apply` was still passing the removed `--set-default` flag through to a sub-call, causing every upgrade to roll back. The orphaned flag is removed and upgrade now applies cleanly.

---

## [1.3.0] - 2026-05-21

### Changed

- Baseline version bump. No behavior change for end users; this release exists to align the kernel version line with the new schema-pin work that lands in 1.3.1+.
