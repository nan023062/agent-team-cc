# @cbim/cli migrate -- Implementation Contract

> Scope: `packages/cli/src/commands/migrate.ts` + `packages/engine/src/migration/`
> Consumer: End users running `npx @cbim/cli migrate <project-path>`
> Status: Phase 0 implementation contract

---

## 1. CLI Interface

### Command Signature

```
cbim migrate <project-path> [options]
```

### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project-path` | Yes | Path to the v1 project root to migrate. Absolute or relative to cwd. Must contain at least one v1 indicator (`.dna/`, `.claude/agents/`, `cbim/memory/store/`, or `CLAUDE.md`). |

### Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--dry-run` | boolean | `false` | Print the migration plan without writing any files. Exit code 0 if plan would succeed. |
| `--force` | boolean | `false` | Overwrite existing `.cbim/` directory if it already exists. Without this flag, migration aborts if `.cbim/` exists. |
| `--verbose` | boolean | `false` | Print detailed per-action output (source, destination, bytes transferred). |
| `--no-delete` | boolean | `false` | Migrate (copy) files to v2 locations but do NOT delete v1 sources. Useful for cautious migration. |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Migration completed successfully (or dry-run plan is valid). |
| `1` | Migration failed -- at least one action could not be completed. Details printed to stderr. |
| `2` | Invalid arguments -- missing project-path, path does not exist, or no v1 indicators found. |
| `3` | Target conflict -- `.cbim/` already exists and `--force` not specified. |

---

## 2. Core Types

All types are defined in `@cbim/engine/migration` and consumed by `@cbim/cli`.

```typescript
/**
 * A single atomic migration action.
 */
interface MigrationAction {
  /** Action type. */
  readonly type: 'move' | 'delete' | 'transform' | 'create'
  /** Source path (relative to project root). Undefined for 'create' actions. */
  readonly src?: string
  /** Destination path (relative to project root). Undefined for 'delete' actions. */
  readonly dest?: string
  /** Human-readable description of what this action does. */
  readonly description: string
  /** Action category for grouped display. */
  readonly category: 'root-module' | 'agents' | 'memory' | 'config' | 'cleanup'
}

/**
 * The complete migration plan for a v1 project.
 */
interface MigrationPlan {
  /** Absolute path to the project root. */
  readonly projectPath: string
  /** Ordered list of actions to execute. Order matters -- later actions may depend on earlier ones. */
  readonly actions: readonly MigrationAction[]
  /** Warnings discovered during planning (e.g., files that look unusual but are not blockers). */
  readonly warnings: readonly string[]
  /** Whether the project has v1 indicators sufficient for migration. */
  readonly isV1Project: boolean
}

/**
 * Result of executing a migration plan.
 */
interface MigrationResult {
  /** Whether all actions completed without error. */
  readonly success: boolean
  /** Actions that were successfully applied, in order. */
  readonly applied: readonly MigrationAction[]
  /** Actions that were skipped (source did not exist at execution time). */
  readonly skipped: readonly MigrationAction[]
  /** Actions that failed, with error details. */
  readonly errors: readonly MigrationActionError[]
}

/**
 * A failed migration action with its error.
 */
interface MigrationActionError {
  readonly action: MigrationAction
  readonly error: string
}

/**
 * Summary statistics for display after migration.
 */
interface MigrationSummary {
  readonly modulesmigrated: number
  readonly agentsMigrated: number
  readonly memoryEntriesMigrated: number
  readonly configExtracted: boolean
  readonly filesDeleted: number
  readonly warnings: readonly string[]
  readonly errors: readonly string[]
}
```

---

## 3. Error Types

```typescript
/**
 * Project path does not exist or is not a directory.
 */
interface InvalidProjectPathError extends Error {
  readonly name: 'InvalidProjectPathError'
  readonly projectPath: string
}

/**
 * No v1 indicators found at the given path.
 * The project does not appear to be a v1 CBIM project.
 */
interface NotV1ProjectError extends Error {
  readonly name: 'NotV1ProjectError'
  readonly projectPath: string
  readonly checkedIndicators: readonly string[]
}

/**
 * Target .cbim/ directory already exists and --force was not specified.
 */
interface TargetExistsError extends Error {
  readonly name: 'TargetExistsError'
  readonly targetPath: string
}

/**
 * A transform action failed (e.g., CLAUDE.md parsing failure, agent frontmatter synthesis failure).
 */
interface TransformError extends Error {
  readonly name: 'TransformError'
  readonly action: MigrationAction
  readonly reason: string
}
```

