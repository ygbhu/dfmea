import { describe, expect, it } from 'vitest';
import { HealthController } from './health.controller';

describe('HealthController', () => {
  it('returns the API health payload', () => {
    const controller = new HealthController();

    expect(controller.getHealth()).toEqual({
      service: 'dfmea-api',
      status: 'ok',
    });
  });
});
