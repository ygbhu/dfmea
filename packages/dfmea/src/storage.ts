import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { buildDfmeaStorageLayout, joinDfmeaPath } from './content';
import { type DfmeaProposal } from './proposal';
import { buildRuntimeManifest, buildRuntimeShard, type DfmeaRuntimeManifest, type DfmeaRuntimeShard, type DfmeaSubtreeDocument, type DfmeaSubtreeEntry, type DfmeaSubtreeNote } from './runtimeIndex';
import { searchRuntimeShard } from './runtimeSearch';

export interface DfmeaChangeRecord {
  timestamp: string;
  kind: 'review-apply';
  proposalId: string;
  subtreeId: string;
  summary: string;
  status: 'applied' | 'failed';
  targetFiles: string[];
}

export interface DfmeaProjectSearchHit {
  subtreeId: string;
  node: DfmeaRuntimeShard['nodes'][number];
}

export interface DfmeaProjectSearchResult {
  query: string;
  results: DfmeaProjectSearchHit[];
}

function normalizeFsPath(value: string): string {
  return value.replace(/\\/g, '/');
}

function toSectionHeading(name: string): string {
  return name.trim().replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
}

function fromSectionHeading(name: string): string {
  return name.trim().toLowerCase().replace(/\s+/g, '_');
}

function escapeMarkdown(value: string): string {
  return value.replace(/\r\n/g, '\n').trim();
}

function parseEntry(line: string): DfmeaSubtreeEntry | null {
  const match = line.match(/^\-\s+\[(.+?)\]\s+\((.+?)\)\s+(.+?)\s*::\s*(.*?)\s*(?:\|\|\s*refs:\s*(.+))?$/);
  if (!match) {
    return null;
  }

  const [, id, kind, title, summary, refs] = match;
  return {
    id: id.trim(),
    kind: kind.trim(),
    title: title.trim(),
    summary: summary.trim(),
    refs: typeof refs === 'string' && refs.trim().length > 0
      ? refs.split(',').map((value) => value.trim()).filter(Boolean)
      : [],
  };
}

function serializeDocument(document: DfmeaSubtreeDocument): string {
  const lines: string[] = [
    `# ${document.title}`,
    '',
    `subtreeId: ${document.subtreeId}`,
    '',
  ];

  for (const section of document.sections) {
    lines.push(`## ${toSectionHeading(section.name)}`);
    lines.push('');

    if (section.entries.length === 0) {
      lines.push('- [TBD] (placeholder) Section pending definition :: Pending summary');
    } else {
      for (const entry of section.entries) {
        const refs = entry.refs.length > 0 ? ` || refs: ${entry.refs.join(', ')}` : '';
        lines.push(`- [${entry.id}] (${entry.kind}) ${escapeMarkdown(entry.title)} :: ${escapeMarkdown(entry.summary)}${refs}`);
      }
    }

    lines.push('');
  }

  if (document.notes && document.notes.length > 0) {
    lines.push('## Notes');
    lines.push('');

    for (const note of document.notes) {
      lines.push(`- (${note.section}) ${escapeMarkdown(note.text)}`);
    }

    lines.push('');
  }

  return `${lines.join('\n').trim()}\n`;
}

function parseNotes(lines: string[]): DfmeaSubtreeNote[] {
  const notes: DfmeaSubtreeNote[] = [];

  for (const line of lines) {
    const match = line.match(/^\-\s+\((.+?)\)\s+(.+)$/);
    if (!match) {
      continue;
    }

    notes.push({
      section: fromSectionHeading(match[1]),
      text: match[2].trim(),
    });
  }

  return notes;
}

function parseDocument(content: string, filePath: string): DfmeaSubtreeDocument {
  const normalized = content.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');

  const titleLine = lines.find((line) => line.startsWith('# '));
  const subtreeLine = lines.find((line) => line.startsWith('subtreeId: '));

  if (!titleLine || !subtreeLine) {
    throw new Error(`Invalid DFMEA subtree document: ${filePath}`);
  }

  const sections: DfmeaSubtreeDocument['sections'] = [];
  let currentSection: DfmeaSubtreeDocument['sections'][number] | null = null;
  let collectingNotes = false;
  let noteLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith('## ')) {
      const heading = line.slice(3).trim();

      if (heading.toLowerCase() === 'notes') {
        collectingNotes = true;
        currentSection = null;
        continue;
      }

      collectingNotes = false;
      currentSection = {
        name: fromSectionHeading(heading),
        entries: [],
      };
      sections.push(currentSection);
      continue;
    }

    if (collectingNotes) {
      if (line.trim()) {
        noteLines.push(line);
      }
      continue;
    }

    if (!currentSection) {
      continue;
    }

    const entry = parseEntry(line.trim());
    if (entry && entry.id !== 'TBD') {
      currentSection.entries.push(entry);
    }
  }

  const notes = parseNotes(noteLines);

  return {
    subtreeId: subtreeLine.slice('subtreeId: '.length).trim(),
    filePath: normalizeFsPath(filePath),
    title: titleLine.slice(2).trim(),
    sections,
    ...(notes.length > 0 ? { notes } : {}),
  };
}

