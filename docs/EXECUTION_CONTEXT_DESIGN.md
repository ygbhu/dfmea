# Execution Context 详细设计

日期：2026-05-01

## 1. 设计目标

Execution Context 定义一次 Agent 执行过程中：

```text
能看到什么
能调用什么 capability
基于哪个 workspace revision
能生成什么 AI Draft
输出必须符合什么契约
```

它不是 prompt 模板，也不是完整业务数据包。

它是平台发给 Agent Runtime、Agent Native Plugin、Workspace Capability Server、Domain Plugin Skill 的受控执行契约。

## 2. 核心定位

Execution Context 的定位：

```text
scope
+ capability manifest
+ fresh read access
+ draft policy
+ output contract
+ revision binding
+ audit metadata
```

不是：

```text
完整业务数据包
数据库连接
自由文件工作区
插件私有状态容器
长期 memory
```

原则：

```text
Agent 看到 workspace capabilities。
Skill 看到受控 service facade。
Service 才能操作事实层。
Repository 只在 Service 内部使用。
```

## 3. Context 类型

第一阶段定义三类：

```text
Run Execution Context
Capability Execution Context
Skill Execution Context
```

### 3.1 Run Execution Context

面向一次 Agent run。

由 Runtime Service 创建，并传给 Agent Runtime Provider / Agent Native Plugin。

包含：

- 用户目标。
- Execution Scope。
- active domain plugin。
- base_workspace_revision。
- Capability Manifest。
- projection refs / summaries。
- knowledge retrieval policy。
- draft policy。
- output contract。
- runtime constraints。

### 3.2 Capability Execution Context

面向一次 capability invocation。

由 Workspace Capability Server 创建。

包含：

- 当前 run。
- capability_id。
- invocation_id。
- arguments。
- timeout。
- scope。
- correlation id。
- base_workspace_revision。
- audit metadata。

### 3.3 Skill Execution Context

面向插件 skill handler。

由 Workspace Capability Server 在调用 skill 时创建。

包含：

- Execution Scope。
- plugin_id / skill_id。
- base_workspace_revision。
- allowed service facades。
- fresh projection access。
- knowledge / evidence access。
- validation access。
- AI draft proposal access。
- event recorder。

Skill Handler 不能拿数据库连接，不能绕过平台服务写 current data。

## 4. Execution Scope

最小字段：

```text
user_id
workspace_id
project_id
session_id
run_id
plugin_id
```

可选字段：

```text
draft_batch_id
projection_id
invocation_id
skill_id
correlation_id
```

规则：

- 所有 capability invocation 必须绑定 scope。
- 所有 Skill 执行必须绑定 scope。
- 所有 Projection 查询必须校验 scope。
- 所有 Knowledge retrieve 必须校验 scope。
- 所有 AI Draft proposal 必须绑定 scope。
- 禁止跨 workspace / project / session 读取未授权数据。

## 5. Context Pack

Context Pack 是传给 Agent Runtime 的轻量上下文包。

它不包含完整业务数据。

它包含：

```text
task goal
scope summary
active plugin summary
capability manifest
projection summaries
evidence refs
draft policy
output contract
constraints
base_workspace_revision
```

示例：

```json
{
  "goal": "基于当前项目资料生成一版质量分析初稿",
  "scope": {
    "workspace_id": "ws_001",
    "project_id": "proj_001",
    "session_id": "sess_001",
    "run_id": "run_001"
  },
  "plugin": {
    "plugin_id": "dfmea",
    "version": "0.1.0"
  },
  "base_workspace_revision": 12,
  "capabilities": [
    "workspace.projection.get",
    "workspace.knowledge.retrieve",
    "workspace.knowledge.get_evidence",
    "workspace.ai_draft.propose",
    "workspace.ai_draft.validate",
    "workspace.question.ask_user"
  ],
  "draft_policy": "propose_draft",
  "output_contract": "ai_draft_proposal"
}
```

Agent 需要更多信息时，通过 Workspace Capability Server 按需获取。

## 6. Projection Access

Context 不直接塞完整 projection payload。

Context 只携带：

```text
projection ref
projection kind
projection category
source_revision
summary
freshness status
```

读取流程：

```text
Agent
  -> workspace.projection.get
  -> Workspace Capability Server
  -> Projection Service
  -> freshness check
  -> return projection payload or stale error
```

规则：

- AI 在线查询不能静默读取 stale projection。
- API Push 必须读取 fresh export projection。
- Projection 不作为写入入口。

## 7. Knowledge Access

Context 不携带大段资料全文。

Context 只携带：

```text
knowledge policy
allowed knowledge base types
evidence refs
retrieval constraints
```

知识库类型：

```text
temporary
project
public
historical_fmea
```

历史 FMEA 是参考知识，不是当前工作区事实。

基于知识生成业务内容时，必须进入 AI Draft Batch。

## 8. Draft Policy

Execution Context 必须携带 draft policy。

第一阶段建议：

```text
propose_draft
apply_requires_user
force_apply_allowed_by_user
```

默认：

```text
propose_draft
```

含义：

- Agent 可以生成 AI Draft Batch。
- 默认不直接 apply 到 current data。
- 用户在 UI 中 confirm / edit / apply。

Force Apply 可作为用户显式动作预留。

## 9. Capability Permission

Capability Manifest 必须声明本次 run 可用能力。

Workspace Capability Server 每次 invocation 都重新校验：

