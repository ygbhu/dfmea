import { Inject, Injectable } from '@nestjs/common';
import type { OnModuleInit } from '@nestjs/common';
import { readdir, readFile, stat } from 'node:fs/promises';
import { accessSync, constants } from 'node:fs';
import { isAbsolute, relative, resolve } from 'node:path';
import {
  createPluginCapabilityId,
  supportedPluginManifestVersion,
  type PluginCapabilities,
  type PluginExporterManifestEntry,
  type PluginInfo,
  type PluginManifest,
  type PluginProjectionManifestEntry,
  type PluginSchemaManifestEntry,
  type PluginSkillManifestEntry,
  type PluginValidatorManifestEntry,
  type PluginViewManifestEntry,
} from '@dfmea/plugin-sdk';
import { PluginLoadError } from './plugin-load-error';
import { PluginRegistryService } from './plugin-registry.service';
import type {
  LoadedPluginDefinition,
  LoadedProjectionDefinition,
  LoadedSchemaDefinition,
  LoadedSkillDefinition,
} from './plugin-registry.service';

const semverPattern = /^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$/;

@Injectable()
export class PluginLoaderService implements OnModuleInit {
  constructor(@Inject(PluginRegistryService) private readonly registry: PluginRegistryService) {}

  async onModuleInit(): Promise<void> {
    await this.loadPlugins(resolveDefaultPluginDir());
  }

  async loadPlugins(pluginDir: string = resolveDefaultPluginDir()): Promise<PluginRegistryService> {
    const pluginRoots = await this.findPluginRoots(pluginDir);
    const loadedPlugins: LoadedPluginDefinition[] = [];
    const pluginIds = new Set<string>();

    for (const pluginRoot of pluginRoots) {
      const plugin = await this.loadPlugin(pluginRoot);

      if (pluginIds.has(plugin.pluginId)) {
        throw new PluginLoadError('PLUGIN_ID_DUPLICATED', 'Plugin id is duplicated.', {
          plugin_id: plugin.pluginId,
          plugin_root: pluginRoot,
        });
      }

      pluginIds.add(plugin.pluginId);
      loadedPlugins.push(plugin);
    }

    this.registry.clear();

    for (const plugin of loadedPlugins) {
      this.registry.registerPlugin(plugin);
    }

    return this.registry;
  }

  private async findPluginRoots(pluginDir: string): Promise<string[]> {
    if (!(await directoryExists(pluginDir))) {
      throw new PluginLoadError('PLUGIN_DIR_NOT_FOUND', 'Plugin directory does not exist.', {
        plugin_dir: pluginDir,
      });
    }

    const entries = await readdir(pluginDir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => resolve(pluginDir, entry.name))
      .sort((left, right) => left.localeCompare(right));
  }

