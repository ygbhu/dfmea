# Tech Stack Decision

日期：2026-05-01

状态：Accepted for MVP

## 1. 决策目标

本文锁定第一阶段 MVP 的技术栈。

目标不是选择最“先进”的组合，而是满足当前项目的核心架构诉求：

```text
AI-first Quality Engineering Workspace
Domain Plugin 可插拔
Agent Runtime 可替换
PostgreSQL 在线事实源
AI Draft / Projection / API Push 可落地
后续可接入真实 RAG 和成熟 FMEA 系统
```

第一阶段优先级：

```text
1. 快速跑通 vertical slice。
2. 数据模型和服务边界清晰。
3. 类型和 schema 可维护。
4. Agent / Plugin / API / UI 之间容易集成。
5. 不被某一个 Agent Runtime 或 UI 项目绑死。
```

## 2. 总体选择

第一阶段采用：

```text
TypeScript-first modular monolith
PostgreSQL + pgvector
React + Vite frontend
TypeScript plugin handlers
Mock Runtime / Mock Knowledge first
API Push deferred until main flow is running
```

核心判断：

```text
平台主要是结构化数据、API、插件、Agent capability 和 UI 工作区。
TypeScript 能统一后端、前端、插件 SDK、Capability Schema、Agent adapter。
Python 作为后续可选 plugin sidecar / RAG adapter，而不是第一阶段主平台语言。
```

## 3. Repository 结构

建议新建主工程结构：

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

docs/
  architecture/
