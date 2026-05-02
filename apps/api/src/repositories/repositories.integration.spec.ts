import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { eq, inArray } from 'drizzle-orm';
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
import { AiDraftRepository } from './ai-draft.repository';
import { ArtifactRepository } from './artifact.repository';
import { ScopeRepository } from './scope.repository';
import { ProjectionService } from '../services/projection.service';

loadEnvFiles();

const maybeDescribe = process.env.DATABASE_URL ? describe : describe.skip;

maybeDescribe('Phase 2 repositories', () => {
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

  async function createScope() {
    const scopeRepository = new ScopeRepository(client.db);
    const workspace = await scopeRepository.createWorkspace({ name: 'Phase 2 test workspace' });
    const project = await scopeRepository.createProject({
      workspaceId: workspace.workspaceId,
      name: 'Cooling fan test project',
    });
    const session = await scopeRepository.createSession({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      userId: 'test_user',
      activePluginId: 'dfmea',
    });

    workspaceIds.push(workspace.workspaceId);
    projectIds.push(project.projectId);

    return { workspace, project, session };
  }

  it('creates workspace, project, and session with revision initialized', async () => {
    const { project, session } = await createScope();

    expect(project.workspaceRevision).toBe(0);
    expect(session.activePluginId).toBe('dfmea');
  });

  it('writes and reads artifacts and edges', async () => {
    const { workspace, project } = await createScope();
    const artifactRepository = new ArtifactRepository(client.db);

    const system = await artifactRepository.createArtifact({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      artifactType: 'dfmea.system',
      schemaVersion: '1.0.0',
      revision: project.workspaceRevision,
      payload: { name: 'Cooling fan system' },
    });
    const component = await artifactRepository.createArtifact({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      artifactType: 'dfmea.component',
      schemaVersion: '1.0.0',
      revision: project.workspaceRevision,
      payload: { name: 'Motor assembly' },
    });
    const edge = await artifactRepository.createEdge({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      sourceArtifactId: system.artifactId,
      targetArtifactId: component.artifactId,
      relationType: 'dfmea.contains',
      schemaVersion: '1.0.0',
      revision: project.workspaceRevision,
    });

    const artifactsInProject = await artifactRepository.listProjectArtifacts(project.projectId);
    const edgesInProject = await artifactRepository.listProjectEdges(project.projectId);

    expect(artifactsInProject).toHaveLength(2);
    expect(edgesInProject[0]?.edgeId).toBe(edge.edgeId);
  });

  it('applies an AI draft batch and increments project workspace revision', async () => {
    const { workspace, project } = await createScope();
    const aiDraftRepository = new AiDraftRepository(client.db);

    const batch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: 'Cooling fan initial draft',
      goal: 'Generate cooling fan DFMEA initial analysis',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
    });

    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      tempRef: 'system',
      artifactType: 'dfmea.system',
      afterPayload: { name: 'Cooling fan system' },
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      tempRef: 'component',
      artifactType: 'dfmea.component',
      afterPayload: { name: 'Fan motor' },
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_edge',
      targetType: 'edge',
      relationType: 'dfmea.contains',
      sourceTempRef: 'system',
      targetTempRef: 'component',
      afterPayload: {},
    });

    const result = await aiDraftRepository.applyDraftBatch({
      draftBatchId: batch.draftBatchId,
      appliedBy: 'test_user',
    });

    const [updatedProject] = await client.db
      .select()
      .from(projects)
      .where(eq(projects.projectId, project.projectId));
    const [updatedBatch] = await client.db
      .select()
      .from(aiDraftBatches)
      .where(eq(aiDraftBatches.draftBatchId, batch.draftBatchId));
    const revisionEvents = await client.db
      .select()
      .from(workspaceRevisionEvents)
      .where(eq(workspaceRevisionEvents.draftBatchId, batch.draftBatchId));

    expect(result.fromRevision).toBe(0);
    expect(result.toRevision).toBe(1);
    expect(result.artifactIds).toHaveLength(2);
    expect(result.edgeIds).toHaveLength(1);
    expect(updatedProject?.workspaceRevision).toBe(1);
    expect(updatedBatch?.status).toBe('applied');
    expect(revisionEvents[0]?.toRevision).toBe(1);
  });

  it('keeps pending and rejected drafts out of canonical data', async () => {
    const { workspace, project } = await createScope();
    const aiDraftRepository = new AiDraftRepository(client.db);
    const artifactRepository = new ArtifactRepository(client.db);

    const batch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: 'Rejected draft',
      goal: 'Generate a draft that will be rejected',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
    });

    const patch = await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      artifactType: 'dfmea.system',
      afterPayload: { name: 'Draft before edit' },
    });

    await aiDraftRepository.editDraftPatch({
      draftPatchId: patch.draftPatchId,
      afterPayload: { name: 'Draft after edit' },
      editedBy: 'test_user',
    });

    expect(await artifactRepository.listProjectArtifacts(project.projectId)).toHaveLength(0);

    const rejectedBatch = await aiDraftRepository.rejectDraftBatch({
      draftBatchId: batch.draftBatchId,
      rejectedBy: 'test_user',
    });
    const rejectedPatches = await aiDraftRepository.listDraftPatches(batch.draftBatchId);
    const [unchangedProject] = await client.db
      .select()
      .from(projects)
      .where(eq(projects.projectId, project.projectId));

    expect(rejectedBatch?.status).toBe('rejected');
    expect(rejectedPatches.every((draftPatch) => draftPatch.status === 'rejected')).toBe(true);
    expect(await artifactRepository.listProjectArtifacts(project.projectId)).toHaveLength(0);
    expect(unchangedProject?.workspaceRevision).toBe(0);
  });

  it('rejects apply when draft base revision is stale', async () => {
    const { workspace, project } = await createScope();
    const aiDraftRepository = new AiDraftRepository(client.db);
    const artifactRepository = new ArtifactRepository(client.db);

    const staleBatch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: 'Stale draft',
      goal: 'Generate stale draft',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: staleBatch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      artifactType: 'dfmea.system',
      afterPayload: { name: 'Stale system' },
    });

    const freshBatch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: 'Fresh draft',
      goal: 'Generate fresh draft',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: freshBatch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      artifactType: 'dfmea.system',
      afterPayload: { name: 'Fresh system' },
    });

    await aiDraftRepository.applyDraftBatch({
      draftBatchId: freshBatch.draftBatchId,
      appliedBy: 'test_user',
    });

    await expect(
      aiDraftRepository.applyDraftBatch({
        draftBatchId: staleBatch.draftBatchId,
        appliedBy: 'test_user',
      }),
    ).rejects.toMatchObject({
      code: 'DRAFT_BASE_REVISION_CONFLICT',
      details: expect.objectContaining({
        draft_batch_id: staleBatch.draftBatchId,
        base_workspace_revision: 0,
        current_workspace_revision: 1,
      }),
    });

    const artifactsInProject = await artifactRepository.listProjectArtifacts(project.projectId);
    const [unchangedStaleBatch] = await client.db
      .select()
      .from(aiDraftBatches)
      .where(eq(aiDraftBatches.draftBatchId, staleBatch.draftBatchId));

    expect(artifactsInProject).toHaveLength(1);
    expect(artifactsInProject[0]?.payload).toEqual({ name: 'Fresh system' });
    expect(unchangedStaleBatch?.status).toBe('pending');
  });

  it('applies update and logical delete draft patches', async () => {
    const { workspace, project } = await createScope();
    const aiDraftRepository = new AiDraftRepository(client.db);
    const artifactRepository = new ArtifactRepository(client.db);

    const system = await artifactRepository.createArtifact({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      artifactType: 'dfmea.system',
      schemaVersion: '1.0.0',
      revision: project.workspaceRevision,
      payload: { name: 'Cooling fan system' },
    });
    const oldComponent = await artifactRepository.createArtifact({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      artifactType: 'dfmea.component',
      schemaVersion: '1.0.0',
      revision: project.workspaceRevision,
      payload: { name: 'Old fan motor' },
    });
    const edge = await artifactRepository.createEdge({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      sourceArtifactId: system.artifactId,
      targetArtifactId: oldComponent.artifactId,
      relationType: 'dfmea.contains',
      schemaVersion: '1.0.0',
      revision: project.workspaceRevision,
      payload: { label: 'old' },
    });

    const batch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: 'Update existing draft',
      goal: 'Update and delete existing canonical records',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
    });

    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'update_artifact',
      targetType: 'artifact',
      targetId: system.artifactId,
      afterPayload: { name: 'Updated cooling fan system' },
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      tempRef: 'new_component',
      artifactType: 'dfmea.component',
      afterPayload: { name: 'New fan motor' },
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'update_edge',
      targetType: 'edge',
      targetId: edge.edgeId,
      targetTempRef: 'new_component',
      afterPayload: { label: 'updated' },
    });
    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'logical_delete',
      targetType: 'artifact',
      targetId: oldComponent.artifactId,
    });

    const result = await aiDraftRepository.applyDraftBatch({
      draftBatchId: batch.draftBatchId,
      appliedBy: 'test_user',
    });
    const [updatedSystem] = await client.db
      .select()
      .from(artifacts)
      .where(eq(artifacts.artifactId, system.artifactId));
    const [deletedComponent] = await client.db
      .select()
      .from(artifacts)
      .where(eq(artifacts.artifactId, oldComponent.artifactId));
    const [updatedEdge] = await client.db
      .select()
      .from(artifactEdges)
      .where(eq(artifactEdges.edgeId, edge.edgeId));
    const [updatedProject] = await client.db
      .select()
      .from(projects)
      .where(eq(projects.projectId, project.projectId));

    expect(result.toRevision).toBe(1);
    expect(result.artifactIds).toHaveLength(3);
    expect(result.edgeIds).toHaveLength(1);
    expect(updatedProject?.workspaceRevision).toBe(1);
    expect(updatedSystem?.payload).toEqual({ name: 'Updated cooling fan system' });
    expect(deletedComponent?.status).toBe('logically_deleted');
    expect(updatedEdge?.payload).toEqual({ label: 'updated' });
    expect(updatedEdge?.targetArtifactId).not.toBe(oldComponent.artifactId);
  });

  it('marks projection stale after apply and rebuilds fresh projection for AI reads', async () => {
    const { workspace, project } = await createScope();
    const aiDraftRepository = new AiDraftRepository(client.db);
    const projectionService = new ProjectionService(client.db);
    const projectionInput = {
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'platform',
      kind: 'test_project_summary',
      category: 'working',
      scopeType: 'project',
      scopeId: project.projectId,
    };

    const initialProjection = await projectionService.rebuildProjectProjection(projectionInput);

    expect(initialProjection.projection.sourceRevision).toBe(0);
    expect(initialProjection.projection.status).toBe('fresh');
    expect(initialProjection.projection.payload).toMatchObject({
      artifact_count: 0,
      workspace_revision: 0,
    });

    const batch = await aiDraftRepository.createDraftBatch({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      title: 'Projection stale draft',
      goal: 'Create artifact and stale projections',
      baseWorkspaceRevision: project.workspaceRevision,
      createdBy: 'test_user',
    });

    await aiDraftRepository.createDraftPatch({
      draftBatchId: batch.draftBatchId,
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      pluginId: 'dfmea',
      patchType: 'create_artifact',
      targetType: 'artifact',
      artifactType: 'dfmea.system',
      afterPayload: { name: 'Cooling fan system' },
    });

    await aiDraftRepository.applyDraftBatch({
      draftBatchId: batch.draftBatchId,
      appliedBy: 'test_user',
    });

    const [staleProjection] = await client.db
      .select()
      .from(projections)
      .where(eq(projections.projectionId, initialProjection.projection.projectionId));

    expect(staleProjection?.status).toBe('stale');
    expect(staleProjection?.sourceRevision).toBe(0);

    const uiRead = await projectionService.getProjection({ ...projectionInput, consumer: 'ui' });

    expect(uiRead.freshness).toBe('stale');
    expect(uiRead.projection.sourceRevision).toBe(0);

    const aiRead = await projectionService.getFreshProjection(projectionInput);

    expect(aiRead.freshness).toBe('fresh');
    expect(aiRead.projection.status).toBe('fresh');
    expect(aiRead.projection.sourceRevision).toBe(1);
    expect(aiRead.projection.payload).toMatchObject({
      artifact_count: 1,
      workspace_revision: 1,
    });
    expect(projectionService.listEvents()).toContain('projection.stale_detected');
    expect(projectionService.listEvents()).toContain('projection.rebuild.completed');
  });
});
