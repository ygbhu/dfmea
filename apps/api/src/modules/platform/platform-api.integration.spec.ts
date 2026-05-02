import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { firstValueFrom } from 'rxjs';
import { take, toArray } from 'rxjs/operators';
import { eq, inArray } from 'drizzle-orm';
import type { JsonObject, JsonValue } from '@dfmea/shared';
import { createDatabaseClient, type DatabaseClient } from '../../db/client';
import { loadEnvFiles } from '../../db/env';
import { runMigrations } from '../../db/migrate';
import {
  apiPushJobs,
  apiPushRecords,
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
} from '../../db/schema';
import { normalizeApiError, validationFailed } from './platform-api.error';
import { PlatformApiController } from './platform-api.controller';
import { PlatformApiService } from './platform-api.service';

loadEnvFiles();

const maybeDescribe = process.env.DATABASE_URL ? describe : describe.skip;

maybeDescribe('Platform API Phase 9 flow', () => {
  let client: DatabaseClient;
  let controller: PlatformApiController;
  let service: PlatformApiService;
  const projectIds: string[] = [];
  const workspaceIds: string[] = [];

  beforeAll(async () => {
    await runMigrations();
    client = createDatabaseClient();
    service = new PlatformApiService(client.db);
    controller = new PlatformApiController(service);
  }, 60_000);

  afterAll(async () => {
    if (projectIds.length) {
      await client.db.delete(evidenceLinks).where(inArray(evidenceLinks.projectId, projectIds));
      await client.db.delete(evidenceRefs).where(inArray(evidenceRefs.projectId, projectIds));
      await client.db.delete(vectorIndexes).where(inArray(vectorIndexes.projectId, projectIds));
      await client.db
        .delete(workspaceRevisionEvents)
        .where(inArray(workspaceRevisionEvents.projectId, projectIds));
      await client.db.delete(apiPushRecords).where(inArray(apiPushRecords.projectId, projectIds));
      await client.db.delete(apiPushJobs).where(inArray(apiPushJobs.projectId, projectIds));
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

    await service?.onModuleDestroy();
    await client?.close();
  });

  it('runs the main REST and SSE flow through persisted draft preview', async () => {
    const workspaceResponse = await controller.createWorkspace({
      name: 'Phase 9 platform workspace',
    });
    expect(workspaceResponse.ok).toBe(true);
    const workspace = workspaceResponse.data.workspace;
    workspaceIds.push(workspace.workspaceId);

    const projectResponse = await controller.createProject(workspace.workspaceId, {
      name: 'Phase 9 cooling fan project',
    });
    expect(projectResponse.ok).toBe(true);
    const project = projectResponse.data.project;
    projectIds.push(project.projectId);

    const sessionResponse = await controller.createSession(project.projectId, {
      user_id: 'phase9_user',
      active_plugin_id: 'dfmea',
    });
    expect(sessionResponse.ok).toBe(true);
    const session = sessionResponse.data.session;

    const runResponse = await controller.startRun(session.sessionId, {
      goal: 'Generate passenger vehicle cooling fan controller DFMEA draft',
    });
    expect(runResponse.ok).toBe(true);
    const runResult = runResponse.data.run;

    expect(runResult.eventsUrl).toBe(`/api/runs/${runResult.runId}/events/stream`);
    expect(runResult.draftUrl).toBe(`/api/ai-drafts/${runResult.draftBatchId}`);

    const runEventsResponse = await controller.listRunEvents(runResult.runId);
    expect(runEventsResponse.ok).toBe(true);
    expect(runEventsResponse.data.events.map((event) => event.eventType)).toContain('runtime.completed');

    const runSseEvent = await firstValueFrom(controller.streamRunEvents(runResult.runId).pipe(take(1)));
    expect(runSseEvent.type).toBe('runtime.started');

    const draftResponse = await controller.getDraft(runResult.draftBatchId);
    expect(draftResponse.ok).toBe(true);
    expect(draftResponse.data.draft.patches).toHaveLength(20);

    const previewResponse = await controller.getDraftPreview(runResult.draftBatchId);
    expect(previewResponse.ok).toBe(true);
    expect(previewResponse.data.preview.nodes).toHaveLength(10);
    expect(previewResponse.data.preview.edges).toHaveLength(10);
    expect(previewResponse.data.preview.evidenceRefs).toHaveLength(2);

    const previewEvents = await firstValueFrom(
      controller.streamDraftPreviewEvents(runResult.draftBatchId).pipe(take(3), toArray()),
    );
    expect(previewEvents[0]?.type).toBe('draft.preview.started');
    expect(previewEvents.map((event) => event.type)).toContain('draft.preview.node_upserted');

    const firstPatch = draftResponse.data.draft.patches.find(
      (patch) => patch.targetType === 'artifact' && patch.artifactType === 'dfmea.system',
    );
    expect(firstPatch).toBeDefined();

    if (firstPatch === undefined) {
      throw new Error('Expected system draft patch.');
    }

    const editResponse = await controller.editDraftPatch(
      runResult.draftBatchId,
      firstPatch.draftPatchId,
      {
        after_payload: {
          name: 'Edited cooling fan controller system',
          description: 'Edited through Platform API test.',
        },
        edited_by: 'phase9_user',
      },
    );
    expect(editResponse.ok).toBe(true);
    expect(editResponse.data.patch.afterPayload).toMatchObject({
      name: 'Edited cooling fan controller system',
    });

    const applyResponse = await controller.applyDraft(runResult.draftBatchId, {
      applied_by: 'phase9_user',
    });
    expect(applyResponse.ok).toBe(true);
    expect(applyResponse.data.applyResult.toRevision).toBe(1);
    expect(applyResponse.data.workingTreeProjection?.freshness).toBe('fresh');

    const projectionResponse = await controller.getProjectProjection(project.projectId, {
      plugin_id: 'dfmea',
      kind: 'working_tree',
    });
    expect(projectionResponse.ok).toBe(true);
    expect(projectionResponse.data.projection.freshness).toBe('fresh');
    expect(projectionResponse.data.projection.projection.payload).toMatchObject({
      kind: 'dfmea.working_tree',
      artifact_count: 10,
      edge_count: 10,
    });

    const projectionEvents = await firstValueFrom(
      controller
        .streamProjectionRebuild(project.projectId, {
          plugin_id: 'dfmea',
          kind: 'working_tree',
        })
        .pipe(take(2), toArray()),
    );
    expect(projectionEvents.map((event) => event.type)).toEqual([
      'projection.rebuild.started',
      'projection.rebuild.completed',
    ]);

    const invocationId = readInvocationId(runEventsResponse.data.events);
    const invocationResponse = await controller.getCapabilityInvocation(invocationId);
    expect(invocationResponse.ok).toBe(true);
    expect(invocationResponse.data.invocation.status).toBe('completed');

    const openApiControllerResponse = normalizeApiError(
      validationFailed('Example validation error.', { field: 'goal' }),
    );
    expect(openApiControllerResponse.envelope).toMatchObject({
      code: 'VALIDATION_FAILED',
      message: 'Example validation error.',
      details: { field: 'goal' },
    });
  }, 60_000);

  it('normalizes stale draft base revision conflicts', async () => {
    const { session } = await createPlatformScope('conflict');
    const firstRun = await startCoolingFanRun(session.sessionId);
    const secondRun = await startCoolingFanRun(session.sessionId);

    await controller.applyDraft(secondRun.draftBatchId, {
      applied_by: 'phase11_user',
    });
    const normalized = await captureNormalizedError(() =>
      controller.applyDraft(firstRun.draftBatchId, {
        applied_by: 'phase11_user',
      }),
    );

    expect(normalized.statusCode).toBe(409);
    expect(normalized.envelope).toMatchObject({
      code: 'AI_DRAFT_BASE_REVISION_CONFLICT',
      details: expect.objectContaining({
        draft_batch_id: firstRun.draftBatchId,
        base_workspace_revision: 0,
        current_workspace_revision: 1,
      }),
    });
  }, 60_000);

  it('surfaces stale UI projections and rebuilds them fresh', async () => {
    const { project, session } = await createPlatformScope('projection');
    const run = await startCoolingFanRun(session.sessionId);

    await controller.applyDraft(run.draftBatchId, {
      applied_by: 'phase11_user',
    });
    const freshProjection = await controller.getProjectProjection(project.projectId, {
      plugin_id: 'dfmea',
      kind: 'working_tree',
    });
    const currentRevision = freshProjection.data.projection.currentWorkspaceRevision;

    await client.db
      .update(projects)
      .set({
        workspaceRevision: currentRevision + 1,
        updatedAt: new Date(),
      })
      .where(eq(projects.projectId, project.projectId));

    const staleProjection = await controller.getProjectProjection(project.projectId, {
      plugin_id: 'dfmea',
      kind: 'working_tree',
    });
    expect(staleProjection.data.projection.freshness).toBe('stale');
    expect(staleProjection.data.projection.currentWorkspaceRevision).toBe(currentRevision + 1);

    const rebuild = await controller.rebuildProjection({
      project_id: project.projectId,
      plugin_id: 'dfmea',
      kind: 'working_tree',
    });
    expect(rebuild.data.result.freshness).toBe('fresh');
    expect(rebuild.data.result.projection.sourceRevision).toBe(currentRevision + 1);
  }, 60_000);

  it('rejects AI drafts without changing canonical project data', async () => {
    const { project, session } = await createPlatformScope('reject');
    const run = await startCoolingFanRun(session.sessionId);

    const rejected = await controller.rejectDraft(run.draftBatchId, {
      rejected_by: 'phase11_user',
    });
    const projectAfterReject = await controller.getProject(project.projectId);
    const projectArtifacts = await client.db
      .select()
      .from(artifacts)
      .where(eq(artifacts.projectId, project.projectId));

    expect(rejected.data.batch.status).toBe('rejected');
    expect(projectAfterReject.data.project.workspaceRevision).toBe(0);
    expect(projectArtifacts).toHaveLength(0);
  }, 60_000);

  it('pushes only a fresh export projection to the mock mature FMEA API', async () => {
    const { project, session } = await createPlatformScope('api-push');
    const run = await startCoolingFanRun(session.sessionId);
    await controller.applyDraft(run.draftBatchId, {
      applied_by: 'phase12_user',
    });
    const projectBeforePush = await controller.getProject(project.projectId);
    const artifactCountBefore = await countProjectArtifacts(project.projectId);

    const validate = await controller.validateApiPush({
      project_id: project.projectId,
      created_by: 'phase12_user',
    });
    expect(validate.data.job.mode).toBe('validate_only');
    expect(validate.data.job.status).toBe('completed');
    expect(validate.data.record).toBeNull();
    expect(validate.data.validation.status).toBe('passed');

    const execute = await controller.executeApiPush({
      project_id: project.projectId,
      created_by: 'phase12_user',
    });
    const record = execute.data.record;

    expect(execute.data.job.status).toBe('completed');
    expect(record).not.toBeNull();
    expect(record?.externalSystem).toBe('mock-mature-fmea');
    expect(record?.externalStatus).toBe('accepted');
    expect(record?.sourceWorkspaceRevision).toBe(projectBeforePush.data.project.workspaceRevision);
    expect(execute.data.sourceProjection.freshness).toBe('fresh');
    expect(execute.data.sourceProjection.projection).toMatchObject({
      kind: 'export_payload',
      category: 'export',
      sourceRevision: projectBeforePush.data.project.workspaceRevision,
    });
    expect(execute.data.events).toContain('api_push.execute.completed');

    const jobResponse = await controller.getApiPushJob(execute.data.job.apiPushJobId);
    expect(jobResponse.data.job.status).toBe('completed');

    if (record === null) {
      throw new Error('Expected API Push record.');
    }

    const recordResponse = await controller.getApiPushRecord(record.apiPushRecordId);
    const projectAfterPush = await controller.getProject(project.projectId);
    const artifactCountAfter = await countProjectArtifacts(project.projectId);

    expect(recordResponse.data.record.payloadChecksum).toBe(record.payloadChecksum);
    expect(projectAfterPush.data.project.workspaceRevision).toBe(
      projectBeforePush.data.project.workspaceRevision,
    );
    expect(artifactCountAfter).toBe(artifactCountBefore);
  }, 60_000);

  async function createPlatformScope(label: string): Promise<{
    workspace: typeof workspaces.$inferSelect;
    project: typeof projects.$inferSelect;
    session: typeof sessions.$inferSelect;
  }> {
    const workspaceResponse = await controller.createWorkspace({
      name: `Phase 11 ${label} workspace`,
    });
    const workspace = workspaceResponse.data.workspace;
    workspaceIds.push(workspace.workspaceId);

    const projectResponse = await controller.createProject(workspace.workspaceId, {
      name: `Phase 11 ${label} cooling fan project`,
    });
    const project = projectResponse.data.project;
    projectIds.push(project.projectId);

    const sessionResponse = await controller.createSession(project.projectId, {
      user_id: 'phase11_user',
      active_plugin_id: 'dfmea',
    });

    return {
      workspace,
      project,
      session: sessionResponse.data.session,
    };
  }

  async function startCoolingFanRun(sessionId: string): Promise<{
    runId: string;
    draftBatchId: string;
    evidenceRefs: string[];
    eventsUrl: string;
    draftUrl: string;
  }> {
    const runResponse = await controller.startRun(sessionId, {
      goal: 'Generate passenger vehicle cooling fan controller DFMEA draft',
    });

    return runResponse.data.run;
  }

  async function captureNormalizedError(action: () => Promise<unknown>) {
    try {
      await action();
    } catch (error) {
      return normalizeApiError(error);
    }

    throw new Error('Expected Platform API action to fail.');
  }

  async function countProjectArtifacts(projectId: string): Promise<number> {
    const rows = await client.db.select().from(artifacts).where(eq(artifacts.projectId, projectId));
    return rows.length;
  }
});

function readInvocationId(events: { eventType: string; payload: JsonValue }[]): string {
  const event = events.find((candidate) => candidate.eventType === 'runtime.capability_invocation.started');

  if (event === undefined) {
    throw new Error('Expected capability invocation event.');
  }

  const payload = asJsonObject(event.payload);
  const invocationId = payload.invocation_id;

  if (typeof invocationId !== 'string') {
    throw new Error('Expected invocation_id payload.');
  }

  return invocationId;
}

function asJsonObject(value: JsonValue): JsonObject {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value;
  }

  throw new Error('Expected JSON object.');
}