  private async loadPlugin(pluginRoot: string): Promise<LoadedPluginDefinition> {
    const manifestPath = resolve(pluginRoot, 'plugin.json');

    if (!(await fileExists(manifestPath))) {
      throw new PluginLoadError('PLUGIN_MANIFEST_NOT_FOUND', 'Plugin manifest does not exist.', {
        plugin_root: pluginRoot,
        manifest_path: manifestPath,
      });
    }

    const manifest = parsePluginManifest(await readManifestJson(manifestPath), manifestPath);
    const pluginId = manifest.plugin.plugin_id;
    const pluginVersion = manifest.plugin.version;
    const schemaById = new Map<string, LoadedSchemaDefinition>();
    const projectionByKind = new Map<string, LoadedProjectionDefinition>();

    const schemas = await Promise.all(
      manifest.schemas.map(async (schema) => {
        assertUnique(schemaById, schema.schema_id, 'schema_id', pluginId);
        const schemaPath = await requirePluginFile(
          pluginRoot,
          schema.path,
          'PLUGIN_SCHEMA_NOT_FOUND',
          'Schema file does not exist.',
          { plugin_id: pluginId, schema_id: schema.schema_id, path: schema.path },
        );
        const loadedSchema: LoadedSchemaDefinition = {
          ...schema,
          pluginId,
          pluginVersion,
          schemaPath,
        };
        schemaById.set(schema.schema_id, loadedSchema);
        return loadedSchema;
      }),
    );

    const skills = await Promise.all(
      manifest.skills.map(async (skill) => {
        const inputSchema = requireSchema(schemaById, skill.input_schema, pluginId, 'skill', skill.skill_id);
        const outputSchema = requireSchema(schemaById, skill.output_schema, pluginId, 'skill', skill.skill_id);
        const handlerPath = await requirePluginFile(
          pluginRoot,
          skill.handler_ref,
          'PLUGIN_HANDLER_NOT_FOUND',
          'Skill handler file does not exist.',
          { plugin_id: pluginId, skill_id: skill.skill_id, handler_ref: skill.handler_ref },
        );
        const capabilityId = createPluginCapabilityId(pluginId, skill.skill_id);
        const loadedSkill: LoadedSkillDefinition = {
          ...skill,
          pluginId,
          pluginVersion,
          capabilityId,
          handlerPath,
          inputSchema,
          outputSchema,
        };

        if (skill.prompt_ref !== undefined) {
          loadedSkill.promptPath = await requirePluginFile(
            pluginRoot,
            skill.prompt_ref,
            'PLUGIN_REFERENCE_INVALID',
            'Skill prompt file does not exist.',
            { plugin_id: pluginId, skill_id: skill.skill_id, prompt_ref: skill.prompt_ref },
          );
        }

        return loadedSkill;
      }),
    );

    const validators = await Promise.all(
      manifest.validators.map(async (validator) => {
        const inputSchema = requireSchema(
          schemaById,
          validator.input_schema,
          pluginId,
          'validator',
          validator.validator_id,
        );
        const outputSchema = requireSchema(
          schemaById,
          validator.output_schema,
          pluginId,
          'validator',
          validator.validator_id,
        );
        const handlerPath = await requirePluginFile(
          pluginRoot,
          validator.handler_ref,
          'PLUGIN_HANDLER_NOT_FOUND',
          'Validator handler file does not exist.',
          {
            plugin_id: pluginId,
            validator_id: validator.validator_id,
            handler_ref: validator.handler_ref,
          },
        );

        return {
          ...validator,
          pluginId,
          pluginVersion,
          handlerPath,
          inputSchema,
          outputSchema,
        };
      }),
    );

    const projections = await Promise.all(
      manifest.projections.map(async (projection) => {
        assertUnique(projectionByKind, projection.kind, 'projection_kind', pluginId);
        const payloadSchema = requireSchema(
          schemaById,
          projection.payload_schema,
          pluginId,
          'projection',
          projection.kind,
        );
        const handlerPath = await requirePluginFile(
          pluginRoot,
          projection.handler_ref,
          'PLUGIN_HANDLER_NOT_FOUND',
          'Projection handler file does not exist.',
          { plugin_id: pluginId, projection_kind: projection.kind, handler_ref: projection.handler_ref },
        );

        const loadedProjection: LoadedProjectionDefinition = {
          ...projection,
          pluginId,
          pluginVersion,
          handlerPath,
          payloadSchema,
        };
        projectionByKind.set(projection.kind, loadedProjection);
        return loadedProjection;
      }),
    );

    const exporters = await Promise.all(
      manifest.exporters.map(async (exporter) => {
        const sourceProjection = projectionByKind.get(exporter.source_projection);

        if (sourceProjection === undefined) {
          throw new PluginLoadError('PLUGIN_REFERENCE_INVALID', 'Exporter source projection does not exist.', {
            plugin_id: pluginId,
            exporter_id: exporter.exporter_id,
            source_projection: exporter.source_projection,
          });
        }

        const inputSchema = requireSchema(
          schemaById,
          exporter.input_schema,
          pluginId,
          'exporter',
          exporter.exporter_id,
        );
        const handlerPath = await requirePluginFile(
          pluginRoot,
          exporter.handler_ref,
          'PLUGIN_HANDLER_NOT_FOUND',
          'Exporter handler file does not exist.',
          { plugin_id: pluginId, exporter_id: exporter.exporter_id, handler_ref: exporter.handler_ref },
        );

        return {
          ...exporter,
          pluginId,
          pluginVersion,
          handlerPath,
          inputSchema,
          sourceProjection,
        };
      }),
    );

    const views = manifest.views.map((view) => {
      const projection = projectionByKind.get(view.projection_kind);

      if (projection === undefined) {
        throw new PluginLoadError('PLUGIN_REFERENCE_INVALID', 'View projection kind does not exist.', {
          plugin_id: pluginId,
          view_id: view.view_id,
          projection_kind: view.projection_kind,
        });
      }

      return {
        ...view,
        pluginId,
        pluginVersion,
        projection,
      };
    });

    return {
      pluginId,
      pluginVersion,
      name: manifest.plugin.name,
      pluginRoot,
      manifest,
      schemas,
      skills,
      validators,
      projections,
      exporters,
      views,
    };
  }
}

