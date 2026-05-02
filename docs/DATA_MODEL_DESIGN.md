# Data Model 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义 AI-first Quality Engineering Workspace 的通用数据模型。

数据库不是 Agent 的直接工作区，而是平台在线事实层。

Agent 通过 Workspace Capability Server 使用数据：

```text
fresh Projection
Knowledge Reference
AI Draft Batch
Capability Invocation
API Push
```

平台核心不创建 DFMEA/PFMEA 专用业务表，也不把一个项目的数据塞进一个巨大 JSON 字段。

核心方向：

```text
通用 Artifact
+ 通用 Edge
+ jsonb payload
+ plugin schema 校验
+ AI Draft Batch
+ Workspace Revision
+ Projection 读模型
+ Knowledge 引用
+ API Push 记录
```

## 2. 数据分层

平台数据分为九层：

```text
Scope Layer
  workspace / project / session

Runtime Layer
  run / run_event / capability_invocation

Plugin Registry Layer
  plugin / schema / skill / projection / exporter / view metadata

Canonical Layer
  artifact / artifact_edge

AI Draft Layer
  ai_draft_batch / draft_patch

Version Layer
  workspace_revision_event / optional snapshot

Read Model Layer
  projection / projection_dependency

Knowledge Reference Layer
  evidence_ref / evidence_link

Vector & API Push Layer
  vector_index / api_push_job / api_push_record
```

典型流转：

```text
User Goal
  -> Agent Run
  -> Capability Invocation
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Artifact / Edge Current Data
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Knowledge / Query / API Push
```

## 3. 核心原则

### 3.1 PostgreSQL 是唯一在线事实来源

PostgreSQL 保存 workspace current data 和版本状态。

以下内容不是事实源：

- Agent runtime message
- Projection
- Vector result
- Knowledge snippet
- API push payload
- Mature FMEA system response
- UI 临时状态

### 3.2 Artifact 是业务对象

不采用：

```text
projects.dfmea_payload jsonb
projects.pfmea_payload jsonb
```

采用：

```text
artifacts
  一行一个业务对象

artifact_edges
  一行一个业务关系
```

业务对象粒度由 Domain Plugin 定义。

### 3.3 AI Draft 是批量草稿

AI 生成或修改内容时，不直接写 current data。

AI 输出先进入：

```text
ai_draft_batches
draft_patches
```

用户确认或编辑后，再 apply 到：

```text
artifacts
artifact_edges
```

### 3.4 Workspace Revision 是版本边界

每次成功 apply AI Draft Batch 后：

```text
workspace.current_revision += 1
```

Projection、Knowledge Link、API Push 必须绑定 revision。

### 3.5 Projection 是读模型

AI、UI、API Push 优先读取 Projection。

Projection 可以删除、过期、重建。

任何修改都必须回到 AI Draft / Artifact / Edge。

## 4. Scope Layer

第一阶段不做复杂企业权限，但必须保留隔离边界。

### 4.1 workspaces

```text
workspaces
  workspace_id
  name
  status
  metadata jsonb
  created_at
  updated_at
```

Workspace 是工作区边界，不直接承载第一阶段的数据版本计数。

第一阶段数据版本物理落在 `projects.workspace_revision`。

文档其他位置如果使用 `workspace.current_revision`，表示逻辑上的当前工作区数据版本；MVP 代码实现应读取当前 project 的 `workspace_revision`。

### 4.2 projects

```text
projects
  project_id
  workspace_id
  name
  status
  workspace_revision
  metadata jsonb
  created_at
  updated_at
```

Project 可以作为 workspace 下的业务容器。

第一阶段也可以把 project 直接作为 workspace 使用。

`workspace_revision` 表示该 project 当前 canonical data 的版本号。

第一阶段一 workspace 通常只有一个 active project，因此它等价于逻辑 `workspace.current_revision`。

### 4.3 sessions

```text
sessions
  session_id
  workspace_id
  project_id
  user_id
  active_plugin_id
  status
  metadata jsonb
  created_at
  updated_at
```

Session 是一次用户工作上下文。

## 5. Runtime Layer

Runtime Layer 记录 Agent 执行过程。

### 5.1 runs

```text
runs
  run_id
  workspace_id
  project_id
  session_id
  user_id
  runtime_provider_id
  agent_plugin_id
  active_domain_plugin_id
  goal
  status
  base_workspace_revision
  started_at
  completed_at
  error jsonb
  metadata jsonb
  created_at
  updated_at
```

`base_workspace_revision` 表示 Agent run 启动时看到的工作区版本。

`status` 枚举以 `RUNTIME_PROVIDER_DESIGN.md` 的 Run Lifecycle 为准。

### 5.2 run_events

