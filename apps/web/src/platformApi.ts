import type { ApiResponseEnvelope, JsonObject, JsonValue } from '@dfmea/shared';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000';

export interface WorkspaceRecord {
  workspaceId: string;
  name: string;
  status: string;
  metadata: JsonObject;
}

export interface ProjectRecord {
  projectId: string;
  workspaceId: string;
  name: string;
  status: string;
  workspaceRevision: number;
  metadata: JsonObject;
}

export interface SessionRecord {
  sessionId: string;
  workspaceId: string;
  projectId: string;
  userId: string | null;
  activePluginId: string | null;
  status: string;
}

export interface RunStartResult {
  runId: string;
  draftBatchId: string;
  evidenceRefs: string[];
  eventsUrl: string;
  draftUrl: string;
}

export interface RuntimeEventRecord {
  eventId: string;
  eventType: string;
  workspaceId: string;
  projectId: string;
  sessionId: string | null;
  runId: string;
  sequence: number;
  payload: JsonValue;
  createdAt: string;
}

export interface DraftBatchRecord {
  draftBatchId: string;
  workspaceId: string;
  projectId: string;
  sessionId: string | null;
  runId: string | null;
  pluginId: string;
  title: string;
  goal: string;
  status: string;
  baseWorkspaceRevision: number;
  targetWorkspaceRevision: number | null;
  summary: JsonObject;
}

export interface DraftPatchRecord {
  draftPatchId: string;
  draftBatchId: string;
  workspaceId: string;
  projectId: string;
  pluginId: string;
  patchType: string;
  targetType: 'artifact' | 'edge';
  targetId: string | null;
  tempRef: string | null;
  artifactType: string | null;
  relationType: string | null;
  sourceTempRef: string | null;
  targetTempRef: string | null;
  sourceArtifactId: string | null;
  targetArtifactId: string | null;
  afterPayload: JsonObject | null;
  payloadPatch: JsonObject | null;
  status: string;
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
    status: string;
    pendingPatchCount: number;
    rejectedPatchCount: number;
  };
}

export interface ProjectionReadResult {
  projection: {
    projectionId: string;
    workspaceId: string;
    projectId: string;
    pluginId: string;
    kind: string;
    category: string;
    scopeType: string;
    scopeId: string;
    sourceRevision: number;
    status: string;
    payload: JsonObject;
    summary: string | null;
  };
  freshness: 'fresh' | 'stale';
  validationStatus: 'passed' | 'failed';
  currentWorkspaceRevision: number;
}

export interface DraftResponse {
  draft: {
    batch: DraftBatchRecord;
    patches: DraftPatchRecord[];
  };
}

export interface DraftPreviewResponse {
  draft: DraftResponse['draft'];
  preview: DraftPreview;
}

export interface ApplyDraftResponse {
  applyResult: {
    draftBatchId: string;
    fromRevision: number;
    toRevision: number;
    artifactIds: string[];
    edgeIds: string[];
  };
  workingTreeProjection: ProjectionReadResult | null;
}

export interface ApiPushJobRecord {
  apiPushJobId: string;
  workspaceId: string;
  projectId: string;
  pluginId: string;
  adapterId: string;
  mode: 'validate_only' | 'execute';
  status: string;
  sourceProjectionId: string;
  sourceWorkspaceRevision: number;
  idempotencyKey: string;
  request: JsonObject;
  result: JsonObject | null;
  error: JsonObject | null;
}

export interface ApiPushRecord {
  apiPushRecordId: string;
  apiPushJobId: string;
  workspaceId: string;
  projectId: string;
  pluginId: string;
  adapterId: string;
  externalSystem: string;
  externalSystemId: string;
  externalJobId: string | null;
  externalRecordId: string | null;
  externalStatus: string;
  sourceProjectionId: string;
  sourceWorkspaceRevision: number;
  payloadChecksum: string;
  responseSummary: JsonObject;
  error: JsonObject | null;
}

export interface ApiPushResult {
  job: ApiPushJobRecord;
  record: ApiPushRecord | null;
  validation: {
    status: 'passed' | 'failed';
    findings: JsonObject[];
    [key: string]: JsonValue;
  };
  sourceProjection: ProjectionReadResult;
  events: string[];
  idempotent: boolean;
}

export interface PlatformEvent {
  event_id?: string;
  eventId?: string;
  event_type?: string;
  eventType?: string;
  sequence?: number;
  created_at?: string;
  createdAt?: string;
  payload?: JsonValue;
  [key: string]: JsonValue | undefined;
}

