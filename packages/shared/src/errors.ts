import type { JsonObject } from './json';

export interface ErrorEnvelope {
  code: string;
  message: string;
  details?: JsonObject;
  retryable?: boolean;
}

export const platformErrorCodeValues = [
  'VALIDATION_FAILED',
  'SCOPE_DENIED',
  'WORKSPACE_NOT_FOUND',
  'PROJECT_NOT_FOUND',
  'SESSION_NOT_FOUND',
  'RUN_NOT_FOUND',
  'CAPABILITY_INVOCATION_NOT_FOUND',
  'AI_DRAFT_NOT_FOUND',
  'AI_DRAFT_PATCH_NOT_FOUND',
  'AI_DRAFT_ALREADY_APPLIED',
  'AI_DRAFT_REJECTED',
  'AI_DRAFT_BASE_REVISION_CONFLICT',
  'AI_DRAFT_PATCH_INVALID',
  'AI_DRAFT_TARGET_NOT_FOUND',
  'PROJECTION_NOT_FOUND',
  'PROJECTION_HANDLER_NOT_FOUND',
  'PROJECTION_STALE',
  'PROJECTION_REBUILD_FAILED',
  'API_PUSH_JOB_NOT_FOUND',
  'API_PUSH_RECORD_NOT_FOUND',
  'EXPORT_PROJECTION_MISSING',
  'EXPORT_PROJECTION_STALE',
  'EXPORT_PAYLOAD_INVALID',
  'EXPORT_ADAPTER_NOT_FOUND',
  'EXPORT_ADAPTER_UNAVAILABLE',
  'EXPORT_IDEMPOTENCY_CONFLICT',
  'EXTERNAL_VALIDATION_FAILED',
  'EXTERNAL_PUSH_FAILED',
  'INTERNAL_WRITE_FAILED',
  'INTERNAL_SERVER_ERROR',
] as const;
export type PlatformErrorCode = (typeof platformErrorCodeValues)[number];

export interface ValidationIssue {
  instancePath: string;
  schemaPath: string;
  message: string;
  keyword: string;
  params: JsonObject;
}

export interface ValidationResult {
  status: 'valid' | 'invalid';
  issues: ValidationIssue[];
}

export const validationSeverityValues = ['blocking', 'warning', 'info'] as const;
export type ValidationSeverity = (typeof validationSeverityValues)[number];

export interface ValidationFinding {
  code: string;
  severity: ValidationSeverity;
  targetType: string;
  targetId?: string;
  message: string;
  details?: JsonObject;
}

export interface StructuredValidationResult {
  status: 'passed' | 'failed';
  severity: ValidationSeverity;
  summary: string;
  findings: ValidationFinding[];
}

export function createErrorEnvelope(
  code: string,
  message: string,
  options: { details?: JsonObject; retryable?: boolean } = {},
): ErrorEnvelope {
  return {
    code,
    message,
    ...(options.details ? { details: options.details } : {}),
    ...(typeof options.retryable === 'boolean' ? { retryable: options.retryable } : {}),
  };
}
