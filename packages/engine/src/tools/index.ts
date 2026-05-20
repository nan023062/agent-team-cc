// @cbim/engine — SDK Tool adapter layer placeholder
// Phase 1+ will implement: cbim_* tool definitions wrapping engine functions

export type ToolRole = 'coordinator' | 'architect' | 'programmer' | 'hr' | 'auditor'

export type CbimTool = {
  name: string
  description: string
  inputSchema: Record<string, unknown>
}

/**
 * Returns the set of cbim_* tools permitted for the given agent role.
 * Placeholder — returns empty set until tools are implemented.
 */
export function getToolSet(_role: ToolRole): CbimTool[] {
  return []
}
