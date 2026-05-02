import { Injectable } from '@nestjs/common';
import { createPluginCapabilityId } from '@dfmea/plugin-sdk';
import type {
  PluginExporterManifestEntry,
  PluginManifest,
  PluginProjectionManifestEntry,
  PluginSchemaManifestEntry,
  PluginSkillManifestEntry,
  PluginValidatorManifestEntry,
  PluginViewManifestEntry,
} from '@dfmea/plugin-sdk';
import { PluginLoadError } from './plugin-load-error';

export interface LoadedSchemaDefinition extends PluginSchemaManifestEntry {
  pluginId: string;
  pluginVersion: string;
  schemaPath: string;
}

export interface LoadedSkillDefinition extends PluginSkillManifestEntry {
  pluginId: string;
  pluginVersion: string;
  capabilityId: string;
  handlerPath: string;
  promptPath?: string;
  inputSchema: LoadedSchemaDefinition;
  outputSchema: LoadedSchemaDefinition;
}

export interface LoadedValidatorDefinition extends PluginValidatorManifestEntry {
  pluginId: string;
  pluginVersion: string;
  handlerPath: string;
  inputSchema: LoadedSchemaDefinition;
  outputSchema: LoadedSchemaDefinition;
}

export interface LoadedProjectionDefinition extends PluginProjectionManifestEntry {
  pluginId: string;
  pluginVersion: string;
  handlerPath: string;
  payloadSchema: LoadedSchemaDefinition;
}

export interface LoadedExporterDefinition extends PluginExporterManifestEntry {
  pluginId: string;
  pluginVersion: string;
  handlerPath: string;
  inputSchema: LoadedSchemaDefinition;
  sourceProjection: LoadedProjectionDefinition;
}

export interface LoadedViewDefinition extends PluginViewManifestEntry {
  pluginId: string;
  pluginVersion: string;
  projection: LoadedProjectionDefinition;
}

export interface LoadedPluginDefinition {
  pluginId: string;
  pluginVersion: string;
  name: string;
  pluginRoot: string;
  manifest: PluginManifest;
  schemas: LoadedSchemaDefinition[];
  skills: LoadedSkillDefinition[];
  validators: LoadedValidatorDefinition[];
  projections: LoadedProjectionDefinition[];
  exporters: LoadedExporterDefinition[];
  views: LoadedViewDefinition[];
}

@Injectable()
export class PluginRegistryService {
  private readonly plugins = new Map<string, LoadedPluginDefinition>();
  private readonly skills = new Map<string, LoadedSkillDefinition>();
  private readonly validators = new Map<string, LoadedValidatorDefinition>();
  private readonly projections = new Map<string, LoadedProjectionDefinition>();
  private readonly exporters = new Map<string, LoadedExporterDefinition>();
  private readonly views = new Map<string, LoadedViewDefinition>();

  clear(): void {
    this.plugins.clear();
    this.skills.clear();
    this.validators.clear();
    this.projections.clear();
    this.exporters.clear();
    this.views.clear();
  }

  registerPlugin(plugin: LoadedPluginDefinition): void {
    if (this.plugins.has(plugin.pluginId)) {
      throw new PluginLoadError('PLUGIN_ID_DUPLICATED', 'Plugin id is duplicated.', {
        plugin_id: plugin.pluginId,
      });
    }

    this.plugins.set(plugin.pluginId, plugin);

    for (const skill of plugin.skills) {
      this.skills.set(this.resourceKey(plugin.pluginId, skill.skill_id), skill);
    }

    for (const validator of plugin.validators) {
      this.validators.set(this.resourceKey(plugin.pluginId, validator.validator_id), validator);
    }

    for (const projection of plugin.projections) {
      this.projections.set(this.resourceKey(plugin.pluginId, projection.kind), projection);
    }

    for (const exporter of plugin.exporters) {
      this.exporters.set(this.resourceKey(plugin.pluginId, exporter.exporter_id), exporter);
    }

    for (const view of plugin.views) {
      this.views.set(this.resourceKey(plugin.pluginId, view.view_id), view);
    }
  }

  getPlugin(pluginId: string): LoadedPluginDefinition | undefined {
    return this.plugins.get(pluginId);
  }

  listPlugins(): LoadedPluginDefinition[] {
    return [...this.plugins.values()];
  }

  getSkill(pluginId: string, skillId: string): LoadedSkillDefinition | undefined {
    return this.skills.get(this.resourceKey(pluginId, skillId));
  }

  getSkillByCapabilityId(capabilityId: string): LoadedSkillDefinition | undefined {
    return [...this.skills.values()].find((skill) => skill.capabilityId === capabilityId);
  }

  listSkills(pluginId?: string): LoadedSkillDefinition[] {
    return this.filterByPlugin([...this.skills.values()], pluginId);
  }

  getProjection(pluginId: string, kind: string): LoadedProjectionDefinition | undefined {
    return this.projections.get(this.resourceKey(pluginId, kind));
  }

  listProjections(pluginId?: string): LoadedProjectionDefinition[] {
    return this.filterByPlugin([...this.projections.values()], pluginId);
  }

  getExporter(pluginId: string, exporterId: string): LoadedExporterDefinition | undefined {
    return this.exporters.get(this.resourceKey(pluginId, exporterId));
  }

  listExporters(pluginId?: string): LoadedExporterDefinition[] {
    return this.filterByPlugin([...this.exporters.values()], pluginId);
  }

  listViews(pluginId?: string): LoadedViewDefinition[] {
    return this.filterByPlugin([...this.views.values()], pluginId);
  }

  createSkillCapabilityId(pluginId: string, skillId: string): string {
    return createPluginCapabilityId(pluginId, skillId);
  }

  private resourceKey(pluginId: string, localId: string): string {
    return `${pluginId}.${localId}`;
  }

  private filterByPlugin<T extends { pluginId: string }>(items: T[], pluginId?: string): T[] {
    if (pluginId === undefined) {
      return items;
    }

    return items.filter((item) => item.pluginId === pluginId);
  }
}