---

## 4. API Functions (in @cbim/engine/migration)

```typescript
/**
 * Analyze a v1 project and produce a migration plan.
 *
 * @param projectPath - Absolute path to the v1 project root.
 * @returns A migration plan with ordered actions.
 * @throws InvalidProjectPathError if path does not exist or is not a directory.
 * @throws NotV1ProjectError if no v1 indicators are found.
 *
 * Behavior:
 * 1. Verify projectPath exists and is a directory.
 * 2. Check for v1 indicators (at least one must exist):
 *    - `<project>/.dna/module.md` or `<project>/.dna/module.json`
 *    - `<project>/.claude/agents/` with at least one .md file
 *    - `<project>/cbim/memory/store/`
 *    - `<project>/CLAUDE.md`
 *    If none found, throw NotV1ProjectError.
 * 3. For each indicator found, generate the corresponding migration actions (see Section 5).
 * 4. Order actions: create directories first, then moves, then transforms, then deletes last.
 * 5. Generate warnings for edge cases (see Section 7).
 * 6. Return the plan. The plan is a pure data structure -- no side effects.
 */
function planMigration(projectPath: string): Promise<MigrationPlan>

/**
 * Execute a migration plan.
 *
 * @param plan - The migration plan from planMigration().
 * @param options - Execution options.
 * @returns Result with applied/skipped/failed actions.
 *
 * Behavior:
 * 1. If options.dryRun is true, return immediately with all actions as "applied" (no I/O).
 * 2. Create `<project>/.cbim/` directory structure.
 * 3. Execute actions in order:
 *    - 'move': copy src to dest, then delete src (unless options.noDelete).
 *    - 'delete': remove file/directory (unless options.noDelete).
 *    - 'transform': run the transform function for this action category (see Section 6).
 *    - 'create': write new file at dest with generated content.
 * 4. On action failure: record the error, continue with remaining actions (best-effort, NOT transactional).
 * 5. Return the result.
 *
 * The function does NOT throw on individual action failures -- they are captured in result.errors.
 * The function DOES throw if the plan itself is structurally invalid (should not happen with planMigration output).
 */
function applyMigration(
  plan: MigrationPlan,
  options: {
    readonly dryRun: boolean
    readonly force: boolean
    readonly noDelete: boolean
    readonly verbose: boolean
    readonly log: (message: string) => void
  }
): Promise<MigrationResult>

/**
 * Generate a human-readable summary from a migration result.
 *
 * @param result - The migration result from applyMigration().
 * @param plan - The original migration plan (for warning aggregation).
 * @returns Summary statistics for display.
 *
 * Pure function, no I/O.
 */
function summarizeMigration(result: MigrationResult, plan: MigrationPlan): MigrationSummary
```

---

## 5. Migration Rules (Action Generation)

Each v1 indicator maps to a set of migration actions. All paths below are relative to the project root.

### 5.1 Root Module: `.dna/` -> `.cbim/dna/`

| v1 Source | v2 Destination | Action |
|-----------|----------------|--------|
| `.dna/module.md` | `.cbim/dna/module.md` | move |
| `.dna/module.json` | `.cbim/dna/module.md` | transform (convert JSON+architecture.md to single module.md) |
| `.dna/contract.md` | `.cbim/dna/contract.md` | move |
| `.dna/workflows/` | `.cbim/dna/workflows/` | move (entire directory) |
| `.dna/index.md` | (none) | delete |
| `.dna/<other files>` | `.cbim/dna/<other files>` | move |

**index.md deletion rationale**: v2 generates the module index dynamically via `discoverModules()`. The static index file is obsolete.

