export interface ModuleFrontmatter {
  readonly name: string
  readonly owner: string
  readonly description: string
  readonly keywords: readonly string[]
  readonly dependencies: readonly string[]
  readonly includeDirs: readonly string[]
}

export interface ModuleSections {
  readonly positioning?: string
  readonly diagram?: string
  readonly keyDecisions?: string
  readonly [sectionName: string]: string | undefined
}

export interface Module {
  readonly path: string
  readonly frontmatter: ModuleFrontmatter
  readonly sections: ModuleSections
  readonly contract?: string
  readonly workflows: readonly string[]
}

export interface ModuleNode {
  readonly path: string
  readonly name: string
  readonly children: readonly ModuleNode[]
  readonly isLeaf: boolean
  readonly metadata: {
    readonly owner: string
    readonly description: string
    readonly keywords: readonly string[]
  }
}

export interface Snapshot {
  readonly focus: Module
  readonly ancestors: readonly Module[]
  readonly descendants: readonly Module[]
  readonly siblings: readonly Module[]
  readonly related: readonly Module[]
  readonly unresolvedDependencies: readonly string[]
}
