CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS workspaces (
  workspace_id varchar(64) PRIMARY KEY,
  name text NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
  project_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  name text NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  workspace_revision integer NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_projects_workspace_id ON projects(workspace_id);

CREATE TABLE IF NOT EXISTS sessions (
  session_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  user_id varchar(128),
  active_plugin_id varchar(128),
  status varchar(32) NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessions_workspace_id ON sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);

CREATE TABLE IF NOT EXISTS runs (
  run_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  session_id varchar(64) REFERENCES sessions(session_id),
  user_id varchar(128),
  runtime_provider_id varchar(128) NOT NULL,
  agent_plugin_id varchar(128),
  active_domain_plugin_id varchar(128),
  goal text NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'created',
  base_workspace_revision integer NOT NULL,
  started_at timestamptz,
  completed_at timestamptz,
  error jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_runs_workspace_id ON runs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_runs_project_id ON runs(project_id);
CREATE INDEX IF NOT EXISTS idx_runs_session_id ON runs(session_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);

CREATE TABLE IF NOT EXISTS run_events (
  event_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  session_id varchar(64) REFERENCES sessions(session_id),
  run_id varchar(64) NOT NULL REFERENCES runs(run_id),
  event_type varchar(128) NOT NULL,
  sequence integer NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_run_events_run_id ON run_events(run_id);
CREATE INDEX IF NOT EXISTS idx_run_events_project_id ON run_events(project_id);

CREATE TABLE IF NOT EXISTS capability_invocations (
  invocation_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  session_id varchar(64) REFERENCES sessions(session_id),
  run_id varchar(64) REFERENCES runs(run_id),
  capability_id varchar(256) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'accepted',
  arguments jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb,
  error jsonb,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_capability_invocations_run_id ON capability_invocations(run_id);
CREATE INDEX IF NOT EXISTS idx_capability_invocations_capability_id ON capability_invocations(capability_id);
CREATE INDEX IF NOT EXISTS idx_capability_invocations_status ON capability_invocations(status);

CREATE TABLE IF NOT EXISTS domain_plugins (
  plugin_id varchar(128) PRIMARY KEY,
  name text NOT NULL,
  version varchar(64) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  manifest jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plugin_schemas (
  schema_id varchar(128) PRIMARY KEY,
  plugin_id varchar(128) NOT NULL REFERENCES domain_plugins(plugin_id),
  schema_name varchar(128) NOT NULL,
  schema_version varchar(64) NOT NULL,
  schema_kind varchar(64) NOT NULL,
  json_schema jsonb NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_plugin_schemas_plugin_id ON plugin_schemas(plugin_id);

CREATE TABLE IF NOT EXISTS plugin_skills (
  skill_id varchar(128) PRIMARY KEY,
  plugin_id varchar(128) NOT NULL REFERENCES domain_plugins(plugin_id),
  name varchar(128) NOT NULL,
  version varchar(64) NOT NULL,
  input_schema_id varchar(128),
  output_schema_id varchar(128),
  handler_ref text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  status varchar(32) NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_plugin_skills_plugin_id ON plugin_skills(plugin_id);

CREATE TABLE IF NOT EXISTS plugin_views (
  view_id varchar(128) PRIMARY KEY,
  plugin_id varchar(128) NOT NULL REFERENCES domain_plugins(plugin_id),
  name varchar(128) NOT NULL,
  projection_kind varchar(128) NOT NULL,
  view_type varchar(64) NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  status varchar(32) NOT NULL DEFAULT 'active',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_plugin_views_plugin_id ON plugin_views(plugin_id);

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  plugin_id varchar(128) NOT NULL,
  artifact_type varchar(128) NOT NULL,
  schema_version varchar(64) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  revision integer NOT NULL,
  payload jsonb NOT NULL,
  created_by varchar(128),
  updated_by varchar(128),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_artifacts_workspace_id ON artifacts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_project_id ON artifacts(project_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_plugin_id ON artifacts(plugin_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_artifact_type ON artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status);

CREATE TABLE IF NOT EXISTS artifact_edges (
  edge_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  plugin_id varchar(128) NOT NULL,
  source_artifact_id varchar(64) NOT NULL REFERENCES artifacts(artifact_id),
  target_artifact_id varchar(64) NOT NULL REFERENCES artifacts(artifact_id),
  relation_type varchar(128) NOT NULL,
  schema_version varchar(64) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  revision integer NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by varchar(128),
  updated_by varchar(128),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_artifact_edges_project_id ON artifact_edges(project_id);
CREATE INDEX IF NOT EXISTS idx_artifact_edges_source_artifact_id ON artifact_edges(source_artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_edges_target_artifact_id ON artifact_edges(target_artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifact_edges_relation_type ON artifact_edges(relation_type);
CREATE INDEX IF NOT EXISTS idx_artifact_edges_status ON artifact_edges(status);

CREATE TABLE IF NOT EXISTS ai_draft_batches (
  draft_batch_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  session_id varchar(64) REFERENCES sessions(session_id),
  run_id varchar(64) REFERENCES runs(run_id),
  plugin_id varchar(128) NOT NULL,
  title text NOT NULL,
  goal text NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  base_workspace_revision integer NOT NULL,
  target_workspace_revision integer,
  summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by varchar(128),
  applied_by varchar(128),
  rejected_by varchar(128),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  applied_at timestamptz,
  rejected_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_ai_draft_batches_project_id ON ai_draft_batches(project_id);
CREATE INDEX IF NOT EXISTS idx_ai_draft_batches_status ON ai_draft_batches(status);

CREATE TABLE IF NOT EXISTS draft_patches (
  draft_patch_id varchar(64) PRIMARY KEY,
  draft_batch_id varchar(64) NOT NULL REFERENCES ai_draft_batches(draft_batch_id),
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  plugin_id varchar(128) NOT NULL,
  patch_type varchar(64) NOT NULL,
  target_type varchar(32) NOT NULL,
  target_id varchar(64),
  temp_ref varchar(128),
  artifact_type varchar(128),
  relation_type varchar(128),
  source_temp_ref varchar(128),
  target_temp_ref varchar(128),
  source_artifact_id varchar(64),
  target_artifact_id varchar(64),
  before_payload jsonb,
  after_payload jsonb,
  payload_patch jsonb,
  status varchar(32) NOT NULL DEFAULT 'pending',
  validation_result jsonb,
  applied_result jsonb,
  edited_by varchar(128),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_draft_patches_draft_batch_id ON draft_patches(draft_batch_id);
CREATE INDEX IF NOT EXISTS idx_draft_patches_project_id ON draft_patches(project_id);
CREATE INDEX IF NOT EXISTS idx_draft_patches_status ON draft_patches(status);

CREATE TABLE IF NOT EXISTS workspace_revision_events (
  event_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  from_revision integer NOT NULL,
  to_revision integer NOT NULL,
  draft_batch_id varchar(64) REFERENCES ai_draft_batches(draft_batch_id),
  run_id varchar(64) REFERENCES runs(run_id),
  summary text,
  created_by varchar(128),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projections (
  projection_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  plugin_id varchar(128) NOT NULL,
  kind varchar(128) NOT NULL,
  category varchar(64) NOT NULL,
  scope_type varchar(64) NOT NULL,
  scope_id varchar(128) NOT NULL,
  source_revision integer NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'stale',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  summary text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  built_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_projections_project_kind ON projections(project_id, kind);
CREATE INDEX IF NOT EXISTS idx_projections_source_revision ON projections(source_revision);
CREATE INDEX IF NOT EXISTS idx_projections_status ON projections(status);

CREATE TABLE IF NOT EXISTS evidence_refs (
  evidence_ref_id varchar(64) PRIMARY KEY,
  evidence_ref varchar(256) NOT NULL,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  session_id varchar(64) REFERENCES sessions(session_id),
  knowledge_base_type varchar(64) NOT NULL,
  source_type varchar(64) NOT NULL,
  provider_id varchar(128) NOT NULL,
  provider_ref text NOT NULL,
  title text NOT NULL,
  content_preview text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evidence_refs_project_id ON evidence_refs(project_id);

CREATE TABLE IF NOT EXISTS evidence_links (
  evidence_link_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  target_type varchar(64) NOT NULL,
  target_id varchar(64) NOT NULL,
  evidence_ref varchar(256) NOT NULL,
  relation_type varchar(64) NOT NULL,
  created_by varchar(128),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_evidence_links_project_id ON evidence_links(project_id);
CREATE INDEX IF NOT EXISTS idx_evidence_links_target ON evidence_links(target_type, target_id);

CREATE TABLE IF NOT EXISTS vector_indexes (
  vector_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  owner_type varchar(64) NOT NULL,
  owner_id varchar(64) NOT NULL,
  owner_revision integer NOT NULL,
  text text NOT NULL,
  embedding vector(1536),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_vector_indexes_project_id ON vector_indexes(project_id);
CREATE INDEX IF NOT EXISTS idx_vector_indexes_owner ON vector_indexes(owner_type, owner_id);
