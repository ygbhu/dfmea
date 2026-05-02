# Plugin Skill 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义 Domain Plugin 中 Skill 的设计、声明、执行和结果契约。

Skill 是插件暴露给 Agent Runtime 的受控业务能力。

它处在以下链路中：

```text
Agent Runtime
  -> Workspace Capability Server
  -> Plugin Skill Capability
  -> Skill Handler Code
  -> Platform Service Facade
  -> structured result
```

核心目标：

- 让业务能力可插拔。
- 让 Agent 可以调用业务能力。
- 让 Skill 保持任务级粒度。
- 让 Skill 必须由代码 handler 执行。
- 让 Skill 输出结构化结果。
- 防止 Skill 绕过 AI Draft Batch / User Confirm / Projection 协议。

## 2. Skill 定位

Skill 是：

```text
插件内的任务级业务能力
```

它不是：

```text
prompt 模板
字段级 CRUD 接口
数据库操作脚本
隐藏 workflow engine
长期状态容器
外部系统写入器
```

Skill 的职责：

- 接收结构化输入。
- 使用 Skill Execution Context。
- 读取 fresh projection / evidence。
- 执行业务逻辑。
- 调用必要的模型或确定性代码。
- 返回结构化结果。

Skill 不直接决定平台状态写入。

如果 Skill 生成业务内容，必须通过 AI Draft Batch 进入 confirm/apply 流程。

## 3. Skill 粒度原则

Skill 应该是任务级能力，不是字段级 CRUD。

不建议：

```text
create_item
update_field
delete_row
link_node
set_score
```

建议：

```text
analyze_structure
generate_initial_analysis
validate_consistency
suggest_missing_items
prepare_confirm_summary
prepare_api_push_mapping
```

原则：

- 一个 Skill 对应一个明确业务意图。
- 一个 Skill 可以产出多个候选变更。
- 一个 Skill 不应该只对应一个字段操作。
- 一个 Skill 不应该把完整业务流程都吞进去。
- 编排优先由 Agent Runtime / Platform Core Services / Workspace Capability Server 控制。

## 4. Skill Descriptor

Skill Descriptor 是插件声明 skill 的元数据。

建议字段：

```text
skill_id
name
description
version
input_schema
output_schema
handler_ref
prompt_ref
required_projections
required_knowledge
side_effect
result_types
timeout_ms
tags
```

示例：

```json
{
  "skill_id": "generate_initial_analysis",
  "name": "Generate Initial Analysis",
  "description": "Generate a structured initial analysis proposal for the current task scope.",
  "version": "0.1.0",
  "input_schema": "schemas/skills/generate_initial_analysis.input.schema.json",
  "output_schema": "schemas/skills/generate_initial_analysis.output.schema.json",
  "handler_ref": "skills/generate_initial_analysis.ts",
  "prompt_ref": "prompts/generate_initial_analysis.md",
  "required_projections": ["working_view"],
  "required_knowledge": ["project", "historical_fmea"],
  "side_effect": "returns_ai_draft_proposal",
  "result_types": ["ai_draft_proposal", "question_to_user", "summary"],
  "timeout_ms": 60000
}
```

说明：

- 该示例只表达 skill 结构，不定义具体业务字段。
- `prompt_ref` 是可选资源，不是 skill 的唯一实现。
- `handler_ref` 必须存在。

## 5. Skill Handler

所有 Skill 必须有代码 handler。

推荐接口形态：

```text
handler(input, skill_context) -> SkillResult
```

Handler 负责：

- 解析输入。
- 读取必要 projection。
- 检索必要 evidence。
- 调用模型或业务代码。
- 生成结构化结果。
- 附带 evidence_refs / warnings / questions。

Handler 不负责：

- 直接写 artifact / edge。
- 直接写 projection。
- 直接写外部系统。
- 直接操作数据库。
- 绕过 Workspace Capability Server 返回未校验结果。

### 5.1 Prompt 的位置

Prompt 可以作为 handler 使用的资源。

例如：

```text
method guide
rubric
few-shot examples
output instruction
```

