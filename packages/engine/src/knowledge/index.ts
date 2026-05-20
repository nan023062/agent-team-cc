// Types
export type { ModuleFrontmatter, ModuleSections, Module, ModuleNode, Snapshot } from './types.js'

// Errors
export {
  ModuleNotFoundError,
  FrontmatterParseError,
  InvalidModuleError,
  InvalidProjectRootError,
} from './errors.js'

// Functions
export { discoverModules, loadModule, buildSnapshot, resolveModulePath } from './api.js'
export { parseModuleMd } from './parser.js'
