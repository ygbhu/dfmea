# Development Entry Plan

日期：2026-05-01

## 1. 目标

本文定义如何从当前架构文档进入开发。

实际编码执行顺序以 `DEVELOPMENT_PLAN.md` 为准。

开发目标不是一次性实现完整平台，而是先跑通一个最小 vertical slice：

```text
DFMEA 初稿生成
  -> AI Draft Batch
  -> User Confirm / Apply
  -> Projection
```

只要这条链路跑通，后续 PFMEA、Control Plan、历史 FMEA 知识库、API Push、真实成熟系统 API 都可以按插件和 adapter 扩展。

## 2. 第一阶段开发原则

### 2.1 模块化单体优先

第一阶段采用模块化单体。

不要先拆微服务。

模块边界按 `SERVICE_BOUNDARY_DESIGN.md` 实现：

```text
Runtime Service
Workspace Capability Service
Plugin Service
Artifact Service
AI Draft Service
Workspace Version Service
Projection Service
Knowledge Service
Validation Service
Event Service
```

API Push Service 在第一条主流程后再实现。

### 2.2 先 mock 外部依赖

第一阶段 mock：

```text
Agent Runtime Provider
Knowledge Provider
Mature FMEA API
```

原因：

```text
先验证平台核心闭环。
避免被具体 Agent、RAG、成熟系统 API 拖慢。
```

### 2.3 先通用，后业务

先实现平台通用能力：

```text
workspace / project / session
plugin registry
capability invocation
artifact / edge
ai draft
projection
validation
```

再实现最小 DFMEA plugin。

### 2.4 AI 不直接写 current data

所有 AI 输出必须走：

```text
AI Draft Batch
  -> User Confirm / Apply
  -> Artifact / Edge
```

这是第一阶段不可破坏的核心约束。

## 3. 早期阶段拆分

本节是早期从架构文档进入开发时的阶段拆分，仅保留为背景说明。

实际编码执行顺序、阶段编号和验收标准以 `DEVELOPMENT_PLAN.md` 为准。

### Phase 0: 工程决策

已完成：

```text
TECH_STACK_DECISION.md
```

锁定：

```text
backend language / framework
database migration tool
test framework
plugin handler language
runtime provider transport
frontend integration strategy
```

后续代码实现必须以该文档为准。

### Phase 1: 数据库与基础服务

实现：

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
```

验收：

```text
数据库迁移可重复执行。
基础 repository 测试通过。
projects.workspace_revision 初始化和递增可测试。
```

### Phase 2: Plugin Registry

实现：

```text
扫描 ./plugins
读取 plugin.json
校验 manifest
注册 schemas / skills / validators / projections / exporters / views
```

验收：

```text
最小 dfmea plugin 能被加载。
缺 schema / handler 时加载失败并返回结构化错误。
Plugin Registry 能查询 skill / projection / exporter。
```

### Phase 3: Workspace Capability Server

实现：

```text
Capability Manifest
Capability Descriptor
Capability Invocation Envelope
Permission check
Input / output schema validation
Platform capability handler
Plugin skill handler dispatch
```

第一阶段开放：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user
```

验收：

```text
Agent/mock runtime 只能调用 manifest 内 capability。
非法 scope 被拒绝。
非法 arguments 被拒绝。
plugin skill 能通过 capability invocation 被调用。
```

### Phase 4: AI Draft / Version

实现：

```text
AI Draft Batch create
Draft Patch create / edit / reject
Apply transaction
Base revision check
Workspace revision increment
Projection dirty marking
Workspace revision event
```

第一阶段 patch 策略：

```text
after_payload required
before_payload optional
payload_patch optional
```

验收：

```text
AI Draft pending 后 current data 不变。
Apply 成功后 artifact / edge 更新。
Apply 成功后 projects.workspace_revision +1。
base revision 冲突时拒绝 apply。
Reject 不修改 current data。
```

### Phase 5: Projection

实现：

```text
working projection
export projection
project-level full rebuild
source_revision
freshness check
```

验收：

```text
Apply 后 projection stale。
AI/UI 读取 stale projection 被拒绝或触发 rebuild。
fresh projection source_revision == projects.workspace_revision。
```

### Phase 6: Minimal DFMEA Plugin