function toProjectId(projectRoot: string): string {
  return normalizeFsPath(projectRoot).split('/').filter(Boolean).pop() || 'dfmea-project';
}

function getShardDirectory(projectRoot: string, subtreeId: string): string {
  return joinDfmeaPath(projectRoot, 'runtime', 'shards', subtreeId);
}

function getManifestPath(projectRoot: string): string {
  return joinDfmeaPath(projectRoot, 'runtime', 'manifest.json');
}

function getChangeRecordPath(projectRoot: string, record: DfmeaChangeRecord): string {
  return joinDfmeaPath(projectRoot, 'changes', `${record.timestamp.replace(/[:.]/g, '-')}-${record.proposalId}.json`);
}

async function ensureParentDir(filePath: string): Promise<void> {
  await mkdir(path.dirname(filePath), { recursive: true });
}

async function listMarkdownFiles(root: string): Promise<string[]> {
  const entries = await readdir(root, { withFileTypes: true });
  const result: string[] = [];

  for (const entry of entries) {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      result.push(...await listMarkdownFiles(entryPath));
      continue;
    }

    if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      result.push(normalizeFsPath(entryPath));
    }
  }

  return result;
}

async function resolveSubtreeSourceFile(projectRoot: string, subtreeId: string): Promise<string | null> {
  const manifest = await readRuntimeManifest(projectRoot);
  const fromManifest = manifest?.subtrees.find((entry) => entry.subtreeId === subtreeId)?.sourceFile ?? null;
  if (fromManifest) {
    return fromManifest;
  }

  const contentRoot = buildDfmeaStorageLayout(projectRoot).contentRoot;
  const markdownFiles = await stat(contentRoot)
    .then((stats) => stats.isDirectory() ? listMarkdownFiles(contentRoot) : [])
    .catch(() => []);

  for (const filePath of markdownFiles) {
    const document = await readSubtreeDocument(filePath);
    if (document.subtreeId === subtreeId) {
      return filePath;
    }
  }

  return null;
}

export async function writeSubtreeDocument(document: DfmeaSubtreeDocument): Promise<{ path: string }> {
  const outputPath = normalizeFsPath(document.filePath);
  await ensureParentDir(outputPath);
  await writeFile(outputPath, serializeDocument({ ...document, filePath: outputPath }), 'utf8');
  return { path: outputPath };
}

export async function readSubtreeDocument(filePath: string): Promise<DfmeaSubtreeDocument> {
  const normalizedPath = normalizeFsPath(filePath);
  const content = await readFile(normalizedPath, 'utf8');
  return parseDocument(content, normalizedPath);
}

