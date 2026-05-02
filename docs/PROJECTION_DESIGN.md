# Projection / AI Read Model 详细设计

日期：2026-05-01

## 1. 设计目标

Projection 是从 canonical store 构建出来的任务友好读模型。

它面向：

- AI 在线查询
- UI 展示
- User Confirm
- Export

Projection 解决两个问题：

```text
底层 Artifact / Edge 对 AI 不够友好。
AI 不能静默读取旧数据。
```

Projection 不是事实源。

任何修改必须回到 Artifact / Edge，然后重建 Projection。

## 2. 核心原则

### 2.1 Projection 不是事实源

Projection 可以删除、过期、重建。

Projection 不作为业务写入入口。

### 2.2 AI 只读 fresh Projection

AI 在线查询默认只读取 fresh projection。

不能静默读取 stale projection。

### 2.3 Plugin 定义业务 Projection

平台只定义 projection 通用壳。

Domain Plugin 定义：

- projection kind
- payload schema
- rebuild handler
- 依赖的 artifact / edge / evidence
- 是否需要向量索引

### 2.4 MVP 使用 project-level freshness

第一阶段采用 project-level freshness。

任何 canonical apply 成功后：

```text
workspace.current_revision += 1
projection_dirty = true
```

后续再扩展 scope-level dirty 和 incremental rebuild。

## 3. Projection 分类

平台层只定义通用分类，不定义具体业务内容。

### 3.1 working projection

用于 AI 工作过程。

可以包含：

- draft
- proposed
- confirmed
- applied

但必须标注状态。

### 3.2 draft preview projection

用于 User Confirm 前的草案影响预览。

重点展示：

- AI Draft Batch 影响范围
- 新增内容
- 修改内容
- 废弃内容
- validation issue
- evidence refs

### 3.3 export projection

用于导出。

默认只包含：

- confirmed
- applied

不应包含未确认 proposal。

### 3.4 evidence pack

用于 AI 和用户理解证据来源。

它由 Knowledge & Evidence Layer 生成或参与构建。

### 3.5 summary / dossier / list_view

常见读模型类别：

```text
summary
  项目或任务摘要。

dossier
  围绕某个业务对象的完整上下文。

list_view
  面向表格、列表和筛选的查询视图。
```

具体 projection 名称由插件定义。

## 4. Projection 定义

Projection 至少包含：

```text
projection_id
workspace_id
project_id
session_id
plugin_id
kind
scope_id
source_revision
schema_version
payload
validation_status
updated_at
```

字段含义：

- `kind`：projection 类型。
- `scope_id`：projection 绑定范围。
- `source_revision`：构建时对应的 workspace revision。
- `schema_version`：payload schema 版本。
- `payload`：由插件 schema 约束的 JSONB。

## 5. Freshness 模型

### 5.1 Workspace Revision

Workspace 逻辑上保存当前事实修订号：

```text
workspace.current_revision
projection_dirty
```

MVP 物理实现中，当前事实修订号读取 `projects.workspace_revision`。

每次 canonical apply 成功后：

```text
workspace.current_revision += 1
projection_dirty = true
```

### 5.2 Projection Source Revision

每个 projection 保存：

```text
source_revision
```

fresh 判断：

```text
projection.source_revision == workspace.current_revision
```

### 5.3 Stale Handling

当 projection stale 时，平台可以采用：

```text
rebuild_then_return
return_stale_error
return_stale_with_flag
```

默认策略：

```text
AI 查询：rebuild_then_return
UI 查询：可返回 stale_with_flag
Export 查询：必须 rebuild_then_return 或失败
```

AI 不允许静默使用 stale projection。

## 6. Rebuild 策略

### 6.1 MVP 策略

第一阶段采用：

```text
project-level full rebuild
```

优点：

- 实现简单。
- 状态清晰。
- 不需要 dependency graph。

缺点：

- 项目大后成本较高。

### 6.2 后续扩展

后续支持：

```text
scope-level dirty
projection dependency graph
incremental rebuild
affected_artifacts
affected_edges
affected_projections
rebuild queue
```

## 7. Plugin Rebuild Handler

Projection rebuild 由平台调度，由插件提供 handler。

Plugin rebuild handler 负责：

- 读取当前 scope 内 artifact / edge / evidence。
- 构建 projection payload。
- 校验 projection schema。
- 返回 projection result。

平台负责：

- 调用 handler。
- 保存 projection。
- 更新 source_revision。
- 记录 event。
- 更新向量索引。

Plugin handler 不直接写 projection 表。

## 8. AI 查询接口

AI 通过平台接口查询 projection。

建议接口：

```text
getFreshProjection(kind, scope_id)
queryProjection(kind, filters)
getEvidencePack(scope_id)
```

AI 查询默认要求 fresh。

如果 projection stale：

- 自动 rebuild。
- 或返回 stale error。

查询返回应包含：

```text
projection payload
source_revision
freshness status
evidence refs
```

## 9. UI 消费接口

UI 可以消费 projection。

UI 查询可以允许 stale 标记。

原因：

- UI 可以展示“数据待刷新”。
- 用户可以手动触发 rebuild。
- UI 不应静默把 stale projection 当成最新结果。

UI 主要消费：

- working projection
- draft preview projection
- export projection preview
- summary
- list_view
- dossier

## 10. Export Projection

API Push Adapter 必须基于 export projection。

Export projection 必须 fresh。

导出前检查：

- export projection fresh
- validation passed
- required User Confirm / Apply 状态已完成
- source version bound

Export projection 不包含未确认 proposal。

## 11. Vector Index

部分 projection 可以进入向量索引。

适合向量化：

```text
summary
dossier
evidence_pack
draft preview projection
```

向量检索应结合结构化过滤：

```text
workspace_id
project_id
plugin_id
projection_kind
scope_id
source_revision
```

向量索引不能绕过 freshness。

如果 projection stale，对应 embedding 也应视为 stale。

## 12. 事件记录

Projection 相关事件：

```text
projection.dirty
projection.rebuild.started
projection.rebuild.completed
projection.rebuild.failed
projection.queried
projection.stale_detected
```

这些事件用于调试、审计和性能分析。

## 13. 第一阶段实现边界

第一阶段必须实现：

- projection 表
- workspace.current_revision
- projection_dirty
- source_revision
- project-level full rebuild
- getFreshProjection
- export projection freshness check
- rebuild events

第一阶段暂不实现：

- scope-level dirty
- dependency graph
- incremental rebuild
- rebuild queue
- projection-level ACL
- complex projection cache eviction

## 14. 待决问题

后续需要确认：

- AI 查询 stale projection 时默认自动 rebuild 还是返回 stale error。
- UI 是否默认触发 rebuild。
- Projection payload 是否需要保存构建摘要。
- Vector index 更新是否同步执行还是异步执行。
- project-level rebuild 的性能边界。
