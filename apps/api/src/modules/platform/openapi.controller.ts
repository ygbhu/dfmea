import { Controller, Get } from '@nestjs/common';

@Controller('api')
export class OpenApiController {
  @Get('openapi.json')
  getOpenApiDocument() {
    return {
      openapi: '3.1.0',
      info: {
        title: 'DFMEA Workspace Platform API',
        version: '0.9.0',
      },
      paths: {
        '/api/workspaces': {
          post: { summary: 'Create workspace' },
        },
        '/api/workspaces/{workspaceId}': {
          get: { summary: 'Get workspace' },
        },
        '/api/workspaces/{workspaceId}/projects': {
          post: { summary: 'Create project' },
        },
        '/api/projects/{projectId}/sessions': {
          post: { summary: 'Create session' },
        },
        '/api/sessions/{sessionId}/runs': {
          post: { summary: 'Start mock runtime run' },
        },
        '/api/runs/{runId}': {
          get: { summary: 'Get run' },
        },
        '/api/runs/{runId}/cancel': {
          post: { summary: 'Cancel run' },
        },
        '/api/runs/{runId}/events': {
          get: { summary: 'List run events' },
        },
        '/api/runs/{runId}/events/stream': {
          get: { summary: 'Stream run events by SSE' },
        },
        '/api/projects/{projectId}/ai-drafts': {
          get: { summary: 'List project AI drafts' },
        },
        '/api/ai-drafts/{draftBatchId}': {
          get: { summary: 'Get AI draft batch and patches' },
        },
        '/api/ai-drafts/{draftBatchId}/edit': {
          post: { summary: 'Edit AI draft patch' },
        },
        '/api/ai-drafts/{draftBatchId}/patches/{draftPatchId}': {
          patch: { summary: 'Edit AI draft patch' },
        },
        '/api/ai-drafts/{draftBatchId}/apply': {
          post: { summary: 'Apply AI draft batch' },
        },
        '/api/ai-drafts/{draftBatchId}/reject': {
          post: { summary: 'Reject AI draft batch' },
        },
        '/api/ai-drafts/{draftBatchId}/preview': {
          get: { summary: 'Rebuild persisted draft preview from patches' },
        },
        '/api/ai-drafts/{draftBatchId}/preview/events/stream': {
          get: { summary: 'Stream persisted draft preview events by SSE' },
        },
        '/api/projects/{projectId}/projections': {
          get: { summary: 'Get project projection' },
        },
        '/api/projections/rebuild': {
          post: { summary: 'Rebuild projection' },
        },
        '/api/projects/{projectId}/projections/rebuild/stream': {
          get: { summary: 'Stream projection rebuild events by SSE' },
        },
        '/api/capability-invocations/{invocationId}': {
          get: { summary: 'Get capability invocation' },
        },
        '/api/api-push/validate': {
          post: { summary: 'Validate fresh DFMEA export projection against mock mature FMEA API' },
        },
        '/api/api-push/execute': {
          post: { summary: 'Push fresh DFMEA export projection to mock mature FMEA API' },
        },
        '/api/api-push/jobs/{apiPushJobId}': {
          get: { summary: 'Get API Push job' },
        },
        '/api/api-push/records/{apiPushRecordId}': {
          get: { summary: 'Get API Push record' },
        },
      },
      components: {
        schemas: {
          ApiSuccessEnvelope: {
            type: 'object',
            required: ['ok', 'data'],
            properties: {
              ok: { const: true },
              data: {},
              requestId: { type: 'string' },
            },
          },
          ApiErrorEnvelope: {
            type: 'object',
            required: ['ok', 'error'],
            properties: {
              ok: { const: false },
              error: { $ref: '#/components/schemas/ErrorEnvelope' },
              requestId: { type: 'string' },
            },
          },
          ErrorEnvelope: {
            type: 'object',
            required: ['code', 'message'],
            properties: {
              code: { type: 'string' },
              message: { type: 'string' },
              details: { type: 'object', additionalProperties: true },
              retryable: { type: 'boolean' },
            },
          },
          ApiPushCommandBody: {
            type: 'object',
            required: ['project_id'],
            properties: {
              project_id: { type: 'string' },
              plugin_id: { type: 'string', default: 'dfmea' },
              adapter_id: { type: 'string', default: 'mock-mature-fmea' },
              idempotency_key: { type: 'string' },
              created_by: { type: 'string' },
            },
          },
          ApiPushJob: {
            type: 'object',
            required: [
              'apiPushJobId',
              'projectId',
              'mode',
              'status',
              'sourceProjectionId',
              'sourceWorkspaceRevision',
            ],
            properties: {
              apiPushJobId: { type: 'string' },
              projectId: { type: 'string' },
              pluginId: { type: 'string' },
              adapterId: { type: 'string' },
              mode: { enum: ['validate_only', 'execute'] },
              status: {
                enum: [
                  'created',
                  'validating',
                  'validation_failed',
                  'ready_to_push',
                  'pushing',
                  'completed',
                  'failed',
                  'partial_failed',
                  'cancelled',
                ],
              },
              sourceProjectionId: { type: 'string' },
              sourceWorkspaceRevision: { type: 'integer' },
              idempotencyKey: { type: 'string' },
              result: { type: 'object', additionalProperties: true },
              error: { type: 'object', additionalProperties: true },
            },
          },
          ApiPushRecord: {
            type: 'object',
            required: [
              'apiPushRecordId',
              'apiPushJobId',
              'externalSystem',
              'externalStatus',
              'sourceWorkspaceRevision',
            ],
            properties: {
              apiPushRecordId: { type: 'string' },
              apiPushJobId: { type: 'string' },
              externalSystem: { type: 'string' },
              externalSystemId: { type: 'string' },
              externalJobId: { type: 'string' },
              externalRecordId: { type: 'string' },
              externalStatus: { type: 'string' },
              sourceProjectionId: { type: 'string' },
              sourceWorkspaceRevision: { type: 'integer' },
              payloadChecksum: { type: 'string' },
              responseSummary: { type: 'object', additionalProperties: true },
            },
          },
        },
      },
    };
  }
}
