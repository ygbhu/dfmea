import { Inject, Injectable, Optional, type MessageEvent, type OnModuleDestroy } from '@nestjs/common';
import { and, asc, desc, eq, gt } from 'drizzle-orm';
import { from, interval, mergeMap, Observable, startWith } from 'rxjs';
import type { JsonObject } from '@dfmea/shared';
import { createDatabaseClient, type AppDatabase, type DatabaseClient } from '../../db/client';
import { createId } from '../../db/id';
import {
  aiDraftBatches,
  capabilityInvocations,
  draftPatches,
  projects,
  runEvents,
  runs,
  sessions,
  workspaces,
} from '../../db/schema';
import type { apiPushJobs, apiPushRecords } from '../../db/schema';
import { AiDraftRepository } from '../../repositories/ai-draft.repository';
import { ScopeRepository } from '../../repositories/scope.repository';
import {
  ApiPushService,
  type ApiPushCommandInput,
  type ApiPushCommandResult,
} from '../../services/api-push.service';
import { MockRuntimeService } from '../../services/mock-runtime.service';
import { registerDfmeaProjectionHandlers } from '../../services/dfmea-projection-handlers';
import {
  ProjectionService,
  type ProjectionConsumer,
  type ProjectionRebuildInput,
  type ProjectionReadResult,
} from '../../services/projection.service';
import {
  notFound,
  PlatformApiException,
  scopeDenied,
  validationFailed,
} from './platform-api.error';

export const PLATFORM_API_DATABASE = 'PLATFORM_API_DATABASE';

export interface CreateWorkspaceInput {
  name: string;
  metadata?: JsonObject;
}

export interface CreateProjectInput {
  workspaceId: string;
  name: string;
  metadata?: JsonObject;
}

export interface CreateSessionInput {
  projectId: string;
  userId?: string;
  activePluginId?: string;
  metadata?: JsonObject;
}

export interface StartRunInput {
  sessionId: string;
  goal: string;
  userId?: string;
  pluginId?: string;
}

export interface ProjectionQueryInput {
  projectId: string;
  pluginId?: string;
  kind?: string;
  category?: string;
  scopeType?: string;
  scopeId?: string;
  consumer?: ProjectionConsumer;
}

export interface ProjectionRebuildRequestInput extends ProjectionQueryInput {
  workspaceId?: string;
}

export interface DraftPreviewNode {
  draftPatchId: string;
  operation: string;
  status: string;
  targetType: 'artifact';
  targetId: string | null;
  tempRef: string | null;
  artifactType: string | null;
  payload: JsonObject;
}

export interface DraftPreviewEdge {
  draftPatchId: string;
  operation: string;
  status: string;
  targetType: 'edge';
  targetId: string | null;
  tempRef: string | null;
  relationType: string | null;
  sourceTempRef: string | null;
  targetTempRef: string | null;
  sourceArtifactId: string | null;
  targetArtifactId: string | null;
  payload: JsonObject;
}

export interface DraftPreview {
  draftBatchId: string;
  workspaceId: string;
  projectId: string;
  sessionId: string | null;
  runId: string | null;
  pluginId: string;
  status: string;
  baseWorkspaceRevision: number;
  targetWorkspaceRevision: number | null;
  evidenceRefs: string[];
  nodes: DraftPreviewNode[];
  edges: DraftPreviewEdge[];
  validation: {
    status: 'not_validated' | 'valid' | 'invalid';
    pendingPatchCount: number;
    rejectedPatchCount: number;
  };
}

type WorkspaceRow = typeof workspaces.$inferSelect;
type ProjectRow = typeof projects.$inferSelect;
type SessionRow = typeof sessions.$inferSelect;
type RunRow = typeof runs.$inferSelect;
type RunEventRow = typeof runEvents.$inferSelect;
type DraftBatchRow = typeof aiDraftBatches.$inferSelect;
type DraftPatchRow = typeof draftPatches.$inferSelect;
type CapabilityInvocationRow = typeof capabilityInvocations.$inferSelect;
type ApiPushJobRow = typeof apiPushJobs.$inferSelect;
type ApiPushRecordRow = typeof apiPushRecords.$inferSelect;

