# Platform API 详细设计

日期：2026-05-01

## 1. 设计目标

Platform API 是 AI-first Quality Engineering Workspace 的运行控制入口。

它不是 DFMEA/PFMEA CRUD API，也不是数据库表直接暴露。

主链路：

```text
Frontend / Workspace UI
  -> Platform API
  -> Platform Core Services
  -> Agent Runtime / Workspace Capability Server / Domain Plugin / Projection / Knowledge / API Push
```

第一阶段采用：

```text
REST + SSE
```

REST 用于 command / query。

SSE 用于 Agent run 和工作区事件流。

## 2. API 分层

### 2.1 Public Platform API

面向 UI 和外部调用方。

主要能力：

- 创建 workspace / project / session。
- 启动 Agent run。
- 发送用户补充输入。
- 查询 run 状态。
- 查询 fresh projection。
- 查询 AI Draft Batch。
- 编辑 / 应用 / 拒绝 AI Draft。
- 查询 workspace revision。
- 触发 projection rebuild。

API Push validate / execute 是后续成熟系统集成阶段能力，不进入第一条主流程。

### 2.2 Event Stream API

面向长流程 Agent 执行和异步任务。

第一阶段建议：

```text
GET /api/runs/{run_id}/events
GET /api/workspaces/{workspace_id}/events
```

### 2.3 Workspace Capability API

面向 Agent Native Plugin。

它是 Workspace Capability Server 的传输实现之一。

如果第一阶段使用 MCP，则该层可以表现为 MCP server。

如果使用 HTTP，则可以表现为内部 capability endpoint。

不管传输方式如何，平台内部统一使用：

```text
Capability Manifest
Capability Invocation
Capability Result
```

## 3. 核心资源模型

第一阶段 API 围绕以下资源：

```text
workspace
project
session
run
agent_runtime_provider
agent_native_plugin
domain_plugin
capability
artifact
edge
ai_draft_batch
draft_patch
workspace_revision
projection
evidence
```

后续 API Push 阶段增加：

```text
api_push_job
api_push_record
```

具体 artifact_type、edge_type、projection kind 由 Domain Plugin 定义。

## 4. Command API

Command API 用于触发动作。

典型命令：

```text
POST /api/workspaces
POST /api/workspaces/{workspace_id}/projects
POST /api/projects/{project_id}/sessions
POST /api/sessions/{session_id}/runs
POST /api/runs/{run_id}/input
POST /api/runs/{run_id}/cancel

POST /api/ai-drafts/{draft_batch_id}/edit
POST /api/ai-drafts/{draft_batch_id}/apply
POST /api/ai-drafts/{draft_batch_id}/reject

POST /api/projections/rebuild
```

后续 API Push 阶段增加：

```text
POST /api/api-push/validate
POST /api/api-push/execute
```

Command 返回：

```json
{
  "command_id": "cmd_001",
  "status": "accepted",
  "correlation_id": "corr_001",
  "events_url": "/api/runs/run_001/events"
}
```

### 4.1 幂等性

会产生状态变化的 command 应支持：

```text
Idempotency-Key
```

适用：

- start run。
- apply AI Draft。
- API Push execute 后置。

## 5. Query API

典型查询：

```text
GET /api/workspaces/{workspace_id}
GET /api/workspaces/{workspace_id}/revisions
GET /api/projects/{project_id}
GET /api/sessions/{session_id}
GET /api/runs/{run_id}

GET /api/ai-drafts/{draft_batch_id}
GET /api/projects/{project_id}/ai-drafts

GET /api/projections/{projection_id}
GET /api/projects/{project_id}/projections?kind=...

GET /api/evidence/{evidence_ref}
```

后续 API Push 阶段增加：

```text
GET /api/api-push/jobs/{api_push_job_id}
GET /api/api-push/records/{api_push_record_id}
```

Query API 默认读取：

```text
workspace current state summary
fresh projection
AI Draft status
workspace revision
API Push record
event log
```

不默认暴露底层 canonical 表结构。

## 6. Projection 查询规则

AI 和 API Push 默认只读取 fresh projection。

fresh 条件：

```text
projection.source_revision == workspace.current_revision
```

不同入口的 stale 策略：

```text
workspace.projection.get capability:
  默认 rebuild_then_return。
  如果 rebuild 失败，再返回 PROJECTION_STALE 或 rebuild error。

普通 REST Query API:
  可以返回 PROJECTION_STALE，让 UI 展示 stale 状态或触发 rebuild。

API Push:
  必须 rebuild_then_return 或失败，不允许基于 stale export projection 推送。
```

普通 REST Query API stale 时返回：

```json
{
  "error": {
    "code": "PROJECTION_STALE",
    "message": "Projection is stale.",
    "workspace_revision": 12,
    "projection_source_revision": 11,
    "rebuild_available": true
  }
}
```

UI 可以展示 stale 标识，但不能伪装成最新。

## 7. Event Stream API

事件 envelope：

```json
{
  "event_id": "evt_001",
  "event_type": "ai_draft.created",
  "workspace_id": "ws_001",
  "project_id": "proj_001",
  "session_id": "sess_001",
  "run_id": "run_001",
  "correlation_id": "corr_001",
  "created_at": "2026-05-01T10:00:00Z",
  "payload": {}
}
```

