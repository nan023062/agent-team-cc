---
name: project-lifecycle
owner: architect
description: Per-project lifecycle commands: init, migrate, upgrade
keywords: []
dependencies: []
---

## Positioning

Owns every operation that mutates a project's `<cwd>/.cbim/` directory. Three lifecycle stages: bootstrap (`init`), schema migration (`migrate`), kernel-version repinning (`upgrade`).

## Sub-module Relationships

```mermaid
graph TD
    init["init.py (file)<br/>cbim init: create .cbim/ from templates"]
    migrate["migrate.py (file)<br/>cbim migrate: legacy → global-kernel layout migration, plus pure pin-bump on already-current layout"]
    upgrade["upgrade/ (sub-package)<br/>cbim upgrade check|apply: repin to a newer kernel"]
    tpl["templates/<br/>config.json.tmpl, settings.json.tmpl, CLAUDE.md.tmpl, gitignore_entries.txt"]
    agt["agents/<br/>architect.md, auditor.md, hr.md, programmer.md"]

    init --> tpl
    init --> agt
    migrate --> tpl
    migrate --> agt
    upgrade -.->|reads, never overwrites| tpl
    upgrade -.->|reads installer contract (subprocess)| EXT[installer]
```

`init`, `migrate`, and `upgrade` share `templates/` and `agents/` as read-only source data. None of the three import each other.

## Origin Context

A CBIM project is a directory tree the user controls: `.cbim/config.json` (project config), `.cbim/.pin` (schema version pin — plain text, single line), `.cbim/memory/`, `.cbim/logs/`, `CLAUDE.md`, `.claude/agents/`. Three orthogonal events change its shape:

1. **First use** (`init`) — directory doesn't exist yet, copy a templated skeleton and write the initial `.cbim/.pin`.
2. **Schema drift** (`migrate`) — directory exists but follows an old layout (e.g. the pre-global-kernel "kernel-in-project" layout).
3. **Version drift** (`upgrade`) — directory is current-schema, but `.cbim/.pin` is older than the latest installed kernel.

Three distinct write events → three sub-modules. They share templates because the *shape* of `.cbim/` is one design; the *trigger* for writing it differs.

## Key Decisions

- **`init.py` and `migrate.py` are single files; `upgrade/` is a sub-package.** Reason: `upgrade` is the only one of the three that needs a non-trivial state machine (the 7-scenario matrix below), inspects external state (`<install_root>/versions.json`, git ls-remote), and has its own configuration block in `config.json`. The other two are flat procedures. Pre-emptively packaging them would add boundary cost without enabling reuse.
- **`upgrade` does not import `installer`.** It calls `python -m installer install <ver>` via subprocess. This preserves the root-level "kernel never imports installer" rule even though `upgrade` orchestrates an install-root mutation.
- **Pin lives in `.cbim/.pin`, not in `config.json`.** The pinned `cbim_version` is the single most frequently mutated piece of project state (every `cbim migrate` pin-bump and every `cbim upgrade` repoint writes it). Co-locating it inside `config.json` caused two problems: (1) it forced a full JSON round-trip for a one-line write, and (2) it polluted user-visible diffs every upgrade. The pin is therefore extracted to a dedicated file `.cbim/.pin` — plain text, single line containing the version string followed by a trailing newline (e.g. `1.3.1\n`). No JSON, no surrounding keys. `.cbim/.pin` is listed in the project's `.gitignore` so version bumps never appear in source-control history — the pin is local-machine state, not a shared project artifact. `config.json` retains only stable project configuration (`upgrade.remote`, `upgrade.auto_check`, etc.) and no longer carries `cbim_version`.
- **All pin reads and writes go through a single accessor.** A dedicated pin accessor (canonical home: `project/pin.py`, exposing `read_pin(project_root) -> str | None` and `write_pin(project_root, version) -> None`) is the only code path permitted to touch `.cbim/.pin`. `init`, `migrate` pin-bump path, `upgrade.apply_flow`, and `upgrade.project_state.read_pin` all delegate to it. No module re-implements the read/write inline. This guarantees the file format stays stable and any future change (location, format, locking) has exactly one edit site. **Iron rule, non-negotiable.**
- **`init` writes `.cbim/.pin` at bootstrap.** `cbim init` creates the file with the current kernel version on first use; the file is then maintained by `migrate` and `upgrade`. The `config.json.tmpl` template no longer contains a `cbim_version` field; `gitignore_entries.txt` includes the line `.cbim/.pin` so newly-initialized projects ignore the pin automatically.
- **`upgrade` covers diagnostic, not just action.** Its `check` subcommand is a holistic version-state inspector across two axes (app-side install vs project-side pin), covering 7 scenarios — see `project/upgrade/.dna/module.md`.
