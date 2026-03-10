const normalizeSlashes = (value: string): string => value.replace(/\\/g, '/');

const trimTrailingSlash = (value: string): string => {
  if (value.length <= 1) {
    return value;
  }

  return value.replace(/\/+$/g, '');
};

export function joinDfmeaPath(...parts: string[]): string {
  const filtered = parts
    .map((part) => normalizeSlashes(part.trim()))
    .filter((part) => part.length > 0);

  if (filtered.length === 0) {
    return '';
  }

  const [first, ...rest] = filtered;
  let result = trimTrailingSlash(first);

  for (const part of rest) {
    const normalizedPart = part.replace(/^\/+|\/+$/g, '');
    if (!normalizedPart) {
      continue;
    }

    if (!result || result === '/') {
      result = `${result}${normalizedPart}`;
      continue;
    }

    result = `${trimTrailingSlash(result)}/${normalizedPart}`;
  }

  return result;
}

export interface DfmeaStorageLayout {
  projectRoot: string;
  contentRoot: string;
  runtimeRoot: string;
  changesRoot: string;
}

export function buildDfmeaStorageLayout(projectRoot: string): DfmeaStorageLayout {
  const normalizedProjectRoot = normalizeSlashes(projectRoot);

  return {
    projectRoot: normalizedProjectRoot,
    contentRoot: joinDfmeaPath(normalizedProjectRoot, 'content'),
    runtimeRoot: joinDfmeaPath(normalizedProjectRoot, 'runtime'),
    changesRoot: joinDfmeaPath(normalizedProjectRoot, 'changes'),
  };
}

export function getCanonicalSubtreePath(projectRoot: string, domain: string, subtreeId: string): string {
  return joinDfmeaPath(projectRoot, 'content', domain, `${subtreeId}.md`);
}