核心事件：

```text
run.created
run.started
run.output.delta
run.waiting_for_input
run.completed
run.failed
run.cancelled

capability.invocation.requested
capability.invocation.completed
capability.invocation.failed

ai_draft.created
ai_draft.edited
ai_draft.rejected
ai_draft.apply_started
ai_draft.applied
ai_draft.apply_failed

workspace_revision.changed

projection.rebuild.started
projection.rebuild.completed
projection.rebuild.failed
```

Draft preview events 用于 UI 实时展示 AI 生成中的结构树候选状态：

```text
draft.preview.started
draft.preview.node_upserted
draft.preview.node_updated
draft.preview.edge_upserted
draft.preview.edge_updated
draft.preview.node_removed
draft.preview.validation_updated
draft.preview.evidence_linked
draft.preview.completed
```

后续 API Push 阶段增加：

```text
api_push.validation.started
api_push.validation.completed
api_push.execute.started
api_push.execute.completed
api_push.execute.failed
```

Event Stream 是展示和订阅机制，不是事实源。

## 8. Workspace Capability API

Workspace Capability Server 给 Agent Native Plugin 提供能力入口。

典型能力：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user
```

第一阶段不默认向 Agent 开放 `workspace.ai_draft.apply` 和 `workspace.api_push.execute`。

默认推荐 Agent 生成 draft，用户在 UI 中 apply。
API Push capabilities 在成熟系统集成阶段再开放。

### 8.1 Capability Invocation Envelope

```json
{
  "invocation_id": "inv_001",
  "run_id": "run_001",
  "capability_id": "workspace.ai_draft.propose",
  "arguments": {},
  "timeout_ms": 30000,
  "idempotency_key": "inv_001"
}
```

返回：

```json
{
  "invocation_id": "inv_001",
  "status": "completed",
  "result": {},
  "error": null
}
```

## 9. 状态变更约束

```text
No AI current-data write without AI Draft Batch.
No stale projection for AI/API Push read.
No direct runtime database access.
No plugin state outside platform scope.
No mature FMEA system as source of truth.
```

AI 产生业务修改时，只能进入：

```text
AI Draft Batch
Draft Patch
User Confirm / Apply
Workspace Current Data
Workspace Revision
Projection Rebuild
```

## 10. 多用户 Scope

所有 API 调用必须落在明确 scope 内：

```text
workspace_id
project_id
session_id
run_id
```

第一阶段不做复杂企业权限，但必须保证：

- 用户不能读取其他 workspace。
- Capability invocation 不能跨 session 调用未授权资源。
- Plugin skill 不能直接访问跨 project 数据。
- Knowledge retrieve 必须受 scope 限制。
- API Push 必须绑定 workspace revision。

## 11. 错误模型

统一错误结构：

```json
{
  "error": {
    "code": "AI_DRAFT_BASE_REVISION_CONFLICT",
    "message": "Draft was generated from an older workspace revision.",
    "details": {},
    "correlation_id": "corr_001"
  }
}
```

常见错误码：

```text
VALIDATION_FAILED
RUNTIME_PROVIDER_UNAVAILABLE
RUN_ALREADY_COMPLETED
CAPABILITY_NOT_ALLOWED
CAPABILITY_TIMEOUT
AI_DRAFT_NOT_FOUND
AI_DRAFT_ALREADY_APPLIED
AI_DRAFT_REJECTED
AI_DRAFT_BASE_REVISION_CONFLICT
PROJECTION_STALE
PROJECTION_REBUILD_FAILED
KNOWLEDGE_PROVIDER_UNAVAILABLE
API_PUSH_NOT_READY
API_PUSH_FAILED
SCOPE_DENIED
```

## 12. 外部系统集成

成熟 FMEA 系统不直接写平台 canonical store。

平台通过 API Push Adapter 推送数据。

链路：

```text
workspace current data
  -> fresh export projection
  -> API Push Adapter
  -> Mature FMEA System API
  -> api_push_record
```

API Push 成功不反向覆盖 workspace current data。

## 13. 第一阶段实现边界

第一阶段必须设计并实现：

- REST Command API。
- REST Query API。
- SSE Run / Workspace Event Stream。
- Workspace Capability API。
- scope 传递与校验。
- idempotency key。
- unified error model。
- run / capability / ai draft / projection 事件。

后续 API Push 阶段增加：

- api push 事件。

第一阶段暂不实现：

- GraphQL。
- WebSocket 协同编辑。
- 复杂企业权限。
- 外部 webhook marketplace。
- Runtime 直接数据库访问。
- UI 直接调用 Plugin Skill Handler。
- 成熟系统反向同步。

## 14. 待决问题

后续需要确认：

- API 服务技术栈。
- Workspace Capability Server 采用 MCP、HTTP、IPC 还是 in-process。
- SSE 是否需要 workspace 维度聚合流。
- Event Log 保留周期。
- Public API 是否需要 OpenAPI schema。
- UI 对 stale projection 的展示策略。
