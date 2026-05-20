import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import type {
  MigrationAction,
  MigrationPlan,
  MigrationResult,
  MigrationSummary,
  MigrationActionError,
} from './types.js'
import { InvalidProjectPathError, NotV1ProjectError, TargetExistsError } from './errors.js'
import { parseClaudeMd } from './claude-parser.js'

// ---------------------------------------------------------------------------
// planMigration
// ---------------------------------------------------------------------------

export async function planMigration(projectPath: string): Promise<MigrationPlan> {
  // 1. Verify path exists and is a directory
  try {
    const s = await fs.stat(projectPath)
    if (!s.isDirectory()) throw new InvalidProjectPathError(projectPath)
  } catch (e) {
    if (e instanceof InvalidProjectPathError) throw e
    throw new InvalidProjectPathError(projectPath)
  }

  // 2. Check v1 indicators
  const indicators = {
    dnaModuleMd: path.join(projectPath, '.dna', 'module.md'),
    dnaModuleJson: path.join(projectPath, '.dna', 'module.json'),
    claudeAgentsDir: path.join(projectPath, '.claude', 'agents'),
    cbimMemoryStore: path.join(projectPath, 'cbim', 'memory', 'store'),
    claudeMd: path.join(projectPath, 'CLAUDE.md'),
  }

  const foundIndicators: string[] = []
  for (const [, absPath] of Object.entries(indicators)) {
    if (await pathExists(absPath)) foundIndicators.push(absPath)
  }

  if (foundIndicators.length === 0) {
    throw new NotV1ProjectError(projectPath, Object.values(indicators))
  }

  const actions: MigrationAction[] = []
  const warnings: string[] = []

  // 3. Generate actions per indicator

  // 5.1 Root .dna/ -> .cbim/dna/
  await planRootModule(projectPath, actions, warnings)

  // 5.2 Agents: .claude/agents/ -> .cbim/agents/
  await planAgents(projectPath, actions, warnings)

  // 5.3 Memory: cbim/memory/store/ -> .cbim/memory/
  await planMemory(projectPath, actions)

  // 5.4 Config: CLAUDE.md -> .cbim/config.yaml
  await planConfig(projectPath, actions, warnings)

  // 5.5 Sub-module .dna/: validate (no action, just warnings)
  await validateSubModules(projectPath, warnings)

  // 5.6 Framework cleanup: cbim/
  await planFrameworkCleanup(projectPath, actions, warnings)

  // 4. Order: create first, then move, then transform, then delete
  const ordered = orderActions(actions)

  return {
    projectPath,
    actions: ordered,
    warnings,
    isV1Project: true,
  }
}

// ---------------------------------------------------------------------------
// applyMigration
// ---------------------------------------------------------------------------

