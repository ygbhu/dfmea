import { HttpException, HttpStatus } from '@nestjs/common';
import { createErrorEnvelope, type ErrorEnvelope, type JsonObject } from '@dfmea/shared';
import {
  AiDraftRepositoryError,
  type AiDraftRepositoryErrorCode,
} from '../../repositories/ai-draft.repository';
import {
  ApiPushServiceError,
  type ApiPushServiceErrorCode,
} from '../../services/api-push.service';
import { ProjectionServiceError } from '../../services/projection.service';

export class PlatformApiException extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details: JsonObject | undefined;
  readonly retryable: boolean | undefined;

  constructor(input: {
    code: string;
    message: string;
    statusCode?: number;
    details?: JsonObject;
    retryable?: boolean;
  }) {
    super(input.message);
    this.name = 'PlatformApiException';
    this.code = input.code;
    this.statusCode = input.statusCode ?? HttpStatus.BAD_REQUEST;
    this.details = input.details;
    this.retryable = input.retryable;
    Object.setPrototypeOf(this, PlatformApiException.prototype);
  }
}

export interface NormalizedApiError {
  statusCode: number;
  envelope: ErrorEnvelope;
}

export function notFound(code: string, message: string, details?: JsonObject): PlatformApiException {
  return new PlatformApiException({
    code,
    message,
    statusCode: HttpStatus.NOT_FOUND,
    ...(details !== undefined ? { details } : {}),
  });
}

export function validationFailed(
  message: string,
  details?: JsonObject,
): PlatformApiException {
  return new PlatformApiException({
    code: 'VALIDATION_FAILED',
    message,
    statusCode: HttpStatus.BAD_REQUEST,
    ...(details !== undefined ? { details } : {}),
  });
}

export function scopeDenied(message: string, details?: JsonObject): PlatformApiException {
  return new PlatformApiException({
    code: 'SCOPE_DENIED',
    message,
    statusCode: HttpStatus.FORBIDDEN,
    ...(details !== undefined ? { details } : {}),
  });
}

export function normalizeApiError(error: unknown): NormalizedApiError {
  if (error instanceof PlatformApiException) {
    return {
      statusCode: error.statusCode,
      envelope: createErrorEnvelope(error.code, error.message, {
        ...(error.details !== undefined ? { details: error.details } : {}),
        ...(error.retryable !== undefined ? { retryable: error.retryable } : {}),
      }),
    };
  }

  if (error instanceof AiDraftRepositoryError) {
    const mapped = mapAiDraftRepositoryError(error);
    return {
      statusCode: mapped.statusCode,
      envelope: createErrorEnvelope(mapped.code, error.message, {
        details: error.details as JsonObject,
      }),
    };
  }

  if (error instanceof ProjectionServiceError) {
    return {
      statusCode: mapProjectionStatusCode(error.code),
      envelope: createErrorEnvelope(error.code, error.message, {
        details: error.details as JsonObject,
        retryable: error.code === 'PROJECTION_REBUILD_FAILED',
      }),
    };
  }

  if (error instanceof ApiPushServiceError) {
    return {
      statusCode: mapApiPushStatusCode(error.code),
      envelope: createErrorEnvelope(error.code, error.message, {
        details: error.details as JsonObject,
        retryable: error.code === 'EXTERNAL_PUSH_FAILED',
      }),
    };
  }

  if (error instanceof HttpException) {
    return normalizeHttpException(error);
  }

  return {
    statusCode: HttpStatus.INTERNAL_SERVER_ERROR,
    envelope: createErrorEnvelope(
      'INTERNAL_SERVER_ERROR',
      error instanceof Error ? error.message : 'Unexpected server error.',
    ),
  };
}

