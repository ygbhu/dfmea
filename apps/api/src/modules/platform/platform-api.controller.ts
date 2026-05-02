import {
  Body,
  Controller,
  Get,
  Inject,
  Param,
  Patch,
  Post,
  Query,
  Sse,
  type MessageEvent,
} from '@nestjs/common';
import { ok, type JsonObject } from '@dfmea/shared';
import type { Observable } from 'rxjs';
import type { ProjectionConsumer } from '../../services/projection.service';
import { validationFailed } from './platform-api.error';
import { PlatformApiService } from './platform-api.service';

type QueryParams = Record<string, string | string[] | undefined>;
type BodyRecord = Record<string, unknown>;

@Controller('api')
export class PlatformApiController {
  constructor(@Inject(PlatformApiService) private readonly platformApiService: PlatformApiService) {}

  @Post('workspaces')
  async createWorkspace(@Body() body: unknown) {
    const record = readBody(body);
    const workspace = await this.platformApiService.createWorkspace({
      name: readString(record, 'name') ?? 'Untitled Workspace',
      ...readOptionalJsonObjectProperty(record, 'metadata'),
    });

    return ok({ workspace });
  }

  @Get('workspaces/:workspaceId')
  async getWorkspace(@Param('workspaceId') workspaceId: string) {
    const workspace = await this.platformApiService.getWorkspace(workspaceId);
    return ok({ workspace });
  }

  @Post('workspaces/:workspaceId/projects')
  async createProject(@Param('workspaceId') workspaceId: string, @Body() body: unknown) {
    const record = readBody(body);
    const project = await this.platformApiService.createProject({
      workspaceId,
      name: readString(record, 'name') ?? 'Untitled Project',
      ...readOptionalJsonObjectProperty(record, 'metadata'),
    });

    return ok({ project });
  }

  @Get('projects/:projectId')
  async getProject(@Param('projectId') projectId: string) {
    const project = await this.platformApiService.getProject(projectId);
    return ok({ project });
  }

  @Post('projects/:projectId/sessions')
  async createSession(@Param('projectId') projectId: string, @Body() body: unknown) {
    const record = readBody(body);
    const session = await this.platformApiService.createSession({
      projectId,
      ...readOptionalStringProperty(record, 'userId', 'user_id'),
      ...readOptionalStringProperty(record, 'activePluginId', 'active_plugin_id'),
      ...readOptionalJsonObjectProperty(record, 'metadata'),
    });

    return ok({ session });
  }

  @Get('sessions/:sessionId')
  async getSession(@Param('sessionId') sessionId: string) {
    const session = await this.platformApiService.getSession(sessionId);
    return ok({ session });
  }

  @Post('sessions/:sessionId/runs')
  async startRun(@Param('sessionId') sessionId: string, @Body() body: unknown) {
    const record = readBody(body);
    const goal = readString(record, 'goal');

    if (goal === undefined) {
      throw validationFailed('Run goal is required.');
    }

    const run = await this.platformApiService.startRun({
      sessionId,
      goal,
      ...readOptionalStringProperty(record, 'userId', 'user_id'),
      ...readOptionalStringProperty(record, 'pluginId', 'plugin_id'),
    });

    return ok({ run });
  }

  @Get('runs/:runId')
  async getRun(@Param('runId') runId: string) {
    const run = await this.platformApiService.getRun(runId);
    return ok({ run });
  }

  @Post('runs/:runId/cancel')
  async cancelRun(@Param('runId') runId: string) {
    const run = await this.platformApiService.cancelRun(runId);
    return ok({ run });
  }

  @Get('runs/:runId/events')
  async listRunEvents(@Param('runId') runId: string) {
    const events = await this.platformApiService.listRunEvents(runId);
    return ok({ events });
  }

  @Sse('runs/:runId/events/stream')
  streamRunEvents(@Param('runId') runId: string): Observable<MessageEvent> {
    return this.platformApiService.streamRunEvents(runId);
  }

  @Get('projects/:projectId/ai-drafts')
  async listProjectDrafts(@Param('projectId') projectId: string) {
    const drafts = await this.platformApiService.listProjectDrafts(projectId);
    return ok({ drafts });
  }

  @Get('ai-drafts/:draftBatchId')
  async getDraft(@Param('draftBatchId') draftBatchId: string) {
    const draft = await this.platformApiService.getDraft(draftBatchId);
    return ok({ draft });
  }

