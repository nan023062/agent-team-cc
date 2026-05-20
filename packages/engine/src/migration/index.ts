// @cbim/engine — migration sub-module placeholder
// Phase 0 CLI uses this to migrate v1 projects to v2 layout

export type MigrationPlan = {
  projectPath: string
  actions: MigrationAction[]
}

export type MigrationAction = {
  type: 'move' | 'delete' | 'transform'
  src: string
  dest?: string
  description: string
}

export type MigrationResult = {
  success: boolean
  applied: MigrationAction[]
  errors: string[]
}

export interface MigrationEngine {
  plan(projectPath: string): MigrationPlan
  apply(plan: MigrationPlan): MigrationResult
}
