import cac from 'cac'
import { migrate } from './commands/migrate.js'

const cli = cac('cbim')

cli
  .command('migrate <project-path>', 'Migrate a v1 CBIM project to v2 layout')
  .action((projectPath: string) => {
    migrate(projectPath)
  })

cli.help()
cli.version('0.0.0')
cli.parse()