@Injectable()
export class PlatformApiService implements OnModuleDestroy {
  private readonly db: AppDatabase;
  private readonly client: DatabaseClient | undefined;
  private readonly scopeRepository: ScopeRepository;
  private readonly draftRepository: AiDraftRepository;
  private readonly runtimeService: MockRuntimeService;
  private readonly apiPushService: ApiPushService;

  constructor(@Optional() @Inject(PLATFORM_API_DATABASE) database?: AppDatabase) {
    if (database === undefined) {
      this.client = createDatabaseClient();
      this.db = this.client.db;
    } else {
      this.client = undefined;
      this.db = database;
    }

    this.scopeRepository = new ScopeRepository(this.db);
    this.draftRepository = new AiDraftRepository(this.db);
    this.runtimeService = new MockRuntimeService(this.db);
    this.apiPushService = new ApiPushService(this.db);
  }

  async onModuleDestroy(): Promise<void> {
    await this.client?.close();
  }

  async createWorkspace(input: CreateWorkspaceInput): Promise<WorkspaceRow> {
    const workspace = await this.scopeRepository.createWorkspace({
      name: input.name,
      ...(input.metadata !== undefined ? { metadata: input.metadata } : {}),
    });

    return assertCreated(workspace, 'Workspace creation returned no row.');
  }

  async getWorkspace(workspaceId: string): Promise<WorkspaceRow> {
    const [workspace] = await this.db
      .select()
      .from(workspaces)
      .where(eq(workspaces.workspaceId, workspaceId));

    if (workspace === undefined) {
      throw notFound('WORKSPACE_NOT_FOUND', 'Workspace does not exist.', {
        workspace_id: workspaceId,
      });
    }

    return workspace;
  }

  async createProject(input: CreateProjectInput): Promise<ProjectRow> {
    await this.getWorkspace(input.workspaceId);
    const project = await this.scopeRepository.createProject({
      workspaceId: input.workspaceId,
      name: input.name,
      ...(input.metadata !== undefined ? { metadata: input.metadata } : {}),
    });

    return assertCreated(project, 'Project creation returned no row.');
  }

  async getProject(projectId: string): Promise<ProjectRow> {
    const [project] = await this.db.select().from(projects).where(eq(projects.projectId, projectId));

    if (project === undefined) {
      throw notFound('PROJECT_NOT_FOUND', 'Project does not exist.', {
        project_id: projectId,
      });
    }

    return project;
  }

  async createSession(input: CreateSessionInput): Promise<SessionRow> {
    const project = await this.getProject(input.projectId);

    const session = await this.scopeRepository.createSession({
      workspaceId: project.workspaceId,
      projectId: project.projectId,
      ...(input.userId !== undefined ? { userId: input.userId } : {}),
      ...(input.activePluginId !== undefined ? { activePluginId: input.activePluginId } : {}),
      ...(input.metadata !== undefined ? { metadata: input.metadata } : {}),
    });

    return assertCreated(session, 'Session creation returned no row.');
  }

  async getSession(sessionId: string): Promise<SessionRow> {
    const [session] = await this.db.select().from(sessions).where(eq(sessions.sessionId, sessionId));

    if (session === undefined) {
      throw notFound('SESSION_NOT_FOUND', 'Session does not exist.', {
        session_id: sessionId,
      });
    }

    return session;
  }

