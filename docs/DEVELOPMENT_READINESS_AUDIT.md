# Development Readiness Audit

日期：2026-05-01

## 1. 审核结论

当前文档已经可以作为开发启动依据，但还不是“无脑照着写代码”的完整规格。

可以直接进入开发的部分：

```text
架构定位
核心数据流
服务边界
插件模型
AI Draft / Version
Projection
Workspace Capability Server
Runtime Provider
Runtime Sandbox
Validation
API Push interface / 后续扩展
Knowledge Provider Interface
```

不应立即展开的部分：

```text
完整企业权限
审批 / 签核
完整 rollback / time travel
复杂业务规则引擎
完整 RAG 实现
插件市场
多 Agent 并发协作
成熟系统反向同步
```

总体判断：

```text
架构方向成立。
文档已经足够支撑 MVP vertical slice 开发。
但开发前必须锁定少量工程决策，并严格按 MVP 顺序实现。
```

## 2. 主依据文档

开发实现优先级：

```text
1. ARCHITECTURE.md
2. DEVELOPMENT_PLAN.md
3. DEVELOPMENT_ENTRY_PLAN.md
4. TECH_STACK_DECISION.md
5. MVP_PLAN.md
6. DATA_MODEL_DESIGN.md
7. SERVICE_BOUNDARY_DESIGN.md
8. PLATFORM_API_DESIGN.md
9. WORKSPACE_CAPABILITY_SERVER_DESIGN.md
10. RUNTIME_PROVIDER_DESIGN.md
11. AI_DRAFT_VERSION_DESIGN.md
12. DOMAIN_PLUGIN_SDK_DESIGN.md
13. PLUGIN_MANIFEST_DESIGN.md
14. PLUGIN_REGISTRATION_DESIGN.md
15. PLUGIN_SKILL_DESIGN.md
16. PROJECTION_DESIGN.md
17. VALIDATION_DESIGN.md
18. KNOWLEDGE_PROVIDER_INTERFACE.md
19. API_PUSH_ADAPTER_DESIGN.md
20. RUNTIME_SANDBOX_DESIGN.md
21. WORKSPACE_UI_DESIGN.md
22. DFMEA_PLUGIN_DESIGN.md
```

背景文档：

```text
ARCHITECTURE_REFOCUS.md
```

该文档只用于理解为什么架构从旧方向转到当前方向，不作为实现命名和接口设计的主依据。

## 3. 当前项目目录评估

当前项目包含：

```text
legacy/dfmea-cli-prototype/
OpenCodeUI/
docs/*.md architecture and design documents
```

### 3.1 legacy/dfmea-cli-prototype/

`legacy/dfmea-cli-prototype/` 更像早期 DFMEA CLI / skill 原型。

可以复用：

```text
DFMEA 业务样例
历史测试用例
真实冷却风扇案例
部分 schema / projection 思路
```

不应直接作为新架构主实现：

```text
Markdown / 文件型存储思路
CLI-first 产品形态
旧版本管理方案
旧 export_markdown 路径
```

结论：

```text
legacy/dfmea-cli-prototype/ 是业务参考资产，不是新平台主工程。
新平台 DFMEA 插件业务实现以 DFMEA_PLUGIN_DESIGN.md 为准。
```

### 3.2 OpenCodeUI/

`OpenCodeUI/` 是可参考的独立前端项目。

可以复用或借鉴：

```text
Agent session UI
streaming event 展示
message store
MCP / skill / permission panel
diff / changes panel
terminal / pty / session hooks
```

不应直接决定：

```text
平台数据模型
业务插件模型
AI Draft apply 语义
成熟 FMEA API Push 语义
```

结论：

```text
OpenCodeUI/ 是 Agent UI 参考，不是质量工程业务前端的完整实现。
```

## 4. 已经足够清晰的部分

### 4.1 产品边界

当前产品是：

```text
AI-first Quality Engineering Workspace
```

不是：

```text
企业级 FMEA 管理系统
传统 FMEA 软件
审批 / 签核系统
最终质量记录系统
```

这部分已经清晰，可以开发。

### 4.2 主数据流

主数据流已经清晰：

```text
User Goal
  -> Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Domain Plugin Skill
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Artifact / Edge
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Knowledge Query
```

这条链路可以作为 MVP 验收闭环。

API Push / 成熟系统 API 保留为后续扩展，不阻塞第一条主流程。

### 4.3 存储方向

当前存储方向已经稳定：

```text
PostgreSQL as online source of truth
artifacts / artifact_edges as canonical model
JSONB payload with plugin schema validation
projections as derived read model
pgvector optional for vector index
```

不再使用 Markdown 作为业务存储。

### 4.4 插件方向

插件方向已经稳定：

```text
DFMEA / PFMEA / Control Plan as Domain Plugin
Plugin declares schema / skill / validator / projection / exporter / view metadata
Skill must have code handler
Prompt is resource, not executor
Plugin does not own runtime state
```