export async function materializeDfmeaRuntime(projectRoot: string): Promise<{
  manifest: DfmeaRuntimeManifest;
  manifestPath: string;
  shardPaths: string[];
}> {
  const layout = buildDfmeaStorageLayout(projectRoot);
  await mkdir(layout.runtimeRoot, { recursive: true });

  const markdownFiles = await stat(layout.contentRoot)
    .then((stats) => stats.isDirectory() ? listMarkdownFiles(layout.contentRoot) : [])
    .catch(() => []);

  const documents = await Promise.all(markdownFiles.map((filePath) => readSubtreeDocument(filePath)));
  const manifest = buildRuntimeManifest(toProjectId(projectRoot), documents);
  const manifestPath = getManifestPath(projectRoot);
  const shardPaths: string[] = [];

  for (const document of documents) {
    const shard = buildRuntimeShard(document);
    const shardDirectory = getShardDirectory(projectRoot, document.subtreeId);
    await mkdir(shardDirectory, { recursive: true });
    await writeFile(joinDfmeaPath(shardDirectory, 'meta.json'), JSON.stringify(shard.meta, null, 2), 'utf8');
    await writeFile(joinDfmeaPath(shardDirectory, 'nodes.json'), JSON.stringify(shard.nodes, null, 2), 'utf8');
    await writeFile(joinDfmeaPath(shardDirectory, 'edges.json'), JSON.stringify(shard.edges, null, 2), 'utf8');
    shardPaths.push(shardDirectory);
  }

  await ensureParentDir(manifestPath);
  await writeFile(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');

  return { manifest, manifestPath, shardPaths };
}

export async function readRuntimeManifest(projectRoot: string): Promise<DfmeaRuntimeManifest | null> {
  try {
    const content = await readFile(getManifestPath(projectRoot), 'utf8');
    return JSON.parse(content) as DfmeaRuntimeManifest;
  } catch {
    return null;
  }
}

export async function readRuntimeShard(projectRoot: string, subtreeId: string): Promise<DfmeaRuntimeShard | null> {
  try {
    const shardDirectory = getShardDirectory(projectRoot, subtreeId);
    const [metaContent, nodesContent, edgesContent] = await Promise.all([
      readFile(joinDfmeaPath(shardDirectory, 'meta.json'), 'utf8'),
      readFile(joinDfmeaPath(shardDirectory, 'nodes.json'), 'utf8'),
      readFile(joinDfmeaPath(shardDirectory, 'edges.json'), 'utf8'),
    ]);

    return {
      meta: JSON.parse(metaContent) as DfmeaRuntimeShard['meta'],
      nodes: JSON.parse(nodesContent) as DfmeaRuntimeShard['nodes'],
      edges: JSON.parse(edgesContent) as DfmeaRuntimeShard['edges'],
    };
  } catch {
    return null;
  }
}

export async function searchDfmeaProject(input: {
  projectRoot: string;
  subtreeId?: string | null;
  query: string;
}): Promise<DfmeaProjectSearchResult> {
  const manifest = await readRuntimeManifest(input.projectRoot);
  if (!manifest) {
    await materializeDfmeaRuntime(input.projectRoot);
  }

  const effectiveManifest = await readRuntimeManifest(input.projectRoot);
  if (!effectiveManifest) {
    return { query: input.query, results: [] };
  }

  const subtreeIds = input.subtreeId
    ? [input.subtreeId]
    : effectiveManifest.subtrees.map((subtree) => subtree.subtreeId);

  const hits: DfmeaProjectSearchHit[] = [];

  for (const subtreeId of subtreeIds) {
    const shard = await readRuntimeShard(input.projectRoot, subtreeId);
    if (!shard) {
      continue;
    }

    for (const node of searchRuntimeShard(shard, input.query)) {
      hits.push({ subtreeId, node });
    }
  }

  return {
    query: input.query,
    results: hits,
  };
}

export async function writeChangeRecord(projectRoot: string, record: DfmeaChangeRecord): Promise<{ path: string }> {
  const filePath = getChangeRecordPath(projectRoot, record);
  await ensureParentDir(filePath);
  await writeFile(filePath, JSON.stringify(record, null, 2), 'utf8');
  return { path: filePath };
}

export async function listChangeRecords(projectRoot: string): Promise<DfmeaChangeRecord[]> {
  const changesDirectory = joinDfmeaPath(projectRoot, 'changes');
  const files = await readdir(changesDirectory, { withFileTypes: true }).catch(() => []);

  const records = await Promise.all(
    files
      .filter((entry) => entry.isFile() && entry.name.toLowerCase().endsWith('.json'))
      .map(async (entry) => {
        const content = await readFile(joinDfmeaPath(changesDirectory, entry.name), 'utf8');
        return JSON.parse(content) as DfmeaChangeRecord;
      })
  );

  return records.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
}

export async function updateSubtreeSections(input: {
  projectRoot: string;
  subtreeId: string;
  sections: Array<{
    section: string;
    entries: DfmeaSubtreeEntry[];
  }>;
  notes?: Array<{
    section: string;
    note: string;
  }>;
}): Promise<DfmeaSubtreeDocument> {
  const sourceFile = await resolveSubtreeSourceFile(input.projectRoot, input.subtreeId);

  if (!sourceFile) {
    throw new Error(`Unable to locate subtree source file for ${input.subtreeId}`);
  }

  const document = await readSubtreeDocument(sourceFile);
  const sectionsByName = new Map(document.sections.map((section) => [section.name, section]));

  for (const sectionUpdate of input.sections) {
    const existing = sectionsByName.get(sectionUpdate.section);
    if (existing) {
      existing.entries = sectionUpdate.entries;
      continue;
    }

    document.sections.push({
      name: sectionUpdate.section,
      entries: sectionUpdate.entries,
    });
  }

  if (input.notes && input.notes.length > 0) {
    document.notes = input.notes.map((note) => ({
      section: note.section,
      text: note.note,
    }));
  }

  await writeSubtreeDocument(document);
  return document;
}

export async function recordAppliedProposal(projectRoot: string, proposal: DfmeaProposal): Promise<{ path: string }> {
  return writeChangeRecord(projectRoot, {
    timestamp: new Date().toISOString(),
    kind: 'review-apply',
    proposalId: proposal.proposalId,
    subtreeId: proposal.subtreeId,
    summary: proposal.summary,
    status: proposal.status === 'failed' ? 'failed' : 'applied',
    targetFiles: proposal.targetFiles,
  });
}
