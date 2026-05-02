import { createHash } from 'node:crypto';
import { desc, eq } from 'drizzle-orm';
import type { ApiPushEventType, ApiPushMode, JsonObject, JsonValue } from '@dfmea/shared';
import type { AppDatabase } from '../db/client';
import { createId } from '../db/id';
import { apiPushJobs, apiPushRecords, projects } from '../db/schema';
import { registerDfmeaProjectionHandlers } from './dfmea-projection-handlers';
import { ProjectionService, type ProjectionReadResult } from './projection.service';

const defaultAdapterId = 'mock-mature-fmea';
const defaultPluginId = 'dfmea';
const exportProjectionKind = 'export_payload';

export type ApiPushServiceErrorCode =
  | 'PROJECT_NOT_FOUND'
  | 'API_PUSH_JOB_NOT_FOUND'
  | 'API_PUSH_RECORD_NOT_FOUND'
  | 'EXPORT_PROJECTION_STALE'
  | 'EXPORT_PAYLOAD_INVALID'
  | 'EXPORT_ADAPTER_NOT_FOUND'
  | 'EXPORT_IDEMPOTENCY_CONFLICT'
  | 'EXTERNAL_VALIDATION_FAILED'
  | 'EXTERNAL_PUSH_FAILED';

export class ApiPushServiceError extends Error {
  readonly code: ApiPushServiceErrorCode;
  readonly details: Record<string, unknown>;

  constructor(code: ApiPushServiceErrorCode, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = 'ApiPushServiceError';
    this.code = code;
    this.details = details;
    Object.setPrototypeOf(this, ApiPushServiceError.prototype);
  }
}

export interface ApiPushCommandInput {
  projectId: string;
  pluginId?: string;
  adapterId?: string;
  createdBy?: string;
  idempotencyKey?: string;
}

export interface ApiPushCommandResult {
  job: typeof apiPushJobs.$inferSelect;
  record: typeof apiPushRecords.$inferSelect | null;
  validation: ApiPushValidationResult;
  sourceProjection: ProjectionReadResult;
  events: ApiPushEventType[];
  idempotent: boolean;
}

interface ApiPushValidationResult extends JsonObject {
  status: 'passed' | 'failed';
  findings: JsonObject[];
}

interface ApiPushAdapter {
  adapterId: string;
  validate(payload: JsonObject, context: ApiPushAdapterContext): Promise<ApiPushValidationResult>;
  push(payload: JsonObject, context: ApiPushAdapterContext): Promise<ApiPushAdapterPushResult>;
}

interface ApiPushAdapterContext {
  projectId: string;
  sourceWorkspaceRevision: number;
  sourceProjectionId: string;
  payloadChecksum: string;
  idempotencyKey: string;
}

interface ApiPushAdapterPushResult {
  externalSystem: string;
  externalSystemId: string;
  externalJobId: string;
  externalRecordId: string;
  externalStatus: string;
  responseSummary: JsonObject;
}

export class ApiPushService {
  private readonly adapters = new Map<string, ApiPushAdapter>();

  constructor(private readonly db: AppDatabase) {
    const adapter = new MockMatureFmeaAdapter();
    this.adapters.set(adapter.adapterId, adapter);
  }

  async validate(input: ApiPushCommandInput): Promise<ApiPushCommandResult> {
    return this.runCommand({ ...input, mode: 'validate_only' });
  }

  async execute(input: ApiPushCommandInput): Promise<ApiPushCommandResult> {
    return this.runCommand({ ...input, mode: 'execute' });
  }

  async getJob(apiPushJobId: string): Promise<typeof apiPushJobs.$inferSelect> {
    const [job] = await this.db
      .select()
      .from(apiPushJobs)
      .where(eq(apiPushJobs.apiPushJobId, apiPushJobId));

    if (job === undefined) {
      throw new ApiPushServiceError('API_PUSH_JOB_NOT_FOUND', 'API Push job does not exist.', {
        api_push_job_id: apiPushJobId,
      });
    }

    return job;
  }

  async getRecord(apiPushRecordId: string): Promise<typeof apiPushRecords.$inferSelect> {
    const [record] = await this.db
      .select()
      .from(apiPushRecords)
      .where(eq(apiPushRecords.apiPushRecordId, apiPushRecordId));

    if (record === undefined) {
      throw new ApiPushServiceError('API_PUSH_RECORD_NOT_FOUND', 'API Push record does not exist.', {
        api_push_record_id: apiPushRecordId,
      });
    }

    return record;
  }

