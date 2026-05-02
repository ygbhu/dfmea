# Architecture Refocus

日期：2026-05-01

> 本文是架构转向的背景记录，不作为开发实现的主依据。
> 开发实现应以 `ARCHITECTURE.md`、`DEVELOPMENT_PLAN.md`、各详细设计文档和 `DEVELOPMENT_READINESS_AUDIT.md` 为准。

## 1. 背景

前期架构讨论中，平台逐步形成了：

```text
Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Platform Core Services
  -> Domain Plugins
```

同时也讨论了 AI Draft Batch、User Confirm、Lightweight Events、Validation、API Push、Version 等工程能力。

现在需要重新收窄产品定位。

本项目当前阶段不做企业级 FMEA 管理系统。

企业级权限、审批、签核、正式流程、最终质量记录管理，后续交给成熟 FMEA 系统承接。

本项目核心是：

```text
AI-first Quality Engineering Workspace
```

目标是让 AI 更好地辅助用户生成、分析、查询、补全和沉淀质量失效相关数据，并把结果推送到成熟 FMEA 系统。

## 2. 新产品定位

本项目是：

```text
AI-first Quality Engineering Workspace
```

它不是：

```text
企业级 FMEA 管理系统
审批 / 签核系统
最终质量记录系统
传统 FMEA 表格软件
```

当前核心目标：

```text
AI 生成
AI 分析
AI 查询
AI 补全
AI 校验
企业知识沉淀
API Push 到成熟 FMEA 系统
```

成熟 FMEA 系统负责：

```text
企业权限
审批流程
签核
正式发布
最终质量记录
长期合规管理
```

## 3. 架构主线修正

新的主线应表达为：

```text
Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Platform Core Services
  -> PostgreSQL / Projection / Knowledge / API Push
```

### 3.1 Agent Native Plugin

Agent Native Plugin 面向具体 Agent Runtime。

例如：

```text
OpenCode Plugin
Codex Plugin
Claude Code Plugin
Qwen Code Plugin
```

它让 Agent 以原生方式看到质量工程工作区能力。

Agent 不应被表达成外部调用业务系统 API 的旁路调用者。

### 3.2 Workspace Capability Server

Workspace Capability Server 是平台暴露给 Agent 的工作区能力层。

它可以承载：

```text
resources
action capabilities
prompts
policies
```

它的角色类似 MCP server。

旧文档中的 `Tool Bridge` 仅作为历史迁移术语，不再作为架构主概念或新代码命名。

### 3.3 Platform Core Services

Platform Core Services 管理：

```text
workspace current data
AI draft batch
workspace revision
projection
knowledge
validation
api push
events
```

平台核心不绑定某一个 Agent Runtime。

## 4. 保留的能力

### 4.1 版本管理必须保留

版本管理不是为了企业合规，而是为了 AI 工作区安全。

AI 生成和修改速度快、范围大。

必须能回答：

```text
AI 这次改了什么？
当前工作区是哪一版？
这次推送成熟系统的是哪一版？
能否回到上一个状态？
这条数据来自哪个 AI run？
```

因此必须保留：

```text
workspace_revision
AI Draft Batch
Draft Patch
Projection source revision
API Push revision binding
```

### 4.2 Projection / AI Read Model 保留

AI 不直接读取底层 canonical 表。

AI、UI、API Push 优先读取 projection。

Projection 解决：

```text
AI 读取友好
UI 展示友好
导出结构稳定
freshness 可控
```

### 4.3 Knowledge Provider 保留

知识沉淀是核心能力。

保留：

```text
temporary knowledge
project knowledge
public knowledge
historical FMEA knowledge
```

但 RAG 内部实现仍通过外部 Knowledge Provider 接入。

### 4.4 API Push 保留

当前阶段只规划 API Push 到成熟 FMEA 系统。

不做文件导出主线。

API Push 必须绑定 workspace revision / export projection revision。

### 4.5 Validation 保留为轻量护栏

Validation 只做核心护栏：

```text
Schema Validation
AI Draft Apply Safety Validation
API Push Gate Validation
```

