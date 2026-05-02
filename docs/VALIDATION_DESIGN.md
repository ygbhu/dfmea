# Validation 详细设计

日期：2026-05-01

## 1. 设计目标

Validation 是平台的系统护栏、User Confirm 辅助和 Export 门禁。

它的意义是：

```text
防止 AI 生成的内容破坏系统状态
防止非法 AI Draft Batch 进入 canonical state
防止 stale / invalid projection 被导出
把明显问题提前暴露给用户
```

Validation 不替代人工 User Confirm。

Validation 也不判断 AI 生成的业务内容最终是否“正确”。

第一阶段只实现核心功能：

```text
Schema Validation
AI Draft Batch Safety Validation
Export Projection Validation
```

Plugin Validator 保留机制，但不要求第一阶段写大量业务规则。

## 2. 核心定位

Validation 位于以下链路中：

```text
AI / Skill / User Edit
  -> AI Draft Proposal
  -> Validation
  -> User Confirm
  -> Apply
  -> Projection Rebuild
  -> Export
```

Validation 负责发现问题和阻止明显非法写入。

它不直接修改：

```text
artifact
edge
projection
export payload
external system
```

Validation 结果应进入 User Confirm，帮助用户判断 AI 生成内容的风险。

## 3. Validation 不是什么

Validation 不是：

```text
人工 User Confirm
审批流
业务正确性最终裁判
复杂规则引擎
可视化规则编排器
企业权限系统
事实写入层
```

即使 Validation 全部通过，AI 生成的大量业务内容仍然应进入 User Confirm。

## 4. Validator 类型

第一阶段分两类。

### 4.1 Platform Validator

平台内置校验。

不理解具体业务语义。

负责：

```text
scope 校验
schema 校验
draft_policy 校验
capability permission 校验
base_workspace_revision 校验
projection freshness 校验
ai_draft 状态校验
patch target 是否存在
artifact / edge revision 冲突
export projection 是否 fresh
```

Platform Validator 是第一阶段必须实现的核心。

### 4.2 Plugin Validator

插件业务校验。

由插件 manifest 声明，由插件 handler 实现。

负责：

```text
业务对象完整性
对象关系一致性
必填业务字段
业务规则约束
导出前业务完整性
projection 构建前一致性
```

第一阶段只保留机制。

具体业务规则后续在 DFMEA、PFMEA 等插件详细设计里定义。

## 5. 核心 Validation 场景

第一阶段只围绕三个场景实现。

### 5.1 Schema Validation

保证结构合法。

运行位置：

```text
Capability input
Capability output
Skill input
Skill output
Draft Patch
Artifact payload
Edge payload
Projection payload
Export payload
```

目的：

- 防止缺字段。
- 防止类型错误。
- 防止不合法 enum。
- 防止 payload 结构不匹配插件 schema。

### 5.2 AI Draft Batch Safety Validation

保证 AI Draft Batch 可以安全 apply。

运行位置：

```text
AI Draft proposal 后
User Confirm 前
Apply 前
```

目的：

- patch schema 合法。
- target artifact / edge 存在。
- update/delete target 没有被删除。
- target revision 兼容。
- base_workspace_revision 可接受。
- patch 类型合法。
- draft_policy 允许。

### 5.3 Export Gate Validation

保证导出数据可用。

运行位置：

```text
Export 前
```

目的：

- export projection fresh。
- export payload schema 合法。
- export source_workspace_revision 绑定正确。
- 不存在未处理的 blocking issue。
- 目标导出格式必需字段齐备。

成熟 DFMEA/PFMEA 系统导入前，必须至少经过 Export Gate Validation。

第一条可运行主流程不执行成熟系统 API Push，但仍应保证 export projection 可以通过基础 schema / freshness 校验。

## 6. Validation 执行节点

第一阶段建议执行节点：

```text
Workspace Capability Server:
  input / output schema validation

Skill Handler 返回后:
  skill output validation

AI Draft Proposal 创建时:
  patch schema validation
  proposal safety validation

User Confirm 前:
  validation result 展示给用户

Apply 前:
  apply safety validation

Projection Rebuild 后:
  projection payload schema validation

Export 前:
  export gate validation
```

其中必须实现：

```text
Capability input/output schema validation
AI Draft Batch apply 前 validation
Export 前 validation
```

## 7. Validation Result

Validation 必须输出结构化结果。

示例：

```json
{
  "status": "failed",
  "severity": "blocking",
  "summary": "存在阻止应用的问题。",
  "findings": [
    {
      "code": "SCHEMA_INVALID",
      "severity": "blocking",
      "target_type": "patch",
      "target_id": "patch_001",
      "message": "Patch payload does not match schema.",
      "details": {}
    }
  ]
}
```

字段建议：

```text
status
severity
summary
findings[]
```

Finding 字段建议：

```text
code
severity
target_type
target_id
message
details
```

Validation 不应只返回自然语言。

## 8. Severity 策略

第一阶段只保留三种 severity：

```text
blocking
warning
info
```

规则：

```text
blocking
  阻止 apply / export。

warning
  不阻止流程，但必须展示给用户。

info
  用于提示和审计，不影响流程。
```

不引入复杂 severity 体系。

## 9. Blocking 规则

第一阶段以下问题应视为 blocking：