  @Patch('ai-drafts/:draftBatchId/patches/:draftPatchId')
  async editDraftPatch(
    @Param('draftBatchId') draftBatchId: string,
    @Param('draftPatchId') draftPatchId: string,
    @Body() body: unknown,
  ) {
    const record = readBody(body);
    const afterPayload = readJsonObject(record, 'afterPayload', 'after_payload');

    if (afterPayload === undefined) {
      throw validationFailed('after_payload is required.');
    }

    const patch = await this.platformApiService.editDraftPatch({
      draftBatchId,
      draftPatchId,
      afterPayload,
      ...readOptionalStringProperty(record, 'editedBy', 'edited_by'),
    });

    return ok({ patch });
  }

  @Post('ai-drafts/:draftBatchId/edit')
  async editDraft(@Param('draftBatchId') draftBatchId: string, @Body() body: unknown) {
    const record = readBody(body);
    const draftPatchId = readString(record, 'draftPatchId', 'draft_patch_id');
    const afterPayload = readJsonObject(record, 'afterPayload', 'after_payload');

    if (draftPatchId === undefined || afterPayload === undefined) {
      throw validationFailed('draft_patch_id and after_payload are required.');
    }

    const patch = await this.platformApiService.editDraftPatch({
      draftBatchId,
      draftPatchId,
      afterPayload,
      ...readOptionalStringProperty(record, 'editedBy', 'edited_by'),
    });

    return ok({ patch });
  }

  @Post('ai-drafts/:draftBatchId/patches/:draftPatchId/reject')
  async rejectDraftPatch(
    @Param('draftBatchId') draftBatchId: string,
    @Param('draftPatchId') draftPatchId: string,
    @Body() body: unknown,
  ) {
    const record = readBody(body);
    const patch = await this.platformApiService.rejectDraftPatch({
      draftBatchId,
      draftPatchId,
      ...readOptionalStringProperty(record, 'rejectedBy', 'rejected_by'),
    });

    return ok({ patch });
  }

  @Post('ai-drafts/:draftBatchId/apply')
  async applyDraft(@Param('draftBatchId') draftBatchId: string, @Body() body: unknown) {
    const record = readBody(body);
    const result = await this.platformApiService.applyDraft({
      draftBatchId,
      ...readOptionalStringProperty(record, 'appliedBy', 'applied_by'),
    });

    return ok(result);
  }

  @Post('ai-drafts/:draftBatchId/reject')
  async rejectDraft(@Param('draftBatchId') draftBatchId: string, @Body() body: unknown) {
    const record = readBody(body);
    const batch = await this.platformApiService.rejectDraft({
      draftBatchId,
      ...readOptionalStringProperty(record, 'rejectedBy', 'rejected_by'),
    });

    return ok({ batch });
  }

  @Get('ai-drafts/:draftBatchId/preview')
  async getDraftPreview(@Param('draftBatchId') draftBatchId: string) {
    const preview = await this.platformApiService.getDraftPreview(draftBatchId);
    return ok(preview);
  }

  @Sse('ai-drafts/:draftBatchId/preview/events/stream')
  streamDraftPreviewEvents(@Param('draftBatchId') draftBatchId: string): Observable<MessageEvent> {
    return this.platformApiService.streamDraftPreviewEvents(draftBatchId);
  }

  @Get('projects/:projectId/projections')
  async getProjectProjection(
    @Param('projectId') projectId: string,
    @Query() query: QueryParams,
  ) {
    const projection = await this.platformApiService.getProjectProjection({
      projectId,
      ...readProjectionQuery(query),
    });

    return ok({ projection });
  }

  @Post('projections/rebuild')
  async rebuildProjection(@Body() body: unknown) {
    const record = readBody(body);
    const projectId = readString(record, 'projectId', 'project_id');

    if (projectId === undefined) {
      throw validationFailed('project_id is required.');
    }

    const rebuild = await this.platformApiService.rebuildProjection({
      projectId,
      ...readProjectionBody(record),
    });

    return ok(rebuild);
  }

  @Sse('projects/:projectId/projections/rebuild/stream')
  streamProjectionRebuild(
    @Param('projectId') projectId: string,
    @Query() query: QueryParams,
  ): Observable<MessageEvent> {
    return this.platformApiService.streamProjectionRebuild({
      projectId,
      ...readProjectionQuery(query),
    });
  }

  @Get('capability-invocations/:invocationId')
  async getCapabilityInvocation(@Param('invocationId') invocationId: string) {
    const invocation = await this.platformApiService.getCapabilityInvocation(invocationId);
    return ok({ invocation });
  }

  @Post('api-push/validate')
  async validateApiPush(@Body() body: unknown) {
    const record = readBody(body);
    const projectId = readString(record, 'projectId', 'project_id');

    if (projectId === undefined) {
      throw validationFailed('project_id is required.');
    }

    const result = await this.platformApiService.validateApiPush({
      projectId,
      ...readApiPushCommandBody(record),
    });

    return ok(result);
  }