export async function createWorkspace(name: string): Promise<WorkspaceRecord> {
  const data = await request<{ workspace: WorkspaceRecord }>('/api/workspaces', {
    method: 'POST',
    body: { name },
  });

  return data.workspace;
}

export async function createProject(workspaceId: string, name: string): Promise<ProjectRecord> {
  const data = await request<{ project: ProjectRecord }>(`/api/workspaces/${workspaceId}/projects`, {
    method: 'POST',
    body: { name },
  });

  return data.project;
}

export async function createSession(projectId: string): Promise<SessionRecord> {
  const data = await request<{ session: SessionRecord }>(`/api/projects/${projectId}/sessions`, {
    method: 'POST',
    body: {
      user_id: 'workspace_user',
      active_plugin_id: 'dfmea',
    },
  });

  return data.session;
}

export async function startRun(sessionId: string, goal: string): Promise<RunStartResult> {
  const data = await request<{ run: RunStartResult }>(`/api/sessions/${sessionId}/runs`, {
    method: 'POST',
    body: { goal },
  });

  return data.run;
}

export async function getWorkingProjection(projectId: string): Promise<ProjectionReadResult> {
  const data = await request<{ projection: ProjectionReadResult }>(
    `/api/projects/${projectId}/projections?plugin_id=dfmea&kind=working_tree`,
  );

  return data.projection;
}

export async function getDraft(draftBatchId: string): Promise<DraftResponse['draft']> {
  const data = await request<DraftResponse>(`/api/ai-drafts/${draftBatchId}`);
  return data.draft;
}

export async function getDraftPreview(draftBatchId: string): Promise<DraftPreviewResponse> {
  return request<DraftPreviewResponse>(`/api/ai-drafts/${draftBatchId}/preview`);
}

export async function applyDraft(draftBatchId: string): Promise<ApplyDraftResponse> {
  return request<ApplyDraftResponse>(`/api/ai-drafts/${draftBatchId}/apply`, {
    method: 'POST',
    body: { applied_by: 'workspace_user' },
  });
}

export async function rejectDraft(draftBatchId: string): Promise<DraftBatchRecord> {
  const data = await request<{ batch: DraftBatchRecord }>(`/api/ai-drafts/${draftBatchId}/reject`, {
    method: 'POST',
    body: { rejected_by: 'workspace_user' },
  });

  return data.batch;
}

export async function validateApiPush(projectId: string): Promise<ApiPushResult> {
  return request<ApiPushResult>('/api/api-push/validate', {
    method: 'POST',
    body: {
      project_id: projectId,
      plugin_id: 'dfmea',
      adapter_id: 'mock-mature-fmea',
      created_by: 'workspace_user',
    },
  });
}

export async function executeApiPush(projectId: string): Promise<ApiPushResult> {
  return request<ApiPushResult>('/api/api-push/execute', {
    method: 'POST',
    body: {
      project_id: projectId,
      plugin_id: 'dfmea',
      adapter_id: 'mock-mature-fmea',
      created_by: 'workspace_user',
    },
  });
}

export function connectPlatformEvents(
  path: string,
  eventTypes: string[],
  onEvent: (event: PlatformEvent) => void,
  onError: (message: string) => void,
): () => void {
  const source = new EventSource(toApiUrl(path));

  for (const eventType of eventTypes) {
    source.addEventListener(eventType, (event) => {
      const message = event as MessageEvent<string>;
      const parsed = parseEventData(message.data);

      if (parsed !== undefined) {
        onEvent(parsed);
      }
    });
  }

  source.onerror = () => {
    onError('Event stream disconnected.');
    source.close();
  };

  return () => source.close();
}

async function request<TData>(
  path: string,
  init: { method?: string; body?: JsonObject } = {},
): Promise<TData> {
  const response = await fetch(toApiUrl(path), {
    method: init.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
    ...(init.body !== undefined ? { body: JSON.stringify(init.body) } : {}),
  });
  const envelope = (await response.json()) as ApiResponseEnvelope<TData>;

  if (!envelope.ok) {
    throw new Error(`${envelope.error.code}: ${envelope.error.message}`);
  }

  return envelope.data;
}

function toApiUrl(path: string): string {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }

  return `${apiBaseUrl}${path}`;
}

function parseEventData(data: string): PlatformEvent | undefined {
  try {
    const parsed = JSON.parse(data) as unknown;

    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      return parsed as PlatformEvent;
    }
  } catch {
    return undefined;
  }

  return undefined;
}