```text
payload schema invalid
patch target missing
patch target deleted
target revision conflict
ai_draft status invalid
draft_policy denied
base_workspace_revision conflict
projection stale for AI read
export projection stale
export payload schema invalid
scope denied
```

以下问题可以先作为 warning：

```text
evidence missing
historical reference used without project evidence
optional field missing
low confidence suggestion
non-critical consistency issue
```

具体业务 warning 由插件后续定义。

## 10. AI Draft Batch Validation

AI Draft Batch Validation 是第一阶段重点。

### 10.1 Proposal Validation

在 AI Draft proposal 创建时运行。

检查：

```text
ai_draft scope valid
plugin_id valid
base_workspace_revision present
patch list not empty
patch_type valid
target_type valid
artifact_type / relation_type known
payload schema valid
evidence refs valid if provided
```

Proposal Validation 失败时：

- AI Draft Batch 可以标记为 `failed`。
- 或拒绝创建 AI Draft Batch。
- 错误返回给 Runtime / UI。

具体策略后续可细化。

### 10.2 Apply Validation

在 apply 前运行。

检查：

```text
ai_draft status pending
workspace current_revision compatible
patch target exists
target revision compatible
schema version compatible
all blocking findings resolved
draft_policy allowed
```

Apply Validation 失败时：

- 不写 artifact / edge。
- 不增加 workspace revision。
- 不 rebuild projection。
- 返回结构化错误。

## 11. Projection Validation

Projection Validation 只做最小校验。

运行位置：

```text
Projection rebuild 后
Projection 保存前
AI / Export 读取前
```

检查：

```text
payload schema valid
source_revision present
source_revision == workspace.current_revision for fresh read
projection kind known
projection category known
```

Projection Validation 不判断业务内容是否正确。

Projection stale 时：

- AI 读取必须拒绝。
- Export 必须拒绝。
- UI 可以展示 stale 标识，但不能伪装成最新。

## 12. Export Validation

Export Validation 是导出门禁。

运行位置：

```text
Export job start 前
Export payload 生成后
```

检查：

```text
export projection exists
export projection fresh
export payload schema valid
source_workspace_revision recorded
exporter_id valid
required target fields present
no blocking validation findings
```

Export Validation 失败时：

- 不生成正式 export record。
- 不推送外部系统。
- 返回结构化错误。

## 13. Plugin Validator

Plugin Validator 由插件 manifest 声明。

第一阶段只定义机制。

示例 manifest：

```json
{
  "validator_id": "consistency_check",
  "target": "ai_draft",
  "handler_ref": "validators/consistency_check.ts",
  "severity": "warning"
}
```

Plugin Validator 可以用于：

```text
ai_draft
artifact
edge
projection
export
```

规则：

- Plugin Validator 返回 Validation Result。
- Plugin Validator 不直接修改 current state。
- Plugin Validator 不能绕过 scope。
- Blocking Plugin Validator 可以阻止 apply/export。
- 第一阶段不要实现大量复杂业务规则。

## 14. workspace.ai_draft.validate

Workspace Capability Server 可以暴露：

```text
workspace.ai_draft.validate
```

用途：

- 让 Agent 主动请求校验候选结果。
- 让 Skill 运行特定 validator。
- 让 UI 在 User Confirm 前刷新 validation result。

规则：

- 必须受 Capability Permission 控制。
- 必须绑定 scope。
- 返回结构化 Validation Result。
- 不直接修改 current state。

## 15. Event / Audit

Validation 结果应记录事件。

事件示例：

```text
validation.started
validation.completed
validation.failed
validation.blocking_found
```

记录内容：

```text
validation_id
target_type
target_id
scope
status
severity
findings summary
created_at
```

Validation Event 不是事实源。

它用于审计、UI 展示和问题排查。

## 16. 不做复杂规则引擎

第一阶段不做：

```text
可视化规则引擎
复杂 DSL
动态规则编排
企业审批规则
跨插件规则推理
自动修复业务数据
```

第一阶段采用：

```text
JSON Schema validation
+ platform code validators
+ plugin code validators
```

这足够覆盖 MVP 的系统安全和导出门禁。

## 17. 第一阶段实现边界

第一阶段必须实现：

- Capability input/output schema validation。
- Skill output schema validation。
- AI Draft proposal validation。
- AI Draft Batch apply validation。
- Projection freshness validation。
- Export projection schema / freshness validation。
- 统一 Validation Result。
- `blocking / warning / info` severity。
- blocking 阻止 apply。

第一阶段建议实现：

- `workspace.ai_draft.validate`。
- Plugin Validator 机制。
- Validation event。

第一阶段暂不实现：

- 复杂业务规则库。
- 规则 DSL。
- 可视化规则配置。
- 自动修复。
- 跨插件规则编排。
- 完整业务正确性判断。

## 18. 待决问题

后续需要确认：

- Validation Result 是否单独建表，还是存在 ai_draft / patch metadata 中。
- Proposal Validation 失败时是拒绝创建 AI Draft Batch，还是创建 failed AI Draft Batch。
- Plugin Validator 的执行顺序。
- Blocking Plugin Validator 是否需要用户 force override。
- Validation Result 在 UI User Confirm 中如何展示。
- Export Validation 是否按不同外部系统定义 profile。
