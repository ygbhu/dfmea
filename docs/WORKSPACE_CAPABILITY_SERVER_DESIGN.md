# Workspace Capability Server 详细设计

日期：2026-05-01

命名约定：

```text
Workspace Capability Server 是对 Agent Runtime 暴露的协议边界。
后端代码内部对应模块可以命名为 Workspace Capability Service。
```

## 1. 设计目标

Workspace Capability Server 定义 Agent Runtime 如何原生使用质量工程工作区能力。

它替代旧文档中的架构主概念 `Tool Bridge`。

旧的 Tool Bridge 仅作为历史迁移术语，不再作为新设计或新代码命名。主设计语言统一改为：

```text
Workspace Capability Server
Capability Manifest
Capability Invocation
Capability Descriptor
Capability Result
```

目标：

- 让 Agent 不是“外部调用业务系统 API”，而是在工作区内使用原生能力。
- 统一不同 Agent Runtime 的 capability 调用协议。
- 按 Execution Context 动态生成 Capability Manifest。
- 控制能力权限、scope、schema、timeout、审计。
- 路由到 Platform Service 或 Domain Plugin Skill。
- 防止 Agent 直连数据库或绕过 AI Draft 写 current data。

## 2. 核心定位

```text
Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Platform Service / Domain Plugin Skill Handler
```

Workspace Capability Server 是 Agent 工作区入口。

它不是业务服务本身，也不是数据库访问层。

## 3. 能力类型

第一阶段分三类：

```text
resources
action capabilities
prompts
policies
```

### 3.1 Resources

Agent 可读取的工作区资源引用。

示例：

```text
workspace://projection/working
workspace://projection/export
workspace://knowledge/project
workspace://knowledge/historical-fmea
workspace://schema/current
workspace://draft/pending
```

资源读取必须通过平台服务，不能直接读数据库。

### 3.2 Action Capabilities

Agent 可调用的动作能力。

如果具体 Agent Runtime 采用 MCP 或类似协议，Action Capability 可以映射为其原生 tool。

示例：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user
```

默认不让 Agent 直接 apply AI Draft 或正式执行 API Push。

`workspace.ai_draft.apply` 和 `workspace.api_push.execute` 可以后续在受控模式下开放。

### 3.3 Prompts

平台或插件提供的提示资源。

示例：

```text
analysis_guide
validation_rubric
export_mapping_guide
```

Prompt 是资源，不是唯一执行体。

### 3.4 Policies

平台约束。

示例：

```text
no_direct_database_access
draft_before_apply
fresh_projection_required
api_push_requires_revision_binding
no_mature_system_direct_access
```

## 4. Capability Manifest

Capability Manifest 是某次 run 可用能力的清单。

它不是全平台能力列表。

它由 Run Execution Context 动态生成。

影响因素：

```text
scope
active domain plugin
agent runtime capability
draft policy
projection policy
knowledge policy
task type
```

示例：

```json
{
  "run_id": "run_001",
  "base_workspace_revision": 12,
  "capabilities": [
    {
      "capability_id": "workspace.projection.get",
      "kind": "action",
      "input_schema_ref": "schema.workspace.projection_get.input",
      "output_schema_ref": "schema.workspace.projection_get.output"
    },
    {
      "capability_id": "workspace.ai_draft.propose",
      "kind": "action",
      "input_schema_ref": "schema.workspace.ai_draft_propose.input",
      "output_schema_ref": "schema.workspace.ai_draft_propose.output"
    }
  ]
}
```

规则：

- Manifest 必须绑定 run。
- Manifest 必须绑定 base workspace revision。
- Runtime 只能调用 Manifest 内能力。
- Manifest 可在 context refresh 后重新生成。

## 5. Capability Descriptor

每个 capability 需要稳定描述。

字段建议：

```text
capability_id
kind
display_name
description
owner
input_schema
output_schema
side_effect
requires_fresh_projection
allowed_draft_policy
timeout_ms
result_size_policy
audit_level
```

side_effect 建议：

```text
none
read_only
creates_ai_draft
asks_user
starts_api_push_job
records_event
```

第一阶段不开放直接修改 current data 的 side effect。

## 6. Capability Invocation

平台内部使用统一 Invocation Envelope。

Agent Native Plugin 负责把具体 Agent 的调用格式转换成该 envelope。

### 6.1 Request

```json
{
  "invocation_id": "inv_001",
  "run_id": "run_001",
  "capability_id": "workspace.projection.get",
  "arguments": {
    "kind": "working_view",
    "scope_type": "project",
    "scope_id": "proj_001"
  },
  "timeout_ms": 30000,
  "idempotency_key": "inv_001"
}
```

要求：

- `invocation_id` 必须唯一。
- `run_id` 必须属于当前 scope。
- `capability_id` 必须在当前 Capability Manifest 中。
- `arguments` 必须通过 input schema 校验。
- 有副作用的 capability 必须使用 idempotency key。

### 6.2 Response

```json
{
  "invocation_id": "inv_001",
  "status": "completed",
  "result": {},
  "error": null,
  "events": []
}
```

状态：

```text
accepted
running
completed
failed
cancelled
timeout
denied
invalid_arguments
```

## 7. Permission

每次 capability invocation 都必须重新校验。

校验：

```text
capability in current manifest
run status active
scope allowed
draft policy allowed
runtime capability allowed
plugin capability allowed
input schema valid
projection freshness policy
knowledge policy
rate limit / timeout
```

拒绝码示例：

```text
CAPABILITY_NOT_IN_MANIFEST
CAPABILITY_NOT_ALLOWED
CAPABILITY_SCOPE_DENIED
CAPABILITY_DRAFT_POLICY_DENIED
CAPABILITY_RUNTIME_UNSUPPORTED
CAPABILITY_PLUGIN_UNSUPPORTED
CAPABILITY_ARGUMENT_INVALID
CAPABILITY_RATE_LIMITED
```

## 8. Schema Validation

Workspace Capability Server 必须执行输入输出校验。

执行前：

- arguments JSON schema。
- required fields。
- enum。
- scope 是否匹配。
- id 格式。
- payload size。

执行后：

- result JSON schema。
- error schema。
- result size。
- 是否包含禁止字段。
- 是否包含未授权数据。

Domain Plugin Skill 的 schema 来自插件 manifest，但平台负责执行校验。

## 9. Context Injection

执行 capability 前创建 Capability Execution Context。

调用插件 skill 时创建 Skill Execution Context。

Skill Context 提供受控 facade：

```text
projectionFacade
knowledgeFacade
evidenceFacade
validatorFacade
aiDraftFacade
questionFacade
eventFacade
```

这些 facade 不是数据库连接。

## 10. Dispatch 路由

根据 capability_id 路由：

```text
workspace.*
  -> Platform Capability Handler

