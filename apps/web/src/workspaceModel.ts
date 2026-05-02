import type { JsonObject, JsonValue } from '@dfmea/shared';
import type {
  DraftPatchRecord,
  DraftPreview,
  DraftPreviewNode,
  PlatformEvent,
  ProjectionReadResult,
  RuntimeEventRecord,
} from './platformApi';

export type TreeSource = 'working' | 'draft';
export type TreeNodeStatus = 'confirmed' | 'candidate_new' | 'candidate_updated' | 'candidate_deleted' | 'applied' | 'rejected' | 'stale';

export interface UiTreeNode {
  id: string;
  source: TreeSource;
  label: string;
  type: string;
  status: TreeNodeStatus;
  depth: number;
  markers: string[];
  badgeText: string[];
}

interface WorkingTreeNode extends JsonObject {
  artifact_id: string;
  type: string;
  title: string;
  display_id?: string;
  badges?: JsonObject;
  children?: WorkingTreeNode[];
}

export function buildWorkingTree(projection: ProjectionReadResult | null): UiTreeNode[] {
  if (projection === null) {
    return [];
  }

  const roots = readWorkingRoots(projection.projection.payload);
  const freshnessMarker = projection.freshness === 'stale' ? ['stale'] : [];
  const seenArtifactIds = new Set<string>();

  return roots.flatMap((node) => flattenWorkingNode(node, 0, freshnessMarker, seenArtifactIds));
}

export function buildDraftTree(preview: DraftPreview | null): UiTreeNode[] {
  if (preview === null) {
    return [];
  }

  return preview.nodes.map((node) => ({
    id: node.tempRef ?? node.targetId ?? node.draftPatchId,
    source: 'draft',
    label: readNodeLabel(node),
    type: node.artifactType ?? 'draft.artifact',
    status: draftStatus(node),
    depth: 0,
    markers: draftMarkers(node),
    badgeText: readBadgeText(node.payload),
  }));
}

export function eventLabel(event: RuntimeEventRecord | PlatformEvent): string {
  const eventType = readEventType(event);
  const payload = readPayload(event);

  if (eventType === 'runtime.started') {
    return `Run started: ${readString(payload.goal) ?? 'goal accepted'}`;
  }

  if (eventType === 'runtime.message') {
    return readString(payload.message) ?? 'Runtime message';
  }

  if (eventType === 'runtime.capability_invocation.started') {
    return `Capability started: ${readString(payload.capability_id) ?? 'unknown capability'}`;
  }

  if (eventType === 'runtime.capability_invocation.completed') {
    return `Capability completed: ${readString(payload.status) ?? 'completed'}`;
  }

  if (eventType === 'runtime.result.proposed') {
    return `Draft proposed: ${readString(payload.draft_batch_id) ?? 'new draft'}`;
  }

  if (eventType === 'runtime.completed') {
    return 'Run completed';
  }

  if (eventType === 'ai_draft.applied') {
    return `Draft applied: revision ${readNumber(payload.to_revision) ?? ''}`.trim();
  }

  return eventType;
}

export function patchLabel(patch: DraftPatchRecord): string {
  const payload = patch.afterPayload ?? patch.payloadPatch ?? {};
  return readString(payload.title) ?? readString(payload.name) ?? patch.artifactType ?? patch.relationType ?? patch.patchType;
}

export function readEventType(event: RuntimeEventRecord | PlatformEvent): string {
  const candidate = event as PlatformEvent;

  return typeof candidate.eventType === 'string'
    ? candidate.eventType
    : typeof candidate.event_type === 'string'
      ? candidate.event_type
      : 'event';
}

function flattenWorkingNode(
  node: WorkingTreeNode,
  depth: number,
  inheritedMarkers: string[],
  seenArtifactIds: Set<string>,
): UiTreeNode[] {
  if (seenArtifactIds.has(node.artifact_id)) {
    return [];
  }

  seenArtifactIds.add(node.artifact_id);

  const current: UiTreeNode = {
    id: node.artifact_id,
    source: 'working',
    label: node.title,
    type: node.type,
    status: inheritedMarkers.includes('stale') ? 'stale' : 'confirmed',
    depth,
    markers: inheritedMarkers,
    badgeText: readBadgeText(node.badges ?? {}),
  };
  const children = node.children ?? [];

  return [
    current,
    ...children.flatMap((child) =>
      flattenWorkingNode(child, depth + 1, inheritedMarkers, seenArtifactIds),
    ),
  ];
}

function readWorkingRoots(payload: JsonObject): WorkingTreeNode[] {
  const roots = payload.roots;

  if (!Array.isArray(roots)) {
    return [];
  }

  return roots.filter(isWorkingTreeNode);
}

function isWorkingTreeNode(value: JsonValue): value is WorkingTreeNode {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return false;
  }

  return (
    typeof value.artifact_id === 'string' &&
    typeof value.type === 'string' &&
    typeof value.title === 'string'
  );
}

function readNodeLabel(node: DraftPreviewNode): string {
  return readString(node.payload.title) ?? readString(node.payload.name) ?? node.artifactType ?? 'Draft artifact';
}

function draftStatus(node: DraftPreviewNode): TreeNodeStatus {
  if (node.status === 'applied') {
    return 'applied';
  }

  if (node.status === 'rejected') {
    return 'rejected';
  }

  if (node.operation === 'update_artifact') {
    return 'candidate_updated';
  }

  if (node.operation === 'logical_delete') {
    return 'candidate_deleted';
  }

  return 'candidate_new';
}

function draftMarkers(node: DraftPreviewNode): string[] {
  if (node.operation === 'update_artifact') {
    return ['updated'];
  }

  if (node.operation === 'logical_delete') {
    return ['deleted'];
  }

  return ['new'];
}

function readBadgeText(value: JsonObject): string[] {
  return Object.entries(value)
    .filter((entry): entry is [string, string | number | boolean] => {
      const [, item] = entry;
      return typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean';
    })
    .map(([key, item]) => `${key}: ${String(item)}`);
}

function readPayload(event: RuntimeEventRecord | PlatformEvent): JsonObject {
  const payload = event.payload;

  if (typeof payload === 'object' && payload !== null && !Array.isArray(payload)) {
    return payload;
  }

  return {};
}

function readString(value: JsonValue | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function readNumber(value: JsonValue | undefined): number | undefined {
  return typeof value === 'number' ? value : undefined;
}
