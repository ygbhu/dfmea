# Workspace UI Data Flow Design

日期：2026-05-01

状态：Accepted for MVP data-flow design

## 1. 设计目标

本文只定义前端数据流转、布局职责和 UI 组件扩展边界。

本文不定义具体视觉样式、颜色、字号、组件库细节。

核心目标：

```text
左侧展示质量工程结构树。
右侧展示 AI 对话 / Agent Session。
AI 生成过程中可以实时看到结构树预览。
用户确认后才写入正式工作区数据。
后续可以替换或增加前端 UI 组件，但不改变平台数据流。
```

## 2. 核心 UI 布局

MVP 采用两栏为主：

```text
┌──────────────────────────────────────────────┐
│ Top Bar: workspace / project / revision       │
├───────────────────────┬──────────────────────┤
│ Left Panel            │ Right Panel           │
│ Structure Tree        │ AI Conversation       │
│ Projection / Preview  │ Agent Session         │
│                       │ Draft Actions         │
└───────────────────────┴──────────────────────┘
```

### 2.1 Left Panel

左侧是结构化工作区视图。

主要展示：

```text
Working Structure Tree
Draft Preview Tree
Node status
Validation markers
Evidence markers
Revision freshness
```

### 2.2 Right Panel

右侧是 AI 交互区。

主要展示：

```text
Conversation
Agent run status
Runtime event stream
AI questions
Draft summary
Apply / Reject actions
```

### 2.3 Optional Detail Drawer

后续可以增加详情抽屉或底部面板。

用途：

```text
Selected node detail
Evidence detail
Validation detail
Draft patch detail
```

该区域不是第一阶段必需。

## 3. UI 数据源分层

前端必须区分三类数据源。

```text
Confirmed Data
  已确认工作区事实。
  来源：fresh working projection。

Draft Data
  AI 已生成但未应用的草稿。
  来源：AI Draft Batch / Draft Patch。

Live Preview Data
  AI 运行中实时产生的预览。
  来源：runtime events / draft preview events。
```

三者不能混用。

## 4. 两棵结构树

前端至少有两种树状态。

### 4.1 Working Tree

Working Tree 表示当前已确认工作区数据。

来源：

```text
GET /api/projects/{project_id}/projections?kind=working_view
```

要求：

```text
projection.source_revision == workspace.current_revision
```

用途：

```text
展示当前项目结构。
作为用户确认后的正式视图。
作为 AI 下一轮生成的上下文来源之一。
```

Working Tree 不是前端自己拼底层 artifact / edge。

### 4.2 Draft Preview Tree

Draft Preview Tree 表示 AI 正在生成或已生成但未应用的候选结构。

来源可以有两种：

```text
runtime draft preview events
AI Draft Batch + Draft Patch
```

用途：

```text
实时展示 AI 生成效果。
标记新增 / 修改 / 删除。
让用户在 apply 前查看草稿影响。
```

Draft Preview Tree 不是事实源。

## 5. 主数据流

### 5.1 初始加载

```text
UI opens project
  -> GET project summary
  -> GET fresh working projection
  -> render Working Tree
  -> connect workspace / run SSE if needed
```

如果 working projection stale：

```text
UI shows stale state
  -> request projection rebuild
  -> wait projection.rebuild.completed
  -> refetch projection
```

### 5.2 用户发起 AI 生成

```text
User enters goal in right panel
  -> POST /api/sessions/{session_id}/runs
  -> backend creates run
  -> Runtime Provider starts mock / real agent
  -> UI subscribes run event stream
```

右侧对话框显示：

```text
user goal
agent messages
thinking/status events if available
capability invocation summaries
questions
errors
```

左侧结构树开始进入 preview mode。

### 5.3 AI 实时生成预览

AI 生成过程中，后端可以发送事件：

```text
draft.preview.started
draft.preview.node_upserted
draft.preview.node_updated
draft.preview.edge_upserted
draft.preview.edge_updated
draft.preview.node_removed
draft.preview.validation_updated
draft.preview.evidence_linked
draft.preview.completed
```