但 Prompt 不能替代：

- input schema。
- output schema。
- validator。
- handler code。
- AI Draft Batch 协议。

## 6. Skill Execution Context

Skill Handler 只能通过 Skill Execution Context 访问平台能力。

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

### 6.1 projectionFacade

用于读取 fresh projection。

规则：

- 自动注入 scope。
- 自动执行 freshness check。
- stale 时返回结构化错误。

### 6.2 knowledgeFacade

用于检索知识库。

规则：

- 自动注入 scope。
- 受 knowledge policy 限制。
- 返回 evidence refs。
- 不决定当前项目事实。

### 6.3 aiDraftFacade

用于创建 proposal。

规则：

- 只创建 AI Draft proposal。
- 不直接 apply。
- 必须绑定 base_workspace_revision。
- 必须进入 User Confirm。

### 6.4 eventFacade

用于记录 skill 运行事件。

规则：

- 记录摘要、状态、错误和引用。
- 不把 event 当作事实源。

## 7. Input Schema

Skill input 必须使用 JSON Schema 或平台认可的结构化 schema。

Input Schema 应定义：

```text
task scope
input parameters
projection refs
evidence refs
options
constraints
```

规则：

- Workspace Capability Server 执行输入校验。
- Skill Handler 可以做二次业务校验。
- 输入不应包含完整项目大数据。
- 大内容通过 ref 按需读取。

示例：

```json
{
  "task_scope": {
    "scope_type": "project",
    "scope_id": "proj_001"
  },
  "projection_refs": [
    {
      "kind": "working_view",
      "projection_id": "projection_001"
    }
  ],
  "options": {
    "depth": "initial"
  }
}
```

## 8. Output Schema

Skill output 必须结构化。

统一外壳：

```json
{
  "result_type": "ai_draft_proposal",
  "summary": "生成了候选分析结果。",
  "data": {},
  "evidence_refs": [],
  "questions": [],
  "warnings": []
}
```

规则：

- `result_type` 必须明确。
- `data` 必须符合对应 output schema。
- `evidence_refs` 必须可追溯。
- `warnings` 用于提示风险，不改变事实状态。
- Workspace Capability Server 负责输出 schema 校验。

禁止只返回自然语言大段文本让平台猜测如何落库。

## 9. Result Type

第一阶段建议支持以下结果类型：

```text
ai_draft_proposal
validation_result
question_to_user
summary
candidate_result
api_push_preview
```

### 9.1 ai_draft_proposal

用于生成业务变更候选。

必须能转换为：

```text
ai_draft
draft_patches
evidence_links
confirm state
```

Skill 生成的 proposal 不直接修改 current state。

### 9.2 validation_result

用于校验业务一致性。

可以影响 User Confirm / apply。

不直接修改 current state。

### 9.3 question_to_user

用于信息不足时向用户提问。

应转换为：

```text
run.waiting_for_input
question event
UI prompt
```

### 9.4 summary

用于总结、解释、复盘。

Summary 不是事实源。

### 9.5 candidate_result

用于返回候选结果，但暂不创建 AI Draft Batch。

适合探索、比较、草案前预览。

### 9.6 api_push_preview

用于 API Push 前的映射预览。

不直接写外部系统。

## 10. Side Effect 约束

Skill Descriptor 必须声明 side effect。

第一阶段建议：

```text
read_only
returns_candidate
returns_ai_draft_proposal
asks_user
records_event
starts_api_push_preview_job
```

第一阶段不允许 Skill side effect 为：

```text
writes_artifact_directly
writes_edge_directly
writes_projection_directly
writes_external_system_directly
runs_shell
writes_filesystem
```

如果 Skill 需要产生业务变更，必须返回 `ai_draft_proposal`。

## 11. Evidence / Knowledge 使用

Skill 可以使用 Knowledge Provider 返回的证据。

规则：

- 通过 knowledgeFacade 检索。
- 通过 evidenceFacade 获取证据详情。
- evidence_ref 必须进入输出。
- 历史 FMEA 只能作为参考知识。
- 基于证据生成业务内容时，必须进入 AI Draft Batch。

