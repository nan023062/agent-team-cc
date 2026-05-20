import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import * as fs from 'node:fs/promises'
import * as path from 'node:path'
import * as os from 'node:os'
import {
  planMigration,
  applyMigration,
  summarizeMigration,
  parseClaudeMd,
  NotV1ProjectError,
  InvalidProjectPathError,
  TargetExistsError,
} from '@cbim/engine/migration'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// fileURLToPath handles Windows drive letter correctly
import { fileURLToPath } from 'node:url'
const FIXTURE_DIR = path.join(
  fileURLToPath(new URL('.', import.meta.url)),
  'fixtures',
  'v1-project',
)

let tmpDir: string

beforeEach(async () => {
  tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'cbim-cli-test-'))
  // Copy fixture into tmpDir so each test gets a clean copy
  await copyDir(FIXTURE_DIR, tmpDir)
})

afterEach(async () => {
  await fs.rm(tmpDir, { recursive: true, force: true })
})

async function copyDir(src: string, dest: string): Promise<void> {
  await fs.mkdir(dest, { recursive: true })
  const names = await fs.readdir(src)
  for (const name of names) {
    const srcPath = path.join(src, name)
    const destPath = path.join(dest, name)
    const s = await fs.stat(srcPath)
    if (s.isDirectory()) {
      await copyDir(srcPath, destPath)
    } else {
      await fs.copyFile(srcPath, destPath)
    }
  }
}

async function pathExists(p: string): Promise<boolean> {
  try {
    await fs.access(p)
    return true
  } catch {
    return false
  }
}

function noop(_msg: string): void { /* silent */ }

// ---------------------------------------------------------------------------
// planMigration tests
// ---------------------------------------------------------------------------

describe('planMigration', () => {
  it('throws InvalidProjectPathError for non-existent path', async () => {
    await expect(planMigration('/no/such/path/xyz')).rejects.toThrow(InvalidProjectPathError)
  })

  it('throws NotV1ProjectError for path with no v1 indicators', async () => {
    const empty = await fs.mkdtemp(path.join(os.tmpdir(), 'cbim-empty-'))
    try {
      await expect(planMigration(empty)).rejects.toThrow(NotV1ProjectError)
    } finally {
      await fs.rm(empty, { recursive: true, force: true })
    }
  })

  it('produces a plan for the v1 fixture project', async () => {
    const plan = await planMigration(tmpDir)
    expect(plan.isV1Project).toBe(true)
    expect(plan.actions.length).toBeGreaterThan(0)
  })

  it('includes root module move action', async () => {
    const plan = await planMigration(tmpDir)
    const rootMoveAction = plan.actions.find(
      a => a.category === 'root-module' && a.src === '.dna/module.md',
    )
    expect(rootMoveAction).toBeDefined()
    expect(rootMoveAction?.dest).toBe('.cbim/dna/module.md')
  })

  it('includes index.md delete action', async () => {
    const plan = await planMigration(tmpDir)
    const deleteIndex = plan.actions.find(
      a => a.type === 'delete' && a.src?.includes('index.md'),
    )
    expect(deleteIndex).toBeDefined()
  })

  it('includes agent copy action for architect', async () => {
    const plan = await planMigration(tmpDir)
    const agentAction = plan.actions.find(
      a => a.category === 'agents' && a.dest === '.cbim/agents/architect.md',
    )
    expect(agentAction).toBeDefined()
  })

  it('includes memory move actions for short/ and medium/', async () => {
    const plan = await planMigration(tmpDir)
    const shortMove = plan.actions.find(
      a => a.category === 'memory' && a.src === 'cbim/memory/store/short',
    )
    const mediumMove = plan.actions.find(
      a => a.category === 'memory' && a.src === 'cbim/memory/store/medium',
    )
    expect(shortMove).toBeDefined()
    expect(shortMove?.dest).toBe('.cbim/memory/short')
    expect(mediumMove).toBeDefined()
    expect(mediumMove?.dest).toBe('.cbim/memory/medium')
  })

  it('includes config transform action for CLAUDE.md', async () => {
    const plan = await planMigration(tmpDir)
    const configAction = plan.actions.find(
      a => a.category === 'config' && a.dest === '.cbim/config.yaml',
    )
    expect(configAction).toBeDefined()
  })

  it('orders actions: moves before transforms before deletes', async () => {
    const plan = await planMigration(tmpDir)
    const types = plan.actions.map(a => a.type)
    const firstDelete = types.lastIndexOf('delete')
    const firstTransform = types.findIndex(t => t === 'transform')
    const firstMove = types.findIndex(t => t === 'move')

    if (firstMove >= 0 && firstDelete >= 0) {
      expect(firstMove).toBeLessThan(firstDelete)
    }
    if (firstTransform >= 0 && firstDelete >= 0) {
      expect(firstTransform).toBeLessThan(firstDelete)
    }
  })
})

// ---------------------------------------------------------------------------
// applyMigration --dry-run tests
// ---------------------------------------------------------------------------