  private async runCommand(
    input: ApiPushCommandInput & { mode: ApiPushMode },
  ): Promise<ApiPushCommandResult> {
    const project = await this.getProject(input.projectId);
    const pluginId = input.pluginId ?? defaultPluginId;
    const adapterId = input.adapterId ?? defaultAdapterId;
    const adapter = this.adapters.get(adapterId);

    if (adapter === undefined) {
      throw new ApiPushServiceError('EXPORT_ADAPTER_NOT_FOUND', 'API Push adapter is not registered.', {
        adapter_id: adapterId,
      });
    }

    const sourceProjection = await this.getFreshExportProjection({
      workspaceId: project.workspaceId,
      projectId: project.projectId,
      pluginId,
    });
    const payloadChecksum = checksumJson(sourceProjection.projection.payload);
    const apiPushJobId = createId('pushjob');
    const idempotencyKey =
      input.idempotencyKey ??
      `idem_${project.projectId}_rev_${sourceProjection.projection.sourceRevision}_${adapterId}_${apiPushJobId}`;
    const existing = await this.findExistingJob(idempotencyKey);

    if (existing !== undefined) {
      return this.replayExistingJob(existing, sourceProjection);
    }

    const context: ApiPushAdapterContext = {
      projectId: project.projectId,
      sourceWorkspaceRevision: sourceProjection.projection.sourceRevision,
      sourceProjectionId: sourceProjection.projection.projectionId,
      payloadChecksum,
      idempotencyKey,
    };
    const events: ApiPushEventType[] = ['api_push.job.created', 'api_push.validation.started'];
    const job = await this.createJob({
      apiPushJobId,
      workspaceId: project.workspaceId,
      projectId: project.projectId,
      pluginId,
      adapterId,
      mode: input.mode,
      sourceProjection,
      idempotencyKey,
      createdBy: input.createdBy,
      payloadChecksum,
    });

    try {
      const validation = await adapter.validate(sourceProjection.projection.payload, context);
      events.push('api_push.validation.completed');

      if (validation.status === 'failed') {
        await this.failJob(job.apiPushJobId, 'validation_failed', {
          code: 'EXTERNAL_VALIDATION_FAILED',
          message: 'Mature FMEA mock adapter rejected the export payload.',
          details: { findings: validation.findings },
        });
        throw new ApiPushServiceError(
          'EXTERNAL_VALIDATION_FAILED',
          'Mature FMEA mock adapter rejected the export payload.',
          { findings: validation.findings },
        );
      }

      if (input.mode === 'validate_only') {
        const completedJob = await this.completeJob(job.apiPushJobId, {
          validation,
          payload_checksum: payloadChecksum,
          phases: events,
        });
        return {
          job: completedJob,
          record: null,
          validation,
          sourceProjection,
          events,
          idempotent: false,
        };
      }

      events.push('api_push.execute.started');
      await this.markJobPushing(job.apiPushJobId);
      const pushResult = await adapter.push(sourceProjection.projection.payload, context);
      const record = await this.createRecord({
        job,
        pushResult,
        sourceProjection,
        payloadChecksum,
      });
      events.push('api_push.execute.completed');
      const completedJob = await this.completeJob(job.apiPushJobId, {
        validation,
        api_push_record_id: record.apiPushRecordId,
        external_status: record.externalStatus,
        payload_checksum: payloadChecksum,
        phases: events,
      });

      return {
        job: completedJob,
        record,
        validation,
        sourceProjection,
        events,
        idempotent: false,
      };
    } catch (error) {
      if (error instanceof ApiPushServiceError) {
        throw error;
      }

      events.push('api_push.execute.failed');
      await this.failJob(job.apiPushJobId, 'failed', {
        code: 'EXTERNAL_PUSH_FAILED',
        message: 'Mature FMEA mock adapter push failed.',
        details: { cause: error instanceof Error ? error.message : String(error) },
      });
      throw new ApiPushServiceError('EXTERNAL_PUSH_FAILED', 'Mature FMEA mock adapter push failed.', {
        cause: error instanceof Error ? error.message : String(error),
      });
    }
  }

  private async getProject(projectId: string): Promise<typeof projects.$inferSelect> {
    const [project] = await this.db.select().from(projects).where(eq(projects.projectId, projectId));

    if (project === undefined) {
      throw new ApiPushServiceError('PROJECT_NOT_FOUND', 'Project does not exist.', {
        project_id: projectId,
      });
    }

    return project;
  }

  private async getFreshExportProjection(input: {
    workspaceId: string;
    projectId: string;
    pluginId: string;
  }): Promise<ProjectionReadResult> {
    const projectionService = new ProjectionService(this.db);
    registerDfmeaProjectionHandlers(projectionService);
    const projection = await projectionService.getProjection({
      workspaceId: input.workspaceId,
      projectId: input.projectId,
      pluginId: input.pluginId,
      kind: exportProjectionKind,
      category: 'export',
      scopeType: 'project',
      scopeId: input.projectId,
      consumer: 'export',
    });

    if (
      projection.freshness !== 'fresh' ||
      projection.projection.status !== 'fresh' ||
      projection.projection.sourceRevision !== projection.currentWorkspaceRevision
    ) {
      throw new ApiPushServiceError('EXPORT_PROJECTION_STALE', 'Export projection is not fresh.', {
        project_id: input.projectId,
        projection_id: projection.projection.projectionId,
        source_revision: projection.projection.sourceRevision,
        current_workspace_revision: projection.currentWorkspaceRevision,
      });
    }

    return projection;
  }

