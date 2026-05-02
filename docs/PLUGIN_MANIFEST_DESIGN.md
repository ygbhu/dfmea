# Plugin Manifest 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义 Domain Plugin 的 manifest 结构和注册规则。

Manifest 是插件与平台之间的能力契约。

它让平台在不理解具体业务细节的情况下，知道插件提供：

```text
artifact / edge schemas
skills
validators
projections
exporters
views metadata
requirements
version compatibility
```

Manifest 不保存插件运行态，也不保存业务数据。

## 2. Manifest 定位

Manifest 是：

```text
插件能力声明
插件资源索引
插件注册入口
平台校验依据
Capability Manifest 生成依据之一
```

Manifest 不是：

```text
业务数据存储
用户运行态
prompt 执行体
代码逻辑本身
数据库 schema migration 脚本
UI 实现代码
权限系统
```

核心原则：

```text
Manifest 声明能力。
Handler 执行能力。
Platform 管理状态。
Plugin 不保存运行态事实。
```

## 3. 文件位置

每个插件目录必须包含入口文件：

```text
plugin.json
```

推荐插件目录结构：

```text
plugin-root/
  plugin.json
  schemas/
    artifacts/
    edges/
    skills/
    projections/
    exporters/
  skills/
  validators/
  projections/
  exporters/
  views/
  prompts/
  docs/
```

`plugin.json` 只引用这些资源，不把资源内容全部内联进去。

## 4. Manifest 顶层结构

建议顶层结构：

```json
{
  "manifest_version": "0.1.0",
  "plugin": {},
  "capabilities": {},
  "schemas": [],
  "skills": [],
  "validators": [],
  "projections": [],
  "exporters": [],
  "views": [],
  "requirements": {},
  "compatibility": {},
  "metadata": {}
}
```

第一阶段不要求字段非常多，但结构必须稳定。

## 5. 基础信息

`plugin` 描述插件身份。

示例：

```json
{
  "plugin": {
    "plugin_id": "dfmea",
    "name": "DFMEA",
    "version": "0.1.0",
    "domain": "fmea",
    "description": "Design FMEA domain plugin.",
    "author": "local",
    "license": "private"
  }
}
```

### 5.1 plugin_id

第一阶段 `plugin_id` 采用扁平命名，并与 artifact / schema / skill 前缀保持一致：

```text
dfmea
pfmea
control_plan
eight_d
```

规则：

- 全平台唯一。
- 稳定，不随名称变化。
- 不使用空格。
- 不使用用户可变名称。
- 不在第一阶段使用 `fmea.dfmea` 这类多段命名，避免与 `dfmea.*` artifact / skill 前缀冲突。

### 5.2 version

插件版本必须显式声明。

平台在以下记录中应保存插件版本：

```text
run
capability_invocation
ai_draft
projection
export
```

这样后续结果可追溯。

## 6. Capabilities

Capabilities 声明插件提供哪些能力。

示例：

```json
{
  "capabilities": {
    "artifacts": true,
    "edges": true,
    "skills": true,
    "validators": true,
    "projections": true,
    "exporters": true,
    "views": true,
    "knowledge": true
  }
}
```

说明：

- Capabilities 是能力声明，不是用户权限。
- 平台可以据此决定注册哪些能力。
- 具体运行时是否暴露给 Agent，由 Execution Context 和 Capability Manifest 决定。

## 7. Schemas

Schemas 声明插件定义的结构化 schema。

示例：

```json
{
  "schemas": [
    {
      "schema_id": "dfmea.analysis_item.v1",
      "kind": "artifact",
      "version": "1.0.0",
      "path": "schemas/artifacts/analysis_item.schema.json"
    },
    {
      "schema_id": "dfmea.relation.v1",
      "kind": "edge",
      "version": "1.0.0",
      "path": "schemas/edges/relation.schema.json"
    },
    {
      "schema_id": "dfmea.generate_initial_analysis.input.v1",
      "kind": "skill_input",
      "version": "1.0.0",
      "path": "schemas/skills/generate_initial_analysis.input.schema.json"
    }
  ]
}
```

Schema kind 建议：

```text
artifact
edge
skill_input
skill_output
projection
export
view
```

用途：

- artifact payload 校验。
- edge payload 校验。
- skill input/output 校验。
- projection payload 校验。
- export payload 校验。
- Capability Descriptor 生成。

规则：

- 所有业务 payload 必须有 schema。
- schema_id 必须全局唯一或 plugin 内唯一后由平台归一。
- schema 修改必须升级 version。
- manifest 只引用 schema path，不内联大型 schema。

## 8. Skills

Skills 声明插件暴露的任务级业务能力。

示例：

