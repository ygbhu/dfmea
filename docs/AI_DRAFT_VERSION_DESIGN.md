# AI Draft / Version 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义 AI 生成和修改的数据如何进入工作区当前数据，并形成可追踪的工作区版本。

当前阶段不做企业级变更管理。

旧文档中的 `Change Set / Review` 语义在当前定位下收敛为：

```text
AI Draft Batch
User Confirm / Edit / Apply
Workspace Revision
```

核心目标：

- 支持 AI 一次性生成或修改大量质量工程数据。
- 让用户可以确认、编辑、拒绝 AI 草稿。
- 每次应用草稿后形成新的 workspace revision。
- 支持 projection freshness。
- 支持 API Push 绑定明确版本。
- 保留后续 rollback / compare / snapshot 的扩展空间。

本设计不承担：

```text
企业审批
签核
正式发布
完整审计
复杂 patch 级评审
完整 time travel
```

这些能力由成熟 FMEA 系统或后续增强承接。

## 2. 核心原则

### 2.1 AI Draft 先于 Apply

AI 生成或修改工作区数据时，必须先形成 AI Draft Batch。

```text
AI output
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Workspace Current Data
```

AI 不直接写入 workspace current data。

### 2.2 Apply 形成 Workspace Revision

每次成功 apply AI Draft Batch 后：

```text
workspace_revision += 1
```

Projection、API Push、Knowledge Link 都应能绑定到明确 revision。

### 2.3 版本管理是 AI Workspace 的基础能力

版本管理不是为了企业合规，而是为了控制 AI 批量生成和批量修改带来的风险。

平台必须能回答：

```text
AI 这次生成或修改了什么？
当前工作区是哪一版？
这次 API Push 基于哪一版？
哪些数据来自哪个 AI run？
用户应用前后有什么变化？
```

### 2.4 不做重审批/评审

当前阶段的用户确认不是企业级审批或正式评审。

只保留：

```text
confirm
edit
apply
reject
```

## 3. 核心概念

### 3.1 Workspace Current Data

工作区当前数据是平台当前在线事实。

由以下结构表达：

```text
artifacts
artifact_edges
```

业务对象和关系的具体类型由 Domain Plugin 定义。

### 3.2 Workspace Revision

Workspace Revision 是工作区当前数据的版本号。

```text
workspace.current_revision
```

这是逻辑命名。

MVP 物理实现使用：

```text
projects.workspace_revision
```

因此，本文后续出现的 `workspace.current_revision` 都等价于当前 project 的 `workspace_revision`。

规则：

- 初始化时为 0 或 1。
- 每次 apply AI Draft Batch 成功后递增。
- Projection 必须记录 source_revision。
- API Push 必须记录 source_workspace_revision。

### 3.3 AI Draft Batch

AI Draft Batch 是 AI 一次生成或修改的一组草稿变更。

它不是企业级审批单。

它的职责是：

- 承载 AI 批量输出。
- 给用户确认和编辑。
- 记录 base workspace revision。
- 应用后生成 target workspace revision。
- 为 projection rebuild 和 API Push 提供版本边界。

### 3.4 Draft Patch

Draft Patch 是 AI Draft Batch 内的对象级或关系级变更。

Patch 粒度：

```text
artifact
edge
```

Patch 类型：

```text
create_artifact
update_artifact
delete_artifact
create_edge
update_edge
delete_edge
```

Patch 不应该以整个项目大 payload 为粒度。

### 3.5 User Confirm / Edit / Apply

用户动作简化为：

```text
confirm
edit
apply
reject
```

说明：

- `confirm`：用户确认草稿可应用。
- `edit`：用户在应用前修改草稿内容。
- `apply`：把草稿写入 workspace current data。
- `reject`：拒绝草稿，不写入 current data。

## 4. 数据粒度

平台不采用：

```text
一个 workspace = 一个巨大 payload
一个 AI draft = 一个巨大 payload
```

采用：

```text
Current State:
  artifacts
  artifact_edges

Draft Layer:
  ai_draft_batches
  draft_patches

Read Model:
  projections
```

这样支持：

- AI 批量生成。
- 用户局部查看草稿。
- Apply 前校验。
- Apply 后版本递增。
- Projection 局部或整体重建。
- API Push 绑定版本。

## 5. 建议数据结构

### 5.1 workspaces / projects

如果平台仍使用 `project` 命名，可以先保留。

但语义上它代表 AI 工作区。

建议字段：

```text
workspace_id / project_id
current_revision
status
metadata
created_at
updated_at
```

