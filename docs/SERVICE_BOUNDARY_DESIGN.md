# Service Boundary 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义 AI-first Quality Engineering Workspace 后端的服务职责边界。

第一阶段仍采用：

```text
模块化单体
```

Service Boundary 是代码职责边界，不是微服务拆分边界。

当前主线：

```text
Agent Native Plugin
  -> Workspace Capability Server
  -> Platform Core Services
  -> Repository
```

## 2. 总体分层

```text
Platform API Layer
  -> Application Service Layer
  -> Domain Service Layer
  -> Provider / Adapter Layer
  -> Repository Layer
```

### 2.1 Platform API Layer

负责 HTTP / SSE 请求、认证、request context、DTO 和错误返回。

不直接写 artifact / edge，不直接执行 AI Draft apply，不直接调用插件 handler。

### 2.2 Application Service Layer

负责用户用例编排。

示例：

```text
StartRunApplicationService
ApplyAIDraftApplicationService
RebuildProjectionApplicationService
ApiPushApplicationService
```

### 2.3 Domain Service Layer

负责平台核心规则。

### 2.4 Provider / Adapter Layer

负责外部能力接入：

```text
Agent Runtime Provider Adapter
Knowledge Provider Adapter
API Push Adapter
Embedding Provider
Storage Adapter
```

Adapter 不持有平台事实状态。

### 2.5 Repository Layer

负责数据库读写。

Repository 只被 Service 调用，不被 API、Agent Runtime、Agent Native Plugin、Domain Plugin Skill 直接调用。

## 3. 核心服务清单

第一阶段建议保留：

```text
Scope Service
Workspace / Project / Session Service
Runtime Service
Workspace Capability Service
Plugin Service
Artifact Service
AI Draft Service
Workspace Version Service
Projection Service
Knowledge Service
Validation Service
API Push Service
Event Service
```

这些服务可以全部在一个后端应用内实现。

命名约定：

```text
Workspace Capability Service 是后端内部服务模块。
Workspace Capability Server 是对 Agent 暴露的协议边界。
```

## 4. Scope Service

负责统一校验运行边界。

Scope 包含：

```text
user_id
workspace_id
project_id
session_id
run_id
plugin_id
```

负责：

- 校验 workspace / project / session / run 归属。
- 校验 capability invocation 是否在当前 run 授权范围内。
- 给其他服务提供统一 `ExecutionScope`。

第一阶段不做完整企业 RBAC。

## 5. Workspace / Project / Session Service

负责工作区、项目和会话生命周期。

负责：

- 创建 workspace / project。
- 创建和关闭 session。
- 绑定 active domain plugin。
- 维护逻辑 workspace current_revision。

`current_revision` 只能由 AI Draft apply 的受控流程更新。

MVP 物理字段落在 `projects.workspace_revision`，语义上仍代表当前 project 的 workspace data revision。

## 6. Runtime Service

负责 Agent run 生命周期。

负责：

- 创建 run。
- 选择 Agent Runtime Provider。
- 构建 Run Execution Context。
- 启动 provider run。
- 发送用户补充输入。
- 取消 run。
- 接收 runtime event。
- 记录 run event。

不负责：

- agent loop。
- LLM planning。
- 直接写 artifact / edge。
- 直接 apply AI Draft。

## 7. Workspace Capability Service

Workspace Capability Service 是 Agent 使用工作区能力的统一入口。

旧文档中的 `Tool Bridge Service` 在新架构下收敛为 Workspace Capability Service，仅作为历史迁移术语。

负责：

- 生成 Capability Manifest。
- 校验 Capability Invocation 权限。
- 校验输入输出 schema。
- 注入 Execution Context。
- 路由到平台服务或 Domain Plugin Skill。
- 归一化结果。
- 记录 capability invocation。

典型链路：

```text
Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Service
  -> Platform Service / Plugin Skill Handler
```

不允许暴露：

```text
raw database access
direct artifact write
direct edge write
direct projection write
direct mature system write
shell.run
filesystem.write
```

## 8. Plugin Service

负责插件注册、发现和能力声明。

负责：

- 加载 plugin manifest。
- 管理 schemas、skills、validators、projection handlers、exporters、views metadata。
- 为 Workspace Capability Service 提供可暴露的 plugin skills。

不保存插件运行态业务事实。

## 9. Artifact Service

Artifact Service 负责 workspace current data。

负责：

- 创建、更新、软删除 artifact。
- 创建、更新、软删除 edge。
- schema validation。
- artifact / edge revision 管理。
- projection stale 标记。

第一阶段只有以下路径可以写 artifact / edge：

```text
AI Draft Service
  -> Artifact Service
```

用户手动编辑也应先进入 AI Draft，再 apply。

## 10. AI Draft Service

AI Draft Service 是 AI 和用户批量草稿变更的核心服务。

负责：

- 创建 AI Draft Batch。
- 创建 Draft Patch。
- 编辑 Draft Patch。
- 拒绝 AI Draft Batch。
- Apply AI Draft Batch。
- 校验 draft schema。
- 做 base workspace revision 检查。
- 协调 Artifact Service 写 current data。
- 协调 Workspace Version Service 递增 revision。
- 协调 Projection Service 标记 stale。

