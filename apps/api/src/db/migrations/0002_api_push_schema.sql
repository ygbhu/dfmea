CREATE TABLE IF NOT EXISTS api_push_jobs (
  api_push_job_id varchar(64) PRIMARY KEY,
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  plugin_id varchar(128) NOT NULL,
  adapter_id varchar(128) NOT NULL,
  mode varchar(32) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'created',
  source_projection_id varchar(64) NOT NULL REFERENCES projections(projection_id),
  source_workspace_revision integer NOT NULL,
  idempotency_key varchar(256) NOT NULL,
  request jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb,
  error jsonb,
  created_by varchar(128),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_push_jobs_project_id ON api_push_jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_api_push_jobs_status ON api_push_jobs(status);
CREATE UNIQUE INDEX IF NOT EXISTS uidx_api_push_jobs_idempotency_key
  ON api_push_jobs(idempotency_key);

CREATE TABLE IF NOT EXISTS api_push_records (
  api_push_record_id varchar(64) PRIMARY KEY,
  api_push_job_id varchar(64) NOT NULL REFERENCES api_push_jobs(api_push_job_id),
  workspace_id varchar(64) NOT NULL REFERENCES workspaces(workspace_id),
  project_id varchar(64) NOT NULL REFERENCES projects(project_id),
  plugin_id varchar(128) NOT NULL,
  adapter_id varchar(128) NOT NULL,
  external_system varchar(128) NOT NULL,
  external_system_id varchar(128) NOT NULL,
  external_job_id varchar(128),
  external_record_id varchar(128),
  external_status varchar(64) NOT NULL,
  source_projection_id varchar(64) NOT NULL REFERENCES projections(projection_id),
  source_workspace_revision integer NOT NULL,
  payload_checksum varchar(128) NOT NULL,
  response_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
  error jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_api_push_records_job_id ON api_push_records(api_push_job_id);
CREATE INDEX IF NOT EXISTS idx_api_push_records_project_id ON api_push_records(project_id);
CREATE INDEX IF NOT EXISTS idx_api_push_records_external_record_id
  ON api_push_records(external_record_id);
