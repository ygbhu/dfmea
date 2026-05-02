export const workspaceStatusValues = ['active', 'archived'] as const;
export type WorkspaceStatus = (typeof workspaceStatusValues)[number];

export const projectStatusValues = ['active', 'archived'] as const;
export type ProjectStatus = (typeof projectStatusValues)[number];

export const runStatusValues = [
  'created',
  'starting',
  'running',
  'waiting_for_input',
  'waiting_for_capability',
  'completed',
  'failed',
  'cancelled',
  'timeout',
] as const;
export type RunStatus = (typeof runStatusValues)[number];

export const capabilityInvocationStatusValues = [
  'accepted',
  'running',
  'completed',
  'failed',
  'cancelled',
  'timeout',
  'denied',
  'invalid_arguments',
] as const;
export type CapabilityInvocationStatus = (typeof capabilityInvocationStatusValues)[number];

export const aiDraftStatusValues = ['pending', 'applied', 'rejected', 'failed'] as const;
export type AiDraftStatus = (typeof aiDraftStatusValues)[number];

export const draftPatchStatusValues = ['pending', 'applied', 'rejected', 'failed'] as const;
export type DraftPatchStatus = (typeof draftPatchStatusValues)[number];

export const canonicalRecordStatusValues = ['active', 'logically_deleted'] as const;
export type CanonicalRecordStatus = (typeof canonicalRecordStatusValues)[number];

export const projectionStatusValues = ['fresh', 'stale', 'rebuilding', 'failed'] as const;
export type ProjectionStatus = (typeof projectionStatusValues)[number];

export const projectionFreshnessValues = ['fresh', 'stale'] as const;
export type ProjectionFreshness = (typeof projectionFreshnessValues)[number];

export const validationStatusValues = ['not_validated', 'valid', 'invalid'] as const;
export type ValidationStatus = (typeof validationStatusValues)[number];

export const apiPushModeValues = ['validate_only', 'execute'] as const;
export type ApiPushMode = (typeof apiPushModeValues)[number];

export const apiPushJobStatusValues = [
  'created',
  'validating',
  'validation_failed',
  'ready_to_push',
  'pushing',
  'completed',
  'failed',
  'partial_failed',
  'cancelled',
] as const;
export type ApiPushJobStatus = (typeof apiPushJobStatusValues)[number];

export function isCapabilityInvocationStatus(value: string): value is CapabilityInvocationStatus {
  return capabilityInvocationStatusValues.includes(value as CapabilityInvocationStatus);
}
