import type { DfmeaProjectContext } from './types';
import { buildDfmeaStorageLayout } from './content';

export function createDfmeaProjectContext(projectRoot: string, localSubtreeId: string | null = null): DfmeaProjectContext {
  const layout = buildDfmeaStorageLayout(projectRoot);

  return {
    projectRoot: layout.projectRoot,
    localSubtreeId,
    contentRoot: layout.contentRoot,
    runtimeRoot: layout.runtimeRoot,
    changesRoot: layout.changesRoot,
  };
}