前端处理：

```text
SSE event
  -> normalize event
  -> update local Live Preview Store
  -> derive Draft Preview Tree
  -> render left panel
```

这些事件只影响前端 preview state。

它们不代表数据已经写入工作区。

### 5.4 AI Draft Batch 创建

Agent / Skill 最终输出结构化 proposal 后：

```text
Runtime Result
  -> AI Draft Service
  -> ai_draft_batch created
  -> draft_patches created
  -> ai_draft.created event
```

UI 收到事件后：

```text
fetch AI Draft Batch
fetch Draft Patches
render Draft Preview Tree from persisted draft
show Apply / Reject
```

此时 Draft Preview Tree 从 live preview 过渡到 persisted draft。

### 5.5 用户确认和应用

用户在右侧或左侧选择：

```text
apply
reject
edit draft patch
```

Apply 流程：

```text
POST /api/ai-drafts/{draft_batch_id}/apply
  -> AI Draft apply transaction
  -> artifacts / artifact_edges updated
  -> workspace.current_revision +1
  -> projection marked stale
  -> workspace_revision.changed event
  -> projection.rebuild.started
  -> projection.rebuild.completed
```

UI 收到 `projection.rebuild.completed` 后：

```text
refetch fresh working projection
clear Draft Preview Tree
render updated Working Tree
show applied revision
```

Reject 流程：

```text
POST /api/ai-drafts/{draft_batch_id}/reject
  -> draft status rejected
  -> ai_draft.rejected event
  -> UI clears Draft Preview Tree
```

## 6. UI Event Contract

前端不直接理解各 Agent Runtime 的原始事件。

前端只消费平台统一事件：

```text
run.created
run.started
run.message
run.waiting_for_input
run.completed
run.failed
run.cancelled

capability.invocation.requested
capability.invocation.completed
capability.invocation.failed

draft.preview.started
draft.preview.node_upserted
draft.preview.node_updated
draft.preview.edge_upserted
draft.preview.edge_updated
draft.preview.node_removed
draft.preview.validation_updated
draft.preview.evidence_linked
draft.preview.completed

ai_draft.created
ai_draft.edited
ai_draft.rejected
ai_draft.apply_started
ai_draft.applied
ai_draft.apply_failed

workspace_revision.changed

projection.rebuild.started
projection.rebuild.completed
projection.rebuild.failed
```

## 7. Draft Preview Event Payload

### 7.1 node_upserted

```json
{
  "event_type": "draft.preview.node_upserted",
  "run_id": "run_001",
  "draft_preview_id": "preview_001",
  "node": {
    "temp_id": "tmp_node_001",
    "artifact_type": "fmea.analysis_item",
    "label": "Fan bearing wear",
    "parent_temp_id": "tmp_node_parent",
    "status": "generating",
    "payload": {},
    "evidence_refs": [],
    "validation": []
  }
}
```

### 7.2 edge_upserted

```json
{
  "event_type": "draft.preview.edge_upserted",
  "run_id": "run_001",
  "draft_preview_id": "preview_001",
  "edge": {
    "temp_id": "tmp_edge_001",
    "relation_type": "fmea.causes",
    "source_temp_id": "tmp_node_001",
    "target_temp_id": "tmp_node_002",
    "status": "generating",
    "payload": {}
  }
}
```

### 7.3 validation_updated

```json
{
  "event_type": "draft.preview.validation_updated",
  "run_id": "run_001",
  "draft_preview_id": "preview_001",
  "target_ref": {
    "target_type": "node",
    "target_id": "tmp_node_001"
  },
  "validation": {
    "severity": "warning",
    "message": "Evidence is based on historical FMEA reference."
  }
}
```

## 8. Tree Node State

结构树节点需要状态，而不是只有文本。

建议状态：

