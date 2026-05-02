import { Controller, Get } from '@nestjs/common';
import type { HealthCheckResponse } from '@dfmea/shared';

export type HealthResponse = HealthCheckResponse & {
  service: 'dfmea-api';
};

@Controller('health')
export class HealthController {
  @Get()
  getHealth(): HealthResponse {
    return {
      service: 'dfmea-api',
      status: 'ok',
    };
  }
}
