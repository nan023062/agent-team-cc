// @cbim/engine — knowledge sub-module placeholder
// Phase 1 will implement: listModules, loadModule, buildSnapshot

export type ModuleNode = {
  path: string
  children: ModuleNode[]
}

export type Module = {
  path: string
  content: string
}

export type Snapshot = {
  modules: ModuleNode[]
  focusPath?: string
}

export interface KnowledgeEngine {
  listModules(): ModuleNode[]
  loadModule(path: string): Module
  buildSnapshot(focusModule?: string): Snapshot
}