按 `DFMEA_PLUGIN_DESIGN.md` 实现第一阶段 DFMEA 插件。

实现最小插件，不追求完整 AIAG-VDA 字段体系，但必须具备可运行的 DFMEA 业务闭环。

最小能力：

```text
schemas/artifacts/dfmea.*.schema.json
schemas/edges/dfmea.*.schema.json
skill: generate_initial_analysis
projection: dfmea.working_tree
projection: dfmea.export_payload
validator: basic_schema_check
```

Skill 输出：

```text
ai_draft_proposal
```

验收：

```text
输入一个简单系统目标。
mock Agent 调用 dfmea.generate_initial_analysis。
生成 AI Draft Batch。
用户 apply 后生成 artifacts / artifact_edges。
working projection 可查询。
export projection 可查询。
冷却风扇 MVP 样例可跑通。
```

### Phase 7: Knowledge Provider Mock

实现：

```text
retrieve
getEvidence
```

支持：

```text
project
historical_fmea
```

验收：

```text
Skill 能检索 evidence。
AI Draft proposal 能带 evidence_refs。
evidence_links 能关联到 draft / artifact。
```

### Phase 8: Runtime Provider Mock

先不接真实 Agent。

实现 mock runtime：

```text
startRun
streamEvents
cancel
structured result
capability invocation request
```

验收：

```text
UI / API 能看到 run events。
mock runtime 能请求 capability。
mock runtime 能产出 ai_draft_proposal。
```

### Phase 9: UI 最小闭环

最小 UI 只做：

```text
Left Structure Tree Panel
Right Conversation Panel
Runtime Events
Live Draft Preview Tree
Working Projection Tree
AI Draft Batch summary
AI Draft detail
edit / apply / reject
```

验收：

```text
用户能从一个目标生成 DFMEA 草稿。
AI 生成过程中左侧结构树能显示候选变化。
用户能在右侧看到 Agent run 状态和消息。
用户能查看 AI Draft 草稿变更。
用户能应用草稿。
Apply 后左侧结构树刷新为 fresh Working Tree。
```

### Phase 10: API Push Mock

该阶段后置，不阻塞第一条主流程。

后续实现 mock mature FMEA adapter：

```text
validate(payload, context)
push(payload, context)
```

验收：

```text
validate_only 能校验 fresh export projection。
execute 能生成 api_push_record。
API Push 绑定 source_workspace_revision。
API Push 不修改 current data。
```

## 4. 第一阶段验收用例

使用一个最小冷却风扇系统案例。

输入：

```text
目标：生成冷却风扇系统 DFMEA 初稿。
项目资料：风扇用于控制器散热。
历史资料：风扇卡滞、轴承磨损、连接器松脱等历史 FMEA 片段。
```

期望输出：

```text
AI Draft Batch created
Draft Patches created
User applies draft
Artifacts created
Artifact Edges created
Workspace Revision +1
Working Projection fresh
Export Projection fresh
Draft Preview Tree shown during generation
```

## 5. 不要第一阶段实现的内容

不要在第一阶段实现：

```text
完整 DFMEA 字段体系
完整 PFMEA
复杂风险评分规则
企业权限
审批流
签核
完整 rollback
完整 RAG pipeline
多 Agent 协作
真实成熟系统 API 适配
API Push mock
文件导出
插件市场
```

这些会拖慢最小闭环验证。

## 6. 开发完成定义

第一阶段完成标准：

```text
一个开发者可以启动后端。
一个开发者可以加载 dfmea plugin。
一个开发者可以启动 mock runtime run。
mock runtime 能调用 capability。
dfmea skill 能生成 AI Draft Batch。
用户能 apply draft。
projection 能 rebuild。
UI 能展示左侧结构树和右侧对话框。
核心路径有自动化测试。
```

核心路径测试至少覆盖：

```text
plugin registration
capability permission
ai draft create / edit / apply / reject
base revision conflict
projection freshness
knowledge retrieve
runtime event stream
```

## 7. 下一步

技术栈已经由以下文档锁定：

```text
TECH_STACK_DECISION.md
```

下一步应按 `DEVELOPMENT_PLAN.md` 进入：

```text
Phase 0: 工程骨架
```
