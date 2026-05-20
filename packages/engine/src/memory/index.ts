// @cbim/engine — memory sub-module placeholder
// Phase 3 will implement: three-stage distillation

export type SessionRecord = {
  sessionId: string
  timestamp: string
  content: string
}

export type DistillCriteria = {
  before?: string
  minEntries?: number
}

export type MediumRecord = {
  id: string
  content: string
  createdAt: string
}

export type MemoryHit = {
  record: MediumRecord
  score: number
}

export interface MemoryEngine {
  appendShort(session: SessionRecord): void
  distillToMedium(criteria: DistillCriteria): MediumRecord[]
  promoteToDistilled(record: MediumRecord): void
  query(intent: string): MemoryHit[]
}