```text
run_events
  event_id
  workspace_id
  project_id
  session_id
  run_id
  event_type
  sequence
  payload jsonb
  created_at
```

Run Event 用于 UI 展示、问题排查和轻量追踪。

它不是事实源。

### 5.3 capability_invocations

```text
capability_invocations
  invocation_id
  workspace_id
  project_id
  session_id
  run_id
  capability_id
  status
  arguments jsonb
  result jsonb
  error jsonb
  started_at
  completed_at
  created_at
```

Capability Invocation 记录 Agent 使用 Workspace Capability Server 能力的过程。

敏感参数和大结果可以只保存摘要或引用。

## 6. Plugin Registry Layer

插件定义无状态，可以被多个 workspace / project / session 复用。

### 6.1 domain_plugins

```text
domain_plugins
  plugin_id
  name
  version
  status
  manifest jsonb
  created_at
  updated_at
```

### 6.2 plugin_schemas

```text
plugin_schemas
  schema_id
  plugin_id
  schema_name
  schema_version
  schema_kind
  json_schema jsonb
  status
  created_at
  updated_at
```

`schema_kind` 示例：

```text
artifact
edge
skill_input
skill_output
projection
api_push_payload
```

### 6.3 plugin_skills

```text
plugin_skills
  skill_id
  plugin_id
  name
  version
  input_schema_id
  output_schema_id
  handler_ref
  metadata jsonb
  status
  created_at
  updated_at
```

### 6.4 plugin_views

```text
plugin_views
  view_id
  plugin_id
  name
  projection_kind
  view_type
  metadata jsonb
  status
  created_at
  updated_at
```

View metadata 只描述 UI 如何消费 projection，不保存业务事实。

## 7. Canonical Layer

Canonical Layer 保存 workspace current data。

### 7.1 artifacts

```text
artifacts
  artifact_id
  workspace_id
  project_id
  plugin_id
  artifact_type
  schema_version
  status
  revision
  payload jsonb
  created_by
  updated_by
  created_at
  updated_at
```

平台只负责 scope、schema、revision 和状态管理。

业务语义由插件 schema 和 handler 定义。

### 7.2 artifact_edges

```text
artifact_edges
  edge_id
  workspace_id
  project_id
  plugin_id
  source_artifact_id
  target_artifact_id
  relation_type
  schema_version
  status
  revision
  payload jsonb
  created_by
  updated_by
  created_at
  updated_at
```

Edge 承载对象之间的关系。

复杂关系不塞进 artifact payload。

## 8. AI Draft Layer

AI Draft Layer 承载 AI 一次生成或修改的一批草稿。

### 8.1 ai_draft_batches

```text
ai_draft_batches
  draft_batch_id
  workspace_id
  project_id
  session_id
  run_id
  plugin_id
  title
  goal
  status
  base_workspace_revision
  target_workspace_revision
  summary jsonb
  created_by
  applied_by
  rejected_by
  created_at
  updated_at
  applied_at
  rejected_at
```

状态：

```text
pending
applied
rejected
failed
```

### 8.2 draft_patches

```text
draft_patches
  draft_patch_id
  draft_batch_id
  workspace_id
  project_id
  plugin_id
  patch_type
  target_type
  target_id
  artifact_type
  relation_type
  before_payload jsonb
  after_payload jsonb
  payload_patch jsonb
  status
  validation_result jsonb
  applied_result jsonb
  edited_by
  created_at
  updated_at
```

第一阶段可以主要使用 `after_payload` 表达目标状态。

后续再增强为 JSON Patch、Merge Patch 或插件 semantic patch。

## 9. Version Layer

### 9.1 workspace_revision_events

```text
workspace_revision_events
  event_id
  workspace_id
  project_id
  from_revision
  to_revision
  draft_batch_id
  run_id
  summary
  created_by
  created_at
```

它不是完整 event sourcing。

它用于解释 workspace revision 的变化。

### 9.2 snapshots

```text
snapshots
  snapshot_id
  workspace_id
  project_id
  workspace_revision
  reason
  summary jsonb
  snapshot_ref
  created_by
  created_at
```

Snapshot 第一阶段预留，不要求完整恢复能力。

## 10. Read Model Layer

### 10.1 projections

```text
projections
  projection_id
  workspace_id
  project_id
  plugin_id
  kind
  category
  scope_type
  scope_id
  source_revision
  status
  payload jsonb
  summary text
  metadata jsonb
  built_at
  created_at
  updated_at
```

`source_revision` 必须等于 `workspace.current_revision`，才算 fresh。

Projection category 示例：

```text
working
draft_preview
export
evidence_pack
summary
list_view
```

### 10.2 projection_dependencies

