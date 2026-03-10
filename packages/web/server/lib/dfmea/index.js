import fs from 'fs';
import path from 'path';

const normalizePath = (value) => value.replace(/\\/g, '/');

const joinDfmeaPath = (...parts) => {
  const filtered = parts
    .map((part) => typeof part === 'string' ? normalizePath(part.trim()) : '')
    .filter(Boolean);

  if (filtered.length === 0) {
    return '';
  }

  const [first, ...rest] = filtered;
  let result = first.replace(/\/+$/g, '');

  for (const part of rest) {
    const normalized = part.replace(/^\/+|\/+$/g, '');
    if (!normalized) continue;
    if (!result || result === '/') {
      result = `${result}${normalized}`;
    } else {
      result = `${result.replace(/\/+$/g, '')}/${normalized}`;
    }
  }

  return result;
};

const buildLayout = (projectRoot) => ({
  projectRoot: normalizePath(projectRoot),
  contentRoot: joinDfmeaPath(projectRoot, 'content'),
  runtimeRoot: joinDfmeaPath(projectRoot, 'runtime'),
  changesRoot: joinDfmeaPath(projectRoot, 'changes'),
});

const toSectionHeading = (name) => name.trim().replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
const fromSectionHeading = (name) => name.trim().toLowerCase().replace(/\s+/g, '_');

const parseEntry = (line) => {
  const match = line.match(/^\-\s+\[(.+?)\]\s+\((.+?)\)\s+(.+?)\s*::\s*(.*?)\s*(?:\|\|\s*refs:\s*(.+))?$/);
  if (!match) return null;
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
};

const parseDocument = (content, filePath) => {
  const normalized = content.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const titleLine = lines.find((line) => line.startsWith('# '));
  const subtreeLine = lines.find((line) => line.startsWith('subtreeId: '));

  if (!titleLine || !subtreeLine) {
    throw new Error(`Invalid DFMEA subtree document: ${filePath}`);
  }

  const sections = [];
  const notes = [];
  let currentSection = null;
  let collectingNotes = false;

  for (const line of lines) {
    if (line.startsWith('## ')) {
      const heading = line.slice(3).trim();
      if (heading.toLowerCase() === 'notes') {
        collectingNotes = true;
        currentSection = null;
        continue;
      }

      collectingNotes = false;
      currentSection = { name: fromSectionHeading(heading), entries: [] };
      sections.push(currentSection);
      continue;
    }

    if (collectingNotes) {
      const noteMatch = line.trim().match(/^\-\s+\((.+?)\)\s+(.+)$/);
      if (noteMatch) {
        notes.push({ section: fromSectionHeading(noteMatch[1]), text: noteMatch[2].trim() });
      }
      continue;
    }

    if (!currentSection) continue;
    const entry = parseEntry(line.trim());
    if (entry && entry.id !== 'TBD') {
      currentSection.entries.push(entry);
    }
  }

  return {
    subtreeId: subtreeLine.slice('subtreeId: '.length).trim(),
    filePath: normalizePath(filePath),
    title: titleLine.slice(2).trim(),
    sections,
    ...(notes.length > 0 ? { notes } : {}),
  };
};

const serializeDocument = (document) => {
  const lines = [`# ${document.title}`, '', `subtreeId: ${document.subtreeId}`, ''];

  for (const section of document.sections) {
    lines.push(`## ${toSectionHeading(section.name)}`);
    lines.push('');

    if (section.entries.length === 0) {
      lines.push('- [TBD] (placeholder) Section pending definition :: Pending summary');
    } else {
      for (const entry of section.entries) {
        const refs = entry.refs.length > 0 ? ` || refs: ${entry.refs.join(', ')}` : '';
        lines.push(`- [${entry.id}] (${entry.kind}) ${entry.title.trim()} :: ${entry.summary.trim()}${refs}`);
      }
    }

    lines.push('');
  }

  if (Array.isArray(document.notes) && document.notes.length > 0) {
    lines.push('## Notes');
    lines.push('');
    for (const note of document.notes) {
      lines.push(`- (${note.section}) ${note.text.trim()}`);
    }
    lines.push('');
  }

  return `${lines.join('\n').trim()}\n`;
};

const toAnchor = (value) => value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

const buildRuntimeShard = (document) => {
  const nodes = [];
  const edges = [];

  for (const section of document.sections) {
    for (const entry of section.entries) {
      nodes.push({
        id: entry.id,
        kind: entry.kind,
        title: entry.title,
        section: section.name,
        parentId: null,
        refIds: entry.refs,
        anchor: toAnchor(entry.title || entry.id),
        summary: entry.summary,
      });

      for (const refId of entry.refs) {
        edges.push({ from: entry.id, to: refId, type: 'ref' });
      }
    }
  }

  return {
    meta: {
      subtreeId: document.subtreeId,
      sourceFile: document.filePath,
      title: document.title,
      nodeCount: nodes.length,
      edgeCount: edges.length,
      version: 1,
    },
    nodes,
    edges,
  };
};