**Legacy JSON transform**: If `.dna/module.json` exists (and `.dna/module.md` does not):
1. Read `module.json` as JSON.
2. Read `.dna/architecture.md` if it exists (body content).
3. Synthesize a `module.md` with YAML frontmatter from JSON fields + markdown body from architecture.md content.
4. Write to `.cbim/dna/module.md`.

### 5.2 Agents: `.claude/agents/<id>/<id>.md` -> `.cbim/agents/<id>.md`

**Input structure (v1)**: Each agent is a single markdown file at `.claude/agents/<id>/<id>.md`. The directory name matches the filename stem.

**Output structure (v2)**: Each agent is a single `.md` file directly under `.cbim/agents/`.

**Migration rule**: Direct copy with optional frontmatter normalization.

1. For each directory `<id>/` under `.claude/agents/`:
   a. Locate the agent file: `.claude/agents/<id>/<id>.md`. If not found, generate a warning and skip.
   b. Read the file content.
   c. If frontmatter exists, validate and normalize (see frontmatter mapping below).
   d. If no frontmatter exists, synthesize minimal frontmatter: `name: <id>`.
   e. Write the result to `.cbim/agents/<id>.md`.

2. **Frontmatter field mapping** (v1 -> v2):

| v1 field | v2 field | Handling |
|----------|----------|----------|
| (none) | `name` | Synthesize from `<id>` if absent |
| Any existing field | Same key | Pass through unchanged |

   The v1 agent files do not use structured frontmatter (they are pure markdown system prompts). If a v1 file happens to have frontmatter, all fields are preserved as-is. No fields are renamed or removed.

3. **Core agent handling**: The 4 core agents (`architect`, `hr`, `auditor`, and the assistant defined in `CLAUDE.md`) are migrated like any other agent. The assistant's identity extraction from `CLAUDE.md` is handled separately in Section 5.4.

4. **Edge cases**:
   - Directory contains no `.md` file matching the directory name: generate a warning, skip this agent.
   - Directory contains additional files beyond `<id>.md` (e.g., assets, scratch notes): generate a warning listing the extra files, migrate only `<id>.md`. Extra files are NOT copied.

### 5.3 Memory: `cbim/memory/store/` -> `.cbim/memory/`

| v1 Source | v2 Destination | Action |
|-----------|----------------|--------|
| `cbim/memory/store/short/` | `.cbim/memory/short/` | move (entire directory with all files) |
| `cbim/memory/store/medium/` | `.cbim/memory/medium/` | move (entire directory with all files) |
| `cbim/memory/store/last-session.md` | `.cbim/memory/last-session.md` | move |
| `cbim/memory/store/<other>` | `.cbim/memory/<other>` | move |

**Note**: The `distilled/` directory is new in v2. It does not exist in v1. Migration does NOT create it -- the memory engine creates it on first distillation.

### 5.4 Config: `CLAUDE.md` -> `.cbim/config.yaml` + trimmed `CLAUDE.md`

This is the most complex transformation. `CLAUDE.md` in v1 serves dual purpose:
1. **System configuration** -- role definitions, agent registry, dispatch rules, skill references, hard rules.
2. **User-facing project instructions** -- custom instructions that the user wants injected into every session.

**Extraction algorithm**:

1. Read `CLAUDE.md` as raw markdown.
2. Parse into sections by `## ` headings.
3. Classify each section:

| Section heading (exact match) | Classification | Destination |
|-------------------------------|---------------|-------------|
| `Role` | system | config.yaml |
| `Execution Roles` | system | config.yaml |
| `Workflow` | system | config.yaml |
| `Skills` | system | config.yaml |
| `Hard Rules` | system | config.yaml |
| Any heading containing "Personality" or "Communication" | system | config.yaml |
| Any heading containing "Emotional" | system | config.yaml |
| `Stance` | system | config.yaml |
| Everything else | user | remains in CLAUDE.md |

4. **Content before the first `## ` heading** (typically the `# Title` and any preamble): classified as system, goes to config.yaml under `assistant.preamble`.

5. **Generate `config.yaml`**:

```yaml
# CBIM v2 project configuration
# Migrated from CLAUDE.md on <ISO date>

version: 2

assistant:
  preamble: |
    <content before first ## heading>
  sections:
    - heading: "<section heading>"
      content: |
        <section content>
    # ... one entry per extracted system section, preserving order
```