  async startRun(input: StartRunInput): Promise<{
    runId: string;
    draftBatchId: string;
    evidenceRefs: string[];
    eventsUrl: string;
    draftUrl: string;
  }> {
    const session = await this.getSession(input.sessionId);
    const goal = input.goal.trim();

    if (!goal) {
      throw validationFailed('Run goal is required.');
    }

    const userId = input.userId ?? session.userId ?? undefined;
    const pluginId = input.pluginId ?? session.activePluginId ?? 'dfmea';
    const result = await this.runtimeService.startRun({
      workspaceId: session.workspaceId,
      projectId: session.projectId,
      sessionId: session.sessionId,
      goal,
      ...(userId !== undefined ? { userId } : {}),
      pluginId,
    });

    return {
      ...result,
      eventsUrl: `/api/runs/${result.runId}/events/stream`,
      draftUrl: `/api/ai-drafts/${result.draftBatchId}`,
    };
  }

  async getRun(runId: string): Promise<RunRow> {
    const [run] = await this.db.select().from(runs).where(eq(runs.runId, runId));

    if (run === undefined) {
      throw notFound('RUN_NOT_FOUND', 'Run does not exist.', {
        run_id: runId,
      });
    }

    return run;
  }

  async cancelRun(runId: string): Promise<RunRow> {
    const run = await this.getRun(runId);

    if (isTerminalRunStatus(run.status)) {
      throw validationFailed('Run is already completed.', {
        run_id: run.runId,
        status: run.status,
      });
    }

    await this.runtimeService.cancel(runId);
    return this.getRun(runId);
  }

  async listRunEvents(runId: string): Promise<RunEventRow[]> {
    await this.getRun(runId);
    return this.db
      .select()
      .from(runEvents)
      .where(eq(runEvents.runId, runId))
      .orderBy(asc(runEvents.sequence));
  }

  streamRunEvents(runId: string): Observable<MessageEvent> {
    let lastSequence = 0;

    return interval(1_000).pipe(
      startWith(0),
      mergeMap(async () => {
        const events = await this.listRunEventsAfter(runId, lastSequence);
        return events.map((event) => {
          lastSequence = Math.max(lastSequence, event.sequence);
          return toSseMessage(event.eventId, event.eventType, toRunEventEnvelope(event));
        });
      }),
      mergeMap((messages) => from(messages)),
    );
  }

  async listProjectDrafts(projectId: string): Promise<DraftBatchRow[]> {
    await this.getProject(projectId);
    return this.db
      .select()
      .from(aiDraftBatches)
      .where(eq(aiDraftBatches.projectId, projectId))
      .orderBy(desc(aiDraftBatches.createdAt));
  }

  async getDraft(draftBatchId: string): Promise<{
    batch: DraftBatchRow;
    patches: DraftPatchRow[];
  }> {
    const batch = await this.draftRepository.getDraftBatch(draftBatchId);

    if (batch === undefined) {
      throw notFound('AI_DRAFT_NOT_FOUND', 'AI draft batch does not exist.', {
        draft_batch_id: draftBatchId,
      });
    }

    const patches = await this.draftRepository.listDraftPatches(draftBatchId);

    return { batch, patches };
  }

  async editDraftPatch(input: {
    draftBatchId: string;
    draftPatchId: string;
    afterPayload: JsonObject;
    editedBy?: string;
  }): Promise<DraftPatchRow> {
    const patch = await this.getDraftPatch(input.draftPatchId);

    if (patch.draftBatchId !== input.draftBatchId) {
      throw scopeDenied('Draft patch does not belong to the requested draft batch.', {
        draft_batch_id: input.draftBatchId,
        draft_patch_id: input.draftPatchId,
      });
    }

    const updatedPatch = await this.draftRepository.editDraftPatch({
      draftPatchId: input.draftPatchId,
      afterPayload: input.afterPayload,
      ...(input.editedBy !== undefined ? { editedBy: input.editedBy } : {}),
    });
    const { batch } = await this.getDraft(input.draftBatchId);
    await this.recordDraftRunEvent(batch, 'ai_draft.edited', {
      draft_batch_id: input.draftBatchId,
      draft_patch_id: input.draftPatchId,
    });

    return assertCreated(updatedPatch, 'Draft patch update returned no row.');
  }

