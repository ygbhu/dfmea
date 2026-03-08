import type { DfmeaProjectContext } from './types'

export function createDfmeaProjectContext(projectRoot: string, localSubtreeId: string | null = null): DfmeaProjectContext {
  return {
    projectRoot,
    localSubtreeId,
    contentRoot: `${projectRoot}/content`,
    runtimeRoot: `${projectRoot}/runtime`,
    changesRoot: `${projectRoot}/changes`,
  }
}