6. **Rewrite `CLAUDE.md`**: Keep only user-classified sections. If ALL sections are classified as system (nothing remains), delete `CLAUDE.md` entirely (it would be empty). If some sections remain, rewrite the file with only those sections.

7. **Edge cases**:
   - `CLAUDE.md` does not exist: skip this transformation, no warning.
   - `CLAUDE.md` is empty: skip, no warning.
   - `CLAUDE.md` has no `## ` headings (unstructured prose): classify the entire content as user, do NOT extract to config.yaml. Generate a warning: "CLAUDE.md has no structured sections; cannot extract system configuration. Manual review recommended."
   - `CLAUDE.md` uses `# ` (h1) sub-sections instead of `## `: same logic, but match on `# ` as section delimiter as a fallback.

### 5.5 Sub-module .dna/: No Change

Source tree `.dna/` directories (e.g., `src/x/.dna/`) are **not moved**. They stay in place because they are co-located with their source code and should migrate with the code.

Action: none. Verify they exist and are valid (generate a warning if `module.md` is missing from any `.dna/` found in the source tree).

### 5.6 Framework Cleanup: `cbim/` -> Delete

| v1 Source | Action |
|-----------|--------|
| `cbim/knowledge/` | delete |
| `cbim/memory/` (excluding `store/`, which was moved in 5.3) | delete |
| `cbim/cc-template/` | delete |
| `cbim/*.py` | delete |
| `cbim/*.md` (README, etc.) | delete |
| `cbim/` directory itself (if empty after above) | delete |

**Safety**: Only delete files/directories that match known v1 framework patterns. If `cbim/` contains unexpected files/directories not matching the patterns above, generate a warning and do NOT delete them. List the unexpected items in the warning.

---

## 6. Action Execution Order

Within `applyMigration`, actions execute in this strict order:

1. **Create** `.cbim/` directory structure (`dna/`, `agents/`, `memory/`, `memory/short/`, `memory/medium/`)
2. **Move** root module files (`.dna/` -> `.cbim/dna/`)
3. **Move** memory files (`cbim/memory/store/` -> `.cbim/memory/`)
4. **Move** agents (`.claude/agents/<id>/<id>.md` -> `.cbim/agents/<id>.md`)
5. **Transform** config (`CLAUDE.md` -> `.cbim/config.yaml` + trimmed `CLAUDE.md`)
6. **Delete** `index.md`
7. **Delete** framework files (`cbim/` minus already-moved store)

This order ensures that:
- Destinations exist before moves.
- Transforms can read sources before deletes remove them.
- Deletes happen last, minimizing data loss risk if the process is interrupted.

---

## 7. Safety Boundaries

### 7.1 Target Exists

If `<project>/.cbim/` already exists:
- Without `--force`: abort immediately with exit code 3 and message: "Target .cbim/ already exists. Use --force to overwrite."
- With `--force`: remove the existing `.cbim/` directory entirely before proceeding. Log: "Removing existing .cbim/ directory (--force)."

### 7.2 Dry Run

`--dry-run` must produce **zero file system writes**. It:
1. Runs `planMigration()` to generate the plan.
2. Prints each action in the plan with its source, destination, and description.
3. Prints the summary (what would be migrated).
4. Exits with code 0 (plan is valid) or code 1 (plan generation failed).

### 7.3 Rollback Strategy

**Best-effort, not transactional.**

Rationale: A full transactional rollback (snapshot-restore) adds significant complexity for a one-time migration tool. The risk is mitigated by:
- `--dry-run` for pre-flight validation.
- `--no-delete` for cautious migration (keeps v1 sources, user can manually verify before cleaning up).
- Actions are ordered so that creates/moves happen before deletes.
- Individual action failures are captured and reported; the migration continues with remaining actions.

If the user wants full safety, the recommended workflow is:
1. Commit all changes to git.
2. Run `cbim migrate . --dry-run` to preview.
3. Run `cbim migrate .` to execute.
4. If something goes wrong: `git checkout .` to restore.

The CLI should print this recommendation when the migration starts (if the project is a git repo and has uncommitted changes, print a warning: "You have uncommitted changes. Consider committing before migration.").