  @Post('api-push/execute')
  async executeApiPush(@Body() body: unknown) {
    const record = readBody(body);
    const projectId = readString(record, 'projectId', 'project_id');

    if (projectId === undefined) {
      throw validationFailed('project_id is required.');
    }

    const result = await this.platformApiService.executeApiPush({
      projectId,
      ...readApiPushCommandBody(record),
    });

    return ok(result);
  }

  @Get('api-push/jobs/:apiPushJobId')
  async getApiPushJob(@Param('apiPushJobId') apiPushJobId: string) {
    const job = await this.platformApiService.getApiPushJob(apiPushJobId);
    return ok({ job });
  }

  @Get('api-push/records/:apiPushRecordId')
  async getApiPushRecord(@Param('apiPushRecordId') apiPushRecordId: string) {
    const record = await this.platformApiService.getApiPushRecord(apiPushRecordId);
    return ok({ record });
  }
}

function readBody(body: unknown): BodyRecord {
  if (typeof body === 'object' && body !== null && !Array.isArray(body)) {
    return body as BodyRecord;
  }

  return {};
}

function readString(record: BodyRecord, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];

    if (typeof value === 'string') {
      return value;
    }
  }

  return undefined;
}

function readJsonObject(record: BodyRecord, ...keys: string[]): JsonObject | undefined {
  for (const key of keys) {
    const value = record[key];

    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      return value as JsonObject;
    }
  }

  return undefined;
}

function readOptionalStringProperty(
  record: BodyRecord,
  camelKey: string,
  snakeKey: string,
): { [key: string]: string } {
  const value = readString(record, camelKey, snakeKey);

  return value === undefined ? {} : { [camelKey]: value };
}

function readOptionalJsonObjectProperty(
  record: BodyRecord,
  key: string,
): { [key: string]: JsonObject } {
  const value = readJsonObject(record, key);

  return value === undefined ? {} : { [key]: value };
}

function readProjectionQuery(query: QueryParams): {
  pluginId?: string;
  kind?: string;
  category?: string;
  scopeType?: string;
  scopeId?: string;
  consumer?: ProjectionConsumer;
} {
  const consumer = readProjectionConsumer(readQueryString(query, 'consumer'));

  return {
    ...readOptionalQueryStringProperty(query, 'pluginId', 'plugin_id'),
    ...readOptionalQueryStringProperty(query, 'kind', 'kind'),
    ...readOptionalQueryStringProperty(query, 'category', 'category'),
    ...readOptionalQueryStringProperty(query, 'scopeType', 'scope_type'),
    ...readOptionalQueryStringProperty(query, 'scopeId', 'scope_id'),
    ...(consumer !== undefined ? { consumer } : {}),
  };
}

function readProjectionBody(record: BodyRecord): {
  workspaceId?: string;
  pluginId?: string;
  kind?: string;
  category?: string;
  scopeType?: string;
  scopeId?: string;
} {
  return {
    ...readOptionalStringProperty(record, 'workspaceId', 'workspace_id'),
    ...readOptionalStringProperty(record, 'pluginId', 'plugin_id'),
    ...readOptionalStringProperty(record, 'kind', 'kind'),
    ...readOptionalStringProperty(record, 'category', 'category'),
    ...readOptionalStringProperty(record, 'scopeType', 'scope_type'),
    ...readOptionalStringProperty(record, 'scopeId', 'scope_id'),
  };
}

function readApiPushCommandBody(record: BodyRecord): {
  pluginId?: string;
  adapterId?: string;
  createdBy?: string;
  idempotencyKey?: string;
} {
  return {
    ...readOptionalStringProperty(record, 'pluginId', 'plugin_id'),
    ...readOptionalStringProperty(record, 'adapterId', 'adapter_id'),
    ...readOptionalStringProperty(record, 'createdBy', 'created_by'),
    ...readOptionalStringProperty(record, 'idempotencyKey', 'idempotency_key'),
  };
}

function readQueryString(query: QueryParams, key: string): string | undefined {
  const value = query[key];

  if (Array.isArray(value)) {
    return value[0];
  }

  return value;
}

function readOptionalQueryStringProperty(
  query: QueryParams,
  camelKey: string,
  snakeKey: string,
): { [key: string]: string } {
  const value = readQueryString(query, camelKey) ?? readQueryString(query, snakeKey);

  return value === undefined ? {} : { [camelKey]: value };
}

function readProjectionConsumer(value: string | undefined): ProjectionConsumer | undefined {
  if (value === 'ai' || value === 'ui' || value === 'export') {
    return value;
  }

  return undefined;
}
