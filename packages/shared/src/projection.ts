import type {
  IsoDateTimeString,
  PluginId,
  ProjectId,
  ProjectionId,
  WorkspaceId,
  WorkspaceRevision,
} from './ids';
import type { JsonObject } from './json';
import type { ProjectionFreshness, ProjectionStatus, ValidationStatus } from './statuses';

export const projectionKindValues = ['working', 'draft_preview', 'export', 'test'] as const;
export type ProjectionKind = (typeof projectionKindValues)[number] | string;

export interface ProjectionRecord<TPayload extends JsonObject = JsonObject> {
  projectionId: ProjectionId;
  workspaceId: WorkspaceId;
  projectId: ProjectId;
  pluginId: PluginId;
  projectionKind: ProjectionKind;
  scopeId: string;
  schemaVersion: string;
  sourceRevision: WorkspaceRevision;
  status: ProjectionStatus;
  freshness: ProjectionFreshness;
  validationStatus: ValidationStatus;
  payload: TPayload;
  summary?: string;
  createdAt: IsoDateTimeString;
  updatedAt: IsoDateTimeString;
}

export function getProjectionFreshness(
  sourceRevision: WorkspaceRevision,
  currentWorkspaceRevision: WorkspaceRevision,
): ProjectionFreshness {
  return sourceRevision === currentWorkspaceRevision ? 'fresh' : 'stale';
}
