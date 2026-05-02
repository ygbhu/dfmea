import { asc, eq } from 'drizzle-orm';
import type { JsonObject, JsonValue } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import {
  capabilityInvocations,
  projects,
  runEvents,
  runs,
} from '../db/schema';
import { PluginLoaderService } from '../modules/plugin/plugin-loader.service';
import { PluginRegistryService } from '../modules/plugin/plugin-registry.service';
import { AiDraftRepository } from '../repositories/ai-draft.repository';
import { MockKnowledgeService } from './mock-knowledge.service';
import { WorkspaceCapabilityService } from './capability.service';

export interface StartMockRunInput {
  workspaceId: string;
  projectId: string;
  sessionId?: string;
  userId?: string;
  goal: string;
  pluginId?: string;
}

export interface StartMockRunResult {
  runId: string;
  draftBatchId: string;
  evidenceRefs: string[];
}

export class MockRuntimeService {
  private readonly knowledgeService: MockKnowledgeService;
  private readonly draftRepository: AiDraftRepository;

  constructor(private readonly db: AppDatabase) {
    this.knowledgeService = new MockKnowledgeService(db);
    this.draftRepository = new AiDraftRepository(db);
  }

  async startRun(input: StartMockRunInput): Promise<StartMockRunResult> {
    const pluginId = input.pluginId ?? 'dfmea';
    const [project] = await this.db.select().from(projects).where(eq(projects.projectId, input.projectId));

    if (project === undefined) {
      throw new Error(`Project not found: ${input.projectId}`);
    }

    const runId = createId('run');
    await this.db.insert(runs).values({
      runId,
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      sessionId: input.sessionId,
      userId: input.userId,
      runtimeProviderId: 'mock_runtime',
      activeDomainPluginId: pluginId,
      goal: input.goal,
      status: 'created',
      baseWorkspaceRevision: project.workspaceRevision,
    });
    await this.recordEvent(input.workspaceId, input.projectId, input.sessionId, runId, 'runtime.started', {
      goal: input.goal,
      plugin_id: pluginId,
    });

    await this.db
      .update(runs)
      .set({ status: 'running', startedAt: new Date(), updatedAt: new Date() })
      .where(eq(runs.runId, runId));

    const evidence = await this.knowledgeService.retrieve({
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      sessionId: input.sessionId,
      query: input.goal,
      knowledgeBaseTypes: ['project', 'historical_fmea'],
    });
    const evidenceRefs = evidence.map((item) => item.evidenceRef);
    await this.recordEvent(input.workspaceId, input.projectId, input.sessionId, runId, 'runtime.message', {
      message: 'Mock knowledge retrieved.',
      evidence_refs: evidenceRefs,
    });

    const pluginRegistry = new PluginRegistryService();
    await new PluginLoaderService(pluginRegistry).loadPlugins();
    const capabilityService = new WorkspaceCapabilityService(pluginRegistry);
    const manifest = await capabilityService.buildCapabilityManifest({
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      pluginIds: [pluginId],
    });
    const invocationId = createId('inv');

    await this.db.insert(capabilityInvocations).values({
      invocationId,
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      sessionId: input.sessionId,
      runId,
      capabilityId: 'dfmea.generate_initial_analysis',
      status: 'running',
      arguments: {
        project_id: input.projectId,
        goal: input.goal,
        knowledge_refs: evidenceRefs,
      },
      startedAt: new Date(),
    });
    await this.recordEvent(
      input.workspaceId,
      input.projectId,
      input.sessionId,
      runId,
      'runtime.capability_invocation.started',
      { invocation_id: invocationId, capability_id: 'dfmea.generate_initial_analysis' },
    );

    const invocation = await capabilityService.invoke({
      invocationId,
      manifest,
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      runId,
      capabilityId: 'dfmea.generate_initial_analysis',
      arguments: {
        project_id: input.projectId,
        goal: input.goal,
        knowledge_refs: evidenceRefs,
      },
    });

    await this.db
      .update(capabilityInvocations)
      .set({
        status: invocation.status,
        result: invocation.result,
        error: invocation.error?.details ?? null,
        completedAt: new Date(),
      })
      .where(eq(capabilityInvocations.invocationId, invocationId));
    await this.recordEvent(
      input.workspaceId,
      input.projectId,
      input.sessionId,
      runId,
      'runtime.capability_invocation.completed',
      { invocation_id: invocationId, status: invocation.status },
    );

    if (invocation.status !== 'completed' || invocation.result === null) {
      await this.failRun(input.workspaceId, input.projectId, input.sessionId, runId, invocation.error?.message);
      throw new Error(invocation.error?.message ?? 'Capability invocation failed.');
    }

    const draftBatchId = await this.createDraftProposalFromCapabilityResult({
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      sessionId: input.sessionId,
      runId,
      pluginId,
      userId: input.userId,
      baseWorkspaceRevision: project.workspaceRevision,
      result: invocation.result,
      evidenceRefs,
    });

    await this.recordEvent(input.workspaceId, input.projectId, input.sessionId, runId, 'runtime.result.proposed', {
      draft_batch_id: draftBatchId,
      evidence_refs: evidenceRefs,
    });
    await this.db
      .update(runs)
      .set({ status: 'completed', completedAt: new Date(), updatedAt: new Date() })
      .where(eq(runs.runId, runId));
    await this.recordEvent(input.workspaceId, input.projectId, input.sessionId, runId, 'runtime.completed', {
      draft_batch_id: draftBatchId,
    });

    return {
      runId,
      draftBatchId,
      evidenceRefs,
    };
  }

