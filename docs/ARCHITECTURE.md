# AI-first Quality Engineering Workspace 架构文档

日期：2026-05-01

## 架构图

当前主架构以本文为准。

![AI-first Quality Engineering Workspace System Architecture](./architecture-system-architecture.png)

旧架构图如果仍出现 `AI Orchestrator`、`Tool Bridge` 作为主概念，或把 `Change Set / Review` 表达为企业级流程，应视为待更新。

架构图应按以下主线理解：

```text
User Goal
  -> Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Domain Plugin Skill
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Artifact / Edge canonical state
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Knowledge / Query / API Push
```

平台层级可简化表达为：

```text
Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Domain Plugin / Platform Core Services
  -> PostgreSQL / Projection / Knowledge / API Push
```

## 1. 架构定位

本项目定位为：

```text
AI-first Quality Engineering Workspace
```

它不是企业级 FMEA 管理系统，也不是传统 FMEA 软件的 AI 按钮。

它的核心目标是让 AI 更好地辅助用户：

```text
生成质量失效分析数据
分析和补全质量工程内容
查询当前项目和历史知识
沉淀企业知识库
形成结构化工作区数据
推送到成熟 FMEA 系统
```

企业级能力由成熟 FMEA 系统承接：

```text
企业权限
审批流程
签核
正式发布
最终质量记录
长期合规管理
```

因此，当前平台不追求成为完整质量管理系统，而是成为 AI 主导的质量工程工作区。

## 2. 总体架构

新的总体链路是：

```text
User Goal
  -> Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Domain Plugin Skill
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Workspace Current Data
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Knowledge / Query / API Push
```

架构分层：

```text
Agent Runtime
  外部 Agent 执行能力，例如 OpenCode、Codex、Claude Code、Qwen Code。

Agent Native Plugin
  面向具体 Agent 的原生插件，让 Agent 以自己的方式使用质量工程能力。

Workspace Capability Server
  面向 Agent 暴露 resources、action capabilities、prompts、policies。

Platform Core Services
  管理工作区数据、版本、AI Draft、Projection、Knowledge、Validation、API Push。

Domain Plugins
  DFMEA、PFMEA、Control Plan、8D 等业务能力插件。

PostgreSQL
  保存在线事实数据、版本、AI Draft、Projection 元数据和推送记录。
```

## 3. Agent Native Plugin

Agent 不应被表达成“外部调用业务系统 API 的旁路调用者”。

更合理的表达是：

```text
平台把质量工程工作区能力挂载成 Agent 的原生插件能力。
```

例如：

```text
OpenCode Plugin
Codex Plugin
Claude Code Plugin
Qwen Code Plugin
```

Agent Native Plugin 负责：

- 让 Agent 发现当前工作区资源。
- 让 Agent 调用质量工程能力。
- 让 Agent 使用平台提供的 prompts / policies。
- 把 Agent Runtime 的原生调用协议适配到平台能力协议。

Agent Native Plugin 不负责：

- 保存业务事实数据。
- 直接连接数据库。
- 绕过 AI Draft 写入当前工作区。
- 直接推送成熟 FMEA 系统。

平台核心不绑定某个具体 Agent。

第一阶段可以优先实现一个 Agent 的原生插件接入，但架构上保留多 Agent 适配能力。

## 4. Workspace Capability Server

Workspace Capability Server 是平台暴露给 Agent 的工作区能力层。

它的角色类似 MCP server，面向 Agent 提供：

```text
resources
action capabilities
prompts
policies
```

示例：

```text
resources:
  workspace://projection/working
  workspace://projection/export
  workspace://knowledge/project
  workspace://knowledge/historical-fmea
  workspace://schema/current
  workspace://draft/pending

action capabilities:
  workspace.knowledge.retrieve
  workspace.projection.get
  workspace.ai_draft.propose
  workspace.ai_draft.validate
  workspace.question.ask_user
  workspace.api_push.validate

prompts:
  analysis_guide
  validation_rubric
  export_mapping_guide

policies:
  no_direct_database_access
  draft_before_apply
  fresh_projection_required
  api_push_requires_revision_binding
```

