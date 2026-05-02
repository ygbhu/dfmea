import { describe, expect, it } from 'vitest';
import {
  aiDraftStatusValues,
  apiPushEventTypeValues,
  apiPushJobStatusValues,
  capabilityInvocationStatusValues,
  createJsonSchemaValidator,
  draftPatchOperationValues,
  fail,
  getProjectionFreshness,
  platformErrorCodeValues,
  ok,
  runStatusValues,
} from './index';

describe('shared package', () => {
  it('exports locked MVP status values', () => {
    expect(aiDraftStatusValues).toEqual(['pending', 'applied', 'rejected', 'failed']);
    expect(capabilityInvocationStatusValues).toContain('invalid_arguments');
    expect(draftPatchOperationValues).toContain('logical_delete');
    expect(runStatusValues).toContain('waiting_for_capability');
    expect(apiPushJobStatusValues).toContain('pushing');
    expect(apiPushEventTypeValues).toContain('api_push.execute.completed');
    expect(platformErrorCodeValues).toContain('EXPORT_PROJECTION_STALE');
  });

  it('wraps API responses consistently', () => {
    expect(ok({ id: 'project_1' })).toEqual({
      ok: true,
      data: { id: 'project_1' },
    });

    expect(fail({ code: 'VALIDATION_FAILED', message: 'Invalid payload' })).toEqual({
      ok: false,
      error: {
        code: 'VALIDATION_FAILED',
        message: 'Invalid payload',
      },
    });
  });

  it('validates payloads with JSON Schema', () => {
    const validator = createJsonSchemaValidator();
    const schema = {
      type: 'object',
      properties: {
        name: { type: 'string' },
      },
      required: ['name'],
      additionalProperties: false,
    };

    expect(validator.validate(schema, { name: 'Cooling fan' }).status).toBe('valid');

    const invalid = validator.validate(schema, {});
    expect(invalid.status).toBe('invalid');
    expect(invalid.issues[0]?.keyword).toBe('required');
  });

  it('derives projection freshness from workspace revision', () => {
    expect(getProjectionFreshness(2, 2)).toBe('fresh');
    expect(getProjectionFreshness(1, 2)).toBe('stale');
  });
});
