import { describe, expect, it } from 'vitest';
import { PluginLoaderService } from '../modules/plugin/plugin-loader.service';
import { PluginRegistryService } from '../modules/plugin/plugin-registry.service';
import { WorkspaceCapabilityService } from './capability.service';

describe('WorkspaceCapabilityService', () => {
  async function createService() {
    const pluginRegistry = new PluginRegistryService();
    const pluginLoader = new PluginLoaderService(pluginRegistry);
    await pluginLoader.loadPlugins();

    return new WorkspaceCapabilityService(pluginRegistry);
  }

  it('builds a manifest with platform capabilities and dfmea plugin skill', async () => {
    const service = await createService();
    const manifest = await service.buildCapabilityManifest({
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      pluginIds: ['dfmea'],
    });

    expect(manifest.capabilityIds).toContain('workspace.projection.get');
    expect(manifest.capabilityIds).toContain('dfmea.generate_initial_analysis');
    expect(
      manifest.descriptors.find(
        (descriptor) => descriptor.capabilityId === 'dfmea.generate_initial_analysis',
      )?.kind,
    ).toBe('plugin_skill');
  });

  it('denies capabilities that are not in the current manifest', async () => {
    const service = await createService();
    const manifest = await service.buildCapabilityManifest({
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      pluginIds: [],
    });

    const result = await service.invoke({
      manifest,
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      capabilityId: 'dfmea.generate_initial_analysis',
      arguments: { project_id: 'proj_1' },
    });

    expect(result.status).toBe('denied');
    expect(result.error?.code).toBe('CAPABILITY_NOT_IN_MANIFEST');
  });

  it('rejects invalid arguments before dispatch', async () => {
    const service = await createService();
    const manifest = await service.buildCapabilityManifest({
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      pluginIds: ['dfmea'],
    });

    const result = await service.invoke({
      manifest,
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      capabilityId: 'dfmea.generate_initial_analysis',
      arguments: { focus: 'missing project id' },
    });

    expect(result.status).toBe('invalid_arguments');
    expect(result.error?.code).toBe('CAPABILITY_ARGUMENT_INVALID');
  });

  it('dispatches the dfmea skill placeholder through capability invocation', async () => {
    const service = await createService();
    const manifest = await service.buildCapabilityManifest({
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      pluginIds: ['dfmea'],
    });

    const result = await service.invoke({
      manifest,
      workspaceId: 'ws_1',
      projectId: 'proj_1',
      capabilityId: 'dfmea.generate_initial_analysis',
      arguments: { project_id: 'proj_1', focus: 'cooling fan' },
    });

    expect(result.status).toBe('completed');
    expect(result.error).toBeNull();
    expect(result.result).toMatchObject({
      result_type: 'ai_draft_proposal',
      draft_batch: {
        operations: expect.arrayContaining([
          expect.objectContaining({
            patchType: 'create_artifact',
            artifactType: 'dfmea.failure_mode',
          }),
        ]),
      },
    });
  });
});