不负责：

- Agent runtime 执行。
- 企业审批。
- projection payload 构建。
- 成熟系统 API 调用。

### 10.1 Apply 事务边界

AI Draft apply 应尽量在单个数据库事务内完成：

```text
1. 锁定 ai_draft_batch
2. 检查 batch status
3. 检查 base_workspace_revision
4. 校验 draft_patches
5. 调用 Artifact Service 写 artifacts / edges
6. workspace.current_revision += 1
7. 更新 draft / patch 状态
8. 标记 projection stale
9. 写 workspace_revision_event
```

Projection rebuild、vector rebuild、API Push 可以异步。

## 11. Workspace Version Service

负责工作区版本边界。

负责：

- 读取 current_revision。
- 在 AI Draft apply 成功后递增 revision。
- 写 workspace_revision_event。
- 为 Projection / API Push 提供 revision binding。

第一阶段不实现完整 rollback / time travel。

## 12. Projection Service

负责 AI/UI/API Push 读模型。

负责：

- 查询 fresh projection。
- 拒绝 AI/API Push 读取 stale projection。
- 标记 projection stale。
- 调度 projection rebuild。
- 调用 plugin projection handler。
- 存储 projection payload。
- 维护 projection status 和 dependency。

Projection 不是写入入口，也不是事实源。

## 13. Knowledge Service

负责统一对接 Knowledge Provider。

负责：

- retrieve。
- getEvidence。
- evidence_ref 保存。
- evidence_link 保存。
- knowledge scope 校验。

Knowledge Service 不写 artifact，不创建 AI Draft，不决定当前工作区事实。

AI 或 Skill 基于知识生成内容时，必须进入 AI Draft Batch。

## 14. Validation Service

负责轻量护栏。

第一阶段只做：

```text
Schema Validation
AI Draft Apply Safety Validation
API Push Gate Validation 后置
```

Validation 不替代用户确认，不做企业审批。

## 15. API Push Service

API Push Service 是成熟系统集成的后续阶段服务，不进入第一条可运行主流程。

负责把 fresh export projection 推送到成熟 FMEA 系统。

负责：

- 校验 export projection fresh。
- 创建 api_push_job。
- 调用 API Push Adapter。
- 记录 external response。
- 保存 api_push_record。
- 绑定 source_workspace_revision。

不负责：

- 文件导出主线。
- 反向同步成熟系统。
- 直接读取 artifact / edge 拼目标 payload。
- 修改 workspace current data。

## 16. Event Service

负责轻量事件。

事件用于 UI 展示、审计辅助和问题排查。

第一阶段事件不是完整 event sourcing，也不是事实源。

## 17. Service 调用规则

### 17.1 API 调用

```text
API Controller
  -> Application Service
  -> Domain Service
  -> Repository
```

禁止 API Controller 直接访问 Repository。

### 17.2 Agent 调用

```text
Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Service
  -> Allowed Platform Service / Plugin Skill
```

禁止 Agent Runtime 直接访问 Repository、Artifact Service 写接口或成熟系统 API。

### 17.3 Plugin Skill 调用

```text
Plugin Skill Handler
  -> Skill Execution Context
  -> Allowed Service Facade
```

禁止 Skill 获取 raw database handle、跨 scope 读取、直接写 current data。

### 17.4 写入主路径

```text
AI output / User edit
  -> AI Draft Service
  -> User Confirm / Apply
  -> Artifact Service
  -> Workspace Version Service
  -> Projection Service mark stale
```

这是第一阶段唯一推荐写入主路径。

## 18. 强一致与最终一致

强一致：

- AI Draft apply。
- Artifact / Edge 写入。
- Workspace revision 更新。
- Draft status 更新。
- Projection stale 标记。
- Workspace revision event。

最终一致：

- Projection rebuild。
- Vector rebuild。
- API Push job。
- Evidence enrichment。

## 19. 模块化单体到后续拆分

后续如果需要拆分，优先拆：

```text
Agent Runtime Hub
Knowledge Provider Gateway
Projection Worker
API Push Worker
Vector Worker
```

不建议第一阶段拆：

```text
Artifact Service
AI Draft Service
Workspace Version Service
```

它们处于强一致路径。

## 20. 第一阶段实现边界

第一阶段必须定义：

- Scope Service。
- Runtime Service。
- Workspace Capability Service。
- Plugin Service。
- Artifact Service。
- AI Draft Service。
- Workspace Version Service。
- Projection Service。
- Knowledge Service。
- Validation Service。
- Event Service。
- AI Draft apply 事务边界。

后续 API Push 阶段实现：

- API Push Service。

第一阶段暂不实现：

- 微服务拆分。
- 分布式事务。
- 完整 RBAC。
- 企业审批。
- 完整 event sourcing。
- 完整 rollback。
- Runtime 直接数据库访问。
- Plugin 直接数据库访问。

## 21. 待决问题

后续需要确认：

- 后端技术栈和模块目录结构。
- Workspace Capability Server 的传输方式：MCP、HTTP、IPC 或 in-process。
- Projection rebuild 是否单独 worker。
- API Push job 是否单独 worker。
- Repository 是否按 aggregate 拆分。
- `workspace` 与 `project` 命名是否统一。