function mapAiDraftRepositoryError(error: AiDraftRepositoryError): {
  code: string;
  statusCode: number;
} {
  const codeMap: Record<AiDraftRepositoryErrorCode, string> = {
    DRAFT_BATCH_NOT_FOUND: 'AI_DRAFT_NOT_FOUND',
    DRAFT_BATCH_NOT_PENDING: readBatchStateCode(error),
    DRAFT_BASE_REVISION_CONFLICT: 'AI_DRAFT_BASE_REVISION_CONFLICT',
    DRAFT_PATCH_INVALID: 'AI_DRAFT_PATCH_INVALID',
    DRAFT_TARGET_NOT_FOUND: 'AI_DRAFT_TARGET_NOT_FOUND',
    PROJECT_NOT_FOUND: 'PROJECT_NOT_FOUND',
  };

  const statusMap: Record<AiDraftRepositoryErrorCode, number> = {
    DRAFT_BATCH_NOT_FOUND: HttpStatus.NOT_FOUND,
    DRAFT_BATCH_NOT_PENDING: HttpStatus.CONFLICT,
    DRAFT_BASE_REVISION_CONFLICT: HttpStatus.CONFLICT,
    DRAFT_PATCH_INVALID: HttpStatus.BAD_REQUEST,
    DRAFT_TARGET_NOT_FOUND: HttpStatus.NOT_FOUND,
    PROJECT_NOT_FOUND: HttpStatus.NOT_FOUND,
  };

  return {
    code: codeMap[error.code],
    statusCode: statusMap[error.code],
  };
}

function readBatchStateCode(error: AiDraftRepositoryError): string {
  if (error.details.status === 'applied') {
    return 'AI_DRAFT_ALREADY_APPLIED';
  }

  if (error.details.status === 'rejected') {
    return 'AI_DRAFT_REJECTED';
  }

  return 'AI_DRAFT_NOT_PENDING';
}

function mapProjectionStatusCode(code: string): number {
  if (code === 'PROJECT_NOT_FOUND' || code === 'PROJECTION_NOT_FOUND') {
    return HttpStatus.NOT_FOUND;
  }

  if (code === 'PROJECTION_STALE') {
    return HttpStatus.CONFLICT;
  }

  if (code === 'PROJECTION_HANDLER_NOT_FOUND') {
    return HttpStatus.BAD_REQUEST;
  }

  return HttpStatus.INTERNAL_SERVER_ERROR;
}

function mapApiPushStatusCode(code: ApiPushServiceErrorCode): number {
  const statusMap: Record<ApiPushServiceErrorCode, number> = {
    PROJECT_NOT_FOUND: HttpStatus.NOT_FOUND,
    API_PUSH_JOB_NOT_FOUND: HttpStatus.NOT_FOUND,
    API_PUSH_RECORD_NOT_FOUND: HttpStatus.NOT_FOUND,
    EXPORT_PROJECTION_STALE: HttpStatus.CONFLICT,
    EXPORT_PAYLOAD_INVALID: HttpStatus.BAD_REQUEST,
    EXPORT_ADAPTER_NOT_FOUND: HttpStatus.BAD_REQUEST,
    EXPORT_IDEMPOTENCY_CONFLICT: HttpStatus.CONFLICT,
    EXTERNAL_VALIDATION_FAILED: HttpStatus.BAD_REQUEST,
    EXTERNAL_PUSH_FAILED: HttpStatus.BAD_GATEWAY,
  };

  return statusMap[code];
}

function normalizeHttpException(error: HttpException): NormalizedApiError {
  const response = error.getResponse();

  if (typeof response === 'object' && response !== null && !Array.isArray(response)) {
    const responseObject = response as Record<string, unknown>;
    const responseMessage = responseObject.message;
    const message = Array.isArray(responseMessage)
      ? responseMessage.join('; ')
      : typeof responseMessage === 'string'
        ? responseMessage
        : error.message;

    return {
      statusCode: error.getStatus(),
      envelope: createErrorEnvelope(readErrorCode(responseObject), message),
    };
  }

  return {
    statusCode: error.getStatus(),
    envelope: createErrorEnvelope('HTTP_ERROR', error.message),
  };
}

function readErrorCode(response: Record<string, unknown>): string {
  const code = response.error;
  return typeof code === 'string' ? code.toUpperCase().replaceAll(' ', '_') : 'HTTP_ERROR';
}