```json
{
  "skills": [
    {
      "skill_id": "generate_initial_analysis",
      "name": "Generate Initial Analysis",
      "description": "Generate a structured initial analysis proposal for the current task scope.",
      "version": "0.1.0",
      "input_schema": "dfmea.generate_initial_analysis.input.v1",
      "output_schema": "dfmea.generate_initial_analysis.output.v1",
      "handler_ref": "skills/generate_initial_analysis.ts",
      "prompt_ref": "prompts/generate_initial_analysis.md",
      "required_projections": ["working_view"],
      "required_knowledge": ["project", "historical_fmea"],
      "side_effect": "returns_ai_draft_proposal",
      "result_types": ["ai_draft_proposal", "question_to_user", "summary"],
      "timeout_ms": 60000
    }
  ]
}
```

规则：

- Skill 必须有 `handler_ref`。
- `prompt_ref` 是可选资源。
- Skill 不应是字段级 CRUD。
- Skill 的输入输出必须有 schema。
- Skill 是否暴露给某次 run，由 Capability Manifest 决定。
- Skill 不能直接写 canonical state。

## 9. Validators

Validators 声明插件提供的校验能力。

示例：

```json
{
  "validators": [
    {
      "validator_id": "consistency_check",
      "name": "Consistency Check",
      "version": "0.1.0",
      "target": "ai_draft",
      "input_schema": "dfmea.consistency_check.input.v1",
      "output_schema": "dfmea.consistency_check.output.v1",
      "handler_ref": "validators/consistency_check.ts",
      "severity": "blocking"
    }
  ]
}
```

Validator 可用于：

```text
AI Draft proposal 后
User Confirm 前
Apply 前
Projection rebuild 前
Export 前
```

规则：

- Validator 返回 validation result。
- Validator 不直接修改 current state。
- Blocking validator 可以阻止 apply。
- Validator handler 仍然通过受控 context 访问数据。

## 10. Projections

Projections 声明插件能构建哪些读模型。

示例：

```json
{
  "projections": [
    {
      "kind": "working_view",
      "category": "working",
      "payload_schema": "dfmea.working_view.v1",
      "handler_ref": "projections/working_view.ts",
      "scope": ["project"],
      "vectorizable": true
    },
    {
      "kind": "export_payload",
      "category": "export",
      "payload_schema": "dfmea.export_payload.v1",
      "handler_ref": "projections/export_payload.ts",
      "scope": ["project"],
      "vectorizable": false
    }
  ]
}
```

规则：

- Plugin Projection Handler 负责构建 payload。
- Projection Service 负责调度、存储、freshness 和依赖。
- Projection 不是事实源。
- Projection Handler 不直接写 projection 表。

## 11. Exporters

Exporters 声明插件支持哪些导出方式。

示例：

```json
{
  "exporters": [
    {
      "exporter_id": "api_push_payload",
      "name": "API Push Payload Exporter",
      "version": "0.1.0",
      "source_projection": "export_payload",
      "input_schema": "dfmea.export_payload.v1",
      "output_type": "api_push_payload",
      "handler_ref": "exporters/api_push_payload.ts"
    }
  ]
}
```

规则：

- Exporter 优先读取 export projection。
- Exporter 不直接读取底层 artifact / edge 表拼结果。
- Exporter 不修改 canonical state。
- 外部成熟系统集成应通过 API Push Adapter / Integration Adapter。

## 12. Views

Views 声明插件给 UI 的视图元数据。

示例：

```json
{
  "views": [
    {
      "view_id": "main_workspace",
      "name": "Main Workspace",
      "projection_kind": "working_view",
      "view_type": "table_tree",
      "metadata": {
        "primary": true
      }
    },
    {
      "view_id": "draft_changes",
      "name": "User Confirm Changes",
      "projection_kind": "draft_preview_view",
      "view_type": "ai_draft_confirm"
    }
  ]
}
```

规则：

- View metadata 不是 UI 实现。
- Manifest 不定义复杂交互细节。
- 具体 UI 设计后续单独讨论。
- UI 消费 projection，不直接消费插件私有状态。

## 13. Requirements

Requirements 声明插件运行需要的平台能力。

示例：

```json
{
  "requirements": {
    "platform_capabilities": [
      "workspace.projection.get",
      "workspace.knowledge.retrieve",
      "workspace.knowledge.get_evidence",
      "workspace.ai_draft.propose",
      "workspace.ai_draft.validate",
      "workspace.question.ask_user"
    ],
    "knowledge_base_types": ["project", "historical_fmea"],
    "runtime": {
      "workspace_capabilities": true,
      "streaming": true
    },
    "storage": {
      "canonical_store": "postgresql",
      "vector": "pgvector"
    }
  }
}
```

说明：

- Requirements 不是企业权限。
- Requirements 用于平台加载前检查能力是否满足。
- Capability 是否最终暴露给 Agent，仍由 Execution Context 决定。

## 14. Compatibility

Compatibility 声明插件与平台的兼容关系。

示例：

