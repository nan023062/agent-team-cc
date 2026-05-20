import cac from 'cac'
import { runMigrate } from './commands/migrate.js'

const cli = cac('cbim')

cli
  .command('migrate <project-path>', 'Migrate a v1 CBIM project to v2 layout')
  .option('--dry-run', 'Print migration plan without writing files', { default: false })
  .option('--force', 'Overwrite existing .cbim/ directory', { default: false })
  .option('--verbose', 'Print detailed per-action output', { default: false })
  .option('--no-delete', 'Copy files to v2 locations but do not delete v1 sources', { default: false })
  .action(
    (
      projectPath: string,
      options: { dryRun: boolean; force: boolean; verbose: boolean; noDelete: boolean },
    ) => {
      runMigrate(projectPath, options).catch((err: unknown) => {
        console.error(err instanceof Error ? err.message : String(err))
        process.exit(1)
      })
    },
  )

cli.help()
cli.version('0.0.0')
cli.parse()