export function resolveDefaultPluginDir(): string {
  if (process.env.PLUGIN_DIR !== undefined && process.env.PLUGIN_DIR.trim() !== '') {
    return resolve(process.env.PLUGIN_DIR);
  }

  const cwdPluginDir = resolve(process.cwd(), 'plugins');
  const workspacePluginDir = resolve(process.cwd(), '..', '..', 'plugins');

  return fileExistsSync(cwdPluginDir) ? cwdPluginDir : workspacePluginDir;
}

function parsePluginManifest(value: unknown, manifestPath: string): PluginManifest {
  if (!isRecord(value)) {
    throw invalidManifest(manifestPath, 'Manifest root must be an object.');
  }

  const manifestVersion = readRequiredString(value, 'manifest_version', manifestPath);

  if (manifestVersion !== supportedPluginManifestVersion) {
    throw invalidManifest(manifestPath, 'Plugin manifest version is not supported.', {
      manifest_version: manifestVersion,
      supported_manifest_version: supportedPluginManifestVersion,
    });
  }

  const pluginRecord = readRequiredRecord(value, 'plugin', manifestPath);
  const plugin = parsePluginInfo(pluginRecord, manifestPath);

  if (!semverPattern.test(plugin.version)) {
    throw new PluginLoadError('PLUGIN_VERSION_INVALID', 'Plugin version is invalid.', {
      manifest_path: manifestPath,
      plugin_id: plugin.plugin_id,
      version: plugin.version,
    });
  }

  return {
    manifest_version: manifestVersion,
    plugin,
    capabilities: parseCapabilities(readRequiredRecord(value, 'capabilities', manifestPath), manifestPath),
    schemas: readRequiredArray(value, 'schemas', manifestPath).map((entry, index) =>
      parseSchemaEntry(entry, manifestPath, index),
    ),
    skills: readRequiredArray(value, 'skills', manifestPath).map((entry, index) =>
      parseSkillEntry(entry, manifestPath, index),
    ),
    validators: readRequiredArray(value, 'validators', manifestPath).map((entry, index) =>
      parseValidatorEntry(entry, manifestPath, index),
    ),
    projections: readRequiredArray(value, 'projections', manifestPath).map((entry, index) =>
      parseProjectionEntry(entry, manifestPath, index),
    ),
    exporters: readRequiredArray(value, 'exporters', manifestPath).map((entry, index) =>
      parseExporterEntry(entry, manifestPath, index),
    ),
    views: readRequiredArray(value, 'views', manifestPath).map((entry, index) =>
      parseViewEntry(entry, manifestPath, index),
    ),
    ...optionalRecordProperty(value, 'requirements', manifestPath),
    ...optionalRecordProperty(value, 'compatibility', manifestPath),
    ...optionalRecordProperty(value, 'metadata', manifestPath),
  };
}

function parsePluginInfo(value: Record<string, unknown>, manifestPath: string): PluginInfo {
  const plugin: PluginInfo = {
    plugin_id: readRequiredString(value, 'plugin_id', manifestPath),
    name: readRequiredString(value, 'name', manifestPath),
    version: readRequiredString(value, 'version', manifestPath),
  };
  const domain = readOptionalString(value, 'domain', manifestPath);
  const description = readOptionalString(value, 'description', manifestPath);

  if (domain !== undefined) {
    plugin.domain = domain;
  }

  if (description !== undefined) {
    plugin.description = description;
  }

  return plugin;
}