```text
capability in current manifest
run status active
scope allowed
draft policy allowed
runtime capability allowed
plugin capability allowed
input schema valid
projection freshness policy
knowledge policy
rate limit / timeout
```

禁止能力：

```text
database.query_raw
database.execute_raw
artifact.update_direct
edge.update_direct
projection.update_direct
mature_system.write_direct
filesystem.write
shell.run
```

## 10. Output Contract

Execution Context 必须告诉 Agent 输出什么结构。

第一阶段建议：

```text
ai_draft_proposal
question_to_user
validation_result
summary
candidate_result
api_push_validation_result
```

### 10.1 ai_draft_proposal

必须能转换为：

```text
ai_draft_batch
draft_patches
evidence_links
```

Agent 不能只输出自然语言结果让平台猜测如何落库。

### 10.2 question_to_user

信息不足时进入：

```text
run.waiting_for_input
question event
UI prompt
```

### 10.3 validation_result

用于 AI Draft 或 API Push 的校验结果。

不直接修改 current data。

## 11. Revision / Freshness

Context 必须绑定版本。

最小字段：

```text
base_workspace_revision
context_created_at
projection_refs[].source_revision
```

规则：

- Run 启动时记录 `base_workspace_revision`。
- Projection 查询时检查 freshness。
- AI Draft Batch 记录 base revision。
- Apply 前检查 workspace current_revision。
- revision 冲突时拒绝 apply 或要求用户显式 force apply。

## 12. Context 生命周期

### 12.1 创建

Run Context 在 start run 时创建。

创建时：

- 校验 scope。
- 读取 workspace current revision。
- 选择 active domain plugin。
- 选择 runtime provider。
- 生成 Capability Manifest。
- 生成 Context Pack。

### 12.2 使用

Agent Runtime 使用 Run Context 启动 agent。

Agent 发起 capability invocation 时，Workspace Capability Server 创建 Capability Context。

调用 plugin skill 时，创建 Skill Context。

### 12.3 更新

Context 不应频繁原地变更。

用户补充输入或 workspace revision 改变时，应记录事件，并在必要时创建新的 context snapshot。

### 12.4 结束

Run 完成、失败或取消后，Context 进入只读状态。

## 13. Context Snapshot

平台应保存轻量 Context Snapshot。

保存：

```text
scope
goal
active plugin
runtime provider
capability manifest
draft policy
output contract
base_workspace_revision
projection refs
knowledge policy
created_at
```

不保存完整业务数据。

## 14. Agent-Facing Context

Agent-Facing Context 包含：

- 目标。
- 当前任务边界。
- 可用 capabilities。
- 约束。
- 输出格式。
- 必要 projection summary。
- 必要 evidence refs。

不包含：

- 数据库 schema。
- Repository API。
- 平台内部 service 细节。
- 未授权项目数据。
- 大段完整业务数据。

## 15. Skill-Facing Context

Skill-Facing Context 提供受控 service facade。

示例：

```text
projectionFacade.getFreshProjection(kind, scope)
knowledgeFacade.retrieve(query, filters)
evidenceFacade.getEvidence(evidence_ref)
aiDraftFacade.propose(patches)
validatorFacade.validate(payload)
eventFacade.record(event)
questionFacade.askUser(question)
```

这些 facade 不是数据库连接。

## 16. 安全边界

- Runtime Provider 不获得数据库连接。
- Agent 不获得 raw SQL 能力。
- Skill 不获得 raw database handle。
- Plugin 不保存运行态事实。
- Capability Invocation 不能跨 scope。
- Knowledge retrieve 必须受 scope 限制。
- stale Projection 不能被 AI 静默使用。
- AI Draft apply 必须经过受控服务。

## 17. 典型流程

### 17.1 Start Run

```text
UI start run
  -> Platform API
  -> Runtime Service
  -> Scope Service validates scope
  -> Workspace Service reads current_revision
  -> Plugin Service resolves plugin capabilities
  -> Projection Service prepares refs / summaries
  -> Workspace Capability Server creates Capability Manifest
  -> Run Context created
  -> Runtime Provider starts agent
```

### 17.2 Capability Invocation

```text
Agent invokes capability
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Capability Context created
  -> permission check
  -> dispatch to Platform Service / Plugin Skill
  -> result returned
  -> event recorded
```

### 17.3 AI Draft Proposal

```text
Agent proposes draft
  -> workspace.ai_draft.propose
  -> AI Draft Service
  -> draft_patches created
  -> user confirm / edit / apply
  -> no current data mutation before apply
```

## 18. 第一阶段实现边界

第一阶段必须定义：

- Run Execution Context。
- Capability Execution Context。
- Skill Execution Context。
- Execution Scope。
- Context Pack。
- Capability Manifest。
- Draft Policy。
- Output Contract。
- base_workspace_revision。
- projection freshness check。
- Context Snapshot。

第一阶段暂不实现：

- 长期 agent memory。
- 自动跨 session memory。
- 完整权限系统。
- 完整上下文压缩策略。
- 多 agent 共享上下文协议。
- Agent 直接数据库访问。
- Skill 直接数据库访问。
- 把完整项目业务数据塞进 prompt。

## 19. 待决问题

后续需要确认：

- Context Snapshot 是否单独建表，还是存到 run metadata。
- Context Pack 的最大大小限制。
- Projection summary 由平台生成还是插件生成。
- Capability Permission 是否需要 policy DSL。
- Skill facade 的代码接口形式。
- 用户补充输入是否生成新的 context snapshot。
- 多 Runtime Provider 的 context 格式差异如何归一。
