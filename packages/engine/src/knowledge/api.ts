import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import type { Module, ModuleNode, Snapshot } from './types.js'
import {
  FrontmatterParseError,
  InvalidModuleError,
  InvalidProjectRootError,
  ModuleNotFoundError,
} from './errors.js'
import { parseModuleMd } from './parser.js'

// Directories to skip during tree walk (never descend into)
const SKIP_DIRS = new Set(['node_modules', 'dist', 'build', 'out', '.git', '.cbim'])

// --- resolveModulePath ---

export function resolveModulePath(relativePath: string, projectRoot: string): string {
  return path.normalize(path.join(projectRoot, relativePath))
}

// --- loadModule ---

export async function loadModule(modulePath: string): Promise<Module> {
  // Determine where module.md lives.
  // Root module: <modulePath>/module.md  (when path ends in .cbim/dna or .cbim\dna)
  // Sub-module:  <modulePath>/.dna/module.md
  const normalizedPath = path.normalize(modulePath)
  const isCbimRoot = isRootModulePath(normalizedPath)

  const moduleMdPath = isCbimRoot
    ? path.join(normalizedPath, 'module.md')
    : path.join(normalizedPath, '.dna', 'module.md')

  // Verify exists
  const exists = await fileExists(moduleMdPath)
  if (!exists) {
    throw new ModuleNotFoundError(toForwardSlash(normalizedPath))
  }

  const raw = await fs.readFile(moduleMdPath, 'utf-8')
  const relPath = toForwardSlash(normalizedPath) // caller passes absolute; we trust the caller

  // parseModuleMd throws FrontmatterParseError / InvalidModuleError
  const { frontmatter, sections } = parseModuleMd(raw, relPath)

  // Read optional contract.md
  let contract: string | undefined
  const contractPath = isCbimRoot
    ? path.join(normalizedPath, 'contract.md')
    : path.join(normalizedPath, '.dna', 'contract.md')
  if (await fileExists(contractPath)) {
    contract = await fs.readFile(contractPath, 'utf-8')
  }

  // List workflow names
  const workflowsDir = isCbimRoot
    ? path.join(normalizedPath, 'workflows')
    : path.join(normalizedPath, '.dna', 'workflows')
  const workflows = await listWorkflows(workflowsDir)

  return {
    path: toForwardSlash(normalizedPath),
    frontmatter,
    sections,
    ...(contract !== undefined ? { contract } : {}),
    workflows,
  }
}

// --- discoverModules ---

export async function discoverModules(projectRoot: string): Promise<readonly ModuleNode[]> {
  // Validate projectRoot
  let stat: Awaited<ReturnType<typeof fs.stat>>
  try {
    stat = await fs.stat(projectRoot)
  } catch {
    throw new InvalidProjectRootError(projectRoot)
  }
  if (!stat.isDirectory()) {
    throw new InvalidProjectRootError(projectRoot)
  }

  // Step 1: Check for root module at <projectRoot>/.cbim/dna/
  const cbimDnaPath = path.join(projectRoot, '.cbim', 'dna')
  let rootNode: ModuleNode | undefined

  if (await fileExists(path.join(cbimDnaPath, 'module.md'))) {
    try {
      rootNode = await buildModuleNode(cbimDnaPath, true)
    } catch (e) {
      if (e instanceof FrontmatterParseError || e instanceof InvalidModuleError) {
        console.warn(`[knowledge] Skipping root module (parse error): ${e.message}`)
      } else {
        throw e
      }
    }
  }

  // Step 2: Walk the project tree for sub-modules (skip .cbim and other skip dirs)
  const allSubModulePaths: string[] = []
  await walkForModules(projectRoot, projectRoot, allSubModulePaths)

  // Step 3: Build nodes for all sub-modules
  const subNodes: Array<{ absPath: string; node: ModuleNode }> = []
  for (const absPath of allSubModulePaths) {
    try {
      const node = await buildModuleNode(absPath, false)
      subNodes.push({ absPath, node })
    } catch (e) {
      if (e instanceof FrontmatterParseError || e instanceof InvalidModuleError) {
        console.warn(`[knowledge] Skipping module at ${absPath} (parse error): ${(e as Error).message}`)
      } else {
        throw e
      }
    }
  }

  // Step 4: Assemble tree by filesystem nesting
  // Sort by path length so parents are processed before children
  subNodes.sort((a, b) => a.absPath.length - b.absPath.length)

  // Build a map: absPath -> mutable node (we'll freeze at the end)
  const mutableNodes = new Map<string, MutableModuleNode>()
  for (const { absPath, node } of subNodes) {
    mutableNodes.set(absPath, { ...node, children: [] })
  }

  const roots: MutableModuleNode[] = []

  for (const { absPath } of subNodes) {
    const node = mutableNodes.get(absPath)!
    const parentAbsPath = findNearestParent(absPath, [...mutableNodes.keys()].filter(p => p !== absPath))
    if (parentAbsPath !== undefined) {
      mutableNodes.get(parentAbsPath)!.children.push(node)
    } else if (rootNode !== undefined) {
      // Parent is the root module
      ;(rootNode as MutableModuleNode).children.push(node)
    } else {
      roots.push(node)
    }
  }

  // Freeze and finalize isLeaf
  if (rootNode !== undefined) {
    const mutableRoot = rootNode as MutableModuleNode
    // Update isLeaf based on actual children
    finalizeNode(mutableRoot)
    return [freezeNode(mutableRoot)]
  }

  for (const root of roots) {
    finalizeNode(root)
  }
  return roots.map(freezeNode)
}

