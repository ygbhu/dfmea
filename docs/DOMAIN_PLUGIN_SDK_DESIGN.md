# Domain Plugin SDK 详细设计

日期：2026-05-01

## 1. 设计目标

Domain Plugin SDK 定义业务插件如何开发、注册和被平台调用。

目标：

- 支持 DFMEA、PFMEA、Control Plan 等业务能力可插拔。
- 保持插件无状态。
- 让插件通过 manifest 暴露能力。
- 让 skill handler、validator、projection handler、exporter 都有统一契约。
- 避免插件绕过平台状态、User Confirm、AI Draft Batch 和 Projection 协议。

核心原则：

```text
Plugin Definition is stateless.
Plugin capability is declared by manifest.
Skill must have handler.
Prompt is resource, not executor.
Plugin does not directly write database.
```

## 2. 插件目录结构

建议结构：

```text
plugins/
  dfmea/
    plugin.json
    schemas/
      artifacts/
      skills/
      projections/
      exporters/
    skills/
    prompts/
    validators/
    projections/
    views/
    exporters/
```

目录职责：

- `plugin.json`：插件 manifest。
- `schemas/`：JSON Schema。
- `skills/`：skill handler。
- `prompts/`：prompt 资源。
- `validators/`：validator handler。
- `projections/`：projection rebuild handler。
- `views/`：基础 view metadata。
- `exporters/`：exporter handler。

第一阶段不支持插件自带前端代码。

## 3. plugin.json

`plugin.json` 是插件入口。

示例：

```json
{
  "manifest_version": "0.1.0",
  "plugin": {
    "plugin_id": "dfmea",
    "name": "DFMEA",
    "version": "0.1.0",
    "domain": "quality.fmea.design",
    "description": "Design FMEA plugin"
  },
  "capabilities": {
    "artifacts": true,
    "edges": true,
    "skills": true,
    "validators": true,
    "projections": true,
    "exporters": true,
    "views": true
  },
  "schemas": [],
  "skills": [],
  "validators": [],
  "projections": [],
  "views": [],
  "exporters": [],
  "requirements": {},
  "compatibility": {},
  "metadata": {}
}
```

要求：

- `plugin.plugin_id` 必须稳定。
- `version` 必须显式声明。
- 所有对外能力必须可从 manifest 发现。
- manifest 不保存用户数据。

## 4. Schema 规范

Schema 建议使用 JSON Schema。

插件可以定义：

```text
artifact schema
skill input schema
skill output schema
projection payload schema
export payload schema
```

Schema 命名建议：

```text
{plugin_id}.{domain_object}.{schema_version}
```

例如：

```text
dfmea.failure_chain.v1
pfmea.process_flow.v1
```

平台负责：

- schema 注册。
- schema 版本识别。
- 写入前 schema 校验。
- runtime 输出 schema 校验。

插件负责：

- 定义业务 payload shape。
- 定义 schema 版本。
- 提供必要迁移策略。

## 5. Skill Handler 规范

Skill 是插件内部业务能力入口。

所有 Skill 必须有 handler。

Prompt 是 handler 可使用的资源，不是唯一执行体。

Skill manifest 示例：

```json
{
  "skill_id": "generate_initial_analysis",
  "version": "0.1.0",
  "description": "Generate initial DFMEA analysis proposal",
  "kind": "hybrid_skill",
  "input_schema": "schemas/skills/generate_initial_analysis.input.schema.json",
  "output_schema": "schemas/skills/generate_initial_analysis.output.schema.json",
  "prompt": "prompts/generate_initial_analysis.md",
  "handler": "skills/generate_initial_analysis.ts"
}
```

Manifest 内的 `skill_id` 使用插件内局部 ID。

对 Agent 暴露时，全局 capability id 由平台拼接为：

```text
{plugin_id}.{skill_id}
```

例如：

```text
dfmea.generate_initial_analysis
```

Skill handler 输入：

```text
Execution Context
Capability arguments
Runtime options
```

Skill handler 输出：

```text
ai_draft_proposal
validation_result
question
suggestion
```

Skill handler 可以：

- 读取 Execution Context。
- 请求 fresh projection。
- 检索 knowledge。
- 调用 LLM。
- 执行业务规范化。
- 生成结构化结果。

Skill handler 不可以：

- 直接连接数据库。
- 绕过 AI Draft Batch 写入状态。
- 直接修改 Projection。
- 直接操作 UI。
- 访问 scope 外数据。

## 6. Validator 规范

Validator 负责业务校验。

Validator 可以在以下阶段运行：