function parseCapabilities(value: Record<string, unknown>, manifestPath: string): PluginCapabilities {
  const capabilities: PluginCapabilities = {};

  for (const [key, capabilityValue] of Object.entries(value)) {
    if (typeof capabilityValue !== 'boolean') {
      throw invalidManifest(manifestPath, 'Plugin capability values must be booleans.', {
        capability: key,
      });
    }

    capabilities[key] = capabilityValue;
  }

  return capabilities;
}

function parseSchemaEntry(
  value: unknown,
  manifestPath: string,
  index: number,
): PluginSchemaManifestEntry {
  const entry = readArrayObject(value, manifestPath, 'schemas', index);
  const schema: PluginSchemaManifestEntry = {
    schema_id: readRequiredString(entry, 'schema_id', manifestPath),
    kind: readRequiredString(entry, 'kind', manifestPath),
    version: readRequiredString(entry, 'version', manifestPath),
    path: readRequiredString(entry, 'path', manifestPath),
  };
  const description = readOptionalString(entry, 'description', manifestPath);

  if (description !== undefined) {
    schema.description = description;
  }

  return schema;
}

function parseSkillEntry(value: unknown, manifestPath: string, index: number): PluginSkillManifestEntry {
  const entry = readArrayObject(value, manifestPath, 'skills', index);
  const skill: PluginSkillManifestEntry = {
    skill_id: readRequiredString(entry, 'skill_id', manifestPath),
    name: readRequiredString(entry, 'name', manifestPath),
    version: readRequiredString(entry, 'version', manifestPath),
    input_schema: readRequiredString(entry, 'input_schema', manifestPath),
    output_schema: readRequiredString(entry, 'output_schema', manifestPath),
    handler_ref: readRequiredString(entry, 'handler_ref', manifestPath),
  };
  const description = readOptionalString(entry, 'description', manifestPath);
  const promptRef = readOptionalString(entry, 'prompt_ref', manifestPath);
  const sideEffect = readOptionalString(entry, 'side_effect', manifestPath);
  const requiredProjections = readOptionalStringArray(entry, 'required_projections', manifestPath);
  const requiredKnowledge = readOptionalStringArray(entry, 'required_knowledge', manifestPath);
  const resultTypes = readOptionalStringArray(entry, 'result_types', manifestPath);

  if (description !== undefined) {
    skill.description = description;
  }
  if (promptRef !== undefined) {
    skill.prompt_ref = promptRef;
  }
  if (sideEffect !== undefined) {
    skill.side_effect = sideEffect;
  }
  if (requiredProjections !== undefined) {
    skill.required_projections = requiredProjections;
  }
  if (requiredKnowledge !== undefined) {
    skill.required_knowledge = requiredKnowledge;
  }
  if (resultTypes !== undefined) {
    skill.result_types = resultTypes;
  }

  return skill;
}

function parseValidatorEntry(
  value: unknown,
  manifestPath: string,
  index: number,
): PluginValidatorManifestEntry {
  const entry = readArrayObject(value, manifestPath, 'validators', index);
  const validator: PluginValidatorManifestEntry = {
    validator_id: readRequiredString(entry, 'validator_id', manifestPath),
    name: readRequiredString(entry, 'name', manifestPath),
    version: readRequiredString(entry, 'version', manifestPath),
    target: readRequiredString(entry, 'target', manifestPath),
    input_schema: readRequiredString(entry, 'input_schema', manifestPath),
    output_schema: readRequiredString(entry, 'output_schema', manifestPath),
    handler_ref: readRequiredString(entry, 'handler_ref', manifestPath),
  };
  const severity = readOptionalString(entry, 'severity', manifestPath);

  if (severity !== undefined) {
    validator.severity = severity;
  }

  return validator;
}

