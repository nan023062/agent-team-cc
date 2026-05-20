// Types
export type {
  MigrationAction,
  MigrationPlan,
  MigrationResult,
  MigrationActionError,
  MigrationSummary,
} from './types.js'

// Errors
export { InvalidProjectPathError, NotV1ProjectError, TargetExistsError, TransformError } from './errors.js'

// Functions
export { planMigration, applyMigration, summarizeMigration } from './api.js'

// Exported for testing
export { parseClaudeMd } from './claude-parser.js'
export type { ClaudeSection, ClaudeMdParseResult } from './claude-parser.js'