{plugin_id}.*
  -> Domain Plugin Skill Handler

system.*
  -> System Capability Handler
```

示例：

```text
dfmea.generate_initial_analysis
  -> plugin_id = dfmea
  -> skill_id = generate_initial_analysis
  -> DFMEA Plugin Skill Handler
```

### 10.1 Platform Capability Handler

示例：

```text
workspace.projection.get
  -> Projection Service

workspace.knowledge.retrieve
  -> Knowledge Service

workspace.ai_draft.propose
  -> AI Draft Service

workspace.ai_draft.validate
  -> Validation Service

workspace.question.ask_user
  -> Runtime Service / Event Service

后续 API Push 阶段：

workspace.api_push.validate
  -> API Push Service
```

### 10.2 Plugin Skill Handler

Plugin skill 由 Plugin Service 解析。

调用前必须：

- 确认 plugin 在当前 run 可用。
- 确认 skill 在 Capability Manifest 中。
- 校验 input schema。
- 创建 Skill Execution Context。

调用后必须：

- 校验 output schema。
- 归一化结果。
- 记录事件。

## 11. 第一阶段 Capability

第一阶段建议开放：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user
```

第一阶段谨慎或不开放：

```text
workspace.ai_draft.apply
workspace.api_push.validate
workspace.api_push.execute
```

`workspace.ai_draft.apply` 更适合由用户在 UI 中触发。
API Push capabilities 在成熟系统集成阶段再开放。

## 12. 禁止 Capability

第一阶段不向 Agent Runtime 暴露：

```text
database.query_raw
database.execute_raw
artifact.update_direct
artifact.create_direct
artifact.delete_direct
edge.update_direct
edge.create_direct
edge.delete_direct
projection.update_direct
projection.delete_direct
mature_system.write_direct
filesystem.write
shell.run
```

shell 和 filesystem 属于 Runtime Sandbox 设计，不属于业务 capability。

## 13. Result Normalization

Capability 返回必须归一成：

```text
status
result
error
events
references
```

大结果返回摘要和 ref，不要一次性塞回 Agent。

AI 生成的业务变更必须先进入 AI Draft Batch。

## 14. Event / Audit

至少记录：

```text
invocation_id
run_id
capability_id
scope
arguments summary
status
duration
error
result summary
created_at
completed_at
```

事件示例：

```text
capability.invocation.requested
capability.invocation.started
capability.invocation.completed
capability.invocation.failed
capability.invocation.denied
capability.invocation.timeout
```

敏感参数和大结果只保存摘要、hash 或 ref。

## 15. Runtime Provider / Agent Native Plugin 关系

Workspace Capability Server 内部协议稳定。

Agent Native Plugin 负责适配具体 Agent。

```text
OpenCode / Codex / Claude Code / Qwen Code
  -> Agent Native Plugin
  -> Capability Invocation
  -> Workspace Capability Server
```

Agent Native Plugin 负责：

- 把 Capability Manifest 转成 Agent 原生 tools/resources/prompts。
- 把 Agent 调用转成 Capability Invocation。
- 把 Capability Result 转回 Agent。
- 处理 Agent 特有事件。

不负责：

- 决定业务权限。
- 直接访问数据库。
- 直接执行插件 skill。
- 绕过 Workspace Capability Server。

## 16. 实现形态

内部协议应独立于传输方式。

可能实现：

```text
MCP server
HTTP endpoint
local IPC
in-process call
```

第一阶段可以选择最简单的实现，但保持：

```text
Capability Manifest stable
Capability Invocation stable
Capability Descriptor stable
Agent Native Plugin replaceable
```

## 17. 第一阶段实现边界

第一阶段必须定义：

- Capability ID 命名规则。
- Capability Manifest。
- Capability Descriptor。
- Capability Invocation。
- Permission。
- Schema Validation。
- Context Injection。
- Platform Capability Handler。
- Plugin Skill Handler 调用规范。
- Result Normalization。
- Event。
- Timeout。
- Idempotency key。
- Agent Native Plugin 适配边界。

第一阶段暂不开放：

- raw database capability。
- direct artifact / edge write capability。
- direct projection write capability。
- direct mature system write capability。
- shell capability。
- filesystem write capability。
- 插件自由注册未审核 capability。

## 18. 待决问题

后续需要确认：

- 第一阶段采用 MCP、HTTP、IPC 还是 in-process。
- Capability Manifest 是否持久化，还是从 run context 动态恢复。
- Capability Descriptor 是否由 manifest / JSON Schema 自动生成。
- Plugin Skill Handler 的运行沙箱边界。
- 大型 capability result 的 ref 存储位置。
- Capability retry 最大次数。
- arguments 是否需要脱敏存储。
