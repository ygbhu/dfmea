import type {
  ArtifactEdgeId,
  ArtifactId,
  IsoDateTimeString,
  PluginId,
  ProjectId,
  WorkspaceId,
  WorkspaceRevision,
} from './ids';
import type { JsonObject } from './json';
import type { CanonicalRecordStatus } from './statuses';

export type ArtifactType = `${string}.${string}` | string;
export type EdgeType = `${string}.${string}` | string;

export interface ArtifactRecord<TPayload extends JsonObject = JsonObject> {
  artifactId: ArtifactId;
  workspaceId: WorkspaceId;
  projectId: ProjectId;
  pluginId: PluginId;
  artifactType: ArtifactType;
  schemaVersion: string;
  status: CanonicalRecordStatus;
  revision: WorkspaceRevision;
  payload: TPayload;
  createdAt: IsoDateTimeString;
  updatedAt: IsoDateTimeString;
}

export interface ArtifactEdgeRecord<TPayload extends JsonObject = JsonObject> {
  edgeId: ArtifactEdgeId;
  workspaceId: WorkspaceId;
  projectId: ProjectId;
  pluginId: PluginId;
  edgeType: EdgeType;
  sourceArtifactId: ArtifactId;
  targetArtifactId: ArtifactId;
  schemaVersion: string;
  status: CanonicalRecordStatus;
  revision: WorkspaceRevision;
  payload: TPayload;
  createdAt: IsoDateTimeString;
  updatedAt: IsoDateTimeString;
}
