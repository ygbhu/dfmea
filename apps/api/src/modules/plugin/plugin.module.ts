import { Module } from '@nestjs/common';
import { PluginLoaderService } from './plugin-loader.service';
import { PluginRegistryService } from './plugin-registry.service';

@Module({
  providers: [PluginRegistryService, PluginLoaderService],
  exports: [PluginRegistryService, PluginLoaderService],
})
export class PluginModule {}