### 5.2 ai_draft_batches

```text
ai_draft_batches
  draft_batch_id
  workspace_id
  project_id
  session_id
  run_id
  plugin_id
  title
  goal
  status
  base_workspace_revision
  target_workspace_revision
  summary jsonb
  created_by
  applied_by
  rejected_by
  created_at
  updated_at
  applied_at
  rejected_at
```

### 5.3 draft_patches

```text
draft_patches
  draft_patch_id
  draft_batch_id
  workspace_id
  project_id
  plugin_id
  patch_type
  target_type
  target_id
  artifact_type
  relation_type
  before_payload jsonb
  after_payload jsonb
  payload_patch jsonb
  status
  validation_result jsonb
  applied_result jsonb
  edited_by
  created_at
  updated_at
```

第一阶段可以主要使用 `after_payload` 表达草稿应用后的目标状态。

后续再增强为更严格的 semantic patch 或 reversible patch。

### 5.4 workspace_revision_events

轻量记录版本变化。

```text
workspace_revision_events
  event_id
  workspace_id
  project_id
  from_revision
  to_revision
  draft_batch_id
  run_id
  summary
  created_by
  created_at
```

它不是完整 event sourcing。

它用于解释版本变化。

## 6. 状态模型

### 6.1 AI Draft Batch 状态

第一阶段采用简化状态：

```text
pending
applied
rejected
failed
```

含义：

- `pending`：AI 草稿已生成，等待用户确认、编辑或应用。
- `applied`：已应用到 workspace current data。
- `rejected`：用户拒绝，不进入 current data。
- `failed`：生成或应用失败。

不引入复杂状态：

```text
accepted
partially_accepted
superseded
reviewing
approved
```

### 6.2 Draft Patch 状态

第一阶段采用：

```text
pending
applied
rejected
failed
```

说明：

- 用户可以在 apply 前删除某些 patch。
- 被删除的 patch 进入 `rejected`。
- apply 成功后 patch 进入 `applied`。
- apply 失败的 patch 进入 `failed`。

第一阶段可以不做复杂 patch 级状态流转 UI。

## 7. 用户动作

### 7.1 Confirm

Confirm 表示用户认可 AI Draft Batch 可进入应用阶段。

第一阶段可以不单独持久化 confirm 状态。

用户点击 apply 时，可以视为 confirm + apply。

### 7.2 Edit

Edit 表示用户在 apply 前修改草稿。

第一阶段建议：

```text
编辑 draft_patches.after_payload
记录 edited_by / updated_at
重新运行 schema validation
```

不建议第一阶段把用户编辑再拆成新的 Draft Batch。

原因是当前目标是轻量 AI Workspace，不是复杂变更审批。

### 7.3 Apply

Apply 表示把 pending draft patches 写入 workspace current data。

Apply 成功后：

```text
ai_draft_batch.status = applied
draft_patches.status = applied / rejected
workspace.current_revision += 1
target_workspace_revision = workspace.current_revision
projection marked stale
workspace_revision_event created
```

### 7.4 Reject

Reject 表示拒绝整个 AI Draft Batch。

Reject 后：

```text
ai_draft_batch.status = rejected
draft_patches.status = rejected
不修改 workspace current data
不增加 workspace revision
```

## 8. Apply 语义

Apply 是唯一把 AI Draft 写入当前工作区事实的过程。

Apply 必须执行：

```text
scope validation
schema validation
base revision validation
target existence validation
write policy validation
apply safety validation
event recording
projection stale marking
```

Apply 应尽量在单个数据库事务中完成。

事务内完成：

```text
1. 锁定 AI Draft Batch
2. 检查 draft status
3. 检查 base_workspace_revision
4. 校验 draft patches
5. 写 artifacts / artifact_edges
6. workspace.current_revision += 1
7. 写 target_workspace_revision
8. 更新 draft / patch status
9. 标记 projection stale
10. 写 workspace_revision_event
```

Apply 失败时：

```text
不更新 workspace current data
不增加 workspace revision
draft_batch.status = failed 或保持 pending
返回结构化错误
```

第一阶段建议失败后保持 `pending`，并记录错误，方便用户修正后再次 apply。

## 9. Base Revision 与冲突

AI Draft Batch 必须记录：

```text
base_workspace_revision
```

含义：

```text
AI 生成草稿时看到的工作区版本。
```

Apply 前必须检查：

```text
draft.base_workspace_revision == workspace.current_revision
```

第一阶段推荐严格策略：