  async streamEvents(runId: string) {
    return this.db.select().from(runEvents).where(eq(runEvents.runId, runId)).orderBy(asc(runEvents.sequence));
  }

  async cancel(runId: string): Promise<void> {
    const [run] = await this.db.select().from(runs).where(eq(runs.runId, runId));

    if (run === undefined) {
      throw new Error(`Run not found: ${runId}`);
    }

    await this.db
      .update(runs)
      .set({ status: 'cancelled', completedAt: new Date(), updatedAt: new Date() })
      .where(eq(runs.runId, runId));
    await this.recordEvent(run.workspaceId, run.projectId, run.sessionId ?? undefined, run.runId, 'runtime.cancelled', {});
  }

  private async createDraftProposalFromCapabilityResult(input: {
    workspaceId: string;
    projectId: string;
    sessionId: string | undefined;
    runId: string;
    pluginId: string;
    userId: string | undefined;
    baseWorkspaceRevision: number;
    result: JsonValue;
    evidenceRefs: string[];
  }): Promise<string> {
    const resultObject = asJsonObject(input.result);
    const draftBatch = asJsonObject(resultObject.draft_batch);
    const operations = readOperations(draftBatch.operations);
    const batch = await this.draftRepository.createDraftBatch({
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      sessionId: input.sessionId,
      runId: input.runId,
      pluginId: input.pluginId,
      title: readString(draftBatch.title) ?? 'AI Draft Proposal',
      goal: readString(draftBatch.goal) ?? 'AI Draft Proposal',
      baseWorkspaceRevision: input.baseWorkspaceRevision,
      createdBy: input.userId,
      summary: {
        summary: resultObject.summary ?? null,
        evidence_refs: input.evidenceRefs,
      },
    });

    if (batch === undefined) {
      throw new Error('AI draft batch creation returned no row.');
    }

    for (const operation of operations) {
      await this.draftRepository.createDraftPatch({
        draftBatchId: batch.draftBatchId,
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
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

    return batch.draftBatchId;
  }

  private async failRun(
    workspaceId: string,
    projectId: string,
    sessionId: string | undefined,
    runId: string,
    message: string | undefined,
  ): Promise<void> {
    await this.db
      .update(runs)
      .set({ status: 'failed', completedAt: new Date(), updatedAt: new Date(), error: { message: message ?? '' } })
      .where(eq(runs.runId, runId));
    await this.recordEvent(workspaceId, projectId, sessionId, runId, 'runtime.failed', {
      message: message ?? 'Runtime failed.',
    });
  }

  private async recordEvent(
    workspaceId: string,
    projectId: string,
    sessionId: string | undefined,
    runId: string,
    eventType: string,
    payload: JsonObject,
  ): Promise<void> {
    const existingEvents = await this.db.select().from(runEvents).where(eq(runEvents.runId, runId));
    await this.db.insert(runEvents).values({
      eventId: createId('evt'),
      workspaceId,
      projectId,
      sessionId,
      runId,
      eventType,
      sequence: existingEvents.length + 1,
      payload,
    });
  }
}

function asJsonObject(value: JsonValue | undefined): JsonObject {
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
