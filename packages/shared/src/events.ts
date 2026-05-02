import type { IsoDateTimeString, RuntimeEventId, RunId, WorkspaceId } from './ids';
import type { JsonValue } from './json';

export const runtimeEventTypeValues = [
  'runtime.started',
  'runtime.message',
  'runtime.thinking',
  'runtime.capability_invocation.started',
  'runtime.capability_invocation.completed',
  'runtime.result.proposed',
  'runtime.failed',
  'runtime.cancelled',
  'runtime.completed',
] as const;

export type RuntimeEventType = (typeof runtimeEventTypeValues)[number];

export const draftPreviewEventTypeValues = [
  'draft.preview.started',
  'draft.preview.node_upserted',
  'draft.preview.node_updated',
  'draft.preview.edge_upserted',
  'draft.preview.edge_updated',
  'draft.preview.node_removed',
  'draft.preview.edge_removed',
  'draft.preview.validation_updated',
  'draft.preview.evidence_linked',
  'draft.preview.completed',
] as const;
export type DraftPreviewEventType = (typeof draftPreviewEventTypeValues)[number];

export const projectionEventTypeValues = [
  'projection.dirty',
  'projection.stale_detected',
  'projection.rebuild.started',
  'projection.rebuild.completed',
  'projection.rebuild.failed',
] as const;
export type ProjectionEventType = (typeof projectionEventTypeValues)[number];

export const apiPushEventTypeValues = [
  'api_push.job.created',
  'api_push.validation.started',
  'api_push.validation.completed',
  'api_push.execute.started',
  'api_push.execute.completed',
  'api_push.execute.failed',
] as const;
export type ApiPushEventType = (typeof apiPushEventTypeValues)[number];

export const platformEventTypeValues = [
  ...runtimeEventTypeValues,
  ...draftPreviewEventTypeValues,
  ...projectionEventTypeValues,
  ...apiPushEventTypeValues,
] as const;
export type PlatformEventType = (typeof platformEventTypeValues)[number];

export interface EventEnvelope<TPayload extends JsonValue = JsonValue> {
  eventId: RuntimeEventId;
  workspaceId: WorkspaceId;
  eventType: string;
  payload: TPayload;
  createdAt: IsoDateTimeString;
}

export interface RuntimeEventEnvelope<TPayload extends JsonValue = JsonValue>
  extends EventEnvelope<TPayload> {
  runId: RunId;
  eventType: RuntimeEventType | string;
}
