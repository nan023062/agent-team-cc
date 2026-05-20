export interface MigrationAction {
  readonly type: 'move' | 'delete' | 'transform' | 'create'
  readonly src?: string
  readonly dest?: string
  readonly description: string
  readonly category: 'root-module' | 'agents' | 'memory' | 'config' | 'cleanup'
}

export interface MigrationPlan {
  readonly projectPath: string
  readonly actions: readonly MigrationAction[]
  readonly warnings: readonly string[]
  readonly isV1Project: boolean
}

export interface MigrationResult {
  readonly success: boolean
  readonly applied: readonly MigrationAction[]
  readonly skipped: readonly MigrationAction[]
  readonly errors: readonly MigrationActionError[]
}

export interface MigrationActionError {
  readonly action: MigrationAction
  readonly error: string
}

export interface MigrationSummary {
  readonly modulesmigrated: number
  readonly agentsMigrated: number
  readonly memoryEntriesMigrated: number
  readonly configExtracted: boolean
  readonly filesDeleted: number
  readonly warnings: readonly string[]
  readonly errors: readonly string[]
}