- artifact 写入前
- artifact 写入后
- User Confirm 前
- export 前
- projection rebuild 前

Validator manifest 示例：

```json
{
  "validator_id": "dfmea.failure_chain_integrity",
  "version": "0.1.0",
  "target_artifact_types": [
    "dfmea.failure_chain"
  ],
  "severity": "error",
  "handler": "validators/failure_chain_integrity.ts"
}
```

Validator 输出：

```text
validation_result
```

Validator 不直接修改业务状态。

修复建议应以 suggestion 或 AI Draft proposal 形式返回。

## 7. Projection Handler 规范

Projection Handler 负责构建插件定义的 projection。

Projection manifest 示例：

```json
{
  "projection_id": "dfmea.table_view",
  "version": "0.1.0",
  "category": "list_view",
  "payload_schema": "schemas/projections/table_view.schema.json",
  "handler": "projections/table_view.ts",
  "vector_index": false
}
```

Projection handler 输入：

```text
project scope
artifact query service
edge query service
evidence refs
projection options
```

Projection handler 输出：

```text
projection payload
source refs
validation status
vector index request
```

Projection handler 不直接写 projection 表。

平台负责保存 projection、记录 source revision、更新 freshness 和向量索引。

## 8. Exporter 规范

Exporter 负责将 export projection 转换为外部格式。

Exporter manifest 示例：

```json
{
  "exporter_id": "dfmea.api_push_payload",
  "version": "0.1.0",
  "format": "api_push",
  "input_projection": "dfmea.export_view",
  "handler": "exporters/api_push_payload.ts"
}
```

Exporter 输入：

```text
fresh export projection
export options
target mapping config
```

Exporter 输出：

```text
export payload
target system payload
validation result
```

Exporter 不直接修改 canonical state。

导出记录由平台保存。

## 9. View Metadata 规范

第一阶段只支持基础 view metadata。

插件可以声明：

```text
view_id
projection_kind
view_type
columns
filters
actions
editable_fields
highlight_rules
```

支持的基础 view type：

```text
table
tree
detail
draft-list
risk-list
evidence-panel
api-push-panel
```

第一阶段不支持：

- 插件自带前端代码。
- 自定义 UI 组件。
- 动态页面编排。

## 10. Workspace Capability Server 注册

Plugin Skill 可以注册为 runtime capability。

平台负责把 skill manifest 转换为 Capability Descriptor。

Capability Descriptor 至少包含：

```text
capability_id
description
input_schema
output_schema
```

Agent Runtime 发起 capability invocation 后：

```text
Workspace Capability Server
  -> Skill Handler
  -> structured result
  -> Agent Runtime
```

Skill result 最终仍要通过平台进入 AI Draft Batch / User Confirm / Artifact Service。

## 11. 版本管理

插件必须版本化。

至少包括：

```text
plugin_version
schema_version
skill_version
validator_version
projection_version
exporter_version
```

Artifact 必须记录：

```text
plugin_id
plugin_version
artifact_type
schema_version
```

Runtime run 和 AI Draft Batch 应记录：

```text
plugin_id
plugin_version
skill_id
skill_version
prompt_version
validator_version
```

这样可以追溯 AI 结果由哪个插件版本产生。

## 12. 插件限制

第一阶段插件不允许：

- 自己管理用户 session。
- 自己拥有最终业务状态。
- 直接连接数据库。
- 自建独立业务表作为默认运行态存储。
- 绕过 AI Draft Batch / User Confirm / Projection 协议。
- 直接操作 UI。
- 访问 scope 外数据。

插件允许：

- 定义业务 schema。
- 定义 skills。
- 定义 validators。
- 定义 projections。
- 定义 exporters。
- 定义基础 view metadata。
- 返回 ai_draft_proposal / validation_result / question / projection payload / export payload。

## 13. 第一阶段实现边界

第一阶段必须实现：

- plugin manifest 加载。
- schema 注册。
- skill handler 调用。
- validator handler 调用。
- projection handler 调用。
- exporter handler 调用。
- skill 到 Workspace Capability Server 的注册。
- plugin version 记录。

第一阶段暂不实现：

- 插件自带前端代码。
- 插件私有数据库。
- 插件热插拔运行时升级。
- 复杂 schema migration。
- 插件市场。
- 插件权限模型。

## 14. 待决问题

后续需要确认：

- 插件 handler 使用 TypeScript、Python 还是双语言。
- 插件是否允许依赖外部 npm/pip 包。
- handler 如何隔离执行。
- schema migration 如何设计。
- 插件升级后旧 artifact 如何处理。
- view metadata 的 UI 表达边界。