```text
如果版本不一致，拒绝 apply，要求用户重新生成或刷新草稿。
```

后续可以扩展：

```text
自动 rebase
手动冲突解决
局部 patch merge
```

但不进入第一阶段。

## 10. Force Apply

Force Apply 可以保留为用户显式动作，但语义要简化。

它不是企业审批绕过。

它表示：

```text
用户知道当前草稿基于旧 revision 或存在覆盖风险，仍选择应用。
```

Force Apply 仍必须：

- 通过 AI Draft Batch。
- 记录用户授权。
- 记录原因。
- 记录 base revision 与 current revision。
- 形成新的 workspace revision。
- 标记 projection stale。

第一阶段可以先不实现 Force Apply，只预留字段。

## 11. Projection 关系

AI Draft 不应污染正式 export projection。

Projection 建议区分：

```text
working projection
  基于 workspace current data。

draft preview projection
  可选，用于展示 AI Draft 应用后的预览。

export projection
  基于 workspace current data，用于 API Push。
```

第一阶段必须保证：

```text
AI/UI/API Push 默认读取 fresh projection。
API Push 只读取 fresh export projection。
```

Apply 成功后：

```text
projection stale = true
projection.source_revision < workspace.current_revision
```

之后由 Projection Service rebuild。

## 12. API Push Binding

API Push 必须绑定明确版本。

记录：

```text
source_workspace_revision
source_projection_id
projection_source_revision
draft_batch_id optional
```

规则：

- 只能推送 fresh export projection。
- export projection source_revision 必须等于 workspace current_revision。
- API Push 成功后不反向修改 workspace current data。

这样可以回答：

```text
推送到成熟 FMEA 系统的是哪一版？
对应哪个 AI Draft Batch？
基于哪个 export projection？
```

## 13. Validation 关系

AI Draft / Version 只依赖核心 Validation。

Apply 前至少校验：

```text
draft schema valid
patch schema valid
target exists for update/delete
target revision compatible
base revision compatible
workspace scope valid
no blocking validation findings
```

Validation 不替代用户确认。

Validation 不做企业审批。

## 14. 轻量事件

第一阶段保留轻量事件，不做完整审计系统。

建议事件：

```text
ai_draft.created
ai_draft.edited
ai_draft.rejected
ai_draft.apply_started
ai_draft.applied
ai_draft.apply_failed
workspace_revision.changed
projection.marked_stale
api_push.created
api_push.completed
```

事件用于：

- UI 展示。
- 问题排查。
- 解释 AI 生成结果。
- 后续增强 rollback / compare 的基础。

事件不是事实源。

## 15. Snapshot / Rollback 预留

第一阶段不实现完整 rollback 和 time travel。

但要为后续预留：

```text
snapshot
revision compare
rollback to revision
draft rebase
```

建议后续在以下场景创建 snapshot：

- 大规模 AI 生成前。
- Force Apply 前。
- API Push 前。
- 用户手动保存重要版本。

第一阶段可以只记录 workspace_revision_events。

## 16. 与旧术语映射

为避免历史文档混淆，术语映射如下：

```text
Change Set
  -> AI Draft Batch

Change Set Patch
  -> Draft Patch

Review
  -> User Confirm / Apply

Project Revision
  -> Workspace Revision

Change Set Review
  -> Draft Preview / User Confirm

Export Binding
  -> API Push Revision Binding
```

旧术语可以在迁移期出现，但新设计和新代码优先使用新术语。

## 17. 第一阶段实现边界

第一阶段必须实现：

- AI Draft Batch。
- Draft Patch。
- Workspace Revision。
- User Apply。
- User Reject。
- Draft Edit。
- Apply 事务。
- Base revision check。
- Projection stale marking。
- Workspace revision event。
- API Push revision binding。

第一阶段建议实现：

- Draft preview。
- Force Apply 预留字段。
- Draft patch 局部 reject。

第一阶段暂不实现：

- 企业审批。
- 签核。
- 多人会签。
- 完整 patch 级评审。
- 完整 rollback。
- 完整 time travel。
- 自动 rebase。
- 复杂冲突合并。
- 完整 snapshot restore。
- 重审计系统。

## 18. 待决问题

后续需要确认：

- AI Draft Batch 表是否作为唯一草稿批次表。
- 用户编辑 draft 后是否需要记录编辑 diff。
- base revision 冲突第一阶段是否允许 force apply。
- Draft preview projection 是否第一阶段需要。
- workspace_revision_events 是否单独建表。
- API Push 前是否自动创建 snapshot。
