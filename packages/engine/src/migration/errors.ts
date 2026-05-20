import type { MigrationAction } from './types.js'

export class InvalidProjectPathError extends Error {
  override readonly name = 'InvalidProjectPathError' as const
  readonly projectPath: string

  constructor(projectPath: string) {
    super(`Project path does not exist or is not a directory: ${projectPath}`)
    this.projectPath = projectPath
  }
}

export class NotV1ProjectError extends Error {
  override readonly name = 'NotV1ProjectError' as const
  readonly projectPath: string
  readonly checkedIndicators: readonly string[]

  constructor(projectPath: string, checkedIndicators: readonly string[]) {
    super(`No v1 indicators found at: ${projectPath}`)
    this.projectPath = projectPath
    this.checkedIndicators = checkedIndicators
  }
}

export class TargetExistsError extends Error {
  override readonly name = 'TargetExistsError' as const
  readonly targetPath: string

  constructor(targetPath: string) {
    super(`Target .cbim/ already exists at: ${targetPath}. Use --force to overwrite.`)
    this.targetPath = targetPath
  }
}

export class TransformError extends Error {
  override readonly name = 'TransformError' as const
  readonly action: MigrationAction
  readonly reason: string

  constructor(action: MigrationAction, reason: string) {
    super(`Transform failed for action "${action.description}": ${reason}`)
    this.action = action
    this.reason = reason
  }
}