function parseProjectionEntry(
  value: unknown,
  manifestPath: string,
  index: number,
): PluginProjectionManifestEntry {
  const entry = readArrayObject(value, manifestPath, 'projections', index);
  const projection: PluginProjectionManifestEntry = {
    kind: readRequiredString(entry, 'kind', manifestPath),
    category: readRequiredString(entry, 'category', manifestPath),
    payload_schema: readRequiredString(entry, 'payload_schema', manifestPath),
    handler_ref: readRequiredString(entry, 'handler_ref', manifestPath),
    scope: readRequiredStringArray(entry, 'scope', manifestPath),
  };
  const vectorizable = readOptionalBoolean(entry, 'vectorizable', manifestPath);

  if (vectorizable !== undefined) {
    projection.vectorizable = vectorizable;
  }

  return projection;
}

function parseExporterEntry(value: unknown, manifestPath: string, index: number): PluginExporterManifestEntry {
  const entry = readArrayObject(value, manifestPath, 'exporters', index);
  return {
    exporter_id: readRequiredString(entry, 'exporter_id', manifestPath),
    name: readRequiredString(entry, 'name', manifestPath),
    version: readRequiredString(entry, 'version', manifestPath),
    source_projection: readRequiredString(entry, 'source_projection', manifestPath),
    input_schema: readRequiredString(entry, 'input_schema', manifestPath),
    output_type: readRequiredString(entry, 'output_type', manifestPath),
    handler_ref: readRequiredString(entry, 'handler_ref', manifestPath),
  };
}

function parseViewEntry(value: unknown, manifestPath: string, index: number): PluginViewManifestEntry {
  const entry = readArrayObject(value, manifestPath, 'views', index);
  const view: PluginViewManifestEntry = {
    view_id: readRequiredString(entry, 'view_id', manifestPath),
    name: readRequiredString(entry, 'name', manifestPath),
    projection_kind: readRequiredString(entry, 'projection_kind', manifestPath),
    view_type: readRequiredString(entry, 'view_type', manifestPath),
  };
  const metadata = readOptionalRecord(entry, 'metadata', manifestPath);

  if (metadata !== undefined) {
    view.metadata = metadata;
  }

  return view;
}

async function readManifestJson(manifestPath: string): Promise<unknown> {
  try {
    return JSON.parse(await readFile(manifestPath, 'utf8')) as unknown;
  } catch (error) {
    throw new PluginLoadError('PLUGIN_MANIFEST_INVALID', 'Plugin manifest JSON is invalid.', {
      manifest_path: manifestPath,
      cause: error instanceof Error ? error.message : String(error),
    });
  }
}

async function requirePluginFile(
  pluginRoot: string,
  resourceRef: string,
  code: 'PLUGIN_SCHEMA_NOT_FOUND' | 'PLUGIN_HANDLER_NOT_FOUND' | 'PLUGIN_REFERENCE_INVALID',
  message: string,
  details: Record<string, unknown>,
): Promise<string> {
  const fullPath = resolvePluginResourcePath(pluginRoot, resourceRef, details);

  if (!(await fileExists(fullPath))) {
    throw new PluginLoadError(code, message, { ...details, resolved_path: fullPath });
  }

  return fullPath;
}

function resolvePluginResourcePath(
  pluginRoot: string,
  resourceRef: string,
  details: Record<string, unknown>,
): string {
  if (isAbsolute(resourceRef)) {
    throw new PluginLoadError('PLUGIN_REFERENCE_INVALID', 'Plugin resource path must be relative.', details);
  }

  const fullPath = resolve(pluginRoot, resourceRef);
  const relativePath = relative(pluginRoot, fullPath);

  if (relativePath.startsWith('..') || isAbsolute(relativePath)) {
    throw new PluginLoadError('PLUGIN_REFERENCE_INVALID', 'Plugin resource path escapes plugin root.', {
      ...details,
      resource_ref: resourceRef,
      plugin_root: pluginRoot,
    });
  }

  return fullPath;
}

function requireSchema(
  schemas: Map<string, LoadedSchemaDefinition>,
  schemaId: string,
  pluginId: string,
  ownerKind: string,
  ownerId: string,
): LoadedSchemaDefinition {
  const schema = schemas.get(schemaId);

  if (schema === undefined) {
    throw new PluginLoadError('PLUGIN_REFERENCE_INVALID', 'Manifest references an unknown schema.', {
      plugin_id: pluginId,
      owner_kind: ownerKind,
      owner_id: ownerId,
      schema_id: schemaId,
    });
  }

  return schema;
}

