import type { ErrorEnvelope, ValidationResult } from './errors';
import type {
  AiDraftBatchId,
  ArtifactEdgeId,
  ArtifactId,
  DraftPatchId,
  IsoDateTimeString,
  ProjectId,
  RunId,
  UserId,
  WorkspaceId,
  WorkspaceRevision,
} from './ids';
import type { JsonObject } from './json';
import type { AiDraftStatus, DraftPatchStatus } from './statuses';

export const draftPatchOperationValues = [
  'create_artifact',
  'update_artifact',
  'create_edge',
  'update_edge',
  'logical_delete',
] as const;

export type DraftPatchOperation = (typeof draftPatchOperationValues)[number];

export const draftPatchTargetTypeValues = ['artifact', 'edge'] as const;
export type DraftPatchTargetType = (typeof draftPatchTargetTypeValues)[number];

export interface AiDraftBatchRecord {
  draftBatchId: AiDraftBatchId;
  workspaceId: WorkspaceId;
  projectId: ProjectId;
  runId?: RunId;
  goal: string;
  status: AiDraftStatus;
  baseWorkspaceRevision: WorkspaceRevision;
  targetWorkspaceRevision?: WorkspaceRevision;
  error?: ErrorEnvelope;
  createdBy?: UserId;
  appliedBy?: UserId;
  rejectedBy?: UserId;
  createdAt: IsoDateTimeString;
  updatedAt: IsoDateTimeString;
  appliedAt?: IsoDateTimeString;
  rejectedAt?: IsoDateTimeString;
}

export interface DraftPatchRecord<TPayload extends JsonObject = JsonObject> {
  draftPatchId: DraftPatchId;
  draftBatchId: AiDraftBatchId;
  operation: DraftPatchOperation;
  targetType: DraftPatchTargetType;
  targetId?: ArtifactId | ArtifactEdgeId;
  tempRef?: string;
  beforePayload?: TPayload;
  afterPayload?: TPayload;
  status: DraftPatchStatus;
  validationResult?: ValidationResult;
  appliedResult?: JsonObject;
  createdAt: IsoDateTimeString;
  updatedAt: IsoDateTimeString;
}

export interface AiDraftProposal {
  goal: string;
  baseWorkspaceRevision: WorkspaceRevision;
  patches: DraftPatchRecord[];
}