第一阶段不默认把 `workspace.ai_draft.apply` 和 `workspace.api_push.execute` 暴露给 Agent。
这些动作更适合由用户在 UI 中显式触发。

旧文档中的 `Tool Bridge` 仅作为历史迁移术语，不再作为主架构概念或新代码命名。

但在主架构中，建议统一表达为：

```text
Workspace Capability Server
Capability Manifest
Capability Invocation
```

## 5. Domain Plugin

DFMEA、PFMEA 等业务能力不作为独立 Agent 存在，而是作为 Domain Plugin 存在。

Domain Plugin 负责提供业务能力：

- artifact / edge schema。
- skill handler。
- prompt 资源。
- validator。
- projection handler。
- exporter / api push mapping。
- view metadata。

Domain Plugin 不负责：

- 管理用户 session。
- 保存运行态业务事实。
- 直接访问数据库。
- 直接推送成熟系统。
- 管理企业审批流程。

第一阶段可从 DFMEA Plugin 验证平台能力，但平台核心不写死 DFMEA/PFMEA 字段。

DFMEA 第一阶段业务逻辑以 `DFMEA_PLUGIN_DESIGN.md` 为准。

后续可以继续增加：

```text
PFMEA
Control Plan
8D
DRBFM
FMEA-MSR
其他质量工程方法
```

## 6. Plugin Skill

Skill 是 Domain Plugin 暴露给 Agent 的任务级业务能力。

Skill 不是：

```text
prompt 模板
字段级 CRUD
数据库脚本
隐藏 workflow engine
```

Skill 必须有代码 handler。

Prompt 只是 handler 可使用的资源。

Skill 通过 Workspace Capability Server 提供给 Agent。

Skill 输出必须结构化，例如：

```text
AI Draft proposal
validation result
question to user
summary
candidate result
```

如果 Skill 产生业务内容，应进入 AI Draft Batch，而不是直接写当前工作区事实。

## 7. 工作区数据模型

平台在线事实层采用 PostgreSQL。

核心采用：

```text
workspace current data
  artifacts
  artifact_edges

AI draft layer
  ai_draft_batches
  draft_patches

read model
  projections

knowledge refs
  evidence_refs
  evidence_links

api push
  api_push_jobs
  api_push_records
```

平台核心不创建 DFMEA/PFMEA 专用业务表。

推荐模型：

```text
通用 Artifact
+ 通用 Edge
+ jsonb payload
+ plugin schema 校验
+ AI Draft Batch
+ Workspace Revision
+ Projection
```

业务字段由 Domain Plugin schema 定义。

平台负责 scope、schema、版本、应用草稿、projection freshness 和 API Push binding。

## 8. 版本管理

版本管理必须保留。

原因不是企业合规，而是 AI 生成和修改速度太快、范围太大。

平台必须能回答：

```text
AI 这次改了什么？
当前工作区是哪一版？
这次 API Push 基于哪一版？
这条数据由哪个 AI run 生成？
能不能回到上一个重要状态？
```

第一阶段最小版本能力：

```text
workspace_revision
  每次 apply AI Draft 后递增。

ai_draft_batch
  AI 一次生成或修改的一组草稿变更。

draft_patch
  草稿中每个 artifact / edge 的新增、修改、删除。

projection.source_revision
  Projection 基于哪个 workspace revision 构建。

api_push.source_workspace_revision
  推送成熟系统时绑定的工作区版本。
```

第一阶段不要求完整 rollback、time travel、patch 级审批。

实现约定：

```text
workspace_revision 是逻辑概念。
MVP 物理字段放在 projects.workspace_revision。
文档中的 workspace.current_revision 可理解为当前 project 的 workspace_revision。
```

但数据结构应为后续 revision compare、snapshot、rollback 留空间。

## 9. AI Draft Batch

旧文档中的 `Change Set` 在当前定位下应简化为：

```text
AI Draft Batch
```

AI Draft Batch 表示：

```text
AI 一次生成或修改的一组草稿变更。
```

流程：

```text
Agent / Skill generates draft
  -> AI Draft Batch created
  -> User Confirm / Edit / Reject
  -> Apply Draft
  -> Workspace Current Data updated
  -> Workspace Revision +1
  -> Projection marked stale / rebuilt
```