// --- buildSnapshot ---

export async function buildSnapshot(
  focusModulePath: string,
  tree: readonly ModuleNode[],
): Promise<Snapshot> {
  const normalizedFocus = path.normalize(focusModulePath)
  const focusRelPath = toForwardSlash(normalizedFocus)

  // Locate the focus node in the tree
  const focusNode = findNodeByAbsPath(tree, normalizedFocus)
  if (focusNode === undefined) {
    throw new ModuleNotFoundError(focusRelPath)
  }

  // Load focus module (fatal if it fails)
  const focus = await loadModule(normalizedFocus)

  // Collect ancestors: walk up the tree
  const ancestorNodes = collectAncestors(focusNode, tree)
  const ancestors = await loadBestEffort(ancestorNodes.map(n => resolveNodeAbsPath(n, normalizedFocus, tree)))

  // Load descendants (direct children of focus)
  const descendants = await loadBestEffort(
    focusNode.children.map(child => resolveNodeAbsPath(child, normalizedFocus, tree)),
  )

  // Load siblings (other children of focus's parent)
  const parentNode = findParentNode(focusNode, tree)
  const siblingNodes = parentNode !== undefined
    ? parentNode.children.filter(c => c.path !== focusNode.path)
    : []
  const siblings = await loadBestEffort(siblingNodes.map(n => resolveNodeAbsPath(n, normalizedFocus, tree)))

  // Resolve dependencies
  const alreadyIncluded = new Set<string>([
    focus.path,
    ...ancestors.map(m => m.path),
    ...descendants.map(m => m.path),
    ...siblings.map(m => m.path),
  ])

  const related: Module[] = []
  const unresolvedDependencies: string[] = []

  for (const depRelPath of focus.frontmatter.dependencies) {
    // Find node in tree by relative path
    const depNode = findNodeByRelPath(tree, depRelPath)
    if (depNode === undefined) {
      unresolvedDependencies.push(depRelPath)
      continue
    }
    if (alreadyIncluded.has(depNode.path)) {
      continue // dedup
    }
    // Derive abs path from context
    // focusModulePath is absolute; tree paths are absolute too because we stored them
    const depAbsPath = resolveNodeAbsPath(depNode, normalizedFocus, tree)
    try {
      const m = await loadModule(depAbsPath)
      related.push(m)
      alreadyIncluded.add(depNode.path)
    } catch (e) {
      console.warn(`[knowledge] Could not load dependency ${depRelPath}: ${(e as Error).message}`)
      unresolvedDependencies.push(depRelPath)
    }
  }

  return {
    focus,
    ancestors,
    descendants,
    siblings,
    related,
    unresolvedDependencies,
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

interface MutableModuleNode {
  path: string
  name: string
  children: MutableModuleNode[]
  isLeaf: boolean
  metadata: { owner: string; description: string; keywords: readonly string[] }
}

async function buildModuleNode(absPath: string, isRoot: boolean): Promise<ModuleNode> {
  const moduleMdPath = isRoot
    ? path.join(absPath, 'module.md')
    : path.join(absPath, '.dna', 'module.md')

  const raw = await fs.readFile(moduleMdPath, 'utf-8')
  // May throw FrontmatterParseError or InvalidModuleError — let caller handle
  const { frontmatter } = parseModuleMd(raw, absPath)

  return {
    path: toForwardSlash(absPath),
    name: frontmatter.name,
    children: [],
    isLeaf: true, // will be updated during tree assembly
    metadata: {
      owner: frontmatter.owner,
      description: frontmatter.description,
      keywords: frontmatter.keywords,
    },
  }
}

async function walkForModules(
  dir: string,
  projectRoot: string,
  result: string[],
): Promise<void> {
  let entryNames: string[]
  try {
    entryNames = await fs.readdir(dir)
  } catch {
    return
  }

  for (const name of entryNames) {
    const fullPath = path.join(dir, name)

    // Check if directory
    let entryStat: Awaited<ReturnType<typeof fs.stat>>
    try {
      entryStat = await fs.stat(fullPath)
    } catch {
      continue
    }
    if (!entryStat.isDirectory()) continue

    // Skip dirs per contract
    if (SKIP_DIRS.has(name)) continue
    // Skip dot-dirs except .dna
    if (name.startsWith('.') && name !== '.dna') continue

    if (name === '.dna') {
      // The parent directory is a module candidate
      const parentDir = dir // dir is the module directory
      if (parentDir !== projectRoot && await fileExists(path.join(fullPath, 'module.md'))) {
        result.push(parentDir)
      }
      // Don't recurse into .dna
      continue
    }

    await walkForModules(fullPath, projectRoot, result)
  }
}

function findNearestParent(absPath: string, candidates: string[]): string | undefined {
  // Find the longest candidate that is a proper ancestor of absPath
  let best: string | undefined
  for (const candidate of candidates) {
    if (isProperAncestor(candidate, absPath)) {
      if (best === undefined || candidate.length > best.length) {
        best = candidate
      }
    }
  }
  return best
}

function isProperAncestor(candidate: string, target: string): boolean {
  const rel = path.relative(candidate, target)
  return !rel.startsWith('..') && rel !== ''
}

function finalizeNode(node: MutableModuleNode): void {
  node.isLeaf = node.children.length === 0
  for (const child of node.children) {
    finalizeNode(child)
  }
}

function freezeNode(node: MutableModuleNode): ModuleNode {
  return {
    path: node.path,
    name: node.name,
    isLeaf: node.isLeaf,
    metadata: node.metadata,
    children: node.children.map(freezeNode),
  }
}

function findNodeByAbsPath(tree: readonly ModuleNode[], absPath: string): ModuleNode | undefined {
  const targetForward = toForwardSlash(absPath)
  return findNodeByPredicate(tree, n => n.path === targetForward)
}

function findNodeByRelPath(tree: readonly ModuleNode[], relPath: string): ModuleNode | undefined {
  // node.path stores absolute paths as forward-slash strings
  // relPath is relative to project root — we match by suffix
  const normalized = relPath.replace(/\\/g, '/')
  return findNodeByPredicate(tree, n => n.path.endsWith('/' + normalized) || n.path === normalized)
}

function findNodeByPredicate(
  tree: readonly ModuleNode[],
  pred: (n: ModuleNode) => boolean,
): ModuleNode | undefined {
  for (const node of tree) {
    if (pred(node)) return node
    const found = findNodeByPredicate(node.children, pred)
    if (found !== undefined) return found
  }
  return undefined
}

function collectAncestors(focus: ModuleNode, tree: readonly ModuleNode[]): ModuleNode[] {
  const ancestors: ModuleNode[] = []
  let current: ModuleNode | undefined = focus
  while (current !== undefined) {
    const parent = findParentNode(current, tree)
    if (parent === undefined) break
    ancestors.push(parent)
    current = parent
  }
  return ancestors
}

function findParentNode(target: ModuleNode, tree: readonly ModuleNode[]): ModuleNode | undefined {
  for (const node of tree) {
    if (node.children.some(c => c.path === target.path)) return node
    const found = findParentNode(target, node.children)
    if (found !== undefined) return found
  }
  return undefined
}

function resolveNodeAbsPath(
  node: ModuleNode,
  _focusAbsPath: string,
  _tree: readonly ModuleNode[],
): string {
  // node.path is already stored as the absolute path (forward slash)
  // Convert back to platform-native for fs calls
  return node.path.replace(/\//g, path.sep)
}

async function loadBestEffort(absPaths: string[]): Promise<Module[]> {
  const results: Module[] = []
  for (const absPath of absPaths) {
    try {
      results.push(await loadModule(absPath))
    } catch (e) {
      console.warn(`[knowledge] Could not load module at ${absPath}: ${(e as Error).message}`)
    }
  }
  return results
}

async function listWorkflows(workflowsDir: string): Promise<readonly string[]> {
  try {
    const entryNames = await fs.readdir(workflowsDir)
    const names: string[] = []
    for (const name of entryNames) {
      const fullPath = path.join(workflowsDir, name)
      try {
        const s = await fs.stat(fullPath)
        if (!s.isDirectory()) continue
      } catch {
        continue
      }
      const hasWorkflow = await fileExists(path.join(fullPath, 'workflow.md'))
      if (hasWorkflow) names.push(name)
    }
    return names
  } catch {
    return []
  }
}

async function fileExists(p: string): Promise<boolean> {
  try {
    await fs.access(p)
    return true
  } catch {
    return false
  }
}

function isRootModulePath(absPath: string): boolean {
  // True when the path ends with .cbim/dna (or .cbim\dna on Windows)
  const normalized = absPath.replace(/\\/g, '/')
  return normalized.endsWith('/.cbim/dna') || normalized.endsWith('/.cbim/dna/')
}

function toForwardSlash(p: string): string {
  return p.replace(/\\/g, '/')
}