```json
{
  "compatibility": {
    "platform_version": ">=0.1.0",
    "manifest_version": "0.1.x",
    "schema_migration": "manual",
    "requires_runtime_provider_features": ["workspace_capabilities"]
  }
}
```

第一阶段只预留迁移声明。

不实现复杂自动 migration。

## 15. Metadata

Metadata 保存非核心信息。

示例：

```json
{
  "metadata": {
    "tags": ["quality", "fmea"],
    "homepage": "",
    "docs": "docs/README.md"
  }
}
```

Metadata 不参与核心业务判断。

## 16. Registration

插件注册流程：

```text
1. 读取 plugin.json
2. 校验 manifest schema
3. 校验 plugin_id / version
4. 校验资源路径存在
5. 注册 schemas
6. 注册 skills
7. 注册 validators
8. 注册 projections
9. 注册 exporters
10. 注册 views metadata
11. 检查 requirements
12. 写入 Plugin Registry
```

注册后：

- Plugin Service 可以查询插件能力。
- Workspace Capability Server 可以基于 skill 生成 Capability Descriptor。
- Projection Service 可以调用 projection handler。
- API Push Service 可以调用 exporter。

## 17. Manifest Validation

平台加载 manifest 时必须校验：

- JSON 格式合法。
- manifest_version 支持。
- plugin_id 合法且唯一。
- version 合法。
- schema path 存在。
- handler_ref 存在。
- skill input/output schema 存在。
- projection payload schema 存在。
- exporter source_projection 存在。
- view projection_kind 存在。
- requirements 可满足或明确降级。

如果校验失败，插件不能进入 enabled 状态。

## 18. 安全边界

Manifest 不能声明或获取以下能力：

```text
raw database access
direct artifact write
direct edge write
direct projection write
direct external system write
unrestricted filesystem write
unrestricted shell run
cross workspace access
```

如果后续需要文件或 shell 能力，应进入 Runtime Sandbox 设计，不应混入业务 manifest 的默认能力。

## 19. 完整示例

```json
{
  "manifest_version": "0.1.0",
  "plugin": {
    "plugin_id": "dfmea",
    "name": "DFMEA",
    "version": "0.1.0",
    "domain": "fmea",
    "description": "Design FMEA domain plugin."
  },
  "capabilities": {
    "artifacts": true,
    "edges": true,
    "skills": true,
    "validators": true,
    "projections": true,
    "exporters": true,
    "views": true,
    "knowledge": true
  },
  "schemas": [
    {
      "schema_id": "dfmea.analysis_item.v1",
      "kind": "artifact",
      "version": "1.0.0",
      "path": "schemas/artifacts/analysis_item.schema.json"
    }
  ],
  "skills": [
    {
      "skill_id": "generate_initial_analysis",
      "name": "Generate Initial Analysis",
      "version": "0.1.0",
      "input_schema": "dfmea.generate_initial_analysis.input.v1",
      "output_schema": "dfmea.generate_initial_analysis.output.v1",
      "handler_ref": "skills/generate_initial_analysis.ts",
      "prompt_ref": "prompts/generate_initial_analysis.md",
      "side_effect": "returns_ai_draft_proposal",
      "result_types": ["ai_draft_proposal"]
    }
  ],
  "projections": [
    {
      "kind": "working_view",
      "category": "working",
      "payload_schema": "dfmea.working_view.v1",
      "handler_ref": "projections/working_view.ts",
      "scope": ["project"]
    }
  ],
  "requirements": {
    "platform_capabilities": [
      "workspace.projection.get",
      "workspace.ai_draft.propose"
    ],
    "runtime": {
      "workspace_capabilities": true,
      "streaming": true
    }
  },
  "compatibility": {
    "platform_version": ">=0.1.0",
    "manifest_version": "0.1.x",
    "schema_migration": "manual"
  }
}
```

该示例用于表达 manifest 结构，不代表最终业务字段设计。

## 20. 第一阶段实现边界

第一阶段必须定义：

- `plugin.json` 位置。
- manifest_version。
- plugin 基础信息。
- capabilities。
- schemas。
- skills。
- validators。
- projections。
- exporters。
- views metadata。
- requirements。
- compatibility。
- manifest validation。
- registration flow。

第一阶段暂不实现：

- 复杂 schema migration。
- 插件 marketplace。
- 插件热更新。
- 插件远程安装。
- 插件企业权限模型。
- 插件自定义数据库表。
- 插件直接数据库访问。
- manifest 内嵌大型 schema。
- manifest 内嵌业务运行态。
- UI 复杂交互 schema。

## 21. 待决问题

后续需要确认：

- manifest schema 是否用 JSON Schema 发布。
- handler_ref 支持 TypeScript、Python，还是双语言。
- 插件注册是启动时扫描，还是后台导入。
- 插件版本升级时旧 project 如何兼容。
- schema migration 是否由插件声明脚本，还是平台工具驱动。
- views metadata 的最小字段。
- requirements 不满足时是禁止加载还是降级加载。