```text
confirmed
generating
candidate_new
candidate_updated
candidate_deleted
warning
blocking
applied
rejected
stale
```

状态来源：

```text
confirmed
  from working projection

generating / candidate_*
  from draft preview events or draft patches

warning / blocking
  from validation result

applied / rejected
  from AI Draft Batch status

stale
  from projection freshness
```

## 9. Frontend State Model

前端建议分几个 store。

```text
WorkspaceStore
  workspace_id
  project_id
  current_revision
  selected_plugin_id

ProjectionStore
  working_projection
  export_projection
  freshness
  loading / error

RunStore
  active_run_id
  run_status
  messages
  runtime_events

LivePreviewStore
  draft_preview_id
  preview_nodes
  preview_edges
  preview_status

AiDraftStore
  draft_batch
  draft_patches
  validation_result

SelectionStore
  selected_node_ref
  selected_patch_ref
  selected_evidence_ref
```

UI 组件只读 store，不直接调用底层服务。

命令通过 API client 或 command service 发出。

## 10. Component Boundary

为了后续替换 UI 组件，组件必须按数据契约分层。

### 10.1 Container Components

```text
WorkspacePage
  负责组装布局和数据订阅。

StructureTreePanel
  负责连接 projection / preview / selection store。

ConversationPanel
  负责 run、message、user input。

DraftConfirmPanel
  负责 draft batch、patch、apply / reject。
```

### 10.2 Pure View Components

```text
TreeView
TreeNode
NodeStatusBadge
ConversationTimeline
MessageBubble
DraftPatchList
ValidationList
EvidenceList
```

Pure View Components 不直接请求 API。

它们只接收 props：

```text
nodes
edges
selectedId
status
markers
onSelect
onExpand
```

这样后续替换树组件、对话组件、详情组件时，不影响平台数据流。

## 11. Tree Data Contract

前端树组件统一使用 UI Tree Model。

```ts
type UiTreeNode = {
  id: string
  source: 'projection' | 'draft_preview' | 'ai_draft'
  artifactId?: string
  draftPatchId?: string
  tempId?: string
  artifactType: string
  label: string
  parentId?: string
  children?: UiTreeNode[]
  status: UiTreeNodeStatus
  markers: UiTreeMarker[]
  payloadSummary?: Record<string, unknown>
}
```

```ts
type UiTreeMarker = {
  kind: 'new' | 'updated' | 'deleted' | 'warning' | 'blocking' | 'evidence'
  message?: string
  refId?: string
}
```

`UiTreeNode` 是前端视图模型，不是后端事实模型。

## 12. Projection To Tree

Projection payload 由插件定义，但 UI 需要统一入口。

插件应声明 view metadata：

```text
view_id
projection_kind
view_type = tree
node_mapping
label_field
parent_field
status_field
actions
```

前端转换流程：

```text
working projection payload
  -> plugin view metadata
  -> UiTreeNode[]
  -> TreeView
```

如果插件没有提供完整 mapping，平台可以使用默认 adapter。

## 13. Draft Patch To Tree

Draft Patch 转树时要合并 Working Tree 和 Draft Patch。

流程：

```text
Working Tree
  + Draft Patches
  -> Draft Preview Tree
```

Patch 映射：

```text
create_artifact
  -> candidate_new node

update_artifact
  -> candidate_updated node

delete_artifact
  -> candidate_deleted node

create_edge / update_edge / delete_edge
  -> update relationship markers
```

UI 不直接修改 confirmed node。

用户编辑草稿时，修改的是 draft patch：

```text
PATCH /api/ai-drafts/{draft_batch_id}/patches/{draft_patch_id}
```

## 14. Right Conversation Panel

右侧对话框不是独立聊天系统。

它是当前 workspace / project / session 的 Agent 控制面板。

右侧输入会创建或继续 run：

```text
User input
  -> start run / send run input
  -> runtime events
  -> draft preview events
  -> AI Draft Batch
```

