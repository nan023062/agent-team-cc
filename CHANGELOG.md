# Changelog

[English](CHANGELOG.md) | [中文](CHANGELOG.zh-CN.md)

All notable changes to CBIM are recorded here. Format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the project follows semantic versioning at the kernel level.

---

## Versioning Policy

During CBIM's early phase, fix cadence is high. To keep user friction low:

- **Major / minor bumps** ship features or schema changes; users `cbim migrate --version <v>` to adopt.
- **Patches** (bug fixes, doc tweaks, internal refactors) do **not** bump the version. Users pull them with `cbim update --reinstall --local <kernel-src>` (or remote equivalent), keeping their current pin. The CHANGELOG records what was rolled into the pinned version after-the-fact.

This keeps the version line meaningful (each tag is a real surface change) and avoids forcing reinstall churn for every fix.

---

## [1.0.1] - 2026-05-22 — Execution-loop mechanism layer

This release lifts the execution loop from coordinator improvisation into an explicit, soul-prompt-driven mechanism. No new CLI, no new hook — the discipline lives in the skill texts and the project `CLAUDE.md` template that `cbim init` lays down. Existing projects pick it up via `cbim update --reinstall` + a re-`init` of `CLAUDE.md`.

### `arch_modules` skill

- **Execution Gate** — DNA state triage (0 / 1 / 2 / 3) with an explicit state→action matrix and a Worth0 decision step, so the architect routes by knowledge state instead of by gut.
- **ContextPack Schema** — four top-level fields plus a `modules[]` sub-schema, a Markdown example, and the consumption rule for Work Agents (reject on missing, no paraphrasing).

### `dispatch` skill

- **Decomposition Heuristics** — parallel-vs-sequential triage with a conservative default (when in doubt, sequence).
- **Phase 2 Input Contract** — ContextPack is forwarded verbatim, wrapped in standardized `<!-- BEGIN ContextPack -->` / `<!-- END ContextPack -->` markers; Work Agents reject any prompt missing this block.
- **Interruption Thresholds** — three explicit stop conditions: intent ambiguity, result conflict, destructive overreach.

### `CLAUDE.md` template (kernel-generated, never user-edited)

- **Workflow rewritten.** Step 6 grows a Branch A loopback path: Work Agent → Architect via the `NEEDS_ARCH_DECISION:` escalation marker. Step 7 becomes three-branch consolidation: done / follow-up / conflict.
- **Loop termination.** 5-iteration soft cap plus an explicit convergence signal — the loop must terminate, no silent spinning.
- **Requirement-type task definition.** Code / module / contract / `.dna` writes are first-class requirement types.
- **Escalation marker format.** Work Agent escalation uses a fixed `NEEDS_ARCH_DECISION:` prefix.
- **Hard Rules + 3.** Knowledge-first on every loop iteration; honor the escalation marker; the loop must terminate.

### Architectural decisions reinforced

- All configs are kernel-generated, never copied — `cbim init` / `cbim update` overwrite `CLAUDE.md` from the template; user edits to that file are not preserved.
- The CBIM execution loop runs as soul-prompt-driven LLM self-discipline. No new CLI command, no new hook. The discipline is in the text.

### Upgrade path

```bash
cbim update --reinstall --local <kernel-src>   # pull 1.0.1 into the install root
cbim migrate --version 1.0.1                   # re-pin the project
```

Then re-run `cbim init` in each project (or wait for the template-refresh path) to pick up the new `CLAUDE.md`.

---

## [1.0.0] - 2026-05-22

Initial public release. Version numbering reset from internal iteration.

### Architecture

CBIM (Capability–Business Independence + Memory) splits an LLM agent project along two axes:
- **Business axis** — per-module `.dna/` knowledge tree governed by the Architect role.
- **Capability axis** — specialized agents and their skills, governed by the HR role.

A session-spanning memory pipeline loads only `target-agent-soul × task-subtree.dna` per task — bounded context, fewer hallucinations, durable cross-session knowledge.

Two implementations live side by side:
- **V1 — CC Kernel** (this release): Python add-on on top of Claude Code.
- **V2 — Native Agent**: Standalone C# / .NET 8 runtime; design phase.

### Kernel CLI

- `cbim init` — bootstrap `.cbim/`, `.claude/`, `CLAUDE.md`, `.claudeignore` in a project.
- `cbim migrate --version <v>` — migrate project layout and pin to a kernel version.
- `cbim update [--reinstall] [--local <path>]` — update installed kernel; `--reinstall` (alias `--force`) forces snapshot redeploy even when the version number is unchanged.
- `cbim upgrade {check, apply}` — compare and apply schema upgrades.
- `cbim dna {list, show, init, edit, reindex, write-doc, write-section}` — module knowledge CRUD. `edit --target {frontmatter|body|section|contract|contract-section|workflow}` is the unified entry; `--value-list` writes block-style YAML lists for list-typed fields. `write-doc` / `write-section` kept as deprecated aliases.
- `cbim agent {list, show, scaffold, archive}` — agent definition CRUD.
- `cbim memory {add, query, cleanup, reindex}` — memory entries; session-start/end memory flush is handled by hooks in-process.
- `cbim skill {list, show}` — built-in skill discovery.
- `cbim snapshot`, `cbim config`, `cbim log`, `cbim dashboard`, `cbim debug`, `cbim hook`, `cbim mcp`, `cbim project`, `cbim release-notes`.

### Internal Architecture

- `cbi/resources/` — unified resource object model: `Agent`, `DNAModule`, `Skill`, `Workflow`, `Memory`. Each façade exposes `.frontmatter` / `.body` / sub-collection accessors and an atomic `.save()`.
- `cbi/_primitives/` — internal engine primitives (load / parse / write). Not for direct import; use `cbi.resources` instead.
- `services/_fm.py` — sole frontmatter parser / renderer.
- Strict unidirectional dependency: `cli → resources → _primitives → services/_fm`.
- Hooks (`write_memory`, `load_memory`) run in-process for low-latency session boundary handling.

### Rolling Fixes (under pinned 1.0.0)

Per the versioning policy above, the following fixes have been rolled into the 1.0.0 source line without a version bump. Pull with `cbim update --reinstall --local <kernel-src>`.

- `cbim upgrade` / `cbim update` invoked through the kernel facade now propagate `<install_root>` on `PYTHONPATH` to the spawned `python -m updater` subprocess, fixing `ModuleNotFoundError: No module named 'updater'` on projects that had installed kernel 1.0.0.
- `cbim install` (both `--local` and GitHub release paths) now refreshes the on-PATH launcher (`cbim_launcher.py`, `cbim`, `cbim.cmd`) under `<install_root>/bin/`. Previously the launcher was written once at first install and never updated, so routing changes (e.g. the addition of `upgrade` / `check` / `apply` to `UPDATER_COMMANDS`) never reached the user's machine. Refresh is atomic via `os.replace`, safe under Windows file-lock semantics.

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.sh | bash
```

Windows / no-bash:

```bash
curl -fsSL https://raw.githubusercontent.com/nan023062/cbim/master/bootstrap.py | python3
```

Pin a specific version: `CBIM_VERSION=1.0.0 curl ... | bash`

### Requirements

- Python 3.10+
- Claude Code CLI