AI Draft Batch 的目标不是企业级审计，而是：

- 批量承载 AI 输出。
- 让用户确认 AI 的修改。
- 让工作区数据有版本边界。
- 支撑 API Push revision binding。

## 10. User Confirm / Apply

旧文档中的 `Review` 不作为企业审批流。

当前阶段简化为：

```text
User Confirm
User Edit
User Apply
User Reject
```

用户确认的对象优先是 AI Draft Batch。

第一阶段不做：

```text
企业审批
签核
多人会签
正式发布流程
复杂 patch 级评审
```

成熟 FMEA 系统负责最终审批、签核和正式质量记录。

## 11. Projection / AI Read Model

Projection 是 AI、UI、API Push 优先消费的读模型。

底层 artifact / edge 对 AI 不够友好，因此 AI 不直接拼底层表。

Projection 解决：

- AI 读取友好。
- UI 展示友好。
- API Push 结构稳定。
- freshness 可控。

规则：

```text
Projection 不是事实源。
Projection 可以删除、过期、重建。
AI 在线读取必须使用 fresh projection。
API Push 必须使用 fresh export projection。
任何修改必须回到 AI Draft / Artifact / Edge。
```

fresh 条件：

```text
projection.source_revision == workspace.current_revision
```

## 12. Knowledge Provider

知识沉淀是当前平台的核心能力之一。

平台保留通用 Knowledge Provider Interface，不绑定具体 RAG 实现。

知识库范围：

```text
temporary
project
public
historical_fmea
```

定位：

- temporary：本次 session 临时资料。
- project：当前项目资料。
- public：企业公共规范、方法论、模板。
- historical_fmea：历史 DFMEA/PFMEA/控制计划/历史问题。

Knowledge Provider 只返回证据和参考。

历史 FMEA 是参考知识，不是当前工作区事实。

AI 基于知识生成内容时，仍然进入 AI Draft Batch。

## 13. Validation

Validation 保留为轻量护栏。

它不是人工审批，也不是复杂规则引擎。

第一阶段只做：

```text
Schema Validation
AI Draft Apply Safety Validation
API Push Gate Validation
```

Validation 的职责：

- 防止结构不合法的数据进入工作区。
- 防止 AI Draft 无法安全 apply。
- 防止 stale / invalid export projection 推送成熟系统。
- 给用户确认 AI Draft 时提供 warning / blocking 信息。

第一阶段 severity：

```text
blocking
warning
info
```

只有 blocking 阻止 apply / API Push。

## 14. API Push Adapter

架构上保留 API Push 到成熟 FMEA 系统。

第一条可运行主流程先不实现成熟系统 API，也不要求 API Push validate / execute。
主流程先跑通：

```text
AI Draft Apply
  -> Workspace Current Data
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Fresh working / export projection
```

不以文件导出作为主线。

导出链路：

```text
Workspace Current Data
  -> Projection Service
  -> fresh export projection
  -> API Push Service
  -> API Push Adapter
  -> Mature FMEA System API
  -> api_push_record / push result
```

API Push 规则：

- 必须基于 fresh export projection。
- 必须绑定 workspace revision。
- 必须支持 validate_only / dry_run。
- 正式 execute 必须有 idempotency key。
- 必须记录外部系统返回的 id/status/response。
- 成熟系统不是平台事实源。
- API Push 成功不反向覆盖 workspace current data。

成熟系统的后续修改和回流属于未来 Import / Sync 设计，不进入当前阶段。

## 15. Runtime Sandbox

Agent Native Plugin 可以让 Agent 原生使用质量工程能力，但不能让 Agent 自由访问系统资源。

Runtime Sandbox 与 Workspace Capability Server 是两件事：

```text
Workspace Capability Server
  控制 Agent 能使用哪些工作区能力。

Runtime Sandbox
  控制 Agent Runtime 能访问哪些系统资源。
```

第一阶段原则：

```text
no direct database access
no direct mature system access
no secret exposure
shell disabled by default
filesystem disabled by default
arbitrary network disabled by default
```

如果某个 CLI Agent 需要文件工作区，只给 run 级临时目录：

