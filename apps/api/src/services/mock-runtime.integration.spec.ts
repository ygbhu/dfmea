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
import { ScopeRepository } from '../repositories/scope.repository';
import { MockKnowledgeService } from './mock-knowledge.service';
import { MockRuntimeService } from './mock-runtime.service';

loadEnvFiles();

const maybeDescribe = process.env.DATABASE_URL ? describe : describe.skip;

maybeDescribe('Mock runtime and knowledge providers', () => {
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

  it('retrieves mock evidence and creates a DFMEA draft through mock runtime', async () => {
    const scopeRepository = new ScopeRepository(client.db);
    const workspace = await scopeRepository.createWorkspace({ name: 'Mock runtime workspace' });
    const project = await scopeRepository.createProject({
      workspaceId: workspace.workspaceId,
      name: 'Mock runtime cooling fan project',
    });
    const session = await scopeRepository.createSession({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      userId: 'test_user',
      activePluginId: 'dfmea',
    });
    workspaceIds.push(workspace.workspaceId);
    projectIds.push(project.projectId);

    const knowledgeService = new MockKnowledgeService(client.db);
    const evidence = await knowledgeService.retrieve({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      sessionId: session.sessionId,
      query: 'cooling fan controller',
    });
    const evidenceDetail = await knowledgeService.getEvidence(evidence[0]?.evidenceRef ?? '');

    expect(evidence).toHaveLength(2);
    expect(evidence.map((item) => item.knowledgeBaseType)).toEqual(['project', 'historical_fmea']);
    expect(evidenceDetail?.title).toContain('Cooling fan');

    const runtimeService = new MockRuntimeService(client.db);
    const runResult = await runtimeService.startRun({
      workspaceId: workspace.workspaceId,
      projectId: project.projectId,
      sessionId: session.sessionId,
      userId: 'test_user',
      goal: 'Generate passenger vehicle cooling fan controller DFMEA draft',
    });
    const events = await runtimeService.streamEvents(runResult.runId);
    const [run] = await client.db.select().from(runs).where(eq(runs.runId, runResult.runId));
    const [batch] = await client.db
      .select()
      .from(aiDraftBatches)
      .where(eq(aiDraftBatches.draftBatchId, runResult.draftBatchId));
    const patches = await client.db
      .select()
      .from(draftPatches)
      .where(eq(draftPatches.draftBatchId, runResult.draftBatchId));

    expect(run?.status).toBe('completed');
    expect(runResult.evidenceRefs).toHaveLength(2);
    expect(events.map((event) => event.eventType)).toEqual([
      'runtime.started',
      'runtime.message',
      'runtime.capability_invocation.started',
      'runtime.capability_invocation.completed',
      'runtime.result.proposed',
      'runtime.completed',
    ]);
    expect(batch?.status).toBe('pending');
    expect(batch?.summary).toMatchObject({
      evidence_refs: runResult.evidenceRefs,
    });
    expect(patches).toHaveLength(20);
    expect(patches.map((patch) => patch.artifactType).filter(Boolean)).toContain('dfmea.failure_mode');
  });
});
