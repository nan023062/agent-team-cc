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

## [1.0.5] - 2026-05-22 — DNA: spec status field + atomic split command

New `status` frontmatter field on `.dna/module.md` (orthogonal to `dna_state`):

- Three values: `spec` (designed, not built — S3 state), `planned` (named only, design pending), `implemented` (code matches DNA).
- `status` is declared intent (architect-set, programmer-flipped); `dna_state` (0/1/2/3) is observed drift. Both are surfaced in `cbim dna show` / `dna list` / `cbim snapshot` so architect can spot stale spec flags (e.g. `status:spec + dna_state:1` = programmer forgot to flip after implementing).
- `cbim dna init` accepts `--status` (default `spec` for leaf/parent, `implemented` for root); `cbim dna edit --target frontmatter --field status --value <v>` enforces the enum.
- Backward compat: existing 17 module.md files in this repo (and any others elsewhere) remain byte-stable; missing-status defaults to `implemented` in `load_module()` return dict.
- `arch_modules` skill updated: Worth0 decision / S3 action / orthogonality matrix all teach the new vocabulary. Deprecate Module section rewritten per architect ruling — deprecation is a lifecycle axis, NOT a status enum extension; lifecycle frontmatter schema reserved for a future release (follow-up tracked).

New `cbim dna split <source> --into <path>:<name>:<H1|H2|...>` atomic command:

- Splits a source module into N new modules in one all-or-nothing command. New modules default to `status: spec` (consumes the new field).
- Atomicity: stages all writes to `.tmp` files first, validates the full plan, then sweeps `os.replace` in dependency order; on any failure, unlinks all `.tmp` files and leaves disk untouched (verified with deliberate failure injection in mid-sweep test).
- Source-side default: keeps the original sections with `<!-- split: moved <heading> → <new-path> -->` deprecation comments (traceability); `--no-keep-source` for a clean cut.
- Cross-module reference rewrite is OUT OF SCOPE — the command emits a SCAN-ONLY `dependency_refs` report naming sibling modules whose frontmatter `dependencies:` mention the source path, so architect can follow up with `cbim dna edit --field dependencies --value-list ...` manually. Keeping atomicity bounded to one source's decomposition (C2: single responsibility).
- Test coverage: 7 cases including happy path, target-pre-exists, missing-heading, dependency-report-only, dry-run, `status='spec'` inheritance, mid-sweep rollback.
- CLI limitation: `--into PATH:NAME:HEADINGS` colon-delimited form is awkward for Windows absolute paths; recommend POSIX-relative paths only (documented in `dna split --help`).

---

## [1.0.4] - 2026-05-22 — governance polish: signals template in writer + skill CLI alignment