export async function applyMigration(
  plan: MigrationPlan,
  options: {
    readonly dryRun: boolean
    readonly force: boolean
    readonly noDelete: boolean
    readonly verbose: boolean
    readonly log: (message: string) => void
  },
): Promise<MigrationResult> {
  const { dryRun, force, noDelete, verbose, log } = options

  // 1. Dry run: return all actions as applied
  if (dryRun) {
    return {
      success: true,
      applied: plan.actions,
      skipped: [],
      errors: [],
    }
  }

  const cbimDir = path.join(plan.projectPath, '.cbim')

  // 7.1 Check for existing .cbim/
  if (await pathExists(cbimDir)) {
    if (!force) {
      throw new TargetExistsError(cbimDir)
    }
    log('Removing existing .cbim/ directory (--force).')
    await fs.rm(cbimDir, { recursive: true, force: true })
  }

  // 2. Create .cbim/ directory structure
  const dirsToCreate = [
    cbimDir,
    path.join(cbimDir, 'dna'),
    path.join(cbimDir, 'agents'),
    path.join(cbimDir, 'memory'),
    path.join(cbimDir, 'memory', 'short'),
    path.join(cbimDir, 'memory', 'medium'),
  ]
  for (const dir of dirsToCreate) {
    await fs.mkdir(dir, { recursive: true })
  }

  // 3. Execute actions in order
  const applied: MigrationAction[] = []
  const skipped: MigrationAction[] = []
  const errors: MigrationActionError[] = []

  for (const action of plan.actions) {
    try {
      const result = await executeAction(action, plan.projectPath, noDelete, verbose, log)
      if (result === 'skipped') {
        skipped.push(action)
      } else {
        applied.push(action)
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : String(e)
      errors.push({ action, error: errMsg })
      if (verbose) log(`  ERROR: ${errMsg}`)
    }
  }

  return {
    success: errors.length === 0,
    applied,
    skipped,
    errors,
  }
}

// ---------------------------------------------------------------------------
// summarizeMigration
// ---------------------------------------------------------------------------

export function summarizeMigration(result: MigrationResult, plan: MigrationPlan): MigrationSummary {
  const applied = result.applied

  const modulesMigrated = applied.filter(
    a => a.category === 'root-module' && (a.type === 'move' || a.type === 'transform'),
  ).length

  const agentsMigrated = applied.filter(
    a => a.category === 'agents' && (a.type === 'move' || a.type === 'create'),
  ).length

  const memoryMoved = applied.filter(
    a => a.category === 'memory' && a.type === 'move',
  ).length

  const configExtracted = applied.some(
    a => a.category === 'config',
  )

  const filesDeleted = applied.filter(a => a.type === 'delete').length

  return {
    modulesmigrated: modulesMigrated,
    agentsMigrated,
    memoryEntriesMigrated: memoryMoved,
    configExtracted,
    filesDeleted,
    warnings: plan.warnings,
    errors: result.errors.map(e => `${e.action.description}: ${e.error}`),
  }
}

// ---------------------------------------------------------------------------
// Internal planning helpers
// ---------------------------------------------------------------------------

async function planRootModule(
  projectPath: string,
  actions: MigrationAction[],
  warnings: string[],
): Promise<void> {
  const dnaDir = path.join(projectPath, '.dna')
  if (!await pathExists(dnaDir)) return

  const moduleMd = path.join(dnaDir, 'module.md')
  const moduleJson = path.join(dnaDir, 'module.json')
  const contractMd = path.join(dnaDir, 'contract.md')
  const indexMd = path.join(dnaDir, 'index.md')
  const workflowsDir = path.join(dnaDir, 'workflows')

  if (await pathExists(moduleMd)) {
    actions.push({
      type: 'move',
      src: rel(projectPath, moduleMd),
      dest: '.cbim/dna/module.md',
      description: 'Move .dna/module.md -> .cbim/dna/module.md',
      category: 'root-module',
    })
  } else if (await pathExists(moduleJson)) {
    actions.push({
      type: 'transform',
      src: rel(projectPath, moduleJson),
      dest: '.cbim/dna/module.md',
      description: 'Transform .dna/module.json -> .cbim/dna/module.md',
      category: 'root-module',
    })
  }

  if (await pathExists(contractMd)) {
    actions.push({
      type: 'move',
      src: rel(projectPath, contractMd),
      dest: '.cbim/dna/contract.md',
      description: 'Move .dna/contract.md -> .cbim/dna/contract.md',
      category: 'root-module',
    })
  }

  if (await pathExists(workflowsDir)) {
    actions.push({
      type: 'move',
      src: rel(projectPath, workflowsDir),
      dest: '.cbim/dna/workflows',
      description: 'Move .dna/workflows/ -> .cbim/dna/workflows/',
      category: 'root-module',
    })
  }

  if (await pathExists(indexMd)) {
    actions.push({
      type: 'delete',
      src: rel(projectPath, indexMd),
      description: 'Delete .dna/index.md (superseded by dynamic discovery)',
      category: 'root-module',
    })
  }

  // Move any other files in .dna/ not already handled
  const knownFiles = new Set([
    'module.md', 'module.json', 'contract.md', 'index.md', 'workflows',
  ])
  try {
    const entries = await fs.readdir(dnaDir)
    for (const entry of entries) {
      if (!knownFiles.has(entry)) {
        const srcRel = rel(projectPath, path.join(dnaDir, entry))
        actions.push({
          type: 'move',
          src: srcRel,
          dest: `.cbim/dna/${entry}`,
          description: `Move .dna/${entry} -> .cbim/dna/${entry}`,
          category: 'root-module',
        })
      }
    }
  } catch {
    warnings.push('Could not list .dna/ directory contents for additional files')
  }
}

async function planAgents(
  projectPath: string,
  actions: MigrationAction[],
  warnings: string[],
): Promise<void> {
  const agentsDir = path.join(projectPath, '.claude', 'agents')
  if (!await pathExists(agentsDir)) return

  let agentDirs: string[]
  try {
    agentDirs = await fs.readdir(agentsDir)
  } catch {
    warnings.push('Could not read .claude/agents/ directory')
    return
  }

  for (const agentId of agentDirs) {
    const agentDir = path.join(agentsDir, agentId)
    const s = await fsStat(agentDir)
    if (!s || !s.isDirectory()) continue

    const agentFile = path.join(agentDir, `${agentId}.md`)
    if (!await pathExists(agentFile)) {
      warnings.push(`Agent directory .claude/agents/${agentId}/ has no matching ${agentId}.md file — skipped`)
      continue
    }

    // Check for extra files
    try {
      const entries = await fs.readdir(agentDir)
      const extra = entries.filter(e => e !== `${agentId}.md`)
      if (extra.length > 0) {
        warnings.push(`Agent .claude/agents/${agentId}/ contains extra files not migrated: ${extra.join(', ')}`)
      }
    } catch {
      // ignore
    }

    actions.push({
      type: 'move',
      src: rel(projectPath, agentFile),
      dest: `.cbim/agents/${agentId}.md`,
      description: `Copy .claude/agents/${agentId}/${agentId}.md -> .cbim/agents/${agentId}.md`,
      category: 'agents',
    })
  }
}

async function planMemory(
  projectPath: string,
  actions: MigrationAction[],
): Promise<void> {
  const storeDir = path.join(projectPath, 'cbim', 'memory', 'store')
  if (!await pathExists(storeDir)) return

  const subdirs = ['short', 'medium']
  for (const sub of subdirs) {
    const srcDir = path.join(storeDir, sub)
    if (await pathExists(srcDir)) {
      actions.push({
        type: 'move',
        src: rel(projectPath, srcDir),
        dest: `.cbim/memory/${sub}`,
        description: `Move cbim/memory/store/${sub}/ -> .cbim/memory/${sub}/`,
        category: 'memory',
      })
    }
  }

  // last-session.md
  const lastSession = path.join(storeDir, 'last-session.md')
  if (await pathExists(lastSession)) {
    actions.push({
      type: 'move',
      src: rel(projectPath, lastSession),
      dest: '.cbim/memory/last-session.md',
      description: 'Move cbim/memory/store/last-session.md -> .cbim/memory/last-session.md',
      category: 'memory',
    })
  }

  // Other files in store/
  try {
    const knownEntries = new Set(['short', 'medium', 'last-session.md'])
    const entries = await fs.readdir(storeDir)
    for (const entry of entries) {
      if (!knownEntries.has(entry)) {
        const srcRel = rel(projectPath, path.join(storeDir, entry))
        actions.push({
          type: 'move',
          src: srcRel,
          dest: `.cbim/memory/${entry}`,
          description: `Move cbim/memory/store/${entry} -> .cbim/memory/${entry}`,
          category: 'memory',
        })
      }
    }
  } catch {
    // ignore
  }
}

async function planConfig(
  projectPath: string,
  actions: MigrationAction[],
  warnings: string[],
): Promise<void> {
  const claudeMdPath = path.join(projectPath, 'CLAUDE.md')
  if (!await pathExists(claudeMdPath)) return

  const raw = await fs.readFile(claudeMdPath, 'utf-8')
  if (!raw.trim()) return

  const parsed = parseClaudeMd(raw)

  if (parsed.isUnstructured) {
    warnings.push(
      'CLAUDE.md has no structured sections; cannot extract system configuration. Manual review recommended.',
    )
    return
  }

  if (parsed.systemSections.length > 0 || parsed.preamble) {
    actions.push({
      type: 'transform',
      src: 'CLAUDE.md',
      dest: '.cbim/config.yaml',
      description: 'Extract system sections from CLAUDE.md -> .cbim/config.yaml',
      category: 'config',
    })
  }

  if (parsed.userSections.length > 0) {
    actions.push({
      type: 'transform',
      src: 'CLAUDE.md',
      dest: 'CLAUDE.md',
      description: 'Rewrite CLAUDE.md to keep only user sections',
      category: 'config',
    })
  } else if (parsed.systemSections.length > 0) {
    actions.push({
      type: 'delete',
      src: 'CLAUDE.md',
      description: 'Delete CLAUDE.md (all sections extracted to config.yaml)',
      category: 'config',
    })
  }
}

async function validateSubModules(projectPath: string, warnings: string[]): Promise<void> {
  // Walk source tree looking for .dna/ directories, check each has module.md
  const found: string[] = []
  await walkForDna(projectPath, projectPath, found)
  for (const dnaDir of found) {
    const moduleMd = path.join(dnaDir, 'module.md')
    if (!await pathExists(moduleMd)) {
      const rel2 = path.relative(projectPath, dnaDir)
      warnings.push(`Sub-module ${rel2} is missing module.md`)
    }
  }
}

async function walkForDna(dir: string, projectRoot: string, result: string[]): Promise<void> {
  const SKIP = new Set(['node_modules', 'dist', 'build', 'out', '.git', '.cbim', '.claude', 'cbim'])
  let entries: string[]
  try {
    entries = await fs.readdir(dir)
  } catch {
    return
  }
  for (const name of entries) {
    if (SKIP.has(name)) continue
    if (name.startsWith('.') && name !== '.dna') continue
    const full = path.join(dir, name)
    const s = await fsStat(full)
    if (!s || !s.isDirectory()) continue
    if (name === '.dna' && dir !== projectRoot) {
      result.push(full)
      continue
    }
    await walkForDna(full, projectRoot, result)
  }
}

async function planFrameworkCleanup(
  projectPath: string,
  actions: MigrationAction[],
  warnings: string[],
): Promise<void> {
  const cbimFwDir = path.join(projectPath, 'cbim')
  if (!await pathExists(cbimFwDir)) return

  const knownDirs = new Set(['knowledge', 'memory', 'cc-template'])
  const knownExts = new Set(['.py', '.md'])

  let entries: string[]
  try {
    entries = await fs.readdir(cbimFwDir)
  } catch {
    return
  }

  const unexpected: string[] = []
  for (const entry of entries) {
    const full = path.join(cbimFwDir, entry)
    const ext = path.extname(entry)

    if (entry === 'memory') {
      // memory/store/ was already moved; delete the rest of memory/
      actions.push({
        type: 'delete',
        src: rel(projectPath, full),
        description: 'Delete cbim/memory/ (store/ already migrated)',
        category: 'cleanup',
      })
      continue
    }

    if (knownDirs.has(entry)) {
      actions.push({
        type: 'delete',
        src: rel(projectPath, full),
        description: `Delete cbim/${entry}/`,
        category: 'cleanup',
      })
      continue
    }

    if (knownExts.has(ext)) {
      actions.push({
        type: 'delete',
        src: rel(projectPath, full),
        description: `Delete cbim/${entry}`,
        category: 'cleanup',
      })
      continue
    }

    unexpected.push(entry)
  }

  if (unexpected.length > 0) {
    warnings.push(
      `cbim/ contains unrecognized items that were NOT deleted: ${unexpected.join(', ')}`,
    )
  }
}

// ---------------------------------------------------------------------------
// Action execution
// ---------------------------------------------------------------------------

async function executeAction(
  action: MigrationAction,
  projectPath: string,
  noDelete: boolean,
  verbose: boolean,
  log: (msg: string) => void,
): Promise<'applied' | 'skipped'> {
  const srcAbs = action.src ? path.join(projectPath, action.src) : undefined
  const destAbs = action.dest ? path.join(projectPath, action.dest) : undefined

  if (verbose) {
    const srcPart = action.src ? ` ${action.src}` : ''
    const destPart = action.dest ? ` -> ${action.dest}` : ''
    log(`  [${action.category}]${srcPart}${destPart}`)
  }

  switch (action.type) {
    case 'move': {
      if (!srcAbs || !destAbs) throw new Error('move action requires src and dest')
      if (!await pathExists(srcAbs)) return 'skipped'
      await ensureParentDir(destAbs)
      await copyRecursive(srcAbs, destAbs)
      if (!noDelete) {
        await fs.rm(srcAbs, { recursive: true, force: true })
      }
      return 'applied'
    }

    case 'delete': {
      if (!srcAbs) throw new Error('delete action requires src')
      if (noDelete) return 'skipped'
      if (!await pathExists(srcAbs)) return 'skipped'
      await fs.rm(srcAbs, { recursive: true, force: true })
      return 'applied'
    }

    case 'transform': {
      if (!srcAbs || !destAbs) throw new Error('transform action requires src and dest')
      if (!await pathExists(srcAbs)) return 'skipped'
      await runTransform(action, srcAbs, destAbs, projectPath, noDelete)
      return 'applied'
    }

    case 'create': {
      if (!destAbs) throw new Error('create action requires dest')
      await ensureParentDir(destAbs)
      // content is embedded in description for now (not used in current plan)
      return 'applied'
    }

    default:
      throw new Error(`Unknown action type: ${String((action as MigrationAction).type)}`)
  }
}

async function runTransform(
  action: MigrationAction,
  srcAbs: string,
  destAbs: string,
  projectPath: string,
  noDelete: boolean,
): Promise<void> {
  if (action.category === 'root-module') {
    // JSON -> module.md transform
    const json = JSON.parse(await fs.readFile(srcAbs, 'utf-8')) as Record<string, unknown>
    const archMd = await tryReadFile(path.join(path.dirname(srcAbs), 'architecture.md'))
    const md = synthesizeModuleMd(json, archMd)
    await ensureParentDir(destAbs)
    await fs.writeFile(destAbs, md, 'utf-8')
    if (!noDelete) {
      await fs.rm(srcAbs, { recursive: true, force: true })
    }
    return
  }

  if (action.category === 'config') {
    // CLAUDE.md -> config.yaml  OR  CLAUDE.md -> trimmed CLAUDE.md
    const claudeMdPath = srcAbs // src is always CLAUDE.md
    const raw = await fs.readFile(claudeMdPath, 'utf-8')
    const parsed = parseClaudeMd(raw)

    if (action.dest && action.dest.endsWith('config.yaml')) {
      // Generate config.yaml
      const configYaml = buildConfigYaml(parsed.preamble, parsed.systemSections)
      await ensureParentDir(destAbs)
      await fs.writeFile(destAbs, configYaml, 'utf-8')
    } else if (action.dest === 'CLAUDE.md') {
      // Rewrite CLAUDE.md with only user sections
      const remaining = buildRemainingClaudeMd(parsed.userSections)
      await fs.writeFile(destAbs, remaining, 'utf-8')
    }
    return
  }

  throw new Error(`No transform handler for category: ${action.category}`)
}

// ---------------------------------------------------------------------------
// Content synthesis helpers
// ---------------------------------------------------------------------------

function synthesizeModuleMd(json: Record<string, unknown>, archMd: string | undefined): string {
  const name = typeof json['name'] === 'string' ? json['name'] : 'unknown'
  const owner = typeof json['owner'] === 'string' ? json['owner'] : 'unknown'
  const description = typeof json['description'] === 'string' ? json['description'] : ''
  const keywords = Array.isArray(json['keywords']) ? (json['keywords'] as unknown[]).map(String) : []
  const deps = Array.isArray(json['dependencies']) ? (json['dependencies'] as unknown[]).map(String) : []

  const kwLine = keywords.length > 0 ? `keywords: [${keywords.join(', ')}]\n` : ''
  const depsLine = deps.length > 0 ? `dependencies: [${deps.join(', ')}]\n` : ''

  let md = `---\nname: ${name}\nowner: ${owner}\ndescription: ${description}\n${kwLine}${depsLine}---\n`
  if (archMd) {
    md += `\n${archMd.trim()}\n`
  }
  return md
}

function buildConfigYaml(preamble: string, systemSections: Array<{ heading: string; content: string }>): string {
  const now = new Date().toISOString().split('T')[0] ?? new Date().toISOString()
  let yaml = `# CBIM v2 project configuration\n# Migrated from CLAUDE.md on ${now}\n\nversion: 2\n\nassistant:\n`

  if (preamble) {
    const indented = preamble.split('\n').map(l => `    ${l}`).join('\n')
    yaml += `  preamble: |\n${indented}\n`
  }

  if (systemSections.length > 0) {
    yaml += `  sections:\n`
    for (const section of systemSections) {
      yaml += `    - heading: ${JSON.stringify(section.heading)}\n`
      if (section.content) {
        const indented = section.content.split('\n').map(l => `        ${l}`).join('\n')
        yaml += `      content: |\n${indented}\n`
      } else {
        yaml += `      content: ""\n`
      }
    }
  }

  return yaml
}

function buildRemainingClaudeMd(userSections: Array<{ heading: string; content: string }>): string {
  return userSections
    .map(s => `## ${s.heading}\n\n${s.content}`)
    .join('\n\n')
    .trim() + '\n'
}

// ---------------------------------------------------------------------------
// Action ordering
// ---------------------------------------------------------------------------

const TYPE_ORDER: Record<MigrationAction['type'], number> = {
  create: 0,
  move: 1,
  transform: 2,
  delete: 3,
}

function orderActions(actions: MigrationAction[]): MigrationAction[] {
  return [...actions].sort((a, b) => TYPE_ORDER[a.type] - TYPE_ORDER[b.type])
}

// ---------------------------------------------------------------------------
// File system helpers
// ---------------------------------------------------------------------------

async function pathExists(p: string): Promise<boolean> {
  try {
    await fs.access(p)
    return true
  } catch {
    return false
  }
}

async function fsStat(p: string): Promise<Awaited<ReturnType<typeof fs.stat>> | undefined> {
  try {
    return await fs.stat(p)
  } catch {
    return undefined
  }
}

async function ensureParentDir(p: string): Promise<void> {
  await fs.mkdir(path.dirname(p), { recursive: true })
}

async function copyRecursive(src: string, dest: string): Promise<void> {
  const s = await fs.stat(src)
  if (s.isDirectory()) {
    await fs.mkdir(dest, { recursive: true })
    const entries = await fs.readdir(src)
    for (const entry of entries) {
      await copyRecursive(path.join(src, entry), path.join(dest, entry))
    }
  } else {
    await ensureParentDir(dest)
    await fs.copyFile(src, dest)
  }
}

async function tryReadFile(p: string): Promise<string | undefined> {
  try {
    return await fs.readFile(p, 'utf-8')
  } catch {
    return undefined
  }
}

function rel(base: string, full: string): string {
  return path.relative(base, full).replace(/\\/g, '/')
}