const buildRuntimeManifest = (projectRoot, documents) => ({
  projectId: normalizePath(projectRoot).split('/').filter(Boolean).pop() || 'dfmea-project',
  updatedAt: new Date().toISOString(),
  subtrees: documents.map((document) => ({
    subtreeId: document.subtreeId,
    sourceFile: document.filePath,
    shardPath: `runtime/shards/${document.subtreeId}`,
    dirty: false,
  })),
});

const scoreNode = (node, query) => {
  const lowerQuery = query.trim().toLowerCase();
  if (!lowerQuery) return 0;
  let score = 0;
  const lowerTitle = node.title.toLowerCase();
  const lowerSummary = node.summary.toLowerCase();
  const lowerId = node.id.toLowerCase();
  const lowerSection = node.section.toLowerCase();

  if (lowerTitle === lowerQuery) score += 100;
  if (lowerId === lowerQuery) score += 90;
  if (lowerTitle.includes(lowerQuery)) score += 40;
  if (lowerSummary.includes(lowerQuery)) score += 20;
  if (lowerSection.includes(lowerQuery)) score += 10;
  if (lowerSection.includes('failure')) score += 5;

  return score;
};

const searchRuntimeShard = (shard, query) => [...shard.nodes]
  .map((node) => ({ node, score: scoreNode(node, query) }))
  .filter((entry) => entry.score > 0)
  .sort((a, b) => b.score - a.score || a.node.title.localeCompare(b.node.title))
  .map((entry) => entry.node);

const listMarkdownFiles = (root) => {
  const entries = fs.readdirSync(root, { withFileTypes: true });
  const result = [];

  for (const entry of entries) {
    const entryPath = path.join(root, entry.name);
    if (entry.isDirectory()) {
      result.push(...listMarkdownFiles(entryPath));
      continue;
    }

    if (entry.isFile() && entry.name.toLowerCase().endsWith('.md')) {
      result.push(normalizePath(entryPath));
    }
  }

  return result;
};

const readDocument = (filePath) => parseDocument(fs.readFileSync(filePath, 'utf8'), filePath);

const writeDocument = (document) => {
  fs.mkdirSync(path.dirname(document.filePath), { recursive: true });
  fs.writeFileSync(document.filePath, serializeDocument(document), 'utf8');
};

const readRuntimeManifest = (projectRoot) => {
  const manifestPath = joinDfmeaPath(projectRoot, 'runtime', 'manifest.json');
  if (!fs.existsSync(manifestPath)) return null;
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
};

const readRuntimeShard = (projectRoot, subtreeId) => {
  const shardDir = joinDfmeaPath(projectRoot, 'runtime', 'shards', subtreeId);
  const metaPath = joinDfmeaPath(shardDir, 'meta.json');
  const nodesPath = joinDfmeaPath(shardDir, 'nodes.json');
  const edgesPath = joinDfmeaPath(shardDir, 'edges.json');
  if (!fs.existsSync(metaPath) || !fs.existsSync(nodesPath) || !fs.existsSync(edgesPath)) return null;

  return {
    meta: JSON.parse(fs.readFileSync(metaPath, 'utf8')),
    nodes: JSON.parse(fs.readFileSync(nodesPath, 'utf8')),
    edges: JSON.parse(fs.readFileSync(edgesPath, 'utf8')),
  };
};

const materializeDfmeaRuntime = (projectRoot) => {
  const layout = buildLayout(projectRoot);
  fs.mkdirSync(layout.runtimeRoot, { recursive: true });
  const markdownFiles = fs.existsSync(layout.contentRoot) ? listMarkdownFiles(layout.contentRoot) : [];
  const documents = markdownFiles.map((filePath) => readDocument(filePath));
  const manifest = buildRuntimeManifest(projectRoot, documents);
  const manifestPath = joinDfmeaPath(projectRoot, 'runtime', 'manifest.json');

  for (const document of documents) {
    const shard = buildRuntimeShard(document);
    const shardDir = joinDfmeaPath(projectRoot, 'runtime', 'shards', document.subtreeId);
    fs.mkdirSync(shardDir, { recursive: true });
    fs.writeFileSync(joinDfmeaPath(shardDir, 'meta.json'), JSON.stringify(shard.meta, null, 2), 'utf8');
    fs.writeFileSync(joinDfmeaPath(shardDir, 'nodes.json'), JSON.stringify(shard.nodes, null, 2), 'utf8');
    fs.writeFileSync(joinDfmeaPath(shardDir, 'edges.json'), JSON.stringify(shard.edges, null, 2), 'utf8');
  }

  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf8');
  return { manifest, manifestPath };
};