不做复杂业务规则引擎。

## 5. 简化的能力

### 5.1 User Confirm 简化

用户确认不作为企业审批流。

简化为：

```text
User Confirm
User Edit
User Apply
User Reject
```

目标是让用户确认 AI Draft，而不是完成企业签核。

### 5.2 AI Draft Batch 语义简化

旧的 `Change Set` 语义偏工程审计和正式变更管理。

当前阶段建议改为：

```text
AI Draft Batch
```

它表示：

```text
AI 一次生成或修改的一组草稿变更
```

用户确认后：

```text
AI Draft Batch
  -> Apply
  -> Workspace Current Data
  -> Workspace Revision +1
```

### 5.3 Audit 简化

不做完整审计系统。

只保留轻量事件：

```text
run started/completed
draft created/applied
workspace revision changed
projection rebuilt
api push executed
```

用于问题排查和结果解释。

### 5.4 Snapshot 后置

Snapshot 可以作为后续增强。

第一阶段先用：

```text
workspace_revision
AI Draft Batch
Draft Patch
Projection source revision
```

支撑最小版本能力。

完整 rollback / time travel 后续再做。

## 6. 新核心闭环

当前阶段推荐闭环：

```text
User Goal
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

这条链路体现：

- AI 主导生成和修改。
- 用户做轻量确认。
- 平台保留版本。
- 成熟 FMEA 系统承接企业管理。

## 7. 命名修正建议

后续文档建议逐步调整命名。

```text
Tool Bridge
  -> Workspace Capability Server / Capability Invocation

Change Set
  -> AI Draft Batch

Change Set Patch
  -> Draft Patch

Review
  -> User Confirm / Apply

Project Revision
  -> Workspace Revision

Export
  -> API Push
```

说明：

旧术语可以短期保留，但新文档和新代码应优先采用新术语。

## 8. 第一阶段保留 / 简化清单

### 8.1 保留

```text
Agent Runtime Provider 可替换
Agent Native Plugin
Workspace Capability Server
Domain Plugin
Plugin Skill
PostgreSQL canonical current data
AI Draft Batch
Workspace Revision
Projection
Knowledge Provider
Validation core guardrails
API Push Adapter
Runtime Sandbox
```

### 8.2 简化

```text
旧 Review -> User Confirm / Apply
旧 Change Set -> AI Draft Batch
Audit -> Lightweight Events
Snapshot -> 后续增强
Validation -> 核心护栏
Export -> 只做 API Push
```

### 8.3 不做

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

## 9. 对已有文档的影响

本次定位已同步到以下主文档：

```text
ARCHITECTURE.md
AI_DRAFT_VERSION_DESIGN.md
DATA_MODEL_DESIGN.md
DOMAIN_PLUGIN_SDK_DESIGN.md
EXECUTION_CONTEXT_DESIGN.md
API_PUSH_ADAPTER_DESIGN.md
KNOWLEDGE_PROVIDER_INTERFACE.md
MVP_PLAN.md
PLATFORM_API_DESIGN.md
PLUGIN_MANIFEST_DESIGN.md
PLUGIN_REGISTRATION_DESIGN.md
PLUGIN_SKILL_DESIGN.md
PROJECTION_DESIGN.md
RUNTIME_PROVIDER_DESIGN.md
RUNTIME_SANDBOX_DESIGN.md
SERVICE_BOUNDARY_DESIGN.md
VALIDATION_DESIGN.md
WORKSPACE_CAPABILITY_SERVER_DESIGN.md
```

## 10. 当前结论

当前方向是：

```text
AI-first Quality Engineering Workspace
```

它拥抱未来 AI 的方式不是在传统 FMEA 系统上加聊天窗口，而是：

```text
让 Agent 原生使用质量工程工作区能力，
让 AI 主导生成、查询、分析和沉淀，
让平台保留轻量版本和结构化事实，
让成熟 FMEA 系统承接企业管理和最终记录。
```

版本管理必须保留。

企业级审批、审计和签核可以简化或后置。
