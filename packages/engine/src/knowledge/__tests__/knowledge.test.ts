import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import * as os from 'node:os'
import {
  discoverModules,
  loadModule,
  buildSnapshot,
  resolveModulePath,
  parseModuleMd,
  ModuleNotFoundError,
  FrontmatterParseError,
  InvalidModuleError,
  InvalidProjectRootError,
} from '../index.js'

// ---------------------------------------------------------------------------
// Test fixture helpers
// ---------------------------------------------------------------------------

let tmpDir: string

beforeEach(async () => {
  tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cbim-test-'))
})

afterEach(async () => {
  await fs.rm(tmpDir, { recursive: true, force: true })
})

async function writeFile(relPath: string, content: string): Promise<void> {
  const abs = path.join(tmpDir, relPath)
  await fs.mkdir(path.dirname(abs), { recursive: true })
  await fs.writeFile(abs, content, 'utf-8')
}

function moduleMd(name: string, owner: string, extra = ''): string {
  return `---\nname: ${name}\nowner: ${owner}\n${extra}---\n\n## Positioning\n\nThis is the ${name} module.\n`
}

// ---------------------------------------------------------------------------
// parseModuleMd — pure function tests
// ---------------------------------------------------------------------------

describe('parseModuleMd', () => {
  it('parses required fields correctly', () => {
    const raw = `---\nname: my-module\nowner: architect\n---\n\n## Positioning\n\nSome text.\n`
    const { frontmatter, sections } = parseModuleMd(raw)
    expect(frontmatter.name).toBe('my-module')
    expect(frontmatter.owner).toBe('architect')
    expect(frontmatter.description).toBe('')
    expect(frontmatter.keywords).toEqual([])
    expect(frontmatter.dependencies).toEqual([])
    expect(frontmatter.includeDirs).toEqual([])
    expect(sections.positioning).toBe('Some text.')
  })

  it('parses optional frontmatter fields', () => {
    const raw = `---\nname: m\nowner: o\ndescription: My desc\nkeywords: [a, b]\ndependencies: [src/x]\nincludeDirs: [docs]\n---\n`
    const { frontmatter } = parseModuleMd(raw)
    expect(frontmatter.description).toBe('My desc')
    expect(frontmatter.keywords).toEqual(['a', 'b'])
    expect(frontmatter.dependencies).toEqual(['src/x'])
    expect(frontmatter.includeDirs).toEqual(['docs'])
  })

  it('silently ignores unknown frontmatter fields', () => {
    const raw = `---\nname: m\nowner: o\nunknownField: 42\n---\n`
    expect(() => parseModuleMd(raw)).not.toThrow()
  })

  it('maps section headings correctly', () => {
    const raw = `---\nname: m\nowner: o\n---\n\n## Positioning\n\nP text.\n\n## Class Diagram\n\nD text.\n\n## Key Decisions\n\nK text.\n\n## Custom Section\n\nC text.\n`
    const { sections } = parseModuleMd(raw)
    expect(sections.positioning).toBe('P text.')
    expect(sections.diagram).toBe('D text.')
    expect(sections.keyDecisions).toBe('K text.')
    expect(sections['Custom Section']).toBe('C text.')
  })

  it('maps Component Diagram and Sub-module Relationship Diagram to diagram', () => {
    const raw1 = `---\nname: m\nowner: o\n---\n\n## Component Diagram\n\nCD.\n`
    expect(parseModuleMd(raw1).sections.diagram).toBe('CD.')

    const raw2 = `---\nname: m\nowner: o\n---\n\n## Sub-module Relationship Diagram\n\nSRD.\n`
    expect(parseModuleMd(raw2).sections.diagram).toBe('SRD.')
  })

  it('throws FrontmatterParseError when no frontmatter delimiters', () => {
    expect(() => parseModuleMd('No frontmatter here')).toThrow(FrontmatterParseError)
  })

  it('throws FrontmatterParseError when YAML is malformed', () => {
    const raw = `---\nname: [unclosed\n---\n`
    expect(() => parseModuleMd(raw)).toThrow(FrontmatterParseError)
  })

  it('throws InvalidModuleError when name is missing', () => {
    const raw = `---\nowner: o\n---\n`
    expect(() => parseModuleMd(raw)).toThrow(InvalidModuleError)
  })

  it('throws InvalidModuleError when owner is missing', () => {
    const raw = `---\nname: m\n---\n`
    expect(() => parseModuleMd(raw)).toThrow(InvalidModuleError)
  })

  it('throws InvalidModuleError when name is empty string', () => {
    const raw = `---\nname: ""\nowner: o\n---\n`
    expect(() => parseModuleMd(raw)).toThrow(InvalidModuleError)
  })
})

