# @cbim/engine/knowledge -- Implementation Contract

> Scope: `packages/engine/src/knowledge/`
> Consumer: `@cbim/engine/tools` (SDK tool thin shell), `@cbim/cli` (direct import), `@cbim/vscode-extension` (via engine API)
> Status: Phase 0 implementation contract

---

## 1. Core Types

All types are exported from `@cbim/engine/knowledge`. All returned objects must be `Readonly<T>` (deep immutability enforced at the type level; runtime freeze is the implementer's discretion).

```typescript
/**
 * Frontmatter fields parsed from the YAML block of module.md.
 *
 * Required fields: `name`, `owner`.
 * All other fields are optional and have documented defaults.
 */
interface ModuleFrontmatter {
  /** kebab-case module name. Required. */
  readonly name: string
  /** Responsible agent id. Required. */
  readonly owner: string
  /** Brief module description. Default: "" */
  readonly description: string
  /** Keywords for search/filtering. Default: [] */
  readonly keywords: readonly string[]
  /** Relative paths (from project root) of modules this module depends on. Default: [] */
  readonly dependencies: readonly string[]
  /** Additional directories to include in context. Default: [] */
  readonly includeDirs: readonly string[]
}

/**
 * Recognized sections in the module.md markdown body.
 *
 * Each section is the raw markdown string content (excluding the heading itself).
 * If a section is absent in the source file, its value is `undefined`.
 */
interface ModuleSections {
  /** One-sentence module positioning. */
  readonly positioning?: string
  /** Mermaid diagram (classDiagram for leaf modules, relationship diagram for parent modules). */
  readonly diagram?: string
  /** Design rationale invisible in code. */
  readonly keyDecisions?: string
  /** Any section not matching the above three, keyed by heading text. */
  readonly [sectionName: string]: string | undefined
}

/**
 * Frontmatter of a workflow file (workflow.md).
 * Used for eager loading -- only the metadata is parsed during module discovery.
 * Full workflow content is loaded separately via loadWorkflow() (lazy load).
 *
 * This type is structurally symmetric with SkillFrontmatter (defined in tools contract)
 * -- same fields, same purpose. This symmetry is the capability-business symmetry
 * expressed at the type level: skills belong to agents, workflows belong to modules.
 */
interface WorkflowFrontmatter {
  /** kebab-case workflow name. */
  readonly name: string
  /** Keywords for matching / triggering. */
  readonly keywords: readonly string[]
  /** One-sentence summary of the workflow. */
  readonly description: string
  /** Optional trigger conditions. */
  readonly triggers?: readonly { readonly on: string; readonly value?: string; readonly pattern?: string }[]
}

/**
 * A fully loaded workflow (frontmatter + content body).
 * Returned by loadWorkflow() -- the lazy-load counterpart to WorkflowFrontmatter.
 */
interface Workflow {
  /** Parsed frontmatter metadata. */
  readonly frontmatter: WorkflowFrontmatter
  /** The markdown body content (everything after the frontmatter block). */
  readonly content: string
}

/**
 * A fully loaded module with parsed frontmatter, body sections, and optional companion files.
 */
interface Module {
  /** Relative path from project root to the module directory (not to .dna/). "." for root module. */
  readonly path: string
  /** Parsed frontmatter metadata. */
  readonly frontmatter: ModuleFrontmatter
  /** Parsed body sections. */
  readonly sections: ModuleSections
  /** Raw content of contract.md, or undefined if absent. */
  readonly contract?: string
  /**
   * Workflow frontmatters (eager load -- name, keywords, description, triggers only).
   * Full workflow content is loaded separately via loadWorkflow() (lazy load).
   * This follows the eager frontmatter / lazy content pattern symmetric with skill loading.
   */
  readonly workflows: readonly WorkflowFrontmatter[]
}

/**
 * A node in the module tree. Represents a module's position in the filesystem hierarchy.
 *
 * The tree is constructed by filesystem nesting of .dna/ directories.
 * A node with `children.length === 0` is a leaf module.
 */
interface ModuleNode {
  /** Relative path from project root to the module directory. "." for root module, ".cbim/dna" for the cbim root. */
  readonly path: string
  /** Module name from frontmatter. */
  readonly name: string
  /** Direct child modules in the tree. */
  readonly children: readonly ModuleNode[]
  /** True if this node has no child modules. */
  readonly isLeaf: boolean
  /** Subset of frontmatter exposed at tree level for filtering/display without full load. */
  readonly metadata: {
    readonly owner: string
    readonly description: string
    readonly keywords: readonly string[]
  }
}

/**
 * A contextual knowledge snapshot centered on a focus module.
 *
 * Used to assemble agent context: provides the focus module's full content
 * plus enough surrounding structure to understand its place in the system.
 *
 * Every Module in the snapshot (focus, ancestors, descendants, siblings, related)
 * carries `workflows: WorkflowFrontmatter[]` (eager frontmatter only).
 * This lets the agent see which workflows are available in the focus scope
 * without loading all workflow bodies. Use `loadWorkflow()` to lazy-load
 * specific workflow content when needed.
 */
interface Snapshot {
  /** The focus module, fully loaded. */
  readonly focus: Module
  /** Ancestor chain from immediate parent to root (ordered: [parent, grandparent, ..., root]). Loaded with frontmatter + sections. */
  readonly ancestors: readonly Module[]
  /** Direct child modules of the focus, fully loaded. */
  readonly descendants: readonly Module[]
  /** Sibling modules (same parent, excluding focus), fully loaded. */
  readonly siblings: readonly Module[]
  /** Modules referenced by `focus.frontmatter.dependencies`, fully loaded. Modules that fail to resolve are omitted with a warning in `unresolvedDependencies`. */
  readonly related: readonly Module[]
  /** Dependency paths declared in focus.frontmatter.dependencies that could not be resolved to a module. */
  readonly unresolvedDependencies: readonly string[]
}
```

---

## 2. Error Types

All errors extend a common base. Implementer should use `class extends Error` with `name` set to the error name below.

```typescript
/**
 * Base error for all knowledge engine errors.
 * All errors carry the module path that triggered the error.
 */
interface KnowledgeError extends Error {
  /** The path that triggered the error (relative to project root). */
  readonly modulePath: string
}

/**
 * Thrown when a path expected to be a module does not exist on disk,
 * or exists but has no .dna/module.md file.
 */
interface ModuleNotFoundError extends KnowledgeError {
  readonly name: 'ModuleNotFoundError'
}

/**
 * Thrown when module.md exists but its YAML frontmatter cannot be parsed.
 * Includes the underlying parse error message.
 */
interface FrontmatterParseError extends KnowledgeError {
  readonly name: 'FrontmatterParseError'
  /** The raw YAML block that failed to parse. */
  readonly rawYaml: string
  /** The underlying parser error message. */
  readonly parseMessage: string
}

/**
 * Thrown when frontmatter parses successfully but required fields are missing or invalid.
 * Required fields: `name` (non-empty string), `owner` (non-empty string).
 */
interface InvalidModuleError extends KnowledgeError {
  readonly name: 'InvalidModuleError'
  /** List of field-level validation failures. */
  readonly violations: readonly string[]
}

/**
 * Thrown when the project root path does not exist or is not a directory.
 */
interface InvalidProjectRootError extends Error {
  readonly name: 'InvalidProjectRootError'
  readonly projectRoot: string
}

/**
 * Thrown when a workflow is not found in a module's .dna/workflows/ directory.
 */
interface WorkflowNotFoundError extends KnowledgeError {
  readonly name: 'WorkflowNotFoundError'
  /** The workflow name that was not found. */
  readonly workflowName: string
}
```

**Error throw conditions (exhaustive):**

| Function | Error | Condition |
|----------|-------|-----------|
| `discoverModules` | `InvalidProjectRootError` | `projectRoot` does not exist or is not a directory |
| `loadModule` | `ModuleNotFoundError` | Path does not exist, or `.dna/module.md` not found at expected location |
| `loadModule` | `FrontmatterParseError` | `module.md` exists but YAML frontmatter block is malformed |
| `loadModule` | `InvalidModuleError` | Frontmatter parses but `name` or `owner` is missing/empty |
| `buildSnapshot` | `ModuleNotFoundError` | `focusModulePath` does not resolve to a module in the tree |
| `buildSnapshot` | (inherits `loadModule` errors) | Any module in the snapshot fails to load |
| `loadWorkflow` | `ModuleNotFoundError` | `modulePath` does not exist or has no `.dna/` |
| `loadWorkflow` | `WorkflowNotFoundError` | Workflow directory or `workflow.md` not found under `.dna/workflows/<workflowName>/` |
| `loadWorkflow` | `FrontmatterParseError` | `workflow.md` exists but YAML frontmatter is malformed |

---

## 3. API Functions

All functions are **async** (return `Promise`). Rationale: file system I/O is inherently async in Node.js; forcing sync would require `fs.*Sync` calls that block the event loop and harm extension responsiveness.

```typescript
/**
 * Scan the project tree and build the module tree.
 *
 * @param projectRoot - Absolute path to the project root directory.
 * @returns The module tree as a flat array of root-level nodes (typically 0-2 roots).
 * @throws InvalidProjectRootError if projectRoot is not a valid directory.
 *
 * Behavior:
 * 1. Check if `<projectRoot>/.cbim/dna/module.md` exists. If yes, create the root ModuleNode for it.
 * 2. Recursively walk the project tree starting from `projectRoot`, looking for directories containing `.dna/module.md`.
 * 3. Skip these directories entirely during traversal (never descend into them):
 *    - `node_modules`
 *    - `dist`
 *    - `build`
 *    - `out`
 *    - `.git`
 *    - `.cbim` (already handled as root module in step 1)
 *    - Any directory starting with `.` EXCEPT `.dna` itself
 * 4. When a `.dna/module.md` is found at path P:
 *    - Parse frontmatter to extract name, owner, description, keywords (lightweight; does NOT parse body sections).
 *    - If frontmatter parse fails, log a warning and skip this module (do not throw; discovery is best-effort).
 *    - Determine parent: the nearest ancestor directory that also has `.dna/module.md`, or the root module if applicable.
 * 5. Assemble into a tree based on filesystem nesting. Modules with no discovered parent become root-level nodes.
 * 6. Return the root-level nodes array. If no modules are discovered, return [].
 *
 * Performance note: This function performs a full filesystem walk. Consumers should cache the result
 * and rebuild only when the file tree changes (cache invalidation is the consumer's responsibility).
 */
function discoverModules(projectRoot: string): Promise<readonly ModuleNode[]>

/**
 * Load and parse a single module from disk.
 *
 * @param modulePath - Absolute path to the module directory (the directory containing .dna/).
 * @returns The fully parsed Module object.
 * @throws ModuleNotFoundError if the path does not exist or contains no .dna/module.md.
 * @throws FrontmatterParseError if YAML frontmatter is malformed.
 * @throws InvalidModuleError if required frontmatter fields (name, owner) are missing.
 *
 * Behavior:
 * 1. Verify `<modulePath>/.dna/module.md` exists on disk.
 * 2. Read file content (UTF-8).
 * 3. Extract YAML frontmatter block (between opening `---` and closing `---`).
 *    - If no frontmatter delimiters found, throw FrontmatterParseError.
 * 4. Parse YAML frontmatter. Required fields: name (string, non-empty), owner (string, non-empty).
 *    Optional fields with defaults: description (""), keywords ([]), dependencies ([]), includeDirs ([]).
 *    - Unknown fields in frontmatter are silently ignored (forward compatibility).
 * 5. Parse markdown body into sections:
 *    - Split by `## ` headings.
 *    - Map heading text to ModuleSections fields:
 *      "Positioning" -> positioning, "Class Diagram" | "Component Diagram" | "Sub-module Relationship Diagram" -> diagram,
 *      "Key Decisions" -> keyDecisions. All others -> indexed by heading text.
 *    - Section content = everything between this heading and the next `## ` heading (or EOF), trimmed.
 * 6. Check for optional companion files:
 *    - `<modulePath>/.dna/contract.md` -> read as raw string if exists.
 *    - `<modulePath>/.dna/workflows/` -> scan subdirectories that contain `workflow.md`.
 *      For each workflow found, parse ONLY the YAML frontmatter (name, keywords, description, triggers)
 *      to produce a WorkflowFrontmatter object. Do NOT parse the markdown body (content is lazy-loaded
 *      via loadWorkflow()). If a workflow's frontmatter fails to parse, log a warning and skip it
 *      (best-effort, same as discoverModules behavior for broken modules).
 * 7. Construct and return the Module object (with workflows: WorkflowFrontmatter[]).
 *
 * Encoding: All files read as UTF-8. Non-UTF-8 content results in replacement characters (no error).
 */
function loadModule(modulePath: string): Promise<Module>

/**
 * Build a contextual snapshot centered on a focus module.
 *
 * @param focusModulePath - Absolute path to the focus module directory.
 * @param tree - The module tree from discoverModules(). Required because snapshot needs tree context.
 * @returns A Snapshot containing the focus module and its surrounding context.
 * @throws ModuleNotFoundError if focusModulePath is not found in the tree.
 *
 * Behavior:
 * 1. Locate focusModulePath in the provided tree. If not found, throw ModuleNotFoundError.
 * 2. Load the focus module via loadModule().
 * 3. Walk up the tree to collect ancestors: [parent, grandparent, ..., root]. Load each via loadModule().
 * 4. Collect direct children of the focus node. Load each via loadModule().
 * 5. Collect siblings: other children of the focus's parent (excluding focus itself). Load each via loadModule().
 * 6. Resolve dependencies: for each path in focus.frontmatter.dependencies, attempt to find the corresponding
 *    node in the tree. If found, load via loadModule() and add to `related`. If not found, add path to
 *    `unresolvedDependencies`.
 *    - Dependency paths are relative to project root (e.g., "src/types").
 *    - Deduplication: if a dependency is already in ancestors/descendants/siblings, do NOT duplicate it in related.
 * 7. If any loadModule() call fails for a non-focus module (ancestor/child/sibling/related),
 *    log a warning and omit that module from the snapshot (do not throw; snapshot assembly is best-effort
 *    for surrounding context, but focus module failure IS fatal).
 * 8. Return the assembled Snapshot.
 */
function buildSnapshot(
  focusModulePath: string,
  tree: readonly ModuleNode[]
): Promise<Snapshot>

/**
 * Resolve a relative module path to an absolute path given the project root.
 *
 * @param relativePath - Relative path from project root (e.g., "src/combat", ".", ".cbim/dna").
 * @param projectRoot - Absolute path to the project root.
 * @returns Absolute path to the module directory.
 *
 * Behavior:
 * - Joins projectRoot and relativePath using platform path separator.
 * - Normalizes the result (resolves `..`, `.`, duplicate separators).
 * - Does NOT verify existence on disk (pure path computation).
 *
 * This is a synchronous utility -- no I/O.
 */
function resolveModulePath(relativePath: string, projectRoot: string): string

/**
 * Parse a raw module.md string into frontmatter + sections without touching the filesystem.
 *
 * @param raw - The raw content of a module.md file.
 * @returns Parsed frontmatter and sections.
 * @throws FrontmatterParseError if YAML block is malformed.
 * @throws InvalidModuleError if required fields are missing.
 *
 * This is a pure function (no I/O). Useful for testing and for tools that
 * already have file content in memory.
 */
function parseModuleMd(raw: string): {
  frontmatter: ModuleFrontmatter
  sections: ModuleSections
}

/**
 * Load a workflow's full content (frontmatter + markdown body) from a module.
 *
 * This is the lazy-load counterpart to the `workflows: WorkflowFrontmatter[]`
 * field on Module (which provides eager frontmatter only). Together they
 * implement the eager frontmatter / lazy content pattern -- symmetric with
 * skill loading in the capability layer.
 *
 * @param modulePath - Absolute path to the module directory.
 * @param workflowName - Workflow name (subdirectory name under .dna/workflows/).
 * @returns The fully loaded Workflow (frontmatter + content).
 * @throws ModuleNotFoundError if modulePath does not exist or has no .dna/.
 * @throws WorkflowNotFoundError if the workflow does not exist in this module.
 * @throws FrontmatterParseError if workflow.md frontmatter is malformed.
 *
 * Behavior:
 * 1. Verify `<modulePath>/.dna/workflows/<workflowName>/workflow.md` exists.
 * 2. Read workflow.md (UTF-8).
 * 3. Parse YAML frontmatter: required fields are `name` (string), `keywords` (string[]),
 *    `description` (string). Optional: `triggers` (array of trigger objects).
 * 4. Extract markdown body (everything after the frontmatter block).
 * 5. Return Workflow { frontmatter, content }.
 */
function loadWorkflow(
  modulePath: string,
  workflowName: string
): Promise<Workflow>
```

---

## 4. YAML Frontmatter Parsing Strategy

**Decision: Use `js-yaml` (the `yaml` npm package) for YAML parsing.**

Rationale:
- v1 used a hand-written YAML parser (`_parse_yaml_block`) that only supported scalars and simple lists. This was adequate for v1's scope but is fragile and does not handle edge cases (quoted strings with colons, multiline values, nested objects).
- `js-yaml` / `yaml` is the standard YAML parser in the Node.js ecosystem, well-maintained, zero native dependencies, ~50KB bundled.
- The engine already has a bundler (tsup), so the dependency cost is minimal.
- Type safety: `js-yaml` returns `unknown`; the implementer must validate the parsed object against `ModuleFrontmatter` shape and throw `InvalidModuleError` for violations.

**Parsing rules:**
1. Extract the block between the first `---\n` and the next `\n---` (standard frontmatter delimiters).
2. Pass the extracted block to `yaml.load()` with `schema: yaml.JSON_SCHEMA` (no custom types, no `!!` tags -- YAML as a data format only).
3. Validate the result is a plain object. If not, throw `FrontmatterParseError`.
4. Validate required fields (`name`: non-empty string, `owner`: non-empty string). If missing, throw `InvalidModuleError` with specific violations.
5. Coerce optional fields to defaults: `description` -> `""`, `keywords` -> `[]`, `dependencies` -> `[]`, `includeDirs` -> `[]`.
6. Unknown fields are silently ignored.

---

## 5. Caching Strategy

**Decision: No built-in cache. The engine is stateless.**

Rationale:
- The engine is a library consumed by multiple hosts (extension, CLI, tools). Each host has different lifecycle and invalidation needs.
- The VS Code extension should cache the module tree on activation and rebuild on file system watch events (`vscode.workspace.createFileSystemWatcher('**/.dna/module.md')`).
- The CLI does not need caching -- it runs once and exits.
- Adding cache to the engine would create hidden shared state between consumers, violating single-responsibility.

**Implication for consumers:**
- `discoverModules()` performs a full filesystem walk on every call. Consumers MUST cache the result if they need repeated access.
- `loadModule()` reads from disk on every call. Consumers MAY cache individual Module objects and invalidate on file change.

---

## 6. Root Module Convention

The **root module** in v2 lives at `<projectRoot>/.cbim/dna/`, NOT at `<projectRoot>/.dna/`.

- `discoverModules` checks `<projectRoot>/.cbim/dna/module.md` as the root module entry point.
- If `.cbim/dna/` does not exist or has no `module.md`, there is no root module. This is a **legal state** (a project may not have been initialized with CBIM yet). `discoverModules` returns only the sub-modules found in the source tree.
- The root module's `ModuleNode.path` is `.cbim/dna`.
- Sub-modules (e.g., `src/combat/.dna/`) are parented to the root module if no intermediate module exists between them and the project root.

---

## 7. Module Identity and Path Convention

- A module's **identity** is its relative path from the project root to the directory containing `.dna/`.
  - Example: `src/combat` (not `src/combat/.dna/`).
  - Root module: `.cbim/dna` (the `.cbim/dna/` directory itself is the "module directory" because it contains `module.md` directly, unlike sub-modules where `module.md` is at `<dir>/.dna/module.md`).
- The `Module.path` and `ModuleNode.path` fields use forward slashes (`/`) regardless of platform. Implementer must normalize platform separators to `/` in all returned paths.
- Dependency paths in `frontmatter.dependencies` are relative to project root, using forward slashes.

**Root module structural difference:**
- Root module: `<projectRoot>/.cbim/dna/module.md` (module.md is directly inside the dna directory)
- Sub-module: `<projectRoot>/src/x/.dna/module.md` (module.md is inside `.dna/` which is inside the module directory)

The implementer must handle this asymmetry in `discoverModules` and `loadModule`. When `loadModule` receives a path ending in `.cbim/dna`, it looks for `module.md` directly inside that path (not `.dna/module.md`).

---

## 8. Export Surface

All types and functions defined in this contract are exported from `@cbim/engine/knowledge` (the sub-path export). The barrel file at `packages/engine/src/knowledge/index.ts` is the single public entry point.

```typescript
// packages/engine/src/knowledge/index.ts -- public API surface

// Types
export type { ModuleFrontmatter, ModuleSections, Module, ModuleNode, Snapshot }
// Capability-business symmetry types
export type { WorkflowFrontmatter, Workflow }

// Errors
export { ModuleNotFoundError, FrontmatterParseError, InvalidModuleError, InvalidProjectRootError, WorkflowNotFoundError }

// Functions
export { discoverModules, loadModule, buildSnapshot, resolveModulePath, parseModuleMd, loadWorkflow }
```

Everything not listed above is **internal** to the knowledge sub-module and must not be imported by external consumers.
