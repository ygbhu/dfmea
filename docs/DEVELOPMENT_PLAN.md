# Development Plan

日期：2026-05-01

## 1. 目标

本文是后续实际开发执行计划。

开发目标不是一次性完成完整质量管理系统，而是先跑通 MVP 主闭环：

```text
User Goal
  -> Mock Agent Runtime
  -> Workspace Capability Server
  -> DFMEA Plugin Skill
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Artifact / Edge canonical state
  -> projects.workspace_revision +1
  -> Projection Rebuild
  -> Workspace UI
```

MVP 完成后，再扩展真实 Agent、真实 RAG、PFMEA、Control Plan、API Push 和成熟系统集成。

## 2. 开发基线

后续开发必须以以下决策为准：

```text
技术栈：TypeScript-first modular monolith
后端：NestJS
前端：React + Vite
数据库：PostgreSQL + pgvector
ORM：Drizzle ORM
包管理：pnpm workspace
插件 handler：TypeScript
第一阶段 runtime：Mock Runtime Provider
第一阶段 knowledge：Mock Knowledge Provider
```

关键命名锁定：

```text
plugin_id: dfmea
DFMEA skill capability: dfmea.generate_initial_analysis
平台 capability: workspace.* + snake_case
版本字段物理位置: projects.workspace_revision
AI Draft 状态: pending / applied / rejected / failed
Capability Invocation 状态: accepted / running / completed / failed / cancelled / timeout / denied / invalid_arguments
API Push 文档和数据对象: api_push_job / api_push_record
```

核心约束：

```text
Agent Runtime 不直接访问数据库。
Domain Plugin 不直接保存运行态事实。
AI 输出必须先进入 AI Draft Batch。
Artifact / Edge 是 canonical source of truth。
Projection 是可重建读模型，不是事实源。
API Push 不进入第一条 MVP 主流程。
```

## 3. 推荐目录结构

第一阶段新建主工程，不直接改造 `legacy/dfmea-cli-prototype/` 和 `OpenCodeUI/`。

```text
apps/
  api/
  web/

packages/
  shared/
  plugin-sdk/
  capability-sdk/

plugins/
  dfmea/

infra/
  docker-compose.yml
  postgres/
```

架构、详细设计和阶段计划文档统一放在 `docs/`。

`legacy/dfmea-cli-prototype/` 只作为 DFMEA 业务参考资产。

`OpenCodeUI/` 只作为 Agent UI 参考资产。

## 4. 阶段计划

### Phase 0: 工程骨架

目标：

```text
建立可运行、可测试、可扩展的 monorepo 骨架。
```

任务：

- 初始化 `pnpm-workspace.yaml`。
- 创建 `apps/api` NestJS 应用。
- 创建 `apps/web` React + Vite 应用。
- 创建 `packages/shared`。
- 创建 `packages/plugin-sdk`。
- 创建 `packages/capability-sdk`。
- 创建 `plugins/dfmea` 空插件目录。
- 创建 `infra/docker-compose.yml`，包含 PostgreSQL + pgvector。
- 配置 TypeScript、ESLint、Prettier、Vitest。
- 配置基础脚本：`dev`、`build`、`test`、`lint`、`db:migrate`。

验收：

```text
pnpm install 成功。
pnpm build 成功。
pnpm test 成功。
后端 health check 可访问。
前端 dev server 可启动。
PostgreSQL 容器可启动。
```

### Phase 1: Shared Contracts

目标：

```text
先统一 API、事件、错误、schema 校验和核心状态枚举的基础契约。
```

任务：

- 在 `packages/shared` 定义通用 ID、status、event envelope、error envelope。
- 定义 `ArtifactType`、`EdgeType`、`DraftPatch`、`ProjectionRecord` 基础类型。
- 定义 AI Draft、Capability Invocation、Run、Projection 的状态枚举。
- 引入 JSON Schema + AJV 校验工具。
- 定义 capability invocation envelope。
- 定义 runtime event envelope。
- 定义 API response envelope。

验收：

```text
shared 包可被 api/web/plugin-sdk 引用。
AJV schema 校验工具可测试。
错误返回格式一致。
事件 envelope 一致。
核心状态枚举只有一份来源。
```