右侧必须显示：

```text
current goal
run status
agent message
capability invocation summary
question_to_user
draft created notice
apply / reject actions
```

右侧不直接显示完整底层 JSON，除非进入开发调试模式。

## 15. Command Flow

### 15.1 Start Run

```text
Right Panel submit
  -> POST /api/sessions/{session_id}/runs
  -> RunStore.active_run_id = run_id
  -> subscribe /api/runs/{run_id}/events
```

### 15.2 Apply Draft

```text
Apply button
  -> POST /api/ai-drafts/{draft_batch_id}/apply
  -> wait ai_draft.applied
  -> wait projection.rebuild.completed
  -> refetch working projection
```

### 15.3 Reject Draft

```text
Reject button
  -> POST /api/ai-drafts/{draft_batch_id}/reject
  -> clear LivePreviewStore
  -> clear AiDraftStore active draft
```

### 15.4 Select Tree Node

```text
Tree node selected
  -> SelectionStore.selected_node_ref
  -> optional detail drawer loads detail from projection payload / draft patch
```

## 16. Freshness Rules

前端必须显式处理 projection freshness。

规则：

```text
fresh
  projection.source_revision == workspace.current_revision

stale
  projection.source_revision < workspace.current_revision
```

UI 行为：

```text
fresh
  normal display

stale
  show stale marker
  disable start run if fresh projection required
  allow user / system trigger rebuild

rebuilding
  show loading state in tree

failed
  show rebuild error and retry action
```

## 17. Extensible UI Component Model

后续可能引入不同前端 UI 组件。

必须保持以下边界：

```text
Component reads UiTreeNode / ConversationEvent / DraftPatchView.
Component does not read raw artifacts table.
Component does not call plugin handler.
Component does not apply draft directly except through Platform API.
Component does not own business state.
```

可替换组件：

```text
TreeView
ConversationTimeline
DraftPatchList
EvidencePanel
ValidationPanel
NodeDetailDrawer
```

不可替换的数据契约：

```text
Projection payload
AI Draft Batch / Draft Patch
Runtime Event Envelope
Draft Preview Event
UiTreeNode adapter contract
```

## 18. MVP UI Scope

第一阶段必须实现：

```text
Workspace / Project header
Left Structure Tree Panel
Right Conversation Panel
Run Event Stream
Live Draft Preview Tree
Persisted AI Draft Preview
Apply / Reject
Projection refresh after apply
Node selection
Basic evidence marker
Basic validation marker
```

第一阶段暂不实现：

```text
完整表格编辑器
复杂拖拽重排
多人协同编辑
插件自定义 React 组件
完整 API Push panel
复杂权限 UI
规则配置 UI
```

## 19. Acceptance Criteria

MVP UI 验收：

```text
1. 用户打开项目后，左侧看到 fresh Working Tree。
2. 用户在右侧输入目标并启动 run。
3. AI 生成过程中，左侧出现 Draft Preview Tree 或节点状态变化。
4. 右侧能看到 Agent run 状态和关键消息。
5. AI Draft Batch 创建后，左侧能显示新增 / 修改候选节点。
6. 用户可以 apply draft。
7. Apply 后左侧 Working Tree 更新到新 revision。
8. Draft Preview Tree 被清理。
9. Projection stale / rebuilding / failed 状态有明确 UI 状态。
10. 前端没有把 preview 当作事实源。
```

## 20. 与其他文档关系

本文补充：

```text
ARCHITECTURE.md
MVP_PLAN.md
DEVELOPMENT_PLAN.md
DEVELOPMENT_ENTRY_PLAN.md
PLATFORM_API_DESIGN.md
PROJECTION_DESIGN.md
AI_DRAFT_VERSION_DESIGN.md
```

后续如需设计视觉和具体组件库，再单独补：

```text
WORKSPACE_UI_STYLE_GUIDE.md
AI_DRAFT_CONFIRM_UI_DESIGN.md
```