Skill 不应把检索片段直接当作当前项目事实。

## 12. Validation

Skill 相关校验分三层：

```text
Workspace Capability Server schema validation
Skill Handler business validation
Platform Validator validation
```

### 12.1 Workspace Capability Server Schema Validation

负责：

- input schema。
- output schema。
- result_type。
- payload size。
- 禁止字段。

### 12.2 Skill Handler Business Validation

负责：

- 业务规则预检查。
- 证据完整性检查。
- 结果合理性检查。
- 输出 warning。

### 12.3 Platform Validator Validation

负责：

- AI Draft Batch patch 校验。
- schema version 校验。
- apply 前校验。
- consistency check。

## 13. Error Handling

Skill 错误必须结构化。

示例：

```json
{
  "result_type": "error",
  "summary": "无法完成分析。",
  "error": {
    "code": "REQUIRED_PROJECTION_MISSING",
    "message": "Required projection is missing or stale.",
    "details": {}
  },
  "warnings": []
}
```

常见错误码：

```text
SKILL_INPUT_INVALID
SKILL_OUTPUT_INVALID
SKILL_TIMEOUT
SKILL_REQUIRED_PROJECTION_MISSING
SKILL_EVIDENCE_NOT_FOUND
SKILL_KNOWLEDGE_UNAVAILABLE
SKILL_MODEL_FAILED
SKILL_UNSUPPORTED_CONTEXT
```

错误不应被包装成普通 summary。

## 14. Versioning

Skill 必须版本化。

至少记录：

```text
plugin_id
plugin_version
skill_id
skill_version
input_schema_version
output_schema_version
handler_version
prompt_version
```

Runtime run、capability invocation、AI Draft Batch 应记录调用时的 skill 版本信息。

原因：

- AI 结果需要可追溯。
- 后续 skill 升级不能破坏旧记录解释。
- AI Draft Batch 需要知道由哪个版本的能力生成。

## 15. Composition

Skill 可以复用插件内部 helper code。

Skill 可以调用平台 facade。

但不建议 Skill A 直接调用 Skill B 形成复杂链条。

原因：

- 容易隐藏 workflow。
- 容易绕开 Workspace Capability Server 审计。
- 容易形成循环依赖。
- 运行过程难以解释。

编排优先由：

```text
Agent Runtime
Platform Core Services
Workspace Capability Server
```

控制。

## 16. Testing

Skill 应支持独立测试。

建议测试内容：

```text
input schema validation
output schema validation
projection missing / stale
knowledge empty result
evidence link generation
ai_draft_proposal structure
warning generation
error handling
version metadata
```

测试应使用 mock Skill Execution Context。

不要依赖真实数据库连接测试 Skill 核心逻辑。

## 17. 第一阶段实现边界

第一阶段必须定义：

- Skill Descriptor。
- Skill Handler 接口。
- Skill Execution Context 使用规则。
- input schema。
- output schema。
- result_type。
- side_effect。
- evidence_refs。
- structured error。
- skill version metadata。
- Workspace Capability Server 注册规则。

第一阶段建议支持：

- read_only skill。
- candidate_result skill。
- ai_draft_proposal skill。
- validation_result skill。
- question_to_user skill。

第一阶段暂不支持：

- 字段级 CRUD skill。
- Skill 直接写 artifact / edge。
- Skill 直接写 projection。
- Skill 直接写外部系统。
- Skill 直接访问数据库。
- Skill 直接运行 shell。
- Skill 写文件系统。
- Skill 内部复杂 workflow engine。

## 18. 待决问题

后续需要确认：

- Skill Handler 首选 TypeScript、Python，还是双语言。
- Skill Handler 是否需要独立进程沙箱。
- Prompt 资源如何版本化。
- Skill schema 是否自动生成 Capability Descriptor。
- Skill 输出的大结果如何存储和引用。
- Skill 测试夹具如何设计。
- Skill 之间是否允许受控复用。
- Plugin SDK 是否提供标准 Skill helper library。