### Phase 2: 数据库与基础 Repository

目标：

```text
把 canonical data、draft、projection、runtime event 的基础表建起来。
```

任务：

- 配置 Drizzle。
- 建立 migrations。
- 实现基础 schema：

```text
workspaces
projects
sessions
runs
run_events
capability_invocations
artifacts
artifact_edges
ai_draft_batches
draft_patches
workspace_revision_events
projections
evidence_refs
evidence_links
vector_indexes
domain_plugins
plugin_schemas
plugin_skills
plugin_views
```

- `projects.workspace_revision` 初始化。
- plugin registry 表第一阶段只作为 manifest snapshot 预留；运行时仍以内存 registry 为主。
- 基础 repository 和事务工具。
- 测试 workspace/project/session 创建。
- 测试 artifact / edge 创建。
- 测试 AI Draft apply 时 revision 递增。

验收：

```text
数据库迁移可重复执行。
repository 单元测试通过。
projects.workspace_revision 初始化和递增可测试。
artifact / edge 可写入和读取。
vector_indexes 表可迁移但不要求接入真实 embedding。
plugin registry snapshot 表可迁移但不要求 Phase 2 写入。
```

### Phase 3: Plugin Registry

目标：

```text
服务启动时扫描本地插件，并把插件能力注册到内存 registry。
```

任务：

- 实现 `PluginModule`。
- 扫描 `./plugins/*/plugin.json`。
- 校验 `manifest_version`、`plugin.plugin_id`、schemas、skills、validators、projections、views。
- 校验 handler 文件存在。
- 注册 schema / skill / validator / projection / exporter / view metadata。
- 创建 `plugins/dfmea/plugin.json`。
- 创建 DFMEA schema / handler placeholder。

验收：

```text
dfmea plugin 能被加载。
plugin_id = dfmea。
缺少 handler 时启动失败并返回结构化错误。
Plugin Registry 能查询 dfmea 插件的 generate_initial_analysis skill，并能生成全局 capability id `dfmea.generate_initial_analysis`。
```

### Phase 4: Artifact / Edge + AI Draft Apply

目标：

```text
打通 AI Draft 到 canonical data 的核心写入路径。
```

任务：

- 实现 Artifact Service。
- 实现 Artifact Edge Service。
- 实现 AI Draft Service。
- 支持 AI Draft Batch create / edit patch / reject。
- 支持 Draft Patch：

```text
create_artifact
update_artifact
create_edge
update_edge
logical_delete
```

- 第一阶段使用 `after_payload`。
- 支持 batch 内 `temp_ref` 解析。
- 实现 apply transaction：

```text
check batch.status = pending
check base_workspace_revision
create/update artifacts
create/update edges
projects.workspace_revision +1
workspace_revision_event created
projection marked stale
batch.status = applied
```

验收：

```text
pending draft 不改变 canonical data。
apply 成功后 artifact / edge 写入。
apply 成功后 projects.workspace_revision +1。
base revision 冲突时拒绝 apply。
reject 不修改 canonical data。
```

### Phase 5: Validation Core + Projection Core

目标：

```text
先建立通用 Validation / Projection 基础能力，让后续插件 projection 可以接入。
```

任务：

- 实现 Validation Service。
- 实现 Projection Service。
- 支持 project-level full rebuild。
- 支持 projection handler dispatch。
- 支持 projection status / stale marking / rebuild events。
- 支持 projection freshness：

```text
projection.source_revision == projects.workspace_revision
```

- stale 策略：

```text
AI 查询: rebuild_then_return
UI 查询: stale_with_flag 或触发 rebuild
Export 查询: rebuild_then_return 或失败
```

- 实现一个平台级 test projection handler，用于验证 rebuild 调度链路。

DFMEA projection 不在本阶段实现。

`dfmea.working_tree` 和 `dfmea.export_payload` 在 Phase 7 随 DFMEA Plugin 一起实现。

验收：