  async rejectDraftPatch(input: {
    draftBatchId: string;
    draftPatchId: string;
    rejectedBy?: string;
  }): Promise<DraftPatchRow> {
    const patch = await this.getDraftPatch(input.draftPatchId);

    if (patch.draftBatchId !== input.draftBatchId) {
      throw scopeDenied('Draft patch does not belong to the requested draft batch.', {
        draft_batch_id: input.draftBatchId,
        draft_patch_id: input.draftPatchId,
      });
    }

    const rejectedPatch = await this.draftRepository.rejectDraftPatch({
      draftPatchId: input.draftPatchId,
      ...(input.rejectedBy !== undefined ? { rejectedBy: input.rejectedBy } : {}),
    });
    const { batch } = await this.getDraft(input.draftBatchId);
    await this.recordDraftRunEvent(batch, 'ai_draft.edited', {
      draft_batch_id: input.draftBatchId,
      draft_patch_id: input.draftPatchId,
      status: 'rejected',
    });

    return assertCreated(rejectedPatch, 'Draft patch rejection returned no row.');
  }

  async applyDraft(input: { draftBatchId: string; appliedBy?: string }): Promise<{
    applyResult: Awaited<ReturnType<AiDraftRepository['applyDraftBatch']>>;
    workingTreeProjection: ProjectionReadResult | null;
  }> {
    const { batch } = await this.getDraft(input.draftBatchId);
    await this.recordDraftRunEvent(batch, 'ai_draft.apply_started', {
      draft_batch_id: batch.draftBatchId,
    });

    const applyResult = await this.draftRepository.applyDraftBatch({
      draftBatchId: input.draftBatchId,
      ...(input.appliedBy !== undefined ? { appliedBy: input.appliedBy } : {}),
    });
    await this.recordDraftRunEvent(batch, 'ai_draft.applied', {
      draft_batch_id: batch.draftBatchId,
      from_revision: applyResult.fromRevision,
      to_revision: applyResult.toRevision,
    });

    const workingTreeProjection = await this.rebuildDefaultProjectionAfterApply(batch);

    return {
      applyResult,
      workingTreeProjection,
    };
  }

  async rejectDraft(input: { draftBatchId: string; rejectedBy?: string }): Promise<DraftBatchRow> {
    const { batch } = await this.getDraft(input.draftBatchId);
    const rejectedBatch = await this.draftRepository.rejectDraftBatch({
      draftBatchId: input.draftBatchId,
      ...(input.rejectedBy !== undefined ? { rejectedBy: input.rejectedBy } : {}),
    });

    await this.recordDraftRunEvent(batch, 'ai_draft.rejected', {
      draft_batch_id: batch.draftBatchId,
    });

    return assertCreated(rejectedBatch, 'Draft rejection returned no row.');
  }

  async getDraftPreview(draftBatchId: string): Promise<{
    draft: {
      batch: DraftBatchRow;
      patches: DraftPatchRow[];
    };
    preview: DraftPreview;
  }> {
    const draft = await this.getDraft(draftBatchId);

    return {
      draft,
      preview: buildDraftPreview(draft.batch, draft.patches),
    };
  }

  streamDraftPreviewEvents(draftBatchId: string): Observable<MessageEvent> {
    return new Observable<MessageEvent>((subscriber) => {
      void (async () => {
        try {
          const { preview } = await this.getDraftPreview(draftBatchId);
          const events = buildDraftPreviewEvents(preview);

          for (const event of events) {
            subscriber.next(toSseMessage(event.eventId, event.eventType, event));
          }

          subscriber.complete();
        } catch (error) {
          subscriber.error(error);
        }
      })();
    });
  }