// ---------------------------------------------------------------------------
// resolveModulePath — pure utility
// ---------------------------------------------------------------------------

describe('resolveModulePath', () => {
  it('joins and normalizes projectRoot + relativePath', () => {
    const result = resolveModulePath('src/combat', '/project')
    // Platform-native path
    expect(result).toBe(path.normalize('/project/src/combat'))
  })

  it('handles . (root module relative path)', () => {
    const result = resolveModulePath('.', '/project')
    expect(result).toBe(path.normalize('/project'))
  })
})

// ---------------------------------------------------------------------------
// loadModule
// ---------------------------------------------------------------------------

describe('loadModule', () => {
  it('loads a basic sub-module', async () => {
    await writeFile('src/combat/.dna/module.md', moduleMd('combat', 'architect'))
    const mod = await loadModule(path.join(tmpDir, 'src', 'combat'))
    expect(mod.frontmatter.name).toBe('combat')
    expect(mod.frontmatter.owner).toBe('architect')
    expect(mod.sections.positioning).toBe('This is the combat module.')
    expect(mod.workflows).toEqual([])
    expect(mod.contract).toBeUndefined()
  })

  it('loads contract.md when present', async () => {
    await writeFile('src/x/.dna/module.md', moduleMd('x', 'o'))
    await writeFile('src/x/.dna/contract.md', '# Contract\n\nSome contract.')
    const mod = await loadModule(path.join(tmpDir, 'src', 'x'))
    expect(mod.contract).toBe('# Contract\n\nSome contract.')
  })

  it('lists workflow names from .dna/workflows/', async () => {
    await writeFile('src/x/.dna/module.md', moduleMd('x', 'o'))
    await writeFile('src/x/.dna/workflows/deploy/workflow.md', '# Deploy Workflow')
    await writeFile('src/x/.dna/workflows/rollback/workflow.md', '# Rollback Workflow')
    await writeFile('src/x/.dna/workflows/empty-dir/somefile.txt', 'no workflow.md here')
    const mod = await loadModule(path.join(tmpDir, 'src', 'x'))
    expect(mod.workflows).toContain('deploy')
    expect(mod.workflows).toContain('rollback')
    expect(mod.workflows).not.toContain('empty-dir')
  })

  it('loads root module from .cbim/dna/', async () => {
    await writeFile('.cbim/dna/module.md', moduleMd('root', 'admin'))
    const mod = await loadModule(path.join(tmpDir, '.cbim', 'dna'))
    expect(mod.frontmatter.name).toBe('root')
  })

  it('throws ModuleNotFoundError when path does not exist', async () => {
    await expect(loadModule(path.join(tmpDir, 'nonexistent'))).rejects.toThrow(ModuleNotFoundError)
  })

  it('throws ModuleNotFoundError when .dna/module.md is absent', async () => {
    await fs.mkdir(path.join(tmpDir, 'src', 'empty', '.dna'), { recursive: true })
    await expect(loadModule(path.join(tmpDir, 'src', 'empty'))).rejects.toThrow(ModuleNotFoundError)
  })

  it('throws FrontmatterParseError when frontmatter is malformed', async () => {
    await writeFile('src/bad/.dna/module.md', '---\nname: [bad\n---\n')
    await expect(loadModule(path.join(tmpDir, 'src', 'bad'))).rejects.toThrow(FrontmatterParseError)
  })

  it('throws InvalidModuleError when required fields are missing', async () => {
    await writeFile('src/noowner/.dna/module.md', '---\nname: m\n---\n')
    await expect(loadModule(path.join(tmpDir, 'src', 'noowner'))).rejects.toThrow(InvalidModuleError)
  })
})