```text
apply 后 projection stale。
rebuild 后 source_revision 等于 projects.workspace_revision。
AI 查询不会静默读取 stale projection。
平台级 test projection 可 rebuild。
Projection Service 可以调用插件 projection handler。
```

### Phase 6: Workspace Capability Server

目标：

```text
让 Agent 只能通过受控 capability 使用平台能力。
```

任务：

- 实现 Capability Manifest。
- 实现 Capability Descriptor。
- 实现 Capability Invocation Service。
- 实现 permission / scope / schema 校验。
- 平台 capability：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user
```

- 插件 skill capability：

```text
dfmea.generate_initial_analysis
```

验收：

```text
非法 capability 被拒绝。
非法 arguments 被拒绝。
Agent/mock runtime 只能调用 manifest 内 capability。
Capability Server 能识别并调度插件 skill placeholder。
真实 dfmea.generate_initial_analysis handler 在 Phase 7 验收。
```

### Phase 7: DFMEA Plugin MVP

目标：

```text
按 DFMEA_PLUGIN_DESIGN.md 实现最小可用 DFMEA 业务逻辑。
```

任务：

- 定义 DFMEA artifact schemas：

```text
dfmea.system
dfmea.subsystem
dfmea.component
dfmea.function
dfmea.requirement
dfmea.characteristic
dfmea.failure_mode
dfmea.failure_effect
dfmea.failure_cause
dfmea.action
```

- 定义 DFMEA edge schemas。
- 实现 `generate_initial_analysis` handler。
- 实现 DFMEA AP 简化计算。
- 实现 DFMEA validator。
- 实现 `dfmea.working_tree` projection。
- 实现 `dfmea.export_payload` projection。
- 使用冷却风扇案例作为 fixture。

验收：

```text
输入冷却风扇目标。
生成结构、功能、需求、特性、失效模式、后果、原因、措施。
生成 AI Draft Batch。
apply 后 artifacts / artifact_edges 正确。
working tree 能展示 DFMEA 层级。
export payload 能基于 fresh revision 构建。
```

### Phase 8: Mock Knowledge + Mock Runtime

目标：

```text
不依赖真实 RAG 和真实 Agent，先跑通主流程。
```

任务：

- 实现 Mock Knowledge Provider。
- 支持：

```text
project
historical_fmea
```

- 实现 retrieve / getEvidence。
- 实现 Mock Runtime Provider。
- 支持：

```text
startRun
streamEvents
cancel
capability invocation request
structured result
```

- Mock Runtime 根据用户目标调用 `dfmea.generate_initial_analysis`。
- Mock Runtime 将 skill 结果提交为 AI Draft proposal。
- Mock Runtime 产出 runtime events 和 draft preview events。

验收：

```text
run 可创建。
run_events 可流式读取。
mock runtime 能调用 capability。
mock knowledge 能返回 evidence。
AI Draft proposal 能携带 evidence_refs。
dfmea.generate_initial_analysis 可通过 mock runtime 完整触发。
```

### Phase 9: Platform API + SSE

目标：

```text
让前端可以通过 API 完成完整 MVP 操作。
```

任务：

- REST API：

```text
workspace / project / session
runtime run create / cancel / get
run events stream
projection get / rebuild
ai draft get / edit / apply / reject
ai draft preview get
capability invocation get
```

- SSE：

```text
run events
draft preview events
projection rebuild events
```

- OpenAPI 输出。

验收：

```text
Postman 或 API test 能跑通主流程。
SSE 能持续推送 run / draft preview 事件。
AI Draft 创建后，可以通过 AI Draft Batch / Draft Patch 重建 persisted draft preview。
API 错误格式统一。
```

### Phase 10: Workspace UI MVP

目标：

```text
完成左侧结构树、右侧 AI 对话框、Draft Preview、Apply 后刷新。
```

任务：

- 创建基础布局：

```text
Left Structure Tree
Right AI Conversation
Draft / Apply panel
```

- 实现 Working Tree 读取。
- 实现 Draft Preview Tree。
- 支持从 live draft preview events 渲染候选树。
- 支持刷新后从 AI Draft Batch / Draft Patch 重建 persisted draft preview。
- 实现 runtime event 展示。
- 实现 AI Draft summary / detail。
- 实现 apply / reject。
- Apply 后刷新 fresh Working Tree。

第一阶段不做：

```text
复杂样式
插件自定义 React 组件
复杂 diff 编辑器
成熟系统 API Push UI
企业权限 UI
```

验收：

```text
用户输入目标。
右侧显示 mock agent 执行过程。
左侧实时显示 draft preview。
用户能查看 draft。
用户能 apply。
apply 后左侧显示 confirmed working tree。
```

### Phase 11: E2E 与硬化

目标：

```text
确保 MVP 主流程稳定，可作为后续扩展基线。
```

任务：

- E2E 测试覆盖冷却风扇案例。
- 测试 base revision conflict。
- 测试 projection stale / rebuild。
- 测试 plugin load failure。
- 测试 invalid capability。
- 测试 AI Draft reject。
- 补充错误码和事件最小目录。
- 清理命名不一致和死代码。

验收：

```text
一条命令启动依赖。
一条命令启动后端。
一条命令启动前端。
核心 E2E 测试通过。
冷却风扇 DFMEA 从目标到 working tree 完整跑通。
```

### Phase 12: API Push Mock

该阶段在 MVP 主闭环跑通后再做。

目标：

```text
验证 fresh export projection 到成熟系统 API 的后续集成路径。
```

任务：

- 实现 `api_push_jobs` / `api_push_records`。
- 实现 Mock Mature FMEA API Adapter。
- 支持 validate_only。
- 支持 execute。
- 绑定 source_workspace_revision。

验收：

```text
API Push 只能基于 fresh export projection。
api_push_record 能记录外部响应。
API Push 不修改 canonical data。
```

## 5. MVP 验收场景

统一使用冷却风扇案例。

输入：

```text
目标：生成冷却风扇系统 DFMEA 初稿。
项目资料：风扇用于控制器散热。
历史资料：风扇卡滞、轴承磨损、连接器松脱等历史 FMEA 片段。
```

必须产出：

```text
AI Draft Batch created
Draft Patches created
Draft Preview Tree shown during generation
User applies draft
Artifacts created
Artifact Edges created
projects.workspace_revision +1
dfmea.working_tree projection fresh
dfmea.export_payload projection fresh
UI Working Tree refreshed
```

## 6. 测试策略

每个阶段必须有自动化测试。

最低测试层级：

```text
repository tests
service tests
plugin handler tests
projection tests
capability tests
API integration tests
frontend component tests
E2E happy path
```

核心测试必须覆盖：

```text
plugin registration
manifest validation
capability permission
AI Draft create / edit / apply / reject
temp_ref resolve
base revision conflict
projection freshness
DFMEA AP calculation
DFMEA hierarchy validation
knowledge retrieve
runtime event stream
UI draft preview
```

## 7. 暂不做清单

MVP 阶段不要实现：

```text
完整企业权限
审批 / 签核
完整 rollback / time travel
复杂 DFMEA 全字段
完整 PFMEA
复杂 RAG pipeline
真实成熟系统 API
真实 Agent Runtime 深度适配
插件市场
远程插件安装
多 Agent 协作
文件导出主线
Markdown 业务存储
Agent 直连数据库
```

## 8. 开发执行规则

后续开发按以下规则推进：

```text
一次只推进一个 Phase。
每个 Phase 结束必须满足验收条件。
发现架构冲突时，先同步修改架构文档，再继续代码。
不为了后续扩展提前实现复杂能力。
不绕过 AI Draft 写 canonical data。
不让 Projection 成为事实源。
```

每次开发任务建议输出：

```text
1. 本次目标
2. 涉及文档
3. 涉及模块
4. 实现内容
5. 测试内容
6. 未完成事项
```

## 9. 下一步

下一步从 Phase 0 开始：

```text
创建 pnpm workspace
创建 apps/api
创建 apps/web
创建 packages/shared
创建 packages/plugin-sdk
创建 packages/capability-sdk
创建 plugins/dfmea
创建 infra/docker-compose.yml
```

Phase 0 完成后，进入 Phase 1 Shared Contracts。