  private async findExistingJob(
    idempotencyKey: string,
  ): Promise<typeof apiPushJobs.$inferSelect | undefined> {
    const [job] = await this.db
      .select()
      .from(apiPushJobs)
      .where(eq(apiPushJobs.idempotencyKey, idempotencyKey));

    return job;
  }

  private async replayExistingJob(
    job: typeof apiPushJobs.$inferSelect,
    sourceProjection: ProjectionReadResult,
  ): Promise<ApiPushCommandResult> {
    if (
      job.projectId !== sourceProjection.projection.projectId ||
      job.sourceProjectionId !== sourceProjection.projection.projectionId ||
      job.sourceWorkspaceRevision !== sourceProjection.projection.sourceRevision
    ) {
      throw new ApiPushServiceError(
        'EXPORT_IDEMPOTENCY_CONFLICT',
        'Idempotency key is already bound to another API Push source.',
        {
          api_push_job_id: job.apiPushJobId,
          idempotency_key: job.idempotencyKey,
        },
      );
    }

    const [record] = await this.db
      .select()
      .from(apiPushRecords)
      .where(eq(apiPushRecords.apiPushJobId, job.apiPushJobId))
      .orderBy(desc(apiPushRecords.createdAt))
      .limit(1);
    const validation = readValidationResult(job.result);

    return {
      job,
      record: record ?? null,
      validation,
      sourceProjection,
      events: [],
      idempotent: true,
    };
  }

  private async createJob(input: {
    apiPushJobId: string;
    workspaceId: string;
    projectId: string;
    pluginId: string;
    adapterId: string;
    mode: ApiPushMode;
    sourceProjection: ProjectionReadResult;
    idempotencyKey: string;
    createdBy: string | undefined;
    payloadChecksum: string;
  }): Promise<typeof apiPushJobs.$inferSelect> {
    const [job] = await this.db
      .insert(apiPushJobs)
      .values({
        apiPushJobId: input.apiPushJobId,
        workspaceId: input.workspaceId,
        projectId: input.projectId,
        pluginId: input.pluginId,
        adapterId: input.adapterId,
        mode: input.mode,
        status: 'validating',
        sourceProjectionId: input.sourceProjection.projection.projectionId,
        sourceWorkspaceRevision: input.sourceProjection.projection.sourceRevision,
        idempotencyKey: input.idempotencyKey,
        request: {
          mode: input.mode,
          payload_checksum: input.payloadChecksum,
          projection_kind: exportProjectionKind,
        },
        ...(input.createdBy !== undefined ? { createdBy: input.createdBy } : {}),
        startedAt: new Date(),
      })
      .returning();

    if (job === undefined) {
      throw new ApiPushServiceError('EXTERNAL_PUSH_FAILED', 'API Push job insert returned no row.');
    }

    return job;
  }

  private async markJobPushing(apiPushJobId: string): Promise<void> {
    await this.db
      .update(apiPushJobs)
      .set({
        status: 'pushing',
        updatedAt: new Date(),
      })
      .where(eq(apiPushJobs.apiPushJobId, apiPushJobId));
  }

  private async completeJob(
    apiPushJobId: string,
    result: JsonObject,
  ): Promise<typeof apiPushJobs.$inferSelect> {
    const [job] = await this.db
      .update(apiPushJobs)
      .set({
        status: 'completed',
        result,
        error: null,
        completedAt: new Date(),
        updatedAt: new Date(),
      })
      .where(eq(apiPushJobs.apiPushJobId, apiPushJobId))
      .returning();

    if (job === undefined) {
      throw new ApiPushServiceError('API_PUSH_JOB_NOT_FOUND', 'API Push job disappeared.', {
        api_push_job_id: apiPushJobId,
      });
    }

    return job;
  }

  private async failJob(
    apiPushJobId: string,
    status: 'validation_failed' | 'failed',
    error: JsonObject,
  ): Promise<void> {
    await this.db
      .update(apiPushJobs)
      .set({
        status,
        error,
        completedAt: new Date(),
        updatedAt: new Date(),
      })
      .where(eq(apiPushJobs.apiPushJobId, apiPushJobId));
  }

