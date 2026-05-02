# Platform API Guidelines

## Scenario: Phase 9 REST + SSE Platform API

### 1. Scope / Trigger

- Trigger: Adding or changing `apps/api/src/modules/platform/**`.
- Applies to Platform API endpoints that orchestrate workspace scope, mock runtime, AI draft, projection, capability invocation, and SSE event streams.
- The API layer must stay thin: it validates request shape, returns envelopes, and delegates state changes to services/repositories.

### 2. Signatures

Core REST routes:

```text
POST /api/workspaces
POST /api/workspaces/{workspaceId}/projects
POST /api/projects/{projectId}/sessions
POST /api/sessions/{sessionId}/runs
GET  /api/runs/{runId}
POST /api/runs/{runId}/cancel
GET  /api/runs/{runId}/events

GET   /api/ai-drafts/{draftBatchId}
POST  /api/ai-drafts/{draftBatchId}/edit
PATCH /api/ai-drafts/{draftBatchId}/patches/{draftPatchId}
POST  /api/ai-drafts/{draftBatchId}/apply
POST  /api/ai-drafts/{draftBatchId}/reject
GET   /api/ai-drafts/{draftBatchId}/preview

GET  /api/projects/{projectId}/projections?plugin_id=dfmea&kind=working_tree
POST /api/projections/rebuild
GET  /api/capability-invocations/{invocationId}

POST /api/api-push/validate
POST /api/api-push/execute
GET  /api/api-push/jobs/{apiPushJobId}
GET  /api/api-push/records/{apiPushRecordId}
GET  /api/openapi.json
```

SSE routes:

```text
GET /api/runs/{runId}/events/stream
GET /api/ai-drafts/{draftBatchId}/preview/events/stream
GET /api/projects/{projectId}/projections/rebuild/stream
```

### 3. Contracts

Success response envelope:

```json
{
  "ok": true,
  "data": {}
}
```

Error response envelope:

```json
{
  "ok": false,
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Run goal is required.",
    "details": {}
  }
}
```

Important request fields:

```text
POST /api/sessions/{sessionId}/runs
  body.goal: string, required
  body.plugin_id/body.pluginId: string, optional, defaults to active session plugin or dfmea

PATCH /api/ai-drafts/{draftBatchId}/patches/{draftPatchId}
  body.after_payload/body.afterPayload: object, required

POST /api/projections/rebuild
  body.project_id/body.projectId: string, required
  body.plugin_id/body.pluginId: string, optional, defaults to dfmea
  body.kind: string, optional, defaults to working_tree

POST /api/api-push/validate
POST /api/api-push/execute
  body.project_id/body.projectId: string, required
  body.plugin_id/body.pluginId: string, optional, defaults to dfmea
  body.adapter_id/body.adapterId: string, optional, defaults to mock-mature-fmea
  body.idempotency_key/body.idempotencyKey: string, optional
```

Draft preview is rebuilt from persisted `ai_draft_batches` and `draft_patches`; live preview events are display state only and are not canonical writes.

API Push must use `dfmea.export_payload` with `consumer: export`. The service may rebuild a missing or stale export projection, but the job source must be fresh before calling the adapter:

```text
api_push_jobs.source_workspace_revision
  == projections.source_revision
  == projects.workspace_revision
```

The mock mature FMEA adapter validates and maps only the export projection payload. It must not read or write canonical artifacts, edges, or project revision state.

### 4. Validation & Error Matrix

| Case | Code | HTTP Status | Assertion |
| --- | --- | --- | --- |
| Missing required body field | `VALIDATION_FAILED` | 400 | Response uses `{ ok:false, error }` |
| Missing workspace/project/session/run | `*_NOT_FOUND` | 404 | Details include the requested id |
| Draft batch missing | `AI_DRAFT_NOT_FOUND` | 404 | No canonical writes occur |
| Draft already applied/rejected | `AI_DRAFT_ALREADY_APPLIED` / `AI_DRAFT_REJECTED` | 409 | Apply/reject is not repeated |
| Draft base revision stale | `AI_DRAFT_BASE_REVISION_CONFLICT` | 409 | Details include base/current revisions |
| Projection handler missing | `PROJECTION_HANDLER_NOT_FOUND` | 400 | No projection row is created |
| Projection rebuild failed | `PROJECTION_REBUILD_FAILED` | 500 | Error is retryable |
| API Push job missing | `API_PUSH_JOB_NOT_FOUND` | 404 | Details include the requested id |
| API Push record missing | `API_PUSH_RECORD_NOT_FOUND` | 404 | Details include the requested id |
| Export projection stale after rebuild | `EXPORT_PROJECTION_STALE` | 409 | Adapter is not called |
| Export payload rejected | `EXTERNAL_VALIDATION_FAILED` | 400 | Job is marked `validation_failed` |
| API Push idempotency mismatch | `EXPORT_IDEMPOTENCY_CONFLICT` | 409 | Existing job binding is preserved |
| Mock adapter push failure | `EXTERNAL_PUSH_FAILED` | 502 | Error is retryable |

### 5. Good/Base/Bad Cases

Base flow:

```text
workspace -> project -> session -> run -> draft preview -> edit patch -> apply draft -> fresh projection
```

Good:

```typescript
return ok({ projection });
```

Bad:

```typescript
return projection;
```

Returning raw data skips the Platform API envelope and breaks frontend error handling symmetry.

### 6. Tests Required

When changing Platform API behavior, keep or extend:

```text
apps/api/src/modules/platform/platform-api.integration.spec.ts
```

Required assertions:

- Main flow creates a run and persisted AI draft.
- Run SSE emits `runtime.started`.
- Draft preview SSE emits `draft.preview.started` and node/edge events.
- Applying a draft increments workspace revision and returns a fresh working tree projection.
- Projection rebuild SSE emits `projection.rebuild.started` then `projection.rebuild.completed`.
- Capability invocation query returns `completed`.
- Error normalization returns the shared error envelope fields.
- Stale draft base revision maps to `AI_DRAFT_BASE_REVISION_CONFLICT`.
- UI projection reads return `stale`, while explicit rebuild returns `fresh`.
- Rejecting a draft leaves project revision and canonical artifacts unchanged.
- API Push validate/execute bind a fresh export projection, create records, and do not mutate canonical data.

### 7. Wrong vs Correct

#### Wrong

```typescript
@Post('ai-drafts/:draftBatchId/apply')
async applyDraft(@Param('draftBatchId') draftBatchId: string) {
  return this.draftRepository.applyDraftBatch({ draftBatchId });
}
```

This lets the controller execute repository writes directly and bypasses events/projection rebuild.

#### Correct

```typescript
@Post('ai-drafts/:draftBatchId/apply')
async applyDraft(@Param('draftBatchId') draftBatchId: string, @Body() body: unknown) {
  const result = await this.platformApiService.applyDraft({ draftBatchId });
  return ok(result);
}
```

The service owns orchestration: draft apply, run events, projection rebuild, and API response shape.