const resolveSubtreeSourceFile = (projectRoot, subtreeId) => {
  const manifest = readRuntimeManifest(projectRoot);
  const fromManifest = manifest?.subtrees.find((entry) => entry.subtreeId === subtreeId)?.sourceFile;
  if (fromManifest) return fromManifest;

  const contentRoot = buildLayout(projectRoot).contentRoot;
  if (!fs.existsSync(contentRoot)) return null;

  for (const filePath of listMarkdownFiles(contentRoot)) {
    const document = readDocument(filePath);
    if (document.subtreeId === subtreeId) return filePath;
  }

  return null;
};

const listChangeRecords = (projectRoot) => {
  const changesRoot = joinDfmeaPath(projectRoot, 'changes');
  if (!fs.existsSync(changesRoot)) return [];
  return fs.readdirSync(changesRoot)
    .filter((name) => name.toLowerCase().endsWith('.json'))
    .map((name) => JSON.parse(fs.readFileSync(joinDfmeaPath(changesRoot, name), 'utf8')))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp));
};

const writeChangeRecord = (projectRoot, record) => {
  const filePath = joinDfmeaPath(projectRoot, 'changes', `${record.timestamp.replace(/[:.]/g, '-')}-${record.proposalId}.json`);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(record, null, 2), 'utf8');
  return filePath;
};

export const getDfmeaContext = (projectRoot, subtreeId = null) => {
  const layout = buildLayout(projectRoot);
  return {
    projectRoot: layout.projectRoot,
    contentRoot: layout.contentRoot,
    runtimeRoot: layout.runtimeRoot,
    changesRoot: layout.changesRoot,
    subtreeId,
  };
};

export const searchDfmeaProject = ({ projectRoot, subtreeId = null, query }) => {
  if (!readRuntimeManifest(projectRoot)) {
    materializeDfmeaRuntime(projectRoot);
  }

  const manifest = readRuntimeManifest(projectRoot);
  if (!manifest) {
    return { query, results: [] };
  }

  const subtreeIds = subtreeId ? [subtreeId] : manifest.subtrees.map((entry) => entry.subtreeId);
  const results = [];

  for (const currentSubtreeId of subtreeIds) {
    const shard = readRuntimeShard(projectRoot, currentSubtreeId);
    if (!shard) continue;
    for (const node of searchRuntimeShard(shard, query)) {
      results.push({ subtreeId: currentSubtreeId, node });
    }
  }

  return { query, results };
};

export const applyDfmeaReview = ({ projectRoot, request }) => {
  if (!request?.confirm) {
    throw new Error('DFMEA review-apply requires explicit confirmation');
  }

  const proposal = { ...request.proposal, status: 'confirmed' };
  const sourceFile = resolveSubtreeSourceFile(projectRoot, proposal.subtreeId);
  if (!sourceFile) {
    throw new Error(`Unable to locate subtree source file for ${proposal.subtreeId}`);
  }

  const document = readDocument(sourceFile);
  const sectionsByName = new Map(document.sections.map((section) => [section.name, section]));

  for (const sectionUpdate of request.sections || []) {
    const existing = sectionsByName.get(sectionUpdate.section);
    if (existing) {
      existing.entries = sectionUpdate.entries;
    } else {
      document.sections.push({ name: sectionUpdate.section, entries: sectionUpdate.entries });
    }
  }

  if (Array.isArray(request.notes) && request.notes.length > 0) {
    document.notes = request.notes.map((note) => ({ section: note.section, text: note.note }));
  }

  try {
    writeDocument(document);
    materializeDfmeaRuntime(projectRoot);
    const appliedProposal = { ...proposal, status: 'applied' };
    writeChangeRecord(projectRoot, {
      timestamp: new Date().toISOString(),
      kind: 'review-apply',
      proposalId: appliedProposal.proposalId,
      subtreeId: appliedProposal.subtreeId,
      summary: appliedProposal.summary,
      status: 'applied',
      targetFiles: appliedProposal.targetFiles,
    });

    return {
      proposal: appliedProposal,
      changeRecords: listChangeRecords(projectRoot),
    };
  } catch (error) {
    writeChangeRecord(projectRoot, {
      timestamp: new Date().toISOString(),
      kind: 'review-apply',
      proposalId: proposal.proposalId,
      subtreeId: proposal.subtreeId,
      summary: proposal.summary,
      status: 'failed',
      targetFiles: proposal.targetFiles,
    });
    throw error;
  }
};
