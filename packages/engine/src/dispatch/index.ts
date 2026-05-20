// @cbim/engine — dispatch sub-module placeholder
// Phase 2 will implement: agent scheduling via Claude Agent SDK

export type AgentRef = {
  id: string
  configPath: string
}

export type TaskSpec = {
  prompt: string
  context?: string
}

export type TaskResult = {
  output: string
  agentId: string
}

export type Context = {
  sessionId: string
  snapshot?: string
}

export type Subagent = {
  agentRef: AgentRef
  parentCtx: Context
}

export interface DispatchEngine {
  dispatch(agent: AgentRef, task: TaskSpec): Promise<TaskResult>
  spawnSubagent(agent: AgentRef, parentCtx: Context): Subagent
}
