import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { inArray } from 'drizzle-orm';
import type { JsonObject, JsonValue } from '@dfmea/shared';
import { createDatabaseClient, type DatabaseClient } from '../db/client';
import { loadEnvFiles } from '../db/env';
import { runMigrations } from '../db/migrate';
import {
  aiDraftBatches,
  artifactEdges,
  artifacts,
  capabilityInvocations,
  draftPatches,
  evidenceLinks,
  evidenceRefs,
  projects,
  projections,
  runEvents,
  runs,
  sessions,
  vectorIndexes,
  workspaces,
  workspaceRevisionEvents,
} from '../db/schema';
import { PluginLoaderService } from '../modules/plugin/plugin-loader.service';
import { PluginRegistryService } from '../modules/plugin/plugin-registry.service';
import { AiDraftRepository } from '../repositories/ai-draft.repository';
import { ArtifactRepository } from '../repositories/artifact.repository';
import { ScopeRepository } from '../repositories/scope.repository';
import { WorkspaceCapabilityService } from './capability.service';
import { registerDfmeaProjectionHandlers } from './dfmea-projection-handlers';
import { ProjectionService } from './projection.service';

loadEnvFiles();

const maybeDescribe = process.env.DATABASE_URL ? describe : describe.skip;

maybeDescribe('DFMEA MVP flow', () => {
  let client: DatabaseClient;
  const projectIds: string[] = [];
  const workspaceIds: string[] = [];

  beforeAll(async () => {
    await runMigrations();
    client = createDatabaseClient();
  }, 60_000);

  afterAll(async () => {
    if (projectIds.length) {
      await client.db.delete(evidenceLinks).where(inArray(evidenceLinks.projectId, projectIds));
      await client.db.delete(evidenceRefs).where(inArray(evidenceRefs.projectId, projectIds));
      await client.db.delete(vectorIndexes).where(inArray(vectorIndexes.projectId, projectIds));
      await client.db
        .delete(workspaceRevisionEvents)
        .where(inArray(workspaceRevisionEvents.projectId, projectIds));
      await client.db.delete(projections).where(inArray(projections.projectId, projectIds));
      await client.db.delete(draftPatches).where(inArray(draftPatches.projectId, projectIds));
      await client.db.delete(aiDraftBatches).where(inArray(aiDraftBatches.projectId, projectIds));
      await client.db
        .delete(capabilityInvocations)
        .where(inArray(capabilityInvocations.projectId, projectIds));
      await client.db.delete(runEvents).where(inArray(runEvents.projectId, projectIds));
      await client.db.delete(runs).where(inArray(runs.projectId, projectIds));
      await client.db.delete(artifactEdges).where(inArray(artifactEdges.projectId, projectIds));
      await client.db.delete(artifacts).where(inArray(artifacts.projectId, projectIds));
      await client.db.delete(sessions).where(inArray(sessions.projectId, projectIds));
      await client.db.delete(projects).where(inArray(projects.projectId, projectIds));
    }

    if (workspaceIds.length) {
      await client.db.delete(workspaces).where(inArray(workspaces.workspaceId, workspaceIds));
    }

    await client?.close();
  });

  it('generates, applies, and projects the cooling fan DFMEA draft', async () => {
    const scopeRepository = new ScopeRepository(client.db);
    const aiDraftRepository = new AiDraftRepository(client.db);
    const artifactRepository = new ArtifactRepository(client.db);
    const workspace = await scopeRepository.createWorkspace({ name: 'DFMEA MVP workspace' });
    const project = await scopeRepository.createProject({
      workspaceId: workspace.workspaceId,
      name: 'Cooling fan DFMEA MVP project',
    });
    workspaceIds.push(workspace.workspaceId);
    projectIds.push(project.projectId);

    const pluginRegistry = new PluginRegistryService();
    await new PluginLoaderService(pluginRegistry).loadPlugins();
    const capabilityService = new WorkspaceCapabilityService(pluginRegistry);
    const manifest = await capabilityService.buildCapabilityManifest({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginIds: ['dfmea'],
    });
    const invocation = await capabilityService.invoke({
      manifest,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      capabilityId: 'dfmea.generate_initial_analysis',
      arguments: {
        project_id: project.projectId,
        goal: 'Generate passenger vehicle cooling fan controller DFMEA draft',
      },
    });
    const draftResult = asJsonObject(invocation.result);
    const draftBatch = asJsonObject(draftResult.draft_batch);
    const operations = readOperations(draftBatch.operations);

    const batch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: readString(draftBatch.title) ?? 'DFMEA initial draft',
      goal: readString(draftBatch.goal) ?? 'Generate DFMEA initial draft',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
      summary: { summary: draftResult.summary ?? null },
    });

    for (const operation of operations) {
      await aiDraftRepository.createDraftPatch({
        draftBatchId: batch.draftBatchId,
        workspaceId: workspace.workspaceId,
        projectId: project.projectId,
        pluginId: 'dfmea',
        patchType: readPatchType(operation.patchType),
        targetType: readTargetType(operation.targetType),
        tempRef: readString(operation.tempRef),
        artifactType: readString(operation.artifactType),
        relationType: readString(operation.relationType),
        sourceTempRef: readString(operation.sourceTempRef),
        targetTempRef: readString(operation.targetTempRef),
        afterPayload: asOptionalJsonObject(operation.afterPayload),
      });
    }

    const applyResult = await aiDraftRepository.applyDraftBatch({
      draftBatchId: batch.draftBatchId,
      appliedBy: 'test_user',
    });
    const artifactRows = await artifactRepository.listProjectArtifacts(project.projectId);
    const edgeRows = await artifactRepository.listProjectEdges(project.projectId);

    expect(applyResult.toRevision).toBe(1);
    expect(artifactRows).toHaveLength(10);
    expect(edgeRows).toHaveLength(10);
    expect(artifactRows.map((artifact) => artifact.artifactType)).toContain('dfmea.failure_mode');
    expect(edgeRows.map((edge) => edge.relationType)).toContain('dfmea.action_targets_cause');

    const projectionService = new ProjectionService(client.db);
    registerDfmeaProjectionHandlers(projectionService);
    const workingTree = await projectionService.rebuildProjectProjection({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      kind: 'working_tree',
      category: 'working',
      scopeType: 'project',
      scopeId: project.projectId,
    });
    const exportPayload = await projectionService.rebuildProjectProjection({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      kind: 'export_payload',
      category: 'export',
      scopeType: 'project',
      scopeId: project.projectId,
    });

    expect(workingTree.projection.sourceRevision).toBe(1);
    expect(workingTree.projection.payload).toMatchObject({
      kind: 'dfmea.working_tree',
      artifact_count: 10,
      edge_count: 10,
    });
    expect(exportPayload.projection.sourceRevision).toBe(1);
    expect(exportPayload.projection.payload).toMatchObject({
      kind: 'dfmea.export_payload',
      summary: {
        artifact_count: 10,
        edge_count: 10,
        validation_status: 'passed',
      },
    });
  });
});

function asJsonObject(value: JsonValue | null | undefined): JsonObject {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value;
  }

  throw new Error('Expected JSON object.');
}

function asOptionalJsonObject(value: JsonValue | undefined): JsonObject | undefined {
  if (value === undefined) {
    return undefined;
  }

  return asJsonObject(value);
}

function readOperations(value: JsonValue | undefined): JsonObject[] {
  if (Array.isArray(value)) {
    return value.map(asJsonObject);
  }

  throw new Error('Expected draft operations array.');
}

function readString(value: JsonValue | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function readPatchType(value: JsonValue | undefined) {
  if (
    value === 'create_artifact' ||
    value === 'update_artifact' ||
    value === 'create_edge' ||
    value === 'update_edge' ||
    value === 'logical_delete'
  ) {
    return value;
  }

  throw new Error(`Invalid draft patch type: ${String(value)}`);
}

function readTargetType(value: JsonValue | undefined) {
  if (value === 'artifact' || value === 'edge') {
    return value;
  }

  throw new Error(`Invalid draft target type: ${String(value)}`);
}