// ---------------------------------------------------------------------------
// discoverModules
// ---------------------------------------------------------------------------

describe('discoverModules', () => {
  it('throws InvalidProjectRootError for non-existent directory', async () => {
    await expect(discoverModules('/nonexistent/path/xyz')).rejects.toThrow(InvalidProjectRootError)
  })

  it('returns [] when no modules are found', async () => {
    const result = await discoverModules(tmpDir)
    expect(result).toEqual([])
  })

  it('discovers root module from .cbim/dna/', async () => {
    await writeFile('.cbim/dna/module.md', moduleMd('root', 'admin'))
    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1)
    expect(result[0]!.name).toBe('root')
    expect(result[0]!.isLeaf).toBe(true)
  })

  it('discovers sub-modules and builds tree', async () => {
    await writeFile('.cbim/dna/module.md', moduleMd('root', 'admin'))
    await writeFile('src/combat/.dna/module.md', moduleMd('combat', 'architect'))
    await writeFile('src/ui/.dna/module.md', moduleMd('ui', 'architect'))

    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1) // root is the only root node
    const root = result[0]!
    expect(root.name).toBe('root')
    expect(root.children).toHaveLength(2)
    const childNames = root.children.map(c => c.name).sort()
    expect(childNames).toEqual(['combat', 'ui'])
    expect(root.isLeaf).toBe(false)
  })

  it('skips node_modules, dist, build, .git directories', async () => {
    await writeFile('node_modules/fake/.dna/module.md', moduleMd('fake', 'o'))
    await writeFile('dist/fake/.dna/module.md', moduleMd('fake2', 'o'))
    await writeFile('.git/fake/.dna/module.md', moduleMd('fake3', 'o'))
    await writeFile('src/real/.dna/module.md', moduleMd('real', 'o'))

    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1)
    expect(result[0]!.name).toBe('real')
  })

  it('skips .cbim as sub-module (handled as root separately)', async () => {
    await writeFile('.cbim/dna/module.md', moduleMd('root', 'admin'))
    // Ensure .cbim sub-dirs are not walked as regular modules
    await writeFile('src/sub/.dna/module.md', moduleMd('sub', 'o'))
    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1) // only root
    const root = result[0]!
    expect(root.children).toHaveLength(1)
    expect(root.children[0]!.name).toBe('sub')
  })

  it('handles root module path asymmetry correctly (root has no parent .dna/)', async () => {
    // Sub-module without root module -> becomes root-level node itself
    await writeFile('packages/engine/.dna/module.md', moduleMd('engine', 'o'))
    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1)
    expect(result[0]!.name).toBe('engine')
  })

  it('warns and skips modules with bad frontmatter during discovery', async () => {
    await writeFile('src/bad/.dna/module.md', '---\nbad: [yaml\n---\n')
    await writeFile('src/good/.dna/module.md', moduleMd('good', 'o'))
    // Should not throw, just skip the bad one
    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1)
    expect(result[0]!.name).toBe('good')
  })

  it('nests children under the nearest parent', async () => {
    await writeFile('src/.dna/module.md', moduleMd('src', 'o'))
    await writeFile('src/combat/.dna/module.md', moduleMd('combat', 'o'))
    await writeFile('src/combat/physics/.dna/module.md', moduleMd('physics', 'o'))

    const result = await discoverModules(tmpDir)
    expect(result).toHaveLength(1)
    const src = result[0]!
    expect(src.name).toBe('src')
    expect(src.children).toHaveLength(1)
    const combat = src.children[0]!
    expect(combat.name).toBe('combat')
    expect(combat.children).toHaveLength(1)
    expect(combat.children[0]!.name).toBe('physics')
  })
})

// ---------------------------------------------------------------------------
// buildSnapshot
// ---------------------------------------------------------------------------