  private async createRecord(input: {
    job: typeof apiPushJobs.$inferSelect;
    pushResult: ApiPushAdapterPushResult;
    sourceProjection: ProjectionReadResult;
    payloadChecksum: string;
  }): Promise<typeof apiPushRecords.$inferSelect> {
    const [record] = await this.db
      .insert(apiPushRecords)
      .values({
        apiPushRecordId: createId('pushrec'),
        apiPushJobId: input.job.apiPushJobId,
        workspaceId: input.job.workspaceId,
        projectId: input.job.projectId,
        pluginId: input.job.pluginId,
        adapterId: input.job.adapterId,
        externalSystem: input.pushResult.externalSystem,
        externalSystemId: input.pushResult.externalSystemId,
        externalJobId: input.pushResult.externalJobId,
        externalRecordId: input.pushResult.externalRecordId,
        externalStatus: input.pushResult.externalStatus,
        sourceProjectionId: input.sourceProjection.projection.projectionId,
        sourceWorkspaceRevision: input.sourceProjection.projection.sourceRevision,
        payloadChecksum: input.payloadChecksum,
        responseSummary: input.pushResult.responseSummary,
      })
      .returning();

    if (record === undefined) {
      throw new ApiPushServiceError('EXTERNAL_PUSH_FAILED', 'API Push record insert returned no row.');
    }

    return record;
  }
}

class MockMatureFmeaAdapter implements ApiPushAdapter {
  readonly adapterId = defaultAdapterId;

  async validate(payload: JsonObject): Promise<ApiPushValidationResult> {
    const artifacts = readJsonArray(payload.artifacts);
    const edges = readJsonArray(payload.edges);
    const validationStatus = readNestedString(payload, ['summary', 'validation_status']);
    const findings: JsonObject[] = [];

    if (payload.kind !== 'dfmea.export_payload') {
      findings.push({
        code: 'EXPORT_PAYLOAD_KIND_INVALID',
        severity: 'blocking',
        message: 'Expected dfmea.export_payload.',
      });
    }

    if (validationStatus !== 'passed') {
      findings.push({
        code: 'DFMEA_EXPORT_VALIDATION_FAILED',
        severity: 'blocking',
        message: 'DFMEA export projection did not pass graph validation.',
      });
    }

    if (artifacts.length === 0) {
      findings.push({
        code: 'DFMEA_EXPORT_EMPTY',
        severity: 'blocking',
        message: 'DFMEA export payload must include at least one artifact.',
      });
    }

    return {
      status: findings.length ? 'failed' : 'passed',
      findings,
      artifact_count: artifacts.length,
      edge_count: edges.length,
    };
  }

  async push(
    payload: JsonObject,
    context: ApiPushAdapterContext,
  ): Promise<ApiPushAdapterPushResult> {
    const artifacts = readJsonArray(payload.artifacts);
    const edges = readJsonArray(payload.edges);
    const suffix = context.payloadChecksum.slice(0, 16);

    return {
      externalSystem: 'mock-mature-fmea',
      externalSystemId: 'mock-mature-fmea-local',
      externalJobId: `mock_job_rev_${context.sourceWorkspaceRevision}_${suffix.slice(0, 8)}`,
      externalRecordId: `mature_fmea_${suffix}`,
      externalStatus: 'accepted',
      responseSummary: {
        artifact_count: artifacts.length,
        edge_count: edges.length,
        idempotency_key: context.idempotencyKey,
        source_projection_id: context.sourceProjectionId,
        source_workspace_revision: context.sourceWorkspaceRevision,
      },
    };
  }
}

function readJsonArray(value: JsonValue | undefined): JsonObject[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is JsonObject => {
    return typeof item === 'object' && item !== null && !Array.isArray(item);
  });
}

function readNestedString(value: JsonValue | undefined, path: string[]): string | undefined {
  let current = value;

  for (const key of path) {
    if (typeof current !== 'object' || current === null || Array.isArray(current)) {
      return undefined;
    }

    current = current[key];
  }

  return typeof current === 'string' ? current : undefined;
}

function readValidationResult(value: JsonObject | null): ApiPushValidationResult {
  const validation =
    value !== null && typeof value.validation === 'object' && value.validation !== null
      ? value.validation
      : undefined;

  if (validation !== undefined && !Array.isArray(validation) && validation.status === 'passed') {
    return {
      status: 'passed',
      findings: [],
    };
  }

  return {
    status: 'failed',
    findings: [],
  };
}

function checksumJson(value: JsonValue): string {
  return createHash('sha256').update(stableStringify(value)).digest('hex');
}

function stableStringify(value: JsonValue): string {
  if (Array.isArray(value)) {
    return `[${value.map((item) => stableStringify(item)).join(',')}]`;
  }

  if (typeof value === 'object' && value !== null) {
    return `{${Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableStringify(item)}`)
      .join(',')}}`;
  }

  return JSON.stringify(value);
}
