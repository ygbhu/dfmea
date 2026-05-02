# MVP Plan

日期：2026-05-01

> 本文定义 MVP 范围。
> 具体进入开发时，以 `DEVELOPMENT_PLAN.md` 的阶段顺序和验收标准为准。

## 1. MVP 定位

MVP 目标是验证：

```text
AI-first Quality Engineering Workspace
```

不是验证完整企业级 FMEA 管理系统。

第一阶段只做 AI 工作区核心闭环：

```text
User Goal
  -> Agent Runtime
  -> Agent Native Plugin
  -> Workspace Capability Server
  -> Domain Plugin Skill
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Workspace Current Data
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Knowledge Query
```

API Push / 成熟系统 API 作为后续扩展，不阻塞第一条主流程。

## 2. 第一阶段必须验证

### 2.1 Agent 原生接入

- 选择一个主 Agent Runtime。
- 提供 Agent Native Plugin。
- Agent 能发现 workspace resources / capabilities / prompts。
- Agent 能通过 Workspace Capability Server 调用平台能力。

### 2.2 Domain Plugin

- 提供一个最小 DFMEA Domain Plugin。
- DFMEA 业务逻辑以 `DFMEA_PLUGIN_DESIGN.md` 为准。
- 插件声明 schema、skill、projection handler、export projection。
- Skill 必须有代码 handler。
- Prompt 只是辅助资源。

### 2.3 AI Draft / Version

- Agent 生成 AI Draft Batch。
- AI Draft Batch 包含 Draft Patch。
- 用户可以 edit / apply / reject。
- Apply 后更新 workspace current data。
- Apply 后 workspace revision +1。

### 2.4 Projection

- 构建 working projection。
- 构建 export projection。
- AI/UI 读取 fresh projection。
- Apply 后 projection 标记 stale 并 rebuild。

### 2.4.1 Workspace UI Data Flow

- 左侧展示 Working Tree。
- 右侧展示 AI Conversation。
- AI 生成过程中左侧展示 Draft Preview Tree。
- Draft Preview Tree 不作为事实源。
- Apply 后刷新 fresh Working Tree。

### 2.5 Knowledge

- 接入 Knowledge Provider Interface。
- 至少支持 project knowledge 和 historical FMEA knowledge。
- AI 能检索 evidence。
- AI 生成草稿时能关联 evidence_ref。

### 2.6 API Push

- 架构上保留 API Push。
- 第一条主流程不实现成熟系统 API。
- 第一条主流程不要求 API Push validate / execute。
- 先保证 export projection 可以基于 fresh workspace revision 构建。
- 后续再实现 API Push job / adapter / record。

### 2.7 Runtime Sandbox

- Runtime 默认不能直连数据库。
- 默认不开放 shell、外网和非受控文件写入。
- 如 CLI Agent 需要工作目录，使用 per-run sandbox workspace。
- sandbox 文件不是业务事实源，业务结果必须进入 AI Draft Batch。

## 3. 第一阶段不做

```text
企业权限
审批流
签核
正式发布
完整审计
完整 rollback
完整 time travel
文件导出主线
插件 marketplace
远程插件安装
成熟系统反向同步
成熟系统 API / API Push execute
Agent 直连数据库
Agent 直接访问成熟系统 API
```

## 4. 最小数据对象

```text
workspaces / projects / sessions
runs / run_events / capability_invocations
artifacts / artifact_edges
ai_draft_batches / draft_patches
workspace_revision_events
projections
evidence_refs / evidence_links
```

API Push 后续扩展数据对象：

```text
api_push_jobs / api_push_records
```

## 5. 最小能力

Workspace Capability Server 第一阶段提供：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user
```

默认不开放：

```text
workspace.ai_draft.apply
workspace.api_push.execute
database.query_raw
shell.run
filesystem.write
```

`apply` 优先由用户在 UI 中触发。
`api_push.execute` 后续由用户在 UI 中触发，不进入第一条主流程。

## 6. 验收标准

MVP 完成时应能演示：

1. 用户创建工作区和 session。
2. Agent 通过原生插件看到工作区能力。
3. Agent 检索项目资料和历史 FMEA。
4. Agent 调用插件 skill 生成 AI Draft Batch。
5. 用户查看、编辑并 apply AI Draft。
6. Workspace Revision 递增。
7. Projection rebuild 后 AI/UI 能读取 fresh projection。
8. Export projection 能基于 fresh workspace revision 构建。
9. 左侧结构树能实时展示 AI Draft Preview，并在 apply 后切换为 confirmed Working Tree。

## 7. 后续增强

MVP 后再考虑：

- Draft compare。
- Snapshot。
- Rollback。
- 更复杂插件业务规则。
- 多 Agent Native Plugin。
- Remote Runtime Sandbox。
- API Push validate / execute。
- 多成熟系统 Adapter。
