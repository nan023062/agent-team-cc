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
    migrate["migrate.py (file)<br/>cbim migrate: legacy → global-kernel layout"]
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

A CBIM project is a directory tree the user controls: `.cbim/config.json` (pin + project config), `.cbim/memory/`, `.cbim/logs/`, `CLAUDE.md`, `.claude/agents/`. Three orthogonal events change its shape:

1. **First use** (`init`) — directory doesn't exist yet, copy a templated skeleton.
2. **Schema drift** (`migrate`) — directory exists but follows an old layout (e.g. the pre-global-kernel "kernel-in-project" layout).
3. **Version drift** (`upgrade`) — directory is current-schema, but `config.json.cbim_version` is older than the latest installed kernel.

Three distinct write events → three sub-modules. They share templates because the *shape* of `.cbim/` is one design; the *trigger* for writing it differs.

## Key Decisions

- **`init.py` and `migrate.py` are single files; `upgrade/` is a sub-package.** Reason: `upgrade` is the only one of the three that needs a non-trivial state machine (the 7-scenario matrix below), inspects external state (`<install_root>/versions.json`, git ls-remote), and has its own configuration block in `config.json`. The other two are flat procedures. Pre-emptively packaging them would add boundary cost without enabling reuse.
- **`upgrade` does not import `installer`.** It calls `python -m installer install <ver>` via subprocess. This preserves the root-level "kernel never imports installer" rule even though `upgrade` orchestrates an install-root mutation.
- **All three respect `.cbim/config.json` as the source of truth** for the project's pinned `cbim_version`. None write outside `.cbim/` except `init`, which also writes `CLAUDE.md` and `.claude/agents/`.
- **`upgrade` covers diagnostic, not just action.** Its `check` subcommand is a holistic version-state inspector across two axes (app-side install vs project-side pin), covering 7 scenarios — see `project/upgrade/.dna/module.md`.
