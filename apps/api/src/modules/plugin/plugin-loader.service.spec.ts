import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { describe, expect, it } from 'vitest';
import { PluginLoadError } from './plugin-load-error';
import { PluginLoaderService } from './plugin-loader.service';
import { PluginRegistryService } from './plugin-registry.service';

describe('PluginLoaderService', () => {
  it('loads the dfmea plugin and registers its skill capability', async () => {
    const registry = new PluginRegistryService();
    const loader = new PluginLoaderService(registry);

    await loader.loadPlugins(resolve(process.cwd(), 'plugins'));

    const plugin = registry.getPlugin('dfmea');
    const skill = registry.getSkill('dfmea', 'generate_initial_analysis');

    expect(plugin?.pluginId).toBe('dfmea');
    expect(skill?.capabilityId).toBe('dfmea.generate_initial_analysis');
    expect(registry.createSkillCapabilityId('dfmea', 'generate_initial_analysis')).toBe(
      'dfmea.generate_initial_analysis',
    );
    expect(registry.getSkillByCapabilityId('dfmea.generate_initial_analysis')).toBe(skill);
  });

  it('returns a structured error when a skill handler is missing', async () => {
    const pluginDir = await mkdtemp(join(tmpdir(), 'dfmea-plugin-loader-'));

    try {
      await createPluginWithMissingHandler(pluginDir);

      const registry = new PluginRegistryService();
      const loader = new PluginLoaderService(registry);

      await expect(loader.loadPlugins(pluginDir)).rejects.toMatchObject({
        code: 'PLUGIN_HANDLER_NOT_FOUND',
        details: expect.objectContaining({
          plugin_id: 'dfmea',
          skill_id: 'generate_initial_analysis',
          handler_ref: 'skills/missing.ts',
        }),
      });
      await expect(loader.loadPlugins(pluginDir)).rejects.toBeInstanceOf(PluginLoadError);
    } finally {
      await rm(pluginDir, { recursive: true, force: true });
    }
  });
});

async function createPluginWithMissingHandler(pluginDir: string): Promise<void> {
  const root = join(pluginDir, 'dfmea');
  await mkdir(join(root, 'schemas', 'skills'), { recursive: true });

  await writeFile(
    join(root, 'plugin.json'),
    JSON.stringify(
      {
        manifest_version: '0.1.0',
        plugin: {
          plugin_id: 'dfmea',
          name: 'DFMEA',
          version: '0.1.0',
        },
        capabilities: {
          skills: true,
        },
        schemas: [
          {
            schema_id: 'dfmea.generate_initial_analysis.input.v1',
            kind: 'skill_input',
            version: '1.0.0',
            path: 'schemas/skills/generate_initial_analysis.input.schema.json',
          },
          {
            schema_id: 'dfmea.generate_initial_analysis.output.v1',
            kind: 'skill_output',
            version: '1.0.0',
            path: 'schemas/skills/generate_initial_analysis.output.schema.json',
          },
        ],
        skills: [
          {
            skill_id: 'generate_initial_analysis',
            name: 'Generate Initial Analysis',
            version: '0.1.0',
            input_schema: 'dfmea.generate_initial_analysis.input.v1',
            output_schema: 'dfmea.generate_initial_analysis.output.v1',
            handler_ref: 'skills/missing.ts',
          },
        ],
        validators: [],
        projections: [],
        exporters: [],
        views: [],
      },
      null,
      2,
    ),
  );
  await writeFile(
    join(root, 'schemas', 'skills', 'generate_initial_analysis.input.schema.json'),
    JSON.stringify({ type: 'object', additionalProperties: true }),
  );
  await writeFile(
    join(root, 'schemas', 'skills', 'generate_initial_analysis.output.schema.json'),
    JSON.stringify({ type: 'object', additionalProperties: true }),
  );
}
