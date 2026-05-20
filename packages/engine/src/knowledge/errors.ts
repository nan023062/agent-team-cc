export class InvalidProjectRootError extends Error {
  override readonly name = 'InvalidProjectRootError' as const
  readonly projectRoot: string

  constructor(projectRoot: string) {
    super(`Project root does not exist or is not a directory: ${projectRoot}`)
    this.projectRoot = projectRoot
  }
}

export class ModuleNotFoundError extends Error {
  override readonly name = 'ModuleNotFoundError' as const
  readonly modulePath: string

  constructor(modulePath: string) {
    super(`Module not found at: ${modulePath}`)
    this.modulePath = modulePath
  }
}

export class FrontmatterParseError extends Error {
  override readonly name = 'FrontmatterParseError' as const
  readonly modulePath: string
  readonly rawYaml: string
  readonly parseMessage: string

  constructor(modulePath: string, rawYaml: string, parseMessage: string) {
    super(`Failed to parse frontmatter in module at ${modulePath}: ${parseMessage}`)
    this.modulePath = modulePath
    this.rawYaml = rawYaml
    this.parseMessage = parseMessage
  }
}

export class InvalidModuleError extends Error {
  override readonly name = 'InvalidModuleError' as const
  readonly modulePath: string
  readonly violations: readonly string[]

  constructor(modulePath: string, violations: readonly string[]) {
    super(`Invalid module at ${modulePath}: ${violations.join(', ')}`)
    this.modulePath = modulePath
    this.violations = violations
  }
}