  async getProjectProjection(input: ProjectionQueryInput): Promise<ProjectionReadResult> {
    const projectionInput = await this.createProjectionInput(input);
    const projectionService = this.createProjectionService();

    return projectionService.getProjection({
      ...projectionInput,
      consumer: input.consumer ?? 'ui',
    });
  }

  async rebuildProjection(input: ProjectionRebuildRequestInput): Promise<{
    result: ProjectionReadResult;
    events: string[];
  }> {
    const projectionInput = await this.createProjectionInput(input);
    const projectionService = this.createProjectionService();
    const result = await projectionService.rebuildProjectProjection(projectionInput);

    return {
      result,
      events: projectionService.listEvents(),
    };
  }

  streamProjectionRebuild(input: ProjectionRebuildRequestInput): Observable<MessageEvent> {
    return new Observable<MessageEvent>((subscriber) => {
      void (async () => {
        const eventBase = {
          eventId: createId('evt'),
          eventType: 'projection.rebuild.started',
          projectId: input.projectId,
          pluginId: input.pluginId ?? 'dfmea',
          kind: input.kind ?? 'working_tree',
          createdAt: new Date().toISOString(),
          payload: {},
        };

        subscriber.next(toSseMessage(eventBase.eventId, eventBase.eventType, eventBase));

        try {
          const rebuild = await this.rebuildProjection(input);
          const completedEvent = {
            ...eventBase,
            eventId: createId('evt'),
            eventType: 'projection.rebuild.completed',
            createdAt: new Date().toISOString(),
            payload: {
              projection_id: rebuild.result.projection.projectionId,
              freshness: rebuild.result.freshness,
              source_revision: rebuild.result.projection.sourceRevision,
            },
          };

          subscriber.next(
            toSseMessage(completedEvent.eventId, completedEvent.eventType, completedEvent),
          );
          subscriber.complete();
        } catch (error) {
          const failedEvent = {
            ...eventBase,
            eventId: createId('evt'),
            eventType: 'projection.rebuild.failed',
            createdAt: new Date().toISOString(),
            payload: {
              message: error instanceof Error ? error.message : 'Projection rebuild failed.',
            },
          };

          subscriber.next(toSseMessage(failedEvent.eventId, failedEvent.eventType, failedEvent));
          subscriber.complete();
        }
      })();
    });
  }

  async getCapabilityInvocation(invocationId: string): Promise<CapabilityInvocationRow> {
    const [invocation] = await this.db
      .select()
      .from(capabilityInvocations)
      .where(eq(capabilityInvocations.invocationId, invocationId));

    if (invocation === undefined) {
      throw notFound('CAPABILITY_INVOCATION_NOT_FOUND', 'Capability invocation does not exist.', {
        invocation_id: invocationId,
      });
    }

    return invocation;
  }

  async validateApiPush(input: ApiPushCommandInput): Promise<ApiPushCommandResult> {
    return this.apiPushService.validate(input);
  }

  async executeApiPush(input: ApiPushCommandInput): Promise<ApiPushCommandResult> {
    return this.apiPushService.execute(input);
  }

  async getApiPushJob(apiPushJobId: string): Promise<ApiPushJobRow> {
    return this.apiPushService.getJob(apiPushJobId);
  }

  async getApiPushRecord(apiPushRecordId: string): Promise<ApiPushRecordRow> {
    return this.apiPushService.getRecord(apiPushRecordId);
  }

  private async getDraftPatch(draftPatchId: string): Promise<DraftPatchRow> {
    const [patch] = await this.db
      .select()
      .from(draftPatches)
      .where(eq(draftPatches.draftPatchId, draftPatchId));

    if (patch === undefined) {
      throw notFound('AI_DRAFT_PATCH_NOT_FOUND', 'AI draft patch does not exist.', {
        draft_patch_id: draftPatchId,
      });
    }

    return patch;
  }

