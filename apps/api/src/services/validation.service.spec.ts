import { describe, expect, it } from 'vitest';
import { ValidationService } from './validation.service';

describe('ValidationService', () => {
  it('validates JSON schema payloads', () => {
    const service = new ValidationService();
    const schema = {
      type: 'object',
      required: ['name'],
      properties: {
        name: { type: 'string' },
      },
      additionalProperties: false,
    };

    expect(service.validateJsonSchema(schema, { name: 'Cooling fan' }).status).toBe('valid');

    const invalid = service.validateJsonSchema(schema, { name: 42 });

    expect(invalid.status).toBe('invalid');
    expect(invalid.issues[0]?.keyword).toBe('type');
  });

  it('treats stale projection as blocking for AI and warning for UI', () => {
    const service = new ValidationService();

    const aiResult = service.validateProjectionFreshness({
      projectionId: 'projection_1',
      sourceRevision: 1,
      currentWorkspaceRevision: 2,
      status: 'stale',
      consumer: 'ai',
    });
    const uiResult = service.validateProjectionFreshness({
      projectionId: 'projection_1',
      sourceRevision: 1,
      currentWorkspaceRevision: 2,
      status: 'stale',
      consumer: 'ui',
    });

    expect(aiResult.status).toBe('failed');
    expect(aiResult.severity).toBe('blocking');
    expect(uiResult.status).toBe('passed');
    expect(uiResult.severity).toBe('warning');
    expect(uiResult.findings[0]?.code).toBe('PROJECTION_STALE');
  });
});