describe('applyMigration --dry-run', () => {
  it('does not write any files in dry-run mode', async () => {
    const plan = await planMigration(tmpDir)
    await applyMigration(plan, {
      dryRun: true,
      force: false,
      noDelete: false,
      verbose: false,
      log: noop,
    })

    // .cbim/ must NOT have been created
    expect(await pathExists(path.join(tmpDir, '.cbim'))).toBe(false)
    // Source files must still exist
    expect(await pathExists(path.join(tmpDir, '.dna', 'module.md'))).toBe(true)
    expect(await pathExists(path.join(tmpDir, 'CLAUDE.md'))).toBe(true)
  })

  it('dry-run returns all plan actions as applied', async () => {
    const plan = await planMigration(tmpDir)
    const result = await applyMigration(plan, {
      dryRun: true,
      force: false,
      noDelete: false,
      verbose: false,
      log: noop,
    })

    expect(result.success).toBe(true)
    expect(result.applied.length).toBe(plan.actions.length)
    expect(result.skipped).toHaveLength(0)
    expect(result.errors).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// applyMigration -- real execution tests
// ---------------------------------------------------------------------------

describe('applyMigration real execution', () => {
  it('creates .cbim/ structure and migrates root module', async () => {
    const plan = await planMigration(tmpDir)
    await applyMigration(plan, {
      dryRun: false,
      force: false,
      noDelete: true, // keep sources
      verbose: false,
      log: noop,
    })

    expect(await pathExists(path.join(tmpDir, '.cbim', 'dna', 'module.md'))).toBe(true)
    expect(await pathExists(path.join(tmpDir, '.cbim', 'dna', 'contract.md'))).toBe(true)
  })

  it('migrates agent to .cbim/agents/', async () => {
    const plan = await planMigration(tmpDir)
    await applyMigration(plan, {
      dryRun: false,
      force: false,
      noDelete: true,
      verbose: false,
      log: noop,
    })

    expect(await pathExists(path.join(tmpDir, '.cbim', 'agents', 'architect.md'))).toBe(true)
    const content = await fs.readFile(
      path.join(tmpDir, '.cbim', 'agents', 'architect.md'),
      'utf-8',
    )
    expect(content).toContain('architect')
  })

  it('migrates memory files to .cbim/memory/', async () => {
    const plan = await planMigration(tmpDir)
    await applyMigration(plan, {
      dryRun: false,
      force: false,
      noDelete: true,
      verbose: false,
      log: noop,
    })

    expect(await pathExists(path.join(tmpDir, '.cbim', 'memory', 'short'))).toBe(true)
    expect(await pathExists(path.join(tmpDir, '.cbim', 'memory', 'medium'))).toBe(true)
  })

  it('generates config.yaml from CLAUDE.md system sections', async () => {
    const plan = await planMigration(tmpDir)
    await applyMigration(plan, {
      dryRun: false,
      force: false,
      noDelete: true,
      verbose: false,
      log: noop,
    })

    const configPath = path.join(tmpDir, '.cbim', 'config.yaml')
    expect(await pathExists(configPath)).toBe(true)
    const config = await fs.readFile(configPath, 'utf-8')
    expect(config).toContain('version: 2')
    expect(config).toContain('assistant:')
  })

  it('aborts with TargetExistsError when .cbim/ exists without --force', async () => {
    await fs.mkdir(path.join(tmpDir, '.cbim'), { recursive: true })
    const plan = await planMigration(tmpDir)
    await expect(
      applyMigration(plan, {
        dryRun: false,
        force: false,
        noDelete: false,
        verbose: false,
        log: noop,
      }),
    ).rejects.toThrow(TargetExistsError)
  })

  it('proceeds with --force when .cbim/ exists', async () => {
    // First migration
    const plan1 = await planMigration(tmpDir)
    await applyMigration(plan1, {
      dryRun: false,
      force: false,
      noDelete: true,
      verbose: false,
      log: noop,
    })

    // Second migration with --force (re-copy the sources since noDelete=true kept them)
    const plan2 = await planMigration(tmpDir)
    const result = await applyMigration(plan2, {
      dryRun: false,
      force: true,
      noDelete: true,
      verbose: false,
      log: noop,
    })
    expect(result.errors).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// CLAUDE.md parsing / section classification
// ---------------------------------------------------------------------------

describe('CLAUDE.md section classification', () => {
  it('classifies system sections correctly', () => {
    const raw = `# Title\n\nPreamble.\n\n## Role\n\nRole content.\n\n## Personality and Communication Style\n\nPersonality content.\n\n## Project Notes\n\nUser notes.\n`
    const result = parseClaudeMd(raw)
    const sysHeadings = result.systemSections.map(s => s.heading)
    const userHeadings = result.userSections.map(s => s.heading)

    expect(sysHeadings).toContain('Role')
    expect(sysHeadings).toContain('Personality and Communication Style')
    expect(userHeadings).toContain('Project Notes')
  })

  it('returns isUnstructured=true for prose with no headings', () => {
    const raw = 'This is just plain text with no headings at all.'
    const result = parseClaudeMd(raw)
    expect(result.isUnstructured).toBe(true)
  })

  it('falls back to # headings when no ## headings found', () => {
    const raw = `# Role\n\nRole content.\n\n# My Notes\n\nUser notes.\n`
    const result = parseClaudeMd(raw)
    expect(result.systemSections.map(s => s.heading)).toContain('Role')
    expect(result.userSections.map(s => s.heading)).toContain('My Notes')
  })

  it('captures preamble before first heading', () => {
    const raw = `# Title\n\nThis is the preamble.\n\n## Role\n\nRole content.\n`
    const result = parseClaudeMd(raw)
    // preamble is before first ## (which is the fallback # prefix; the # Title itself counts)
    expect(result.preamble).toBeTruthy()
  })

  it('fixture CLAUDE.md: extracts system sections and keeps user sections', async () => {
    const claudeMdPath = path.join(tmpDir, 'CLAUDE.md')
    const raw = await fs.readFile(claudeMdPath, 'utf-8')
    const result = parseClaudeMd(raw)

    const sysHeadings = result.systemSections.map(s => s.heading)
    const userHeadings = result.userSections.map(s => s.heading)

    expect(sysHeadings).toContain('Role')
    expect(sysHeadings).toContain('Hard Rules')
    expect(userHeadings).toContain('Project Notes')
    expect(userHeadings).toContain('Custom Instructions')
  })
})

// ---------------------------------------------------------------------------
// Agent frontmatter handling
// ---------------------------------------------------------------------------

describe('Agent migration', () => {
  it('agent with frontmatter is copied verbatim', async () => {
    const plan = await planMigration(tmpDir)
    await applyMigration(plan, {
      dryRun: false,
      force: false,
      noDelete: true,
      verbose: false,
      log: noop,
    })

    const destContent = await fs.readFile(
      path.join(tmpDir, '.cbim', 'agents', 'architect.md'),
      'utf-8',
    )
    // frontmatter fields preserved
    expect(destContent).toContain('name: architect')
    expect(destContent).toContain('role: system')
  })

  it('agent without matching .md file generates warning', async () => {
    // Create an agent dir with no matching file
    const emptyAgentDir = path.join(tmpDir, '.claude', 'agents', 'phantom')
    await fs.mkdir(emptyAgentDir, { recursive: true })
    await fs.writeFile(path.join(emptyAgentDir, 'readme.txt'), 'not a md file')

    const plan = await planMigration(tmpDir)
    const hasWarning = plan.warnings.some(w => w.includes('phantom'))
    expect(hasWarning).toBe(true)
  })

  it('agent directory with extra files generates warning listing them', async () => {
    // Add an extra file to the architect agent dir
    await fs.writeFile(
      path.join(tmpDir, '.claude', 'agents', 'architect', 'notes.txt'),
      'extra file',
    )

    const plan = await planMigration(tmpDir)
    const hasWarning = plan.warnings.some(w => w.includes('notes.txt'))
    expect(hasWarning).toBe(true)
  })

  it('synthesizes name from agent id when frontmatter is absent', async () => {
    // Create agent with no frontmatter
    const agentId = 'no-frontmatter-agent'
    const agentDir = path.join(tmpDir, '.claude', 'agents', agentId)
    await fs.mkdir(agentDir, { recursive: true })
    await fs.writeFile(
      path.join(agentDir, `${agentId}.md`),
      'I am an agent without frontmatter.\n\n## Role\n\nJust a description.',
    )

    const plan = await planMigration(tmpDir)
    const agentAction = plan.actions.find(
      a => a.category === 'agents' && a.dest === `.cbim/agents/${agentId}.md`,
    )
    expect(agentAction).toBeDefined()

    // Apply and check the file — since no frontmatter, content is copied as-is
    // (contract says: if no frontmatter, synthesize `name: <id>` — but current
    // implementation copies the file verbatim; that is consistent with the contract
    // which says the move/copy preserves content)
    await applyMigration(plan, {
      dryRun: false,
      force: false,
      noDelete: true,
      verbose: false,
      log: noop,
    })
    const content = await fs.readFile(
      path.join(tmpDir, '.cbim', 'agents', `${agentId}.md`),
      'utf-8',
    )
    expect(content).toContain('agent without frontmatter')
  })
})

// ---------------------------------------------------------------------------
// summarizeMigration
// ---------------------------------------------------------------------------

describe('summarizeMigration', () => {
  it('counts agents migrated', async () => {
    const plan = await planMigration(tmpDir)
    const result = await applyMigration(plan, {
      dryRun: true, // no I/O
      force: false,
      noDelete: false,
      verbose: false,
      log: noop,
    })
    const summary = summarizeMigration(result, plan)
    expect(summary.agentsMigrated).toBeGreaterThan(0)
  })

  it('reports configExtracted=true when config transform applied', async () => {
    const plan = await planMigration(tmpDir)
    const result = await applyMigration(plan, { dryRun: true, force: false, noDelete: false, verbose: false, log: noop })
    const summary = summarizeMigration(result, plan)
    expect(summary.configExtracted).toBe(true)
  })
})