  private async listRunEventsAfter(runId: string, sequence: number): Promise<RunEventRow[]> {
    await this.getRun(runId);
    return this.db
      .select()
      .from(runEvents)
      .where(and(eq(runEvents.runId, runId), gt(runEvents.sequence, sequence)))
      .orderBy(asc(runEvents.sequence));
  }

  private createProjectionService(): ProjectionService {
    const projectionService = new ProjectionService(this.db);
    registerDfmeaProjectionHandlers(projectionService);
    return projectionService;
  }

  private async createProjectionInput(input: ProjectionRebuildRequestInput): Promise<ProjectionRebuildInput> {
    const project = await this.getProject(input.projectId);
    const workspaceId = input.workspaceId ?? project.workspaceId;

    if (workspaceId !== project.workspaceId) {
      throw scopeDenied('Projection workspace does not match project workspace.', {
        workspace_id: workspaceId,
        project_workspace_id: project.workspaceId,
        project_id: project.projectId,
      });
    }

    const kind = input.kind ?? 'working_tree';

    return {
      workspaceId,
      projectId: project.projectId,
      pluginId: input.pluginId ?? 'dfmea',
      kind,
      category: input.category ?? defaultProjectionCategory(kind),
      scopeType: input.scopeType ?? 'project',
      scopeId: input.scopeId ?? project.projectId,
    };
  }

  private async rebuildDefaultProjectionAfterApply(
    batch: DraftBatchRow,
  ): Promise<ProjectionReadResult | null> {
    if (batch.pluginId !== 'dfmea') {
      return null;
    }

    const rebuild = await this.rebuildProjection({
      workspaceId: batch.workspaceId,
      projectId: batch.projectId,
      pluginId: batch.pluginId,
      kind: 'working_tree',
      category: 'working',
      scopeType: 'project',
      scopeId: batch.projectId,
    });

    return rebuild.result;
  }

  private async recordDraftRunEvent(
    batch: DraftBatchRow,
    eventType: string,
    payload: JsonObject,
  ): Promise<void> {
    if (batch.runId === null) {
      return;
    }

    const existingEvents = await this.db
      .select()
      .from(runEvents)
      .where(eq(runEvents.runId, batch.runId));
    await this.db.insert(runEvents).values({
      eventId: createId('evt'),
      workspaceId: batch.workspaceId,
      projectId: batch.projectId,
      sessionId: batch.sessionId ?? undefined,
      runId: batch.runId,
      eventType,
      sequence: existingEvents.length + 1,
      payload,
    });
  }
}

function isTerminalRunStatus(status: string): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled' || status === 'timeout';
}

function assertCreated<T>(value: T | undefined, message: string): T {
  if (value === undefined) {
    throw new PlatformApiException({
      code: 'INTERNAL_WRITE_FAILED',
      message,
      statusCode: 500,
    });
  }

  return value;
}

function defaultProjectionCategory(kind: string): string {
  if (kind.includes('export')) {
    return 'export';
  }

  if (kind.includes('draft')) {
    return 'draft_preview';
  }

  return 'working';
}

function buildDraftPreview(batch: DraftBatchRow, patches: DraftPatchRow[]): DraftPreview {
  const nodes = patches
    .filter((patch) => patch.targetType === 'artifact')
    .map((patch): DraftPreviewNode => ({
      draftPatchId: patch.draftPatchId,
      operation: patch.patchType,
      status: patch.status,
      targetType: 'artifact',
      targetId: patch.targetId,
      tempRef: patch.tempRef,
      artifactType: patch.artifactType,
      payload: readPatchPayload(patch),
    }));
  const edges = patches
    .filter((patch) => patch.targetType === 'edge')
    .map((patch): DraftPreviewEdge => ({
      draftPatchId: patch.draftPatchId,
      operation: patch.patchType,
      status: patch.status,
      targetType: 'edge',
      targetId: patch.targetId,
      tempRef: patch.tempRef,
      relationType: patch.relationType,
      sourceTempRef: patch.sourceTempRef,
      targetTempRef: patch.targetTempRef,
      sourceArtifactId: patch.sourceArtifactId,
      targetArtifactId: patch.targetArtifactId,
      payload: readPatchPayload(patch),
    }));
  const rejectedPatchCount = patches.filter((patch) => patch.status === 'rejected').length;
  const pendingPatchCount = patches.filter((patch) => patch.status === 'pending').length;

  return {
    draftBatchId: batch.draftBatchId,
    workspaceId: batch.workspaceId,
    projectId: batch.projectId,
    sessionId: batch.sessionId,
    runId: batch.runId,
    pluginId: batch.pluginId,
    status: batch.status,
    baseWorkspaceRevision: batch.baseWorkspaceRevision,
    targetWorkspaceRevision: batch.targetWorkspaceRevision,
    evidenceRefs: readEvidenceRefs(batch.summary),
    nodes,
    edges,
    validation: {
      status: 'not_validated',
      pendingPatchCount,
      rejectedPatchCount,
    },
  };
}

