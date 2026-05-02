import type { ErrorEnvelope } from './errors';
import type { CapabilityInvocationId, IsoDateTimeString, ProjectId, RunId, WorkspaceId } from './ids';
import type { JsonObject, JsonSchema, JsonValue } from './json';
import type { CapabilityInvocationStatus } from './statuses';

export interface CapabilityInvocationEnvelope<TArguments extends JsonValue = JsonObject> {
  invocationId: CapabilityInvocationId;
  workspaceId: WorkspaceId;
  runId?: RunId;
  capabilityId: string;
  arguments: TArguments;
  status: CapabilityInvocationStatus;
  timeoutMs: number;
  createdAt: IsoDateTimeString;
}

export interface CapabilityInvocationResult<TResult extends JsonValue = JsonValue> {
  invocationId: CapabilityInvocationId;
  status: CapabilityInvocationStatus;
  result: TResult | null;
  error: ErrorEnvelope | null;
  completedAt: IsoDateTimeString;
}

export interface CapabilityDescriptor {
  capabilityId: string;
  title: string;
  description?: string;
  inputSchemaId?: string;
  outputSchemaId?: string;
  inputSchema?: JsonSchema;
  outputSchema?: JsonSchema;
  requiredScopes: string[];
  kind?: 'platform' | 'plugin_skill' | 'system';
  owner?: string;
  sideEffect?: string;
  timeoutMs?: number;
}

export interface CapabilityManifest {
  workspaceId: WorkspaceId;
  projectId?: ProjectId;
  capabilityIds: string[];
  descriptors: CapabilityDescriptor[];
  createdAt: IsoDateTimeString;
}
