import { Module } from '@nestjs/common';
import { OpenApiController } from './openapi.controller';
import { PlatformApiController } from './platform-api.controller';
import { PlatformApiService } from './platform-api.service';

@Module({
  controllers: [OpenApiController, PlatformApiController],
  providers: [PlatformApiService],
  exports: [PlatformApiService],
})
export class PlatformModule {}