function assertUnique<T>(
  map: Map<string, T>,
  value: string,
  field: string,
  pluginId: string,
): void {
  if (map.has(value)) {
    throw new PluginLoadError('PLUGIN_REFERENCE_INVALID', 'Plugin manifest contains duplicate ids.', {
      plugin_id: pluginId,
      field,
      value,
    });
  }
}

function readRequiredString(record: Record<string, unknown>, key: string, manifestPath: string): string {
  const value = record[key];

  if (typeof value !== 'string' || value.trim() === '') {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be a non-empty string.`);
  }

  return value;
}

function readOptionalString(
  record: Record<string, unknown>,
  key: string,
  manifestPath: string,
): string | undefined {
  const value = record[key];

  if (value === undefined) {
    return undefined;
  }

  if (typeof value !== 'string') {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be a string.`);
  }

  return value;
}

function readOptionalBoolean(
  record: Record<string, unknown>,
  key: string,
  manifestPath: string,
): boolean | undefined {
  const value = record[key];

  if (value === undefined) {
    return undefined;
  }

  if (typeof value !== 'boolean') {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be a boolean.`);
  }

  return value;
}

function readRequiredRecord(
  record: Record<string, unknown>,
  key: string,
  manifestPath: string,
): Record<string, unknown> {
  const value = record[key];

  if (!isRecord(value)) {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be an object.`);
  }

  return value;
}

function readOptionalRecord(
  record: Record<string, unknown>,
  key: string,
  manifestPath: string,
): Record<string, unknown> | undefined {
  const value = record[key];

  if (value === undefined) {
    return undefined;
  }

  if (!isRecord(value)) {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be an object.`);
  }

  return value;
}

function optionalRecordProperty(
  record: Record<string, unknown>,
  key: 'requirements' | 'compatibility' | 'metadata',
  manifestPath: string,
): Partial<Pick<PluginManifest, 'requirements' | 'compatibility' | 'metadata'>> {
  const value = readOptionalRecord(record, key, manifestPath);

  if (value === undefined) {
    return {};
  }

  return { [key]: value };
}

function readRequiredArray(record: Record<string, unknown>, key: string, manifestPath: string): unknown[] {
  const value = record[key];

  if (!Array.isArray(value)) {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be an array.`);
  }

  return value;
}

function readArrayObject(
  value: unknown,
  manifestPath: string,
  arrayName: string,
  index: number,
): Record<string, unknown> {
  if (!isRecord(value)) {
    throw invalidManifest(manifestPath, `Manifest ${arrayName}[${index}] must be an object.`);
  }

  return value;
}

function readRequiredStringArray(
  record: Record<string, unknown>,
  key: string,
  manifestPath: string,
): string[] {
  const value = record[key];

  if (!Array.isArray(value) || !value.every((item) => typeof item === 'string')) {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be a string array.`);
  }

  return value;
}

function readOptionalStringArray(
  record: Record<string, unknown>,
  key: string,
  manifestPath: string,
): string[] | undefined {
  const value = record[key];

  if (value === undefined) {
    return undefined;
  }

  if (!Array.isArray(value) || !value.every((item) => typeof item === 'string')) {
    throw invalidManifest(manifestPath, `Manifest field ${key} must be a string array.`);
  }

  return value;
}

function invalidManifest(
  manifestPath: string,
  message: string,
  details: Record<string, unknown> = {},
): PluginLoadError {
  return new PluginLoadError('PLUGIN_MANIFEST_INVALID', message, {
    manifest_path: manifestPath,
    ...details,
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

async function directoryExists(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isDirectory();
  } catch (error) {
    if (isFileSystemNotFoundError(error)) {
      return false;
    }

    throw error;
  }
}

async function fileExists(path: string): Promise<boolean> {
  try {
    return (await stat(path)).isFile();
  } catch (error) {
    if (isFileSystemNotFoundError(error)) {
      return false;
    }

    throw error;
  }
}

function fileExistsSync(path: string): boolean {
  try {
    accessSync(path, constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

function isFileSystemNotFoundError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && 'code' in error && error.code === 'ENOENT';
}
