import * as path from 'node:path'
import * as fs from 'node:fs/promises'
import {
  planMigration,
  applyMigration,
  summarizeMigration,
  TargetExistsError,
  InvalidProjectPathError,
  NotV1ProjectError,
} from '@cbim/engine/migration'
import { discoverModules } from '@cbim/engine/knowledge'

export interface MigrateOptions {
  dryRun: boolean
  force: boolean
  verbose: boolean
  noDelete: boolean
}

export async function runMigrate(rawProjectPath: string, options: MigrateOptions): Promise<void> {
  const projectPath = path.resolve(rawProjectPath)
  const { dryRun, force, verbose, noDelete } = options

  console.log(`cbim migrate v1.0 -> v2.0${dryRun ? ' (dry run)' : ''}`)
  console.log()
  console.log(`${dryRun ? 'Analyzing' : 'Migrating'}: ${projectPath}`)
  console.log()

  // Warn if uncommitted git changes
  await printGitWarning(projectPath)

  // Plan
  let plan
  try {
    plan = await planMigration(projectPath)
  } catch (e) {
    if (e instanceof InvalidProjectPathError) {
      console.error(`Error: ${e.message}`)
      process.exit(2)
    }
    if (e instanceof NotV1ProjectError) {
      console.error(`Error: ${e.message}`)
      process.exit(2)
    }
    throw e
  }

  if (dryRun) {
    printPlan(plan)
    console.log('\nNo files were modified (dry run).')
    process.exit(0)
  }

  // Apply
  let result
  try {
    result = await applyMigration(plan, {
      dryRun,
      force,
      noDelete,
      verbose,
      log: (msg: string) => console.log(msg),
    })
  } catch (e) {
    if (e instanceof TargetExistsError) {
      console.error(`Error: ${e.message}`)
      process.exit(3)
    }
    throw e
  }

  // Post-migration validation
  const validationWarning = await postMigrationValidation(projectPath)
  const allWarnings = validationWarning
    ? [...plan.warnings, validationWarning]
    : plan.warnings

  const summary = summarizeMigration(result, { ...plan, warnings: allWarnings })

  printResult(result)
  printSummary(summary)
  printNextSteps()

  if (!result.success) {
    process.exit(1)
  }
}

function printPlan(plan: Awaited<ReturnType<typeof planMigration>>): void {
  console.log('Migration plan:')
  for (const action of plan.actions) {
    const srcPart = action.src ? ` ${action.src}` : ''
    const destPart = action.dest ? ` -> ${action.dest}` : ''
    console.log(`  [${action.category}] ${action.description}${srcPart}${destPart}`)
  }

  console.log()
  console.log(`Summary (would apply):`)
  const agents = plan.actions.filter(a => a.category === 'agents').length
  const memory = plan.actions.filter(a => a.category === 'memory').length
  const hasConfig = plan.actions.some(a => a.category === 'config')
  const deletes = plan.actions.filter(a => a.type === 'delete').length
  console.log(`  Agents: ${agents}    Memory moves: ${memory}    Config: ${hasConfig ? 'yes' : 'no'}    Deletes: ${deletes}`)

  if (plan.warnings.length > 0) {
    console.log('\nWarnings:')
    for (const w of plan.warnings) {
      console.log(`  - ${w}`)
    }
  }
}

function printResult(result: Awaited<ReturnType<typeof applyMigration>>): void {
  const total = result.applied.length + result.skipped.length + result.errors.length
  console.log(`\nMigration ${result.success ? 'complete' : 'partially completed'}.`)
  if (!result.success) {
    console.error(`\nError: Migration failed for ${result.errors.length} action(s):`)
    for (const err of result.errors) {
      console.error(`  [${err.action.category}] ${err.action.description}`)
      console.error(`           Error: ${err.error}`)
    }
    console.error(`\n${result.applied.length} of ${total} actions succeeded.`)
  }
}

function printSummary(summary: ReturnType<typeof summarizeMigration>): void {
  console.log(`  Modules migrated:  ${summary.modulesmigrated}`)
  console.log(`  Agents migrated:   ${summary.agentsMigrated}`)
  console.log(`  Memory entries:    ${summary.memoryEntriesMigrated}`)
  console.log(`  Config extracted:  ${summary.configExtracted ? 'yes' : 'no'}`)
  console.log(`  Files deleted:     ${summary.filesDeleted}`)

  if (summary.warnings.length > 0) {
    console.log('\nWarnings:')
    for (const w of summary.warnings) {
      console.log(`  - ${w}`)
    }
  }
}

function printNextSteps(): void {
  console.log('\nNext steps:')
  console.log('  1. Install the CBIM v2 VS Code extension')
  console.log('  2. Open this project in VS Code and verify the CBIM sidebar')
}

async function postMigrationValidation(projectPath: string): Promise<string | undefined> {
  try {
    const tree = await discoverModules(projectPath)
    if (tree.length === 0) {
      return 'Post-migration validation: module tree is empty. The .cbim/dna/module.md may be malformed.'
    }
    return undefined
  } catch {
    return 'Post-migration validation: could not run discoverModules.'
  }
}

async function printGitWarning(projectPath: string): Promise<void> {
  try {
    const gitDir = path.join(projectPath, '.git')
    await fs.access(gitDir)
    // It's a git repo — we can't easily check uncommitted changes without spawning git
    // Just print the general safety recommendation
    console.log('Tip: If anything goes wrong, run `git checkout .` to restore.')
    console.log()
  } catch {
    // Not a git repo, no warning needed
  }
}
