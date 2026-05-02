import { Module } from '@nestjs/common';
import { HealthController } from './health/health.controller';
import { PluginModule } from './modules/plugin/plugin.module';
import { PlatformModule } from './modules/platform/platform.module';

@Module({
  imports: [PluginModule, PlatformModule],
  controllers: [HealthController],
})
export class AppModule {}