```text
runtime-workspaces/{run_id}/
```

不挂载：

```text
项目根目录
插件目录
.env
数据库配置
成熟系统凭据
用户 home
系统目录
```

## 16. Frontend / Workspace UI

前端不是传统 FMEA 表格系统，也不是纯聊天 UI。

它应围绕 AI 工作区组织：

```text
Left Panel: Structure Tree
  Working Tree from fresh projection
  Draft Preview Tree from runtime / draft events

Right Panel: AI Conversation
  Agent Session
  Runtime Events
  User Input
  AI Draft Summary
  Apply / Reject
```

前端需要区分：

```text
Working Tree
  已确认工作区事实，来源是 fresh working projection。

Draft Preview Tree
  AI 生成中的候选结构，来源是 runtime events / AI Draft Batch。

Conversation
  右侧对话框，驱动 run 和用户确认。
```

实时预览不是事实源。
任何业务写入仍必须经过 AI Draft Batch / User Confirm / Apply。

UI 可以参考 OpenCodeUI / AionUI 的 agent session、streaming、capability invocation 展示。

但最终 UI 应服务质量工程工作区，而不是做成通用 Agent 终端。

## 17. 架构原则

### 17.1 AI 主导

AI 不是辅助按钮。

Agent 通过 Agent Native Plugin 使用质量工程工作区能力，主导生成、分析、查询、补全和草稿修改。

### 17.2 平台不绑定单一 Agent Runtime

平台核心不绑定 OpenCode、Codex、Claude Code、Qwen Code 或其他单一 Agent。

Agent Native Plugin 是接入层，不是平台核心。

### 17.3 平台不自研完整 Agent Loop

LLM planning、capability selection reasoning、agent loop、runtime retry、agent memory 等交给外部 Agent Runtime。

平台聚焦工作区能力、结构化数据、版本、Projection、Knowledge 和 API Push。

### 17.4 业务能力通过 Domain Plugin 扩展

DFMEA、PFMEA、Control Plan 等业务能力通过 Domain Plugin 扩展。

平台核心不写死业务字段、业务规则和导出结构。

### 17.5 Workspace Capability Server 是 Agent 工作区入口

旧的 Tool Bridge 只作为历史迁移术语。

架构主概念是 Workspace Capability Server。

### 17.6 AI Draft 先于 Apply

AI 生成或修改业务数据时，先形成 AI Draft Batch。

用户确认后才 apply 到 workspace current data。

### 17.7 版本管理必须保留

每次 apply AI Draft 必须形成新的 workspace revision。

Projection、API Push、AI Draft 都必须绑定 revision。

### 17.8 PostgreSQL 是唯一在线事实来源

PostgreSQL 保存 workspace current data 和版本状态。

Projection、runtime message、export record、knowledge snippet 都不是事实源。

### 17.9 Projection 不是事实源

Projection 是可重建读模型。

任何修改必须回到 AI Draft / Artifact / Edge。

### 17.10 成熟 FMEA 系统承接企业管理

本平台不做企业权限、审批、签核和最终质量记录。

这些由成熟 FMEA 系统承担。

## 18. 当前不做

第一阶段不做：

```text
企业权限
审批流
签核
正式发布流程
完整审计系统
复杂规则引擎
完整 rollback
完整 time travel
文件导出主线
远程插件市场
Agent 直连数据库
成熟系统反向同步
```

这些能力可以后续扩展，但不能污染当前 AI 工作区核心。

## 19. 当前架构结论

当前已确认方向：

```text
AI-first Quality Engineering Workspace

Agent Runtime 可替换
Agent Native Plugin 提供原生 Agent 接入
Workspace Capability Server 提供工作区能力
Domain Plugin 提供 DFMEA/PFMEA 等业务能力

AI 生成 AI Draft Batch
用户轻量确认 / 编辑 / 应用
每次应用形成 Workspace Revision
AI/UI 读取 fresh Projection
Knowledge Provider 负责知识检索和沉淀
API Push 后续推送成熟 FMEA 系统

版本管理必须保留
企业级审批、审计和签核简化或后置
成熟 FMEA 系统承接企业管理和最终记录
```

后续详细设计应按本文同步术语和边界。
