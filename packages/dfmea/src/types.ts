export type DfmeaActionId = 'create' | 'query' | 'complete' | 'review-apply'

export interface DfmeaProjectContext {
  projectRoot: string
  localSubtreeId: string | null
  contentRoot: string
  runtimeRoot: string
  changesRoot: string
}