function buildDraftPreviewEvents(preview: DraftPreview): DraftPreviewEvent[] {
  const createdAt = new Date().toISOString();
  const base = {
    workspaceId: preview.workspaceId,
    projectId: preview.projectId,
    sessionId: preview.sessionId,
    runId: preview.runId,
    draftBatchId: preview.draftBatchId,
    createdAt,
  };
  const events: DraftPreviewEvent[] = [
    {
      ...base,
      eventId: createId('evt'),
      eventType: 'draft.preview.started',
      sequence: 1,
      payload: {
        draft_batch_id: preview.draftBatchId,
        base_workspace_revision: preview.baseWorkspaceRevision,
      },
    },
  ];

  for (const node of preview.nodes) {
    events.push({
      ...base,
      eventId: createId('evt'),
      eventType: node.operation === 'logical_delete' ? 'draft.preview.node_removed' : 'draft.preview.node_upserted',
      sequence: events.length + 1,
      payload: node as unknown as JsonObject,
    });
  }

  for (const edge of preview.edges) {
    events.push({
      ...base,
      eventId: createId('evt'),
      eventType: edge.operation === 'logical_delete' ? 'draft.preview.edge_removed' : 'draft.preview.edge_upserted',
      sequence: events.length + 1,
      payload: edge as unknown as JsonObject,
    });
  }

  events.push({
    ...base,
    eventId: createId('evt'),
    eventType: 'draft.preview.validation_updated',
    sequence: events.length + 1,
    payload: preview.validation,
  });
  events.push({
    ...base,
    eventId: createId('evt'),
    eventType: 'draft.preview.completed',
    sequence: events.length + 1,
    payload: {
      node_count: preview.nodes.length,
      edge_count: preview.edges.length,
      freshness: 'persisted',
    },
  });

  return events;
}

interface DraftPreviewEvent {
  eventId: string;
  eventType: string;
  workspaceId: string;
  projectId: string;
  sessionId: string | null;
  runId: string | null;
  draftBatchId: string;
  sequence: number;
  createdAt: string;
  payload: JsonObject;
}

function readPatchPayload(patch: DraftPatchRow): JsonObject {
  return patch.afterPayload ?? patch.payloadPatch ?? patch.beforePayload ?? {};
}

function readEvidenceRefs(summary: JsonObject): string[] {
  const value = summary.evidence_refs;

  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === 'string');
}

function toRunEventEnvelope(event: RunEventRow): JsonObject {
  return {
    event_id: event.eventId,
    event_type: event.eventType,
    workspace_id: event.workspaceId,
    project_id: event.projectId,
    session_id: event.sessionId,
    run_id: event.runId,
    sequence: event.sequence,
    created_at: event.createdAt.toISOString(),
    payload: event.payload,
  };
}

function toSseMessage(eventId: string, eventType: string, data: object): MessageEvent {
  return {
    id: eventId,
    type: eventType,
    data,
  };
}