- Memory write closure: `memory/engine/writer.py` now emits a 4-line `_SIGNAL_TEMPLATE` (MUST / WANT / HOW / IS unchecked rows with placeholder hints) under every `## 信号` heading, so empty-signals entries ship with a fill-in stub instead of a blank slot. `_fill_signals` semantics unchanged — the template is the fallback when no signals are auto-extracted; LLM/heuristic signals still replace everything after the byte-exact `\n## 信号\n` marker.
- `cbi/skills/memory_write/skill.py` "Entry Format" example block byte-aligned with the template (heading was `## Signals` English; corrected to `## 信号` Chinese to match 200+ existing entries + the hook's actual output).
- Skill text ↔ CLI alignment (14 drift points scanned; 6 MUST/SUGGEST text edits applied, 8 verified clean):
  - `arch_modules/skill.py`: `cbim dna update` → `cbim dna edit --target body` (S2 action of Execution Gate; was the only stale-command reference in the architect's hot path).
  - `memory_distill/skill.py`: `(see write.md spec)` → `(see memory_write skill)` (stale file reference); `## Signals` → `## 信号` (aligned with hook output).
  - `memory_query/skill.py`: removed contradictory duplicate code-block ("If CBIM is installed as a subdirectory..." prose was wrong; `cbim` is a launcher, no path prefix needed).
  - `architect/agent.py` + `hr/agent.py`: "engine dna / engine agent / engine memory" → "cbim dna / cbim agent / cbim memory" in the Kernel-Only Writes escalation rules (stale invocation surface from before launcher was canonical).
- Coverage: HR skills already synced in 1.0.3 (P3-1); this round closed all remaining drift in architect / memory skills. `arch_governance/check.py` script existence verified (exists).

---

## [1.0.3] - 2026-05-22 — governance loop wiring: HR write closure + memory threshold trigger

Closes two long-standing governance gaps. (1) HR write closure: the architect-flagged "dead-lock" where `.claude/agents/` is a governed directory but the only path the skill text suggested was `Edit` — agents whose tools list did not include `Edit` had no way to fulfil HR write operations. (2) Memory threshold trigger: the short-tier write pipeline was muscular but the governance side was unwired — entries accumulated indefinitely with no nag to distill.

### HR write closure

- **New CLI subcommands** `cbim agent update` and `cbim agent add-skill`, mirroring the `cbim dna edit` surface: `--target {frontmatter|body|section}`, `--content` / `--content-file` / `--stdin`, `--dry-run`.
- `agent update --target frontmatter` covers `description` / `model` / `tools`. Rejects `--field name` — rename is a separate operation by design.
- `agent update --target section` supports `replace` / `append` / `insert-after` / `delete` on `## Heading` blocks via `Body.write_section`.
- `agent add-skill` creates `.claude/agents/<id>/skills/<skill-id>/skill.md` atomically; exits 2 if the skill already exists.
- Updates targeting **kernel-managed** agents (architect / auditor / hr / programmer) emit a stderr warning — `"kernel-managed; will be overwritten on next 'cbim project sync'"` — but proceed. Local override is intentionally still possible.
- **Engine refactor:** `engine/cli.py` helper `_read_dna_content` renamed to `_read_content_arg` — a single content-input helper across all resources. Five call-sites updated; no behavior change.
- **HR skills synced:** `hr_agents` (Tools / Update / Archive / Fission sections) and `hr_training` (Step 3) now reference `cbim agent ...` instead of "directly edit" prose. The skill text and the CLI surface are finally aligned.

### Memory threshold trigger

- **SessionStart hook** (`load_memory.py`) emits a single-line banner when `count(.cbim/memory/short/*.md) >= memory.distill.suggest_threshold`, nudging the user to run `cbim skill show memory_distill`.
- **Banner ordering** preserves `additionalContext` priority: upgrade banner → threshold banner → snapshot → memory_out. Distillation nudges never bury the upgrade-required signal.
- **Config-driven threshold:** read via `memory.engine.config.load_config()` — fully decoupled from the config file location. Falls back to the in-code `_DEFAULTS` (= 5) when the key is unset, so legacy projects continue to work without migration.
- **Failure mode:** the hook swallows all exceptions per the `hooks/.dna` iron rule — a threshold-check bug never blocks the session.

### `memory.distill.*` config knobs (now visible)

- `v1/src/kernel/cbim_kernel/project/templates/config.json.tmpl` extended with a `memory.distill.{suggest_threshold, how_to_skill_threshold, how_to_workflow_threshold, must_review_threshold}` block, byte-aligned with `_DEFAULTS`.
- New projects ship with the knobs visible in `config.json` (tunable without code dives). Existing projects pick up identical numerical values from `_DEFAULTS` fallback — **zero migration risk, no auto-upgrade**.

### Notes

- No schema bump. Pure additive: new subcommands, new hook banner, new config block with backward-compatible defaults.
- Bug fix in spirit, not in letter — `cbim agent` did not previously crash; it simply had no `update` / `add-skill` verbs. HR's documented workflow was the gap.

---

## [1.0.2] - 2026-05-22 — fix: `cbim migrate` PYTHONPATH bug + enforce updater sibling-split invariant

A pure patch release. No surface change; no schema change. Fixes a regression in `cbim migrate` and removes a long-standing reverse-import that violated the updater↔kernel sibling-split iron rule.

### Bug

- `cbim migrate --version <v>` crashed with `ModuleNotFoundError: No module named 'cbim_kernel'` unless the caller had manually set `PYTHONPATH` to the kernel snapshot path. End-to-end migration was effectively unusable without an undocumented workaround.

### Root cause

- `v1/src/updater/migrate.py` imported `from cbim_kernel.project import sync as project_sync` — a reverse import from updater into kernel. This violates the `.dna` non-negotiable rule that updater and kernel are siblings under launcher, coupled **only** via on-disk contracts (`versions.json`, `kernel/<ver>/`, `.cbim/.pin`); Python imports across the boundary are forbidden in either direction.

### Fix

- New private module `v1/src/updater/sync.py` carries the `KERNEL_AGENT_NAMES` / `KERNEL_COMMAND_NAMES` constants and the `sync_settings` / `sync_agents` / `sync_commands` functions. All three are parameterized by an explicit `kernel_root: Path` argument, resolved via `updater.registry` rather than by importing the kernel package.
- `v1/src/updater/migrate.py` refactored to use `updater.sync` exclusively. The default-version fallback (formerly `from cbim_kernel import __version__`) is replaced with `updater.registry.get_default()`.
- Acceptance: `grep -r "cbim_kernel" v1/src/updater/` returns **0 import lines**; remaining mentions are on-disk path strings or `python -m cbim_kernel` subprocess invocations (legitimate disk-contract direction).

### Notes

- `v1/src/kernel/cbim_kernel/project/sync.py` is left in place — still has 2 internal consumers inside the kernel (`project/init.py`, `engine/cli.py` via `sync_templates` / `read_template`); it is **not** dead code. Deduping the two sync surfaces is deferred to a follow-up PR.
- Out of scope for this patch: launcher PYTHONPATH injection (would have been a fix in the wrong direction); the kernel facade `_fwd` introduced in `a49b62b` (unrelated, already on the correct dependency direction).

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