```text
projection_dependencies
  dependency_id
  projection_id
  source_type
  source_id
  source_revision
  created_at
```

第一阶段可以只记录 workspace 级 source revision。

## 11. Knowledge Reference Layer

Knowledge Provider 可以是外部 RAG 系统。

平台只保存必要引用和证据关联。

### 11.1 evidence_refs

```text
evidence_refs
  evidence_ref_id
  evidence_ref
  workspace_id
  project_id
  session_id
  knowledge_base_type
  source_type
  provider_id
  provider_ref
  title
  content_preview
  metadata jsonb
  created_at
```

`evidence_ref_id` 是平台表主键。

`evidence_ref` 是 provider 返回或平台归一化后的证据引用值，用于 `evidence_links` 关联和对外展示。

### 11.2 evidence_links

```text
evidence_links
  evidence_link_id
  workspace_id
  project_id
  target_type
  target_id
  evidence_ref
  relation_type
  created_by
  created_at
```

`target_type` 示例：

```text
artifact
edge
ai_draft_batch
draft_patch
projection
api_push_record
```

历史 FMEA 证据只能作为参考，不能直接成为当前工作区事实。

## 12. Vector Layer

第一阶段建议使用 PostgreSQL + pgvector。

```text
vector_indexes
  vector_id
  workspace_id
  project_id
  owner_type
  owner_id
  owner_revision
  text
  embedding vector
  metadata jsonb
  created_at
  updated_at
```

`owner_type` 示例：

```text
artifact
edge
projection
evidence
ai_draft_batch
```

向量索引必须绑定 owner revision。

向量结果不是事实源。

## 13. API Push Layer

API Push Layer 是成熟系统集成的后续阶段数据模型。

第一条可运行主流程先不创建 `api_push_jobs` / `api_push_records`，只需要保证 export projection 可以绑定 fresh workspace revision。

### 13.1 api_push_jobs

```text
api_push_jobs
  api_push_job_id
  workspace_id
  project_id
  plugin_id
  adapter_id
  mode
  status
  source_projection_id
  source_workspace_revision
  idempotency_key
  request jsonb
  result jsonb
  error jsonb
  created_by
  started_at
  completed_at
  created_at
  updated_at
```

### 13.2 api_push_records

```text
api_push_records
  api_push_record_id
  api_push_job_id
  workspace_id
  project_id
  external_system
  external_system_id
  external_job_id
  external_record_id
  external_status
  source_projection_id
  source_workspace_revision
  payload_checksum
  response_summary jsonb
  error jsonb
  created_at
```

API Push record 不是事实源。

成熟 FMEA 系统返回结果不反向覆盖 workspace current data。

## 14. Revision 与一致性

Apply AI Draft Batch 时，应在单个事务内完成：

```text
1. 锁定 ai_draft_batch
2. 检查 batch.status = pending
3. 检查 base_workspace_revision == workspace.current_revision
4. 校验 draft_patches
5. 写入 artifacts / artifact_edges
6. workspace.current_revision += 1
7. 写 target_workspace_revision
8. 更新 draft / patch 状态
9. 标记 projection stale
10. 写 workspace_revision_event
```

Projection rebuild、vector rebuild 可以异步。
API Push 执行在后续成熟系统集成阶段异步处理。

## 15. 查询与索引策略

第一阶段建议基础索引：

```text
workspace_id
project_id
session_id
plugin_id
artifact_type
relation_type
status
source_artifact_id
target_artifact_id
run_id
draft_batch_id
projection kind + scope
source_revision
source_workspace_revision
```

JSONB 查询不要承载所有复杂查询。

高频业务视图优先通过 Projection 解决。

## 16. 第一阶段实现边界

第一阶段必须设计：

- workspace / project / session。
- run / run_event / capability_invocation。
- plugin registry 最小结构。
- artifacts。
- artifact_edges。
- ai_draft_batches。
- draft_patches。
- workspace_revision_events。
- projections。
- evidence_refs。
- evidence_links。
- vector_indexes。
- workspace revision。
- projection freshness。

后续 API Push 阶段实现：

- api_push_jobs。
- api_push_records。

第一阶段暂不实现：

- 完整企业权限模型。
- 完整 event sourcing。
- 完整 artifact revision 历史表。
- 完整 snapshot restore。
- 复杂 time travel。
- 自动 rebase。
- 插件专用物理业务表。
- 文件型主存储。
- 成熟系统反向同步。

## 17. 待决问题

后续需要确认：

- AI Draft Batch 表是否作为唯一草稿批次表。
- projection dirty 是否单独建表。
- vector rebuild 是同步还是异步。
- API Push job 是否需要独立 worker。
- 多 workspace 隔离采用字段隔离还是 schema 隔离。