```

架构和详细设计文档统一放在：

```text
docs/
```

## 4. Runtime

### 4.1 Node.js

选择：

```text
Node.js 24 LTS
```

原因：

- 2026 年新项目应使用当前 LTS。
- 前后端、插件 SDK、Agent adapter 统一在 TypeScript 生态。
- 与 React / Vite / NestJS / Drizzle / MCP TypeScript SDK 兼容。

开发约束：

```text
engines.node >= 24
```

### 4.2 Package Manager

选择：

```text
pnpm workspace
```

原因：

- 适合 monorepo。
- 可以管理 `apps/*`、`packages/*`、`plugins/*`。
- 避免重复依赖。

注意：

```text
OpenCodeUI/ 当前使用 npm package-lock，暂时保持独立。
新平台主工程使用 pnpm。
```

## 5. Backend

### 5.1 Language

选择：

```text
TypeScript
```

原因：

- 与前端共享类型和 schema。
- 与 Agent Native Plugin / MCP / capability adapter 更贴近。
- 插件 handler 第一阶段也用 TypeScript，减少跨语言边界。
- 当前平台核心不是模型训练或 RAG pipeline，不需要 Python 作为主语言。

### 5.2 Framework

选择：

```text
NestJS
```

第一阶段使用：

```text
NestJS default HTTP adapter
REST + SSE
OpenAPI
```

原因：

- 模块化结构适合当前 Service Boundary。
- Controller / Service / Provider 模型清晰。
- DI 对 Runtime Provider、Knowledge Provider、API Push Adapter、Plugin Registry 这类可替换组件有价值。
- OpenAPI 支持成熟。
- SSE / REST 足够覆盖第一阶段。

第一阶段不使用：

```text
GraphQL
WebSocket
Microservices transport
Nest CQRS
```

这些会增加复杂度，不利于 MVP。

### 5.3 Backend Module Mapping

`apps/api` 内建议模块：

```text
src/modules/scope
src/modules/runtime
src/modules/capability
src/modules/plugin
src/modules/artifact
src/modules/ai-draft
src/modules/version
src/modules/projection
src/modules/knowledge
src/modules/validation
src/modules/api-push
src/modules/events
```

每个模块先保持模块内分层：

```text
controller
service
repository
types
```

不要第一阶段拆成微服务。

## 6. Database

### 6.1 Database

选择：

```text
PostgreSQL 18
pgvector
```

最低兼容目标：

```text
PostgreSQL >= 16
```

MVP 开发默认：

```text
PostgreSQL 18 + pgvector Docker image
```

原因：

- PostgreSQL 是在线事实源。
- JSONB 适合 plugin payload。
- 关系表适合 artifacts / edges / draft patches / revision / events。
- pgvector 满足后续 projection / evidence 的向量检索需要。
- 不需要额外引入专用向量数据库。

### 6.2 ORM / Query Layer

选择：

```text
Drizzle ORM + node-postgres
```

原因：

- TypeScript-first。
- schema 接近 SQL，便于控制表、索引、JSONB、事务。
- 适合模块化 repository。
- 比 Prisma 更适合保留 PostgreSQL 特性和 raw SQL 控制。

约束：

```text
复杂查询、pgvector、特殊 index 可以使用 raw SQL。
业务写入必须通过 repository / service，不允许在 handler 中散落 SQL。
```

### 6.3 Migration

选择：

```text
drizzle-kit migrations
```

规则：

- 所有表结构进入 migration。
- pgvector extension、复杂 index 可以写手工 SQL migration。
- migration 必须可重复在空库执行。
- 不使用 `drizzle push` 作为正式 schema 管理方式。

### 6.4 Transaction Policy

强事务路径：

```text
AI Draft Apply
Workspace Revision increment
Draft status update
Artifact / Edge write
Projection dirty marking
Workspace revision event
```

异步或后置路径：

```text
Projection rebuild
Vector index rebuild
API Push execution
Runtime event streaming
```

## 7. Schema / Validation

### 7.1 Canonical Schema Format

选择：

```text
JSON Schema
```

适用：

```text
Plugin manifest
Artifact payload
Edge payload
Skill input / output
Capability input / output
Projection payload
Export payload
```

原因：

- 插件天然需要语言无关 schema。
- 后续 Python / external plugin 也能复用。
- 可以与 OpenAPI、AJV、schema registry 组合。

### 7.2 Runtime Validator

选择：

```text
AJV
ajv-formats
```

规则：

- Platform 负责执行 schema validation。
- Plugin 只声明 schema 和 handler。
- Skill output 必须通过 schema validation 后才进入 AI Draft。

### 7.3 Type Sharing

选择：

```text
packages/shared
```

职责：

```text
shared enums
shared DTO types
common error types
capability envelope types
event envelope types
```

注意：

```text
JSON Schema 是插件 payload 的权威契约。
TypeScript 类型是开发体验，不替代 JSON Schema 校验。
```

## 8. API

### 8.1 Public API

选择：

```text
REST
OpenAPI
```

用途：

```text
Frontend / Workspace UI
external integration in future
developer testing
```

第一阶段 API：

```text
workspace / project / session
run
ai draft
projection
knowledge
api push
events
```

### 8.2 Event Stream

选择：

```text
SSE
```

原因：

- Agent run event、AI Draft event、Projection rebuild event 都是服务端到前端的事件流。
- 第一阶段不需要 WebSocket 双向协同。

### 8.3 Workspace Capability API

第一阶段内部实现：

```text
in-process Capability Invocation
```

对外预留：

```text
HTTP endpoint
MCP server adapter
stdio adapter
```

原则：

```text
内部 Capability Invocation Envelope 先稳定。
具体传输方式后续可替换。
```

## 9. Agent Runtime Provider

### 9.1 第一阶段

选择：

```text
mock_runtime_provider
```

能力：

```text
startRun
streamEvents
cancel
request capability invocation
return ai_draft_proposal
```

原因：

```text
先验证平台闭环，不被真实 Agent CLI 行为拖慢。
```

### 9.2 第二阶段

优先接入：

```text
OpenCode / Codex / Claude Code / Qwen Code 中的一个 CLI Agent
```

接入方式优先级：

```text
1. Agent Native Plugin
2. MCP adapter
3. HTTP / stdio adapter
4. text protocol fallback
```

平台核心不绑定任何一个 Agent。

## 10. Plugin System

### 10.1 Plugin Language

第一阶段选择：

```text
TypeScript plugin handler
```

原因：

- 与平台同语言。
- handler 可以直接使用 plugin-sdk。
- 避免第一阶段引入多语言进程沙箱。

后续可扩展：

```text
Python plugin sidecar
external HTTP plugin
WASM plugin
```

### 10.2 Plugin Location

选择：

```text
plugins/
  dfmea/
    plugin.json
    schemas/
    skills/
    validators/
    projections/
    exporters/
    prompts/
```

### 10.3 Registration

第一阶段：

```text
服务启动时扫描 plugins/
注册到内存 registry
校验 schema / handler path
```

暂不实现：

```text
热更新
远程安装
插件市场
多版本并行
```

## 11. Knowledge Provider

第一阶段选择：

```text
mock_knowledge_provider
```

支持：

```text
project
historical_fmea
retrieve
getEvidence
```

后续真实接入：

```text
Dify
FastGPT
LlamaIndex
LangChain
Haystack
custom RAG
```

约束：

```text
Knowledge Provider 只返回 evidence / reference。
不能直接写 Artifact。
不能直接创建 AI Draft。
```

## 12. API Push Adapter

主流程阶段选择：

```text
defer API Push Adapter
```

第一条可运行主流程先停在：

```text
AI Draft Apply
Projection Rebuild
Fresh working / export projection
```

后续再实现：

```text
mock_mature_fmea_adapter
```

支持：

```text
validate_only
execute
idempotency_key
api_push_record
```

约束：

```text
execute 由 UI / Platform Command 触发。
不暴露给 Agent 默认 capability。
API Push 成功不反向修改 current data。
```

## 13. Runtime Sandbox

第一阶段选择：

```text
policy-first sandbox
per-run temp directory optional
```

默认：

```text
database_access = false
filesystem_write = false
shell_command = false
network_access = false
secret_access = false
```

如果 mock / CLI runtime 需要工作目录：

```text
.runtime-sandbox/{run_id}/
```

Sandbox 文件不是事实源。

## 14. Frontend

### 14.1 Frontend Framework

选择：

```text
React
Vite
TypeScript
Tailwind CSS
```

原因：

- 当前 `OpenCodeUI/` 已是 React + Vite + TypeScript 生态。
- AI workspace 需要复杂交互，React 生态更合适。
- Vite 对 MVP 迭代快。

### 14.2 UI Strategy

第一阶段建议：

```text
新建 apps/web。
参考 OpenCodeUI 的 session / streaming / diff / permission / skill panel 交互。
不直接复制 OpenCodeUI 代码，除非明确接受 GPL-3.0-only 约束。
```

原因：

```text
OpenCodeUI 是通用 Agent UI。
本项目需要质量工程 Workspace UI。
直接改 OpenCodeUI 容易被其产品结构和许可证约束绑住。
```

### 14.3 MVP UI 页面

第一阶段只做：

```text
Workspace / Project selector
Agent Session panel
Runtime Events panel
Left Structure Tree Panel
Working Projection Tree
Live Draft Preview Tree
AI Draft Batch list
AI Draft detail / edit / apply / reject
Evidence panel
API Push panel 后置
```

不做：

```text
完整企业后台
复杂权限配置
可视化规则引擎
插件市场 UI
```

## 15. Testing

### 15.1 Test Framework

选择：

```text
Vitest
Testing Library
Playwright
```

用途：

```text
Vitest: backend unit / service / repository tests
Testing Library: frontend component tests
Playwright: MVP critical path e2e
```

### 15.2 Database Tests

第一阶段：

```text
Docker Compose PostgreSQL for integration tests
```

后续可选：

```text
Testcontainers
```

### 15.3 必测路径

```text
plugin registration
capability invocation permission
ai draft create / edit / apply / reject
base revision conflict
projection freshness
knowledge retrieve
runtime event stream
```

## 16. DevOps / Local Development

第一阶段提供：

```text
docker-compose.yml
PostgreSQL + pgvector
apps/api dev command
apps/web dev command
seed script
test script
```

建议命令：

```text
pnpm install
pnpm dev
pnpm test
pnpm lint
pnpm typecheck
pnpm db:migrate
pnpm db:seed
```

## 17. Current Existing Projects Policy

### 17.1 legacy/dfmea-cli-prototype/

定位：

```text
business reference / legacy prototype
```

可复用：

```text
真实 DFMEA 样例
测试场景
业务术语
部分 projection 思路
```

不直接复用：

```text
CLI-first architecture
Markdown storage
export_markdown path
旧版本方案
```

### 17.2 OpenCodeUI/

定位：

```text
Agent UI reference
```

可参考：

```text
session UI
streaming events
diff / changes panel
permission panel
skill panel
MCP panel
terminal / pty handling
```

注意：

```text
OpenCodeUI license is GPL-3.0-only.
如果直接复制或改造代码，需要接受对应许可证约束。
MVP 默认不直接复制 OpenCodeUI 代码。
```

## 18. Explicit Non-Choices

第一阶段不选择：

```text
Python as main backend
FastAPI as main platform API
Prisma as primary ORM
GraphQL
WebSocket-first event channel
Kafka / RabbitMQ
microservices
LangGraph as core runtime
full RAG framework inside platform
direct OpenCodeUI fork as product UI
Markdown business storage
SQLite
```

原因：

```text
这些不是不好，而是会分散 MVP 的核心验证。
第一阶段只验证 AI 工作区闭环。
```

## 19. Risks

### 19.1 NestJS 可能偏重

风险：

```text
NestJS 对很小项目偏重。
```

接受原因：

```text
当前系统模块多，Provider / Adapter / Plugin / Capability 边界复杂。
NestJS 的模块化和 DI 能降低后续失控风险。
```

### 19.2 TypeScript Plugin Handler 后续可能不够

风险：

```text
部分 AI / RAG / 文档处理生态在 Python 更成熟。
```

应对：

```text
第一阶段 TypeScript handler。
后续通过 Python sidecar / HTTP plugin / external Knowledge Provider 接入。
```

### 19.3 Drizzle 对复杂 migration 仍需手工 SQL

风险：

```text
pgvector、复杂 index、JSONB GIN index 需要 raw SQL。
```

应对：

```text
允许手写 migration SQL。
不要把 ORM 当作数据库能力边界。
```

### 19.4 新建 UI 会慢于直接改 OpenCodeUI

风险：

```text
新建 apps/web 初期速度慢。
```

接受原因：

```text
质量工程 UI 与通用 Agent UI 的信息架构不同。
直接改 OpenCodeUI 会带来产品结构和许可证约束。
```

## 20. Development Start Checklist

进入代码前必须完成：

```text
1. 创建 pnpm workspace。
2. 创建 apps/api NestJS 项目。
3. 创建 apps/web React + Vite 项目。
4. 创建 packages/shared。
5. 创建 packages/plugin-sdk。
6. 创建 plugins/dfmea 最小 manifest。
7. 创建 infra/docker-compose.yml。
8. 创建 PostgreSQL migration。
9. 创建 mock runtime / mock knowledge provider。
```

第一条真实业务验收：

```text
冷却风扇系统 DFMEA 初稿
  -> mock runtime run
  -> dfmea skill
  -> AI Draft Batch
  -> apply
  -> projection
```

## 21. Reference Sources

本决策参考：

- Node.js release schedule: https://nodejs.org/en/about/releases/
- NestJS OpenAPI docs: https://docs.nestjs.com/openapi/introduction
- Drizzle migrations docs: https://orm.drizzle.team/docs/migrations
- PostgreSQL 18 release: https://www.postgresql.org/about/news/postgresql-18-released-3142/
- PostgreSQL versioning policy: https://www.postgresql.org/support/versioning/
- pgvector: https://github.com/pgvector/pgvector
- MCP TypeScript SDK: https://ts.sdk.modelcontextprotocol.io/
