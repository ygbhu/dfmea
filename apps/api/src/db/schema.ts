import {
  index,
  integer,
  jsonb,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
  varchar,
} from 'drizzle-orm/pg-core';
import type {
  AiDraftStatus,
  ApiPushJobStatus,
  ApiPushMode,
  CanonicalRecordStatus,
  CapabilityInvocationStatus,
  DraftPatchOperation,
  DraftPatchStatus,
  ProjectionStatus,
  ProjectStatus,
  RunStatus,
  WorkspaceStatus,
} from '@dfmea/shared';
import type { JsonObject, JsonValue } from '@dfmea/shared';

const timestamps = {
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
};

export const workspaces = pgTable('workspaces', {
  workspaceId: varchar('workspace_id', { length: 64 }).primaryKey(),
  name: text('name').notNull(),
  status: varchar('status', { length: 32 }).$type<WorkspaceStatus>().notNull().default('active'),
  metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
  ...timestamps,
});

export const projects = pgTable(
  'projects',
  {
    projectId: varchar('project_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    name: text('name').notNull(),
    status: varchar('status', { length: 32 }).$type<ProjectStatus>().notNull().default('active'),
    workspaceRevision: integer('workspace_revision').notNull().default(0),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    ...timestamps,
  },
  (table) => [index('idx_projects_workspace_id').on(table.workspaceId)],
);

export const sessions = pgTable(
  'sessions',
  {
    sessionId: varchar('session_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    userId: varchar('user_id', { length: 128 }),
    activePluginId: varchar('active_plugin_id', { length: 128 }),
    status: varchar('status', { length: 32 }).notNull().default('active'),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    ...timestamps,
  },
  (table) => [
    index('idx_sessions_workspace_id').on(table.workspaceId),
    index('idx_sessions_project_id').on(table.projectId),
  ],
);

export const runs = pgTable(
  'runs',
  {
    runId: varchar('run_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    sessionId: varchar('session_id', { length: 64 }).references(() => sessions.sessionId),
    userId: varchar('user_id', { length: 128 }),
    runtimeProviderId: varchar('runtime_provider_id', { length: 128 }).notNull(),
    agentPluginId: varchar('agent_plugin_id', { length: 128 }),
    activeDomainPluginId: varchar('active_domain_plugin_id', { length: 128 }),
    goal: text('goal').notNull(),
    status: varchar('status', { length: 32 }).$type<RunStatus>().notNull().default('created'),
    baseWorkspaceRevision: integer('base_workspace_revision').notNull(),
    startedAt: timestamp('started_at', { withTimezone: true }),
    completedAt: timestamp('completed_at', { withTimezone: true }),
    error: jsonb('error').$type<JsonObject>(),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    ...timestamps,
  },
  (table) => [
    index('idx_runs_workspace_id').on(table.workspaceId),
    index('idx_runs_project_id').on(table.projectId),
    index('idx_runs_session_id').on(table.sessionId),
    index('idx_runs_status').on(table.status),
  ],
);

export const runEvents = pgTable(
  'run_events',
  {
    eventId: varchar('event_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    sessionId: varchar('session_id', { length: 64 }).references(() => sessions.sessionId),
    runId: varchar('run_id', { length: 64 })
      .notNull()
      .references(() => runs.runId),
    eventType: varchar('event_type', { length: 128 }).notNull(),
    sequence: integer('sequence').notNull(),
    payload: jsonb('payload').$type<JsonValue>().notNull().default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index('idx_run_events_run_id').on(table.runId),
    index('idx_run_events_project_id').on(table.projectId),
  ],
);

export const capabilityInvocations = pgTable(
  'capability_invocations',
  {
    invocationId: varchar('invocation_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    sessionId: varchar('session_id', { length: 64 }).references(() => sessions.sessionId),
    runId: varchar('run_id', { length: 64 }).references(() => runs.runId),
    capabilityId: varchar('capability_id', { length: 256 }).notNull(),
    status: varchar('status', { length: 32 })
      .$type<CapabilityInvocationStatus>()
      .notNull()
      .default('accepted'),
    arguments: jsonb('arguments').$type<JsonValue>().notNull().default({}),
    result: jsonb('result').$type<JsonValue>(),
    error: jsonb('error').$type<JsonObject>(),
    startedAt: timestamp('started_at', { withTimezone: true }),
    completedAt: timestamp('completed_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index('idx_capability_invocations_run_id').on(table.runId),
    index('idx_capability_invocations_capability_id').on(table.capabilityId),
    index('idx_capability_invocations_status').on(table.status),
  ],
);

export const domainPlugins = pgTable('domain_plugins', {
  pluginId: varchar('plugin_id', { length: 128 }).primaryKey(),
  name: text('name').notNull(),
  version: varchar('version', { length: 64 }).notNull(),
  status: varchar('status', { length: 32 }).notNull().default('active'),
  manifest: jsonb('manifest').$type<JsonObject>().notNull().default({}),
  ...timestamps,
});

export const pluginSchemas = pgTable(
  'plugin_schemas',
  {
    schemaId: varchar('schema_id', { length: 128 }).primaryKey(),
    pluginId: varchar('plugin_id', { length: 128 })
      .notNull()
      .references(() => domainPlugins.pluginId),
    schemaName: varchar('schema_name', { length: 128 }).notNull(),
    schemaVersion: varchar('schema_version', { length: 64 }).notNull(),
    schemaKind: varchar('schema_kind', { length: 64 }).notNull(),
    jsonSchema: jsonb('json_schema').$type<JsonObject>().notNull(),
    status: varchar('status', { length: 32 }).notNull().default('active'),
    ...timestamps,
  },
  (table) => [index('idx_plugin_schemas_plugin_id').on(table.pluginId)],
);

export const pluginSkills = pgTable(
  'plugin_skills',
  {
    skillId: varchar('skill_id', { length: 128 }).primaryKey(),
    pluginId: varchar('plugin_id', { length: 128 })
      .notNull()
      .references(() => domainPlugins.pluginId),
    name: varchar('name', { length: 128 }).notNull(),
    version: varchar('version', { length: 64 }).notNull(),
    inputSchemaId: varchar('input_schema_id', { length: 128 }),
    outputSchemaId: varchar('output_schema_id', { length: 128 }),
    handlerRef: text('handler_ref').notNull(),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    status: varchar('status', { length: 32 }).notNull().default('active'),
    ...timestamps,
  },
  (table) => [index('idx_plugin_skills_plugin_id').on(table.pluginId)],
);

export const pluginViews = pgTable(
  'plugin_views',
  {
    viewId: varchar('view_id', { length: 128 }).primaryKey(),
    pluginId: varchar('plugin_id', { length: 128 })
      .notNull()
      .references(() => domainPlugins.pluginId),
    name: varchar('name', { length: 128 }).notNull(),
    projectionKind: varchar('projection_kind', { length: 128 }).notNull(),
    viewType: varchar('view_type', { length: 64 }).notNull(),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    status: varchar('status', { length: 32 }).notNull().default('active'),
    ...timestamps,
  },
  (table) => [index('idx_plugin_views_plugin_id').on(table.pluginId)],
);

export const artifacts = pgTable(
  'artifacts',
  {
    artifactId: varchar('artifact_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    artifactType: varchar('artifact_type', { length: 128 }).notNull(),
    schemaVersion: varchar('schema_version', { length: 64 }).notNull(),
    status: varchar('status', { length: 32 })
      .$type<CanonicalRecordStatus>()
      .notNull()
      .default('active'),
    revision: integer('revision').notNull(),
    payload: jsonb('payload').$type<JsonObject>().notNull(),
    createdBy: varchar('created_by', { length: 128 }),
    updatedBy: varchar('updated_by', { length: 128 }),
    ...timestamps,
  },
  (table) => [
    index('idx_artifacts_workspace_id').on(table.workspaceId),
    index('idx_artifacts_project_id').on(table.projectId),
    index('idx_artifacts_plugin_id').on(table.pluginId),
    index('idx_artifacts_artifact_type').on(table.artifactType),
    index('idx_artifacts_status').on(table.status),
  ],
);

export const artifactEdges = pgTable(
  'artifact_edges',
  {
    edgeId: varchar('edge_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    sourceArtifactId: varchar('source_artifact_id', { length: 64 })
      .notNull()
      .references(() => artifacts.artifactId),
    targetArtifactId: varchar('target_artifact_id', { length: 64 })
      .notNull()
      .references(() => artifacts.artifactId),
    relationType: varchar('relation_type', { length: 128 }).notNull(),
    schemaVersion: varchar('schema_version', { length: 64 }).notNull(),
    status: varchar('status', { length: 32 })
      .$type<CanonicalRecordStatus>()
      .notNull()
      .default('active'),
    revision: integer('revision').notNull(),
    payload: jsonb('payload').$type<JsonObject>().notNull().default({}),
    createdBy: varchar('created_by', { length: 128 }),
    updatedBy: varchar('updated_by', { length: 128 }),
    ...timestamps,
  },
  (table) => [
    index('idx_artifact_edges_project_id').on(table.projectId),
    index('idx_artifact_edges_source_artifact_id').on(table.sourceArtifactId),
    index('idx_artifact_edges_target_artifact_id').on(table.targetArtifactId),
    index('idx_artifact_edges_relation_type').on(table.relationType),
    index('idx_artifact_edges_status').on(table.status),
  ],
);

export const aiDraftBatches = pgTable(
  'ai_draft_batches',
  {
    draftBatchId: varchar('draft_batch_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    sessionId: varchar('session_id', { length: 64 }).references(() => sessions.sessionId),
    runId: varchar('run_id', { length: 64 }).references(() => runs.runId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    title: text('title').notNull(),
    goal: text('goal').notNull(),
    status: varchar('status', { length: 32 }).$type<AiDraftStatus>().notNull().default('pending'),
    baseWorkspaceRevision: integer('base_workspace_revision').notNull(),
    targetWorkspaceRevision: integer('target_workspace_revision'),
    summary: jsonb('summary').$type<JsonObject>().notNull().default({}),
    createdBy: varchar('created_by', { length: 128 }),
    appliedBy: varchar('applied_by', { length: 128 }),
    rejectedBy: varchar('rejected_by', { length: 128 }),
    ...timestamps,
    appliedAt: timestamp('applied_at', { withTimezone: true }),
    rejectedAt: timestamp('rejected_at', { withTimezone: true }),
  },
  (table) => [
    index('idx_ai_draft_batches_project_id').on(table.projectId),
    index('idx_ai_draft_batches_status').on(table.status),
  ],
);

export const draftPatches = pgTable(
  'draft_patches',
  {
    draftPatchId: varchar('draft_patch_id', { length: 64 }).primaryKey(),
    draftBatchId: varchar('draft_batch_id', { length: 64 })
      .notNull()
      .references(() => aiDraftBatches.draftBatchId),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    patchType: varchar('patch_type', { length: 64 }).$type<DraftPatchOperation>().notNull(),
    targetType: varchar('target_type', { length: 32 }).notNull(),
    targetId: varchar('target_id', { length: 64 }),
    tempRef: varchar('temp_ref', { length: 128 }),
    artifactType: varchar('artifact_type', { length: 128 }),
    relationType: varchar('relation_type', { length: 128 }),
    sourceTempRef: varchar('source_temp_ref', { length: 128 }),
    targetTempRef: varchar('target_temp_ref', { length: 128 }),
    sourceArtifactId: varchar('source_artifact_id', { length: 64 }),
    targetArtifactId: varchar('target_artifact_id', { length: 64 }),
    beforePayload: jsonb('before_payload').$type<JsonObject>(),
    afterPayload: jsonb('after_payload').$type<JsonObject>(),
    payloadPatch: jsonb('payload_patch').$type<JsonObject>(),
    status: varchar('status', { length: 32 }).$type<DraftPatchStatus>().notNull().default('pending'),
    validationResult: jsonb('validation_result').$type<JsonObject>(),
    appliedResult: jsonb('applied_result').$type<JsonObject>(),
    editedBy: varchar('edited_by', { length: 128 }),
    ...timestamps,
  },
  (table) => [
    index('idx_draft_patches_draft_batch_id').on(table.draftBatchId),
    index('idx_draft_patches_project_id').on(table.projectId),
    index('idx_draft_patches_status').on(table.status),
  ],
);

export const workspaceRevisionEvents = pgTable('workspace_revision_events', {
  eventId: varchar('event_id', { length: 64 }).primaryKey(),
  workspaceId: varchar('workspace_id', { length: 64 })
    .notNull()
    .references(() => workspaces.workspaceId),
  projectId: varchar('project_id', { length: 64 })
    .notNull()
    .references(() => projects.projectId),
  fromRevision: integer('from_revision').notNull(),
  toRevision: integer('to_revision').notNull(),
  draftBatchId: varchar('draft_batch_id', { length: 64 }).references(
    () => aiDraftBatches.draftBatchId,
  ),
  runId: varchar('run_id', { length: 64 }).references(() => runs.runId),
  summary: text('summary'),
  createdBy: varchar('created_by', { length: 128 }),
  createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
});

export const projections = pgTable(
  'projections',
  {
    projectionId: varchar('projection_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    kind: varchar('kind', { length: 128 }).notNull(),
    category: varchar('category', { length: 64 }).notNull(),
    scopeType: varchar('scope_type', { length: 64 }).notNull(),
    scopeId: varchar('scope_id', { length: 128 }).notNull(),
    sourceRevision: integer('source_revision').notNull(),
    status: varchar('status', { length: 32 }).$type<ProjectionStatus>().notNull().default('stale'),
    payload: jsonb('payload').$type<JsonObject>().notNull().default({}),
    summary: text('summary'),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    builtAt: timestamp('built_at', { withTimezone: true }),
    ...timestamps,
  },
  (table) => [
    index('idx_projections_project_kind').on(table.projectId, table.kind),
    index('idx_projections_source_revision').on(table.sourceRevision),
    index('idx_projections_status').on(table.status),
  ],
);

export const apiPushJobs = pgTable(
  'api_push_jobs',
  {
    apiPushJobId: varchar('api_push_job_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    adapterId: varchar('adapter_id', { length: 128 }).notNull(),
    mode: varchar('mode', { length: 32 }).$type<ApiPushMode>().notNull(),
    status: varchar('status', { length: 32 })
      .$type<ApiPushJobStatus>()
      .notNull()
      .default('created'),
    sourceProjectionId: varchar('source_projection_id', { length: 64 })
      .notNull()
      .references(() => projections.projectionId),
    sourceWorkspaceRevision: integer('source_workspace_revision').notNull(),
    idempotencyKey: varchar('idempotency_key', { length: 256 }).notNull(),
    request: jsonb('request').$type<JsonObject>().notNull().default({}),
    result: jsonb('result').$type<JsonObject>(),
    error: jsonb('error').$type<JsonObject>(),
    createdBy: varchar('created_by', { length: 128 }),
    startedAt: timestamp('started_at', { withTimezone: true }),
    completedAt: timestamp('completed_at', { withTimezone: true }),
    ...timestamps,
  },
  (table) => [
    index('idx_api_push_jobs_project_id').on(table.projectId),
    index('idx_api_push_jobs_status').on(table.status),
    uniqueIndex('uidx_api_push_jobs_idempotency_key').on(table.idempotencyKey),
  ],
);

export const apiPushRecords = pgTable(
  'api_push_records',
  {
    apiPushRecordId: varchar('api_push_record_id', { length: 64 }).primaryKey(),
    apiPushJobId: varchar('api_push_job_id', { length: 64 })
      .notNull()
      .references(() => apiPushJobs.apiPushJobId),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    pluginId: varchar('plugin_id', { length: 128 }).notNull(),
    adapterId: varchar('adapter_id', { length: 128 }).notNull(),
    externalSystem: varchar('external_system', { length: 128 }).notNull(),
    externalSystemId: varchar('external_system_id', { length: 128 }).notNull(),
    externalJobId: varchar('external_job_id', { length: 128 }),
    externalRecordId: varchar('external_record_id', { length: 128 }),
    externalStatus: varchar('external_status', { length: 64 }).notNull(),
    sourceProjectionId: varchar('source_projection_id', { length: 64 })
      .notNull()
      .references(() => projections.projectionId),
    sourceWorkspaceRevision: integer('source_workspace_revision').notNull(),
    payloadChecksum: varchar('payload_checksum', { length: 128 }).notNull(),
    responseSummary: jsonb('response_summary').$type<JsonObject>().notNull().default({}),
    error: jsonb('error').$type<JsonObject>(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index('idx_api_push_records_job_id').on(table.apiPushJobId),
    index('idx_api_push_records_project_id').on(table.projectId),
    index('idx_api_push_records_external_record_id').on(table.externalRecordId),
  ],
);

export const evidenceRefs = pgTable(
  'evidence_refs',
  {
    evidenceRefId: varchar('evidence_ref_id', { length: 64 }).primaryKey(),
    evidenceRef: varchar('evidence_ref', { length: 256 }).notNull(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    sessionId: varchar('session_id', { length: 64 }).references(() => sessions.sessionId),
    knowledgeBaseType: varchar('knowledge_base_type', { length: 64 }).notNull(),
    sourceType: varchar('source_type', { length: 64 }).notNull(),
    providerId: varchar('provider_id', { length: 128 }).notNull(),
    providerRef: text('provider_ref').notNull(),
    title: text('title').notNull(),
    contentPreview: text('content_preview'),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [index('idx_evidence_refs_project_id').on(table.projectId)],
);

export const evidenceLinks = pgTable(
  'evidence_links',
  {
    evidenceLinkId: varchar('evidence_link_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    targetType: varchar('target_type', { length: 64 }).notNull(),
    targetId: varchar('target_id', { length: 64 }).notNull(),
    evidenceRef: varchar('evidence_ref', { length: 256 }).notNull(),
    relationType: varchar('relation_type', { length: 64 }).notNull(),
    createdBy: varchar('created_by', { length: 128 }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index('idx_evidence_links_project_id').on(table.projectId),
    index('idx_evidence_links_target').on(table.targetType, table.targetId),
  ],
);

export const vectorIndexes = pgTable(
  'vector_indexes',
  {
    vectorId: varchar('vector_id', { length: 64 }).primaryKey(),
    workspaceId: varchar('workspace_id', { length: 64 })
      .notNull()
      .references(() => workspaces.workspaceId),
    projectId: varchar('project_id', { length: 64 })
      .notNull()
      .references(() => projects.projectId),
    ownerType: varchar('owner_type', { length: 64 }).notNull(),
    ownerId: varchar('owner_id', { length: 64 }).notNull(),
    ownerRevision: integer('owner_revision').notNull(),
    text: text('text').notNull(),
    embedding: text('embedding'),
    metadata: jsonb('metadata').$type<JsonObject>().notNull().default({}),
    ...timestamps,
  },
  (table) => [
    index('idx_vector_indexes_project_id').on(table.projectId),
    index('idx_vector_indexes_owner').on(table.ownerType, table.ownerId),
  ],
);
