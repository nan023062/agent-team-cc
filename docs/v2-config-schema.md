# .cbim/config.yaml -- Schema Specification

> Status: Phase 0 design
> Location: `<projectRoot>/.cbim/config.yaml`
> Consumers: `@cbim/vscode-extension` (primary), `@cbim/engine` (defaults), `@cbim/cli` (validation)

---

## Design Principles

1. **Conservative** -- only cross-component configuration lives here. Package-internal settings stay in their own scope.
2. **All-optional** -- every field has a sensible default. A valid `config.yaml` can be an empty file or `{}`.
3. **Flat over nested** -- prefer shallow nesting. Two levels max for any setting group.
4. **Schema-validated** -- engine exposes a `loadConfig()` that parses, validates, and fills defaults. Consumers never parse raw YAML themselves.

---

## Schema (TypeScript Interface)

```typescript
/**
 * Top-level config shape.
 * All fields are optional with documented defaults.
 */
interface CbimConfig {
  /** Schema version. Must be 2 for v2 projects. Default: 2 */
  version?: 2

  /** Framework-level defaults. */
  defaults?: {
    /** Default model identifier for agent queries. Default: "claude-sonnet-4-20250514" */
    model?: string
    /** Maximum tokens for model responses. Default: 16384 */
    maxTokens?: number
  }

  /** Logging and telemetry. */
  observability?: {
    /** Log level. Default: "info" */
    logLevel?: 'debug' | 'info' | 'warn' | 'error'
    /** Whether to send anonymous usage telemetry. Default: false */
    telemetry?: boolean
  }

  /** Agent configuration. */
  agents?: {
    /**
     * Directory containing agent definition files, relative to project root.
     * Default: ".cbim/agents"
     */
    dir?: string
  }

  /** Memory backend configuration. */
  memory?: {
    /**
     * Storage backend type.
     * - "file": local filesystem under .cbim/memory/ (default)
     * - "chroma": ChromaDB vector store (future, requires separate setup)
     * Default: "file"
     */
    backend?: 'file' | 'chroma'
    /**
     * Backend-specific options. Shape depends on `backend` value.
     * For "file": no options needed (uses .cbim/memory/ convention).
     * For "chroma": { url: string, collection?: string }
     * Default: {}
     */
    options?: Record<string, unknown>
  }

  /** Snapshot construction parameters. */
  snapshot?: {
    /**
     * Maximum context token budget for a single snapshot.
     * The snapshot builder will truncate/prioritize content to fit within this limit.
     * Default: 32000
     */
    maxContextTokens?: number
    /**
     * Default focus scope when no explicit focus is provided.
     * - "root": root module only
     * - "active-file": derive focus from the currently active editor file
     * Default: "active-file"
     */
    defaultFocus?: 'root' | 'active-file'
    /**
     * How many ancestor levels to include in the snapshot.
     * -1 means all ancestors up to root.
     * Default: -1
     */
    ancestorDepth?: number
  }

  /** Custom workflow paths (user-defined automation). */
  workflows?: {
    /**
     * Additional directories to scan for workflow definitions,
     * relative to project root. These are searched IN ADDITION to
     * the standard .dna/workflows/ locations inside each module.
     * Default: []
     */
    additionalDirs?: string[]
  }
}
```

---

## YAML Example (Maximal)

```yaml
version: 2

defaults:
  model: claude-sonnet-4-20250514
  maxTokens: 16384

observability:
  logLevel: info
  telemetry: false

agents:
  dir: .cbim/agents

memory:
  backend: file
  options: {}

snapshot:
  maxContextTokens: 32000
  defaultFocus: active-file
  ancestorDepth: -1

workflows:
  additionalDirs: []
```

---

## YAML Example (Minimal -- empty is valid)

```yaml
# All defaults apply. This file can even be omitted entirely.
```

---

## Defaults Table

| Path | Default | Rationale |
|------|---------|-----------|
| `version` | `2` | Schema evolution marker |
| `defaults.model` | `"claude-sonnet-4-20250514"` | Current best balance of cost/capability |
| `defaults.maxTokens` | `16384` | Sufficient for most code tasks without excessive cost |
| `observability.logLevel` | `"info"` | Standard production default |
| `observability.telemetry` | `false` | Opt-in only; privacy-first |
| `agents.dir` | `".cbim/agents"` | Convention from v2-plan Section 5 |
| `memory.backend` | `"file"` | Zero-dependency default; works out of the box |
| `memory.options` | `{}` | No options needed for file backend |
| `snapshot.maxContextTokens` | `32000` | ~50% of Claude Sonnet context, leaving room for conversation |
| `snapshot.defaultFocus` | `"active-file"` | Most natural IDE behavior |
| `snapshot.ancestorDepth` | `-1` | Full lineage by default; user can constrain for large trees |
| `workflows.additionalDirs` | `[]` | No extra dirs unless user configures |

---

## Engine API

```typescript
/**
 * Load and validate .cbim/config.yaml from a project root.
 *
 * @param projectRoot - Absolute path to the project root.
 * @returns Fully resolved config with all defaults filled in.
 *
 * Behavior:
 * 1. Check if <projectRoot>/.cbim/config.yaml exists.
 *    - If not, return a config object with all defaults.
 * 2. Read and parse YAML.
 * 3. Validate against schema (type checks, enum membership).
 *    - Unknown top-level keys: warn and ignore (forward compatibility).
 *    - Invalid values: throw ConfigValidationError with field path and reason.
 * 4. Merge parsed values over defaults (shallow merge per section).
 * 5. Return the resolved CbimConfig.
 */
function loadConfig(projectRoot: string): Promise<CbimConfig>

/**
 * Thrown when config.yaml exists but contains invalid values.
 */
interface ConfigValidationError extends Error {
  readonly name: 'ConfigValidationError'
  readonly violations: readonly { field: string; reason: string }[]
}
```

`loadConfig` lives in `@cbim/engine` at the top level (not inside knowledge/memory/dispatch), because config is cross-cutting. Exported from `@cbim/engine/config`.

---

## What is NOT in config.yaml

These are **excluded by design** (single-component internal concerns):

| Setting | Belongs to | Why not in config.yaml |
|---------|-----------|----------------------|
| VS Code keybindings | extension `package.json` | VS Code-native contribution point |
| Webview theme | ui package | UI-internal preference |
| tsup/vite build options | per-package config | Build tooling, not runtime |
| Agent system prompt content | `.cbim/agents/<id>.md` | Per-agent, not project-level |
| Module frontmatter schema | engine/knowledge contract | Implementation detail of knowledge engine |
| Dispatch concurrency limits | engine/dispatch | Internal tuning, not user-facing in MVP |

---

## Migration: CLAUDE.md -> config.yaml

The migrate CLI (Section 5.4 of cli/contract.md) extracts system sections from CLAUDE.md into config.yaml. The extracted content goes under an `assistant` key:

```yaml
# Migrated sections from CLAUDE.md
assistant:
  preamble: |
    <content before first ## heading>
  sections:
    - heading: "Role"
      content: |
        <section content>
```

The `assistant` key is a **migration artifact** -- it preserves the v1 CLAUDE.md system prompt structure verbatim. In steady-state v2, users may restructure this content into agent files. The `assistant` key is not part of the core schema above but is a valid extension key (unknown top-level keys are preserved, not rejected).