describe('buildSnapshot', () => {
  it('builds a snapshot for the root module', async () => {
    await writeFile('.cbim/dna/module.md', moduleMd('root', 'admin'))
    await writeFile('src/a/.dna/module.md', moduleMd('a', 'o'))

    const tree = await discoverModules(tmpDir)
    const snapshot = await buildSnapshot(path.join(tmpDir, '.cbim', 'dna'), tree)

    expect(snapshot.focus.frontmatter.name).toBe('root')
    expect(snapshot.ancestors).toHaveLength(0) // root has no ancestors
    expect(snapshot.descendants).toHaveLength(1)
    expect(snapshot.descendants[0]!.frontmatter.name).toBe('a')
    expect(snapshot.siblings).toHaveLength(0)
    expect(snapshot.related).toHaveLength(0)
    expect(snapshot.unresolvedDependencies).toHaveLength(0)
  })

  it('builds ancestors chain from child to root', async () => {
    await writeFile('.cbim/dna/module.md', moduleMd('root', 'admin'))
    await writeFile('src/.dna/module.md', moduleMd('src', 'o'))
    await writeFile('src/combat/.dna/module.md', moduleMd('combat', 'o'))

    const tree = await discoverModules(tmpDir)
    const snapshot = await buildSnapshot(path.join(tmpDir, 'src', 'combat'), tree)

    expect(snapshot.focus.frontmatter.name).toBe('combat')
    expect(snapshot.ancestors).toHaveLength(2)
    expect(snapshot.ancestors[0]!.frontmatter.name).toBe('src')
    expect(snapshot.ancestors[1]!.frontmatter.name).toBe('root')
  })

  it('collects siblings correctly', async () => {
    await writeFile('src/.dna/module.md', moduleMd('src', 'o'))
    await writeFile('src/a/.dna/module.md', moduleMd('a', 'o'))
    await writeFile('src/b/.dna/module.md', moduleMd('b', 'o'))
    await writeFile('src/c/.dna/module.md', moduleMd('c', 'o'))

    const tree = await discoverModules(tmpDir)
    const snapshot = await buildSnapshot(path.join(tmpDir, 'src', 'a'), tree)

    expect(snapshot.siblings).toHaveLength(2)
    const siblingNames = snapshot.siblings.map(s => s.frontmatter.name).sort()
    expect(siblingNames).toEqual(['b', 'c'])
  })

  it('resolves dependencies and deduplicates vs ancestors/siblings', async () => {
    await writeFile('src/.dna/module.md', moduleMd('src', 'o'))
    await writeFile('src/a/.dna/module.md', moduleMd('a', 'o', `dependencies: [src/b]\n`))
    await writeFile('src/b/.dna/module.md', moduleMd('b', 'o'))

    const tree = await discoverModules(tmpDir)
    const snapshot = await buildSnapshot(path.join(tmpDir, 'src', 'a'), tree)

    // b is a sibling of a, and also a dependency — should appear in siblings, NOT duplicated in related
    expect(snapshot.siblings.map(s => s.frontmatter.name)).toContain('b')
    expect(snapshot.related).toHaveLength(0)
    expect(snapshot.unresolvedDependencies).toHaveLength(0)
  })

  it('adds unresolved dependency to unresolvedDependencies', async () => {
    await writeFile('src/a/.dna/module.md', moduleMd('a', 'o', `dependencies: [nonexistent/module]\n`))
    const tree = await discoverModules(tmpDir)
    const snapshot = await buildSnapshot(path.join(tmpDir, 'src', 'a'), tree)
    expect(snapshot.unresolvedDependencies).toContain('nonexistent/module')
  })

  it('throws ModuleNotFoundError when focus path not in tree', async () => {
    await writeFile('src/a/.dna/module.md', moduleMd('a', 'o'))
    const tree = await discoverModules(tmpDir)
    await expect(
      buildSnapshot(path.join(tmpDir, 'src', 'nonexistent'), tree),
    ).rejects.toThrow(ModuleNotFoundError)
  })
})
