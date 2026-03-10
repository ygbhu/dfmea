export interface DfmeaSubtreeEntry {
  id: string;
  kind: string;
  title: string;
  summary: string;
  refs: string[];
}

export interface DfmeaSubtreeSection {
  name: string;
  entries: DfmeaSubtreeEntry[];
}

export interface DfmeaSubtreeNote {
  section: string;
  text: string;
}

export interface DfmeaSubtreeDocument {
  subtreeId: string;
  filePath: string;
  title: string;
  sections: DfmeaSubtreeSection[];
  notes?: DfmeaSubtreeNote[];
}

export interface DfmeaRuntimeNode {
  id: string;
  kind: string;
  title: string;
  section: string;
  parentId: string | null;
  refIds: string[];
  anchor: string;
  summary: string;
}

export interface DfmeaRuntimeEdge {
  from: string;
  to: string;
  type: 'tree' | 'ref' | 'chain';
}

export interface DfmeaRuntimeShard {
  meta: {
    subtreeId: string;
    sourceFile: string;
    title: string;
    nodeCount: number;
    edgeCount: number;
    version: 1;
  };
  nodes: DfmeaRuntimeNode[];
  edges: DfmeaRuntimeEdge[];
}

export interface DfmeaRuntimeManifest {
  projectId: string;
  updatedAt: string;
  subtrees: Array<{
    subtreeId: string;
    sourceFile: string;
    shardPath: string;
    dirty: boolean;
  }>;
}

function toAnchor(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

export function buildRuntimeShard(document: DfmeaSubtreeDocument): DfmeaRuntimeShard {
  const nodes: DfmeaRuntimeNode[] = [];
  const edges: DfmeaRuntimeEdge[] = [];

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
        edges.push({
          from: entry.id,
          to: refId,
          type: 'ref',
        });
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
}

export function buildRuntimeManifest(projectId: string, documents: DfmeaSubtreeDocument[]): DfmeaRuntimeManifest {
  return {
    projectId,
    updatedAt: new Date().toISOString(),
    subtrees: documents.map((document) => ({
      subtreeId: document.subtreeId,
      sourceFile: document.filePath,
      shardPath: `runtime/shards/${document.subtreeId}`,
      dirty: false,
    })),
  };
}