### 7.4 Permission Errors

If a file cannot be read (permission denied) or a directory cannot be created:
- Record as an error in `MigrationResult.errors`.
- Continue with remaining actions.
- Print the error in the summary.

---

## 8. Output Format

### 8.1 Normal Run

```
cbim migrate v1.0 -> v2.0

Migrating: /path/to/project

[1/7] Moving root module .dna/ -> .cbim/dna/                    OK
[2/7] Deleting .dna/index.md                                     OK
[3/7] Copying agents (3 found)                                    OK
[4/7] Moving memory store -> .cbim/memory/                       OK
[5/7] Extracting config from CLAUDE.md -> .cbim/config.yaml      OK
[6/7] Cleaning up cbim/ framework files                          OK
[7/7] Validating migrated module tree                            OK

Migration complete.
  Modules migrated:  5 (1 root + 4 sub-modules)
  Agents migrated:   3
  Memory entries:    42 (short: 38, medium: 4)
  Config extracted:  yes
  Files deleted:     12

Warnings:
  - cbim/custom-script.sh was not recognized as a framework file and was kept in place.

Next steps:
  1. Install the CBIM v2 VS Code extension
  2. Open this project in VS Code and verify the CBIM sidebar
```

### 8.2 Dry Run

```
cbim migrate v1.0 -> v2.0 (dry run)

Analyzing: /path/to/project

Migration plan:
  [root-module] Move .dna/module.md -> .cbim/dna/module.md
  [root-module] Move .dna/contract.md -> .cbim/dna/contract.md
  [root-module] Move .dna/workflows/ -> .cbim/dna/workflows/
  [root-module] Delete .dna/index.md
  [agents]      Copy .claude/agents/architect/architect.md -> .cbim/agents/architect.md
  [agents]      Copy .claude/agents/programmer/programmer.md -> .cbim/agents/programmer.md
  [agents]      Copy .claude/agents/hr/hr.md -> .cbim/agents/hr.md
  [memory]      Move cbim/memory/store/short/ -> .cbim/memory/short/ (38 files)
  [memory]      Move cbim/memory/store/medium/ -> .cbim/memory/medium/ (4 files)
  [config]      Transform CLAUDE.md -> .cbim/config.yaml + trimmed CLAUDE.md
  [cleanup]     Delete cbim/knowledge/
  [cleanup]     Delete cbim/memory/ (excluding already-moved store)
  [cleanup]     Delete cbim/cc-template/
  [cleanup]     Delete cbim/*.py, cbim/*.md

Summary (would apply):
  Modules:  5    Agents: 3    Memory: 42    Config: yes    Deletes: 12

No files were modified (dry run).
```

### 8.3 Error Output (stderr)

```
Error: Migration failed for 1 action(s):

  [agents] Copy .claude/agents/broken/broken.md -> .cbim/agents/broken.md
           Error: Permission denied reading .claude/agents/broken/broken.md

Migration partially completed. 6 of 7 actions succeeded.
Review .cbim/ and consider manual cleanup.
```

---

## 9. Post-Migration Validation

After applying all actions (and before printing the summary), the CLI performs a validation step:

1. Call `discoverModules(<project-path>)` from `@cbim/engine/knowledge`.
2. Verify the returned module tree is non-empty (at least the root module should be found).
3. If validation fails, add a warning: "Post-migration validation: module tree is empty. The .cbim/dna/module.md may be malformed."
4. If validation succeeds, report the count in the summary.

This is a **non-blocking** validation -- failure adds a warning, does not change the exit code from 0 to 1.

---

## 10. Export Surface

### From `@cbim/engine/migration`:

```typescript
// Types
export type { MigrationAction, MigrationPlan, MigrationResult, MigrationActionError, MigrationSummary }

// Errors
export { InvalidProjectPathError, NotV1ProjectError, TargetExistsError, TransformError }

// Functions
export { planMigration, applyMigration, summarizeMigration }
```

### From `@cbim/cli` (internal, not exported as library):

The CLI command registration in `packages/cli/src/commands/migrate.ts` is internal. It wires CAC command parsing to engine functions. Not a public API.
