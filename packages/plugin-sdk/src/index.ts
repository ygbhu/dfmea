import type { WorkspaceStatus } from '@dfmea/shared';

export const supportedPluginManifestVersion = '0.1.0';

export interface PluginExecutionContext {
  projectId: string;
  workspaceId: string;
  workspaceStatus?: WorkspaceStatus;
}

export interface PluginSkillHandler<TInput, TOutput> {
  readonly capabilityId: string;
  handle(input: TInput, context: PluginExecutionContext): Promise<TOutput>;
}

export function createPluginCapabilityId(pluginId: string, skillName: string): string {
  return `${pluginId}.${skillName}`;
}

export type PluginCapabilities = Record<string, boolean>;

export interface PluginInfo {
  plugin_id: string;
  name: string;
  version: string;
  domain?: string;
  description?: string;
}

export type PluginSchemaKind =
  | 'artifact'
  | 'edge'
  | 'skill_input'
  | 'skill_output'
  | 'projection'
  | 'export';

export interface PluginSchemaManifestEntry {
  schema_id: string;
  kind: PluginSchemaKind | string;
  version: string;
  path: string;
  description?: string;
}

export interface PluginSkillManifestEntry {
  skill_id: string;
  name: string;
  version: string;
  input_schema: string;
  output_schema: string;
  handler_ref: string;
  description?: string;
  prompt_ref?: string;
  required_projections?: string[];
  required_knowledge?: string[];
  side_effect?: string;
  result_types?: string[];
}

export interface PluginValidatorManifestEntry {
  validator_id: string;
  name: string;
  version: string;
  target: string;
  input_schema: string;
  output_schema: string;
  handler_ref: string;
  severity?: string;
}

export interface PluginProjectionManifestEntry {
  kind: string;
  category: string;
  payload_schema: string;
  handler_ref: string;
  scope: string[];
  vectorizable?: boolean;
}

export interface PluginExporterManifestEntry {
  exporter_id: string;
  name: string;
  version: string;
  source_projection: string;
  input_schema: string;
  output_type: string;
  handler_ref: string;
}

export interface PluginViewManifestEntry {
  view_id: string;
  name: string;
  projection_kind: string;
  view_type: string;
  metadata?: Record<string, unknown>;
}

export interface PluginManifest {
  manifest_version: string;
  plugin: PluginInfo;
  capabilities: PluginCapabilities;
  schemas: PluginSchemaManifestEntry[];
  skills: PluginSkillManifestEntry[];
  validators: PluginValidatorManifestEntry[];
  projections: PluginProjectionManifestEntry[];
  exporters: PluginExporterManifestEntry[];
  views: PluginViewManifestEntry[];
  requirements?: Record<string, unknown>;
  compatibility?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}