这部分可以开发。

### 4.5 AI Draft / Version

AI 批量生成和版本边界已经清晰：

```text
AI Draft Batch
Draft Patch
User Confirm / Edit / Apply / Reject
Workspace Revision
Projection source_revision
API Push source_workspace_revision
```

这部分必须作为第一阶段核心实现。

## 5. 仍需收敛但不阻塞 MVP 的部分

以下问题可以在开发过程中按默认策略实现，不必继续无限讨论。

### 5.1 workspace 与 project 命名

开发默认策略：

```text
workspace 表示 AI 工作区。
project 表示 workspace 下的具体分析项目。
当前版本字段物理放在 project，语义统一为 workspace current data revision。
```

第一阶段建议：

```text
保留 workspace_id + project_id。
版本字段物理放在 projects.workspace_revision。
文档和代码注释说明它代表 workspace current data revision。
```

### 5.2 Draft Patch 表达方式

开发默认策略：

```text
第一阶段使用 after_payload。
before_payload 可选记录。
payload_patch 暂不强制实现。
```

原因：

```text
AI 生成结构化结果时，after_payload 最直接。
JSON Patch / Merge Patch 可后续增强。
```

### 5.3 Projection rebuild

开发默认策略：

```text
第一阶段 project-level full rebuild。
apply 成功后 projection_dirty = true。
AI / UI 读取时必须 fresh。
```

不做：

```text
scope-level dirty
dependency graph
incremental rebuild
```

### 5.4 Plugin registration

开发默认策略：

```text
服务启动时扫描 ./plugins。
读取 plugin.json。
校验 manifest / schema / handler path。
注册到内存 registry。
manifest snapshot 入库后置。
```

### 5.5 Knowledge Provider

开发默认策略：

```text
先实现接口和 mock provider。
支持 project / historical_fmea 两类。
retrieve / getEvidence 必须有。
完整 RAG 后置。
```

### 5.6 API Push

开发默认策略：

```text
第一条主流程先不实现。
先保证 export projection 能基于 fresh workspace revision 构建。
后续再实现 mock mature-system adapter。
execute 由 UI 或平台 command 触发，不暴露给 Agent。
```

## 6. 当前开发阻塞项

真正会阻塞开发的只有以下几项。

### 6.1 技术栈已锁定

技术栈已在以下文档中锁定：

```text
TECH_STACK_DECISION.md
```

第一阶段采用：

```text
TypeScript-first modular monolith
NestJS
PostgreSQL + pgvector
Drizzle ORM
React + Vite
TypeScript plugin handlers
Mock Runtime / Mock Knowledge first
```

该项不再阻塞 MVP 开发准备。

### 6.2 UI 详细设计未完成

UI 数据流设计已由以下文档补齐：

```text
WORKSPACE_UI_DESIGN.md
```

当前已明确：

```text
左侧结构树
右侧 AI 对话框
Working Tree
Draft Preview Tree
Runtime / Draft Preview Events
Apply 后刷新 fresh Working Tree
```

仍未设计具体视觉样式和组件库细节。

建议后续单独输出：

```text
WORKSPACE_UI_STYLE_GUIDE.md
AI_DRAFT_CONFIRM_UI_DESIGN.md
```

### 6.3 Historical FMEA Knowledge 尚未细化

历史成熟 FMEA 数据后期非常重要，但当前只有 Knowledge Provider 的通用接口。

不阻塞第一阶段 mock，但会影响 AI 质量。

建议后续单独输出：

```text
HISTORICAL_FMEA_KNOWLEDGE_DESIGN.md
```

## 7. 文档一致性审核结果

已经确认：

```text
Markdown 不再作为业务存储。
Tool Bridge 不再作为主架构概念。
Change Set / Review 不再作为主动设计术语。
workspace.ai_draft.apply 不默认暴露给 Agent。
workspace.api_push.execute 不默认暴露给 Agent。
API Push 是后续成熟系统输出主线，但不进入第一条主流程。
PostgreSQL 是在线事实源。
Projection 是派生读模型。
```

旧术语只允许出现在：

```text
历史映射
迁移说明
背景说明
```

不允许出现在新代码命名、API 命名、数据库表命名中。

## 8. 开发准入结论

当前状态：

```text
可以进入 MVP vertical slice 开发准备。
不建议直接进入全量系统开发。
```

进入开发前最低需要：

```text
1. 按 DEVELOPMENT_PLAN.md 从 Phase 0 开始创建工程骨架。
2. 按 DEVELOPMENT_PLAN.md 推进 Phase 0 到 Phase 11 跑通主流程。
3. 从最小 DFMEA Plugin vertical slice 开始。
4. 先用 mock Agent Runtime / mock Knowledge Provider。
```

核心原则：

```text
先跑通闭环，再扩业务深度。
先验证架构，再完善 DFMEA/PFMEA 细节。
先做 AI Draft / Projection / Capability，再做复杂 UI 和 RAG。
```
