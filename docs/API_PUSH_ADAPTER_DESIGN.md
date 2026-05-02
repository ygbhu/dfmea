# API Push Adapter 详细设计

日期：2026-05-01

> 本设计是 API Push / 成熟系统集成的后续阶段设计。
> 第一条可运行主流程先不实现成熟系统 API，也不要求 API Push validate / execute。
> 主流程先跑通 AI Draft Apply、Workspace Revision、Projection Rebuild 和 fresh export projection。

## 1. 设计目标

本设计定义平台如何把 AI 生成并经过 User Confirm 的结构化结果推送到成熟质量系统。

第一阶段只规划：

```text
api_push
```

即：

```text
平台 export projection
  -> API Push Adapter
  -> 成熟 DFMEA/PFMEA 系统 API
```

暂不规划文件导出、离线包导出或手动下载。

## 2. 核心定位

API Push Adapter 是平台到外部成熟系统的转换和推送层。

它不是：

```text
平台事实层
插件运行态
外部系统同步引擎
反向导入器
文件导出中心
```

核心原则：

```text
Export 必须基于 fresh export projection。
API Push Adapter 不直接读取 artifacts / artifact_edges。
API Push 是异步 Job。
成熟系统不是平台事实源。
API Push 成功不反向覆盖 canonical state。
```

## 3. 导出链路

固定链路：

```text
Artifact / Edge canonical state
  -> Projection Service
  -> fresh export projection
  -> API Push Service
  -> API Push Adapter
  -> Mature Quality System API
  -> api_push_record / push result
```

说明：

- Artifact / Edge 是平台当前事实。
- Export Projection 是面向目标导出场景的读模型。
- API Push Service 负责创建 job、校验门禁、调度 adapter、记录结果。
- API Push Adapter 负责目标系统 payload mapping 和 API 调用。

## 4. Export Projection

API Push 必须读取 export projection。

不允许 Adapter 直接从底层 canonical 表拼业务数据。

原因：

- 插件最了解业务数据如何组织成导出视图。
- Projection Service 可以统一处理 freshness。
- Export Gate Validation 可以复用 projection schema。
- 外部系统适配不污染 canonical model。

Export projection 必须包含：

```text
projection_id
project_id
plugin_id
kind
category = export
source_revision
payload
payload_schema
metadata
```

fresh 条件：

```text
projection.source_revision == workspace.current_revision
```

如果 export projection stale，API Push 必须拒绝或先触发 rebuild。

## 5. API Push 模式

第一阶段支持两个模式。

### 5.1 validate_only / dry_run

只校验 payload，不正式写入成熟系统。

用途：

- 推送前检查目标系统是否接受 payload。
- 提前发现字段缺失、枚举不匹配、引用不合法。
- 给用户 User Confirm / Export 前确认。

链路：

```text
API Push Service
  -> API Push Adapter.validate(payload)
  -> Mature System validate endpoint
  -> validation response
  -> api_push_job result
```

### 5.2 execute

正式推送成熟系统 API。

链路：

```text
API Push Service
  -> API Push Adapter.push(payload, idempotency_key)
  -> Mature System API
  -> external response
  -> api_push_record
```

正式推送前建议先执行 validate_only。

第一阶段可以允许用户显式跳过 validate_only，但必须记录事件。

## 6. API Push Job

API Push 必须作为异步 Job 执行。

不建议让 UI 请求同步等待外部系统完成。

状态建议：

```text
created
validating
validation_failed
ready_to_push
pushing
completed
failed
partial_failed
cancelled
```

第一阶段可以简化为：

```text
created
running
completed
failed
```

但结果中必须记录 validate / push 阶段。

API Push Job 至少包含：

```text
api_push_job_id
workspace_id
project_id
plugin_id
adapter_id
mode
status
source_projection_id
source_workspace_revision
idempotency_key
request_summary
result
error
created_by
created_at
started_at
completed_at
```

## 7. API Push Record

API Push Record 记录一次成功或失败的外部推送结果。

至少包含：

```text
api_push_record_id
api_push_job_id
workspace_id
project_id
plugin_id
adapter_id
external_system
external_system_id
external_job_id
external_record_id
external_status
source_projection_id
source_workspace_revision
payload_checksum
response_summary
error_code
error_message
created_at
```

API Push Record 只记录外部推送结果。

它不是平台事实源。

## 8. Revision Binding

API Push 必须绑定项目版本。

必须记录：

```text
source_projection_id
source_workspace_revision
projection_source_revision
ai_draft_id optional
snapshot_id optional
```

规则：

- source_workspace_revision 必须等于 export projection source_revision。
- export projection source_revision 必须等于 workspace.current_revision。
- 如果项目 revision 变化，旧 api_push_job 不应继续 execute，除非用户显式确认重新基于旧 revision 推送。

第一阶段建议：

```text
只允许推送当前 fresh revision。
```

## 9. Idempotency

API Push 必须支持幂等。

避免：

- 用户重复点击。
- 网络超时后重试。
- worker 重启重复执行。
- 外部系统响应丢失导致重复创建。

建议 idempotency key：

```text
project_id
+ source_workspace_revision
+ adapter_id
+ api_push_job_id
```

生成示例：

```text
idem_proj_001_rev_12_adapter_x_job_001
```

如果成熟系统支持幂等键，应传给成熟系统。

如果成熟系统不支持，平台也必须记录本地 idempotency，防止重复触发同一 job。

## 10. Adapter Interface

第一阶段定义统一 API Push Adapter Interface。

```text
getCapabilities()
validate(payload, context)
push(payload, context)
getStatus(external_job_id, context)
```

### 10.1 getCapabilities

返回目标系统能力。

示例：

```json
{
  "adapter_id": "mature-system-x",
  "supports_validate": true,
  "supports_push": true,
  "supports_status_query": true,
  "supports_idempotency_key": true,
  "supports_partial_success": false
}
```

### 10.2 validate

只校验，不写外部系统。

输入：

```text
export projection payload
adapter config
source_workspace_revision
```

输出：

```text
validation success / failed
external validation findings
normalized error
```

### 10.3 push

正式调用成熟系统 API。

输入：

```text
export projection payload
idempotency_key
adapter config
source_workspace_revision
```

输出：

```text
external status
external ids
external response summary
normalized error
```

### 10.4 getStatus

用于查询外部异步任务状态。

第一阶段可选。

如果成熟系统 API 是同步响应，可以先不实现。

## 11. Payload Mapping

Payload Mapping 由 API Push Adapter 负责。

输入：

```text
export projection payload
```

输出：

```text
mature system API payload
```

规则：

- Adapter 不直接读取 artifact / edge。
- Adapter 不修改 export projection。
- Adapter 不写 canonical state。
- Adapter 可以做字段映射、枚举转换、单位转换、目标系统结构转换。
- Mapping 错误必须结构化返回。

如果不同成熟系统字段差异很大，每个成熟系统一个 adapter。

不要在平台核心做多个成熟系统的大量 if/else。

## 12. Export Gate Validation

API Push 前必须执行 Export Gate Validation。

检查：

```text
export projection exists
export projection fresh
export projection payload schema valid
source_workspace_revision recorded
adapter available
adapter capabilities match mode
no blocking validation findings
idempotency_key generated
```

Validation 失败时：

- 不调用成熟系统 API。
- api_push_job 标记 failed。
- 返回结构化错误。

## 13. Error Handling

外部 API 错误必须归一化。

统一错误结构：

```json
{
  "code": "EXTERNAL_VALIDATION_FAILED",
  "message": "Mature system rejected the payload.",
  "details": {
    "external_code": "FIELD_REQUIRED",
    "external_message": "risk_level is required"
  }
}
```

常见错误码：

```text
EXPORT_PROJECTION_MISSING
EXPORT_PROJECTION_STALE
EXPORT_PAYLOAD_INVALID
EXPORT_ADAPTER_NOT_FOUND
EXPORT_ADAPTER_UNAVAILABLE
EXPORT_IDEMPOTENCY_CONFLICT
EXTERNAL_AUTH_FAILED
EXTERNAL_TIMEOUT
EXTERNAL_VALIDATION_FAILED
EXTERNAL_PUSH_FAILED
EXTERNAL_PARTIAL_FAILED
EXTERNAL_STATUS_UNKNOWN
```

错误需要进入：

```text
api_push_job.error
api_push_record.error
event / audit
UI API Push panel
```

## 14. Retry Policy

API Push 可以重试，但必须受控。

可重试：

```text
network timeout
temporary unavailable
rate limited
external 5xx
```

不可直接重试：

```text
payload validation failed
auth failed
schema invalid
idempotency conflict
permission denied
```

重试必须使用同一个 idempotency_key。

第一阶段建议：

```text
max_retries = 3
exponential backoff
```

具体实现可后续细化。

## 15. Security / Configuration

API Push Adapter 需要外部系统配置。

示例：

```text
base_url
auth_type
credential_ref
timeout
tenant_id
environment
```

规则：

- 密钥不写入 manifest。
- 密钥不写入 api_push_job 明文。
- Adapter 通过配置或 secret store 获取凭据。
- API Push event 不记录敏感请求头。
- Payload 中敏感字段需要脱敏记录。

第一阶段可以先用本地配置，但接口要预留 credential_ref。

## 16. External System Boundary

成熟系统不是平台事实源。

API Push 成功后，平台只记录：

```text
推送了什么
基于哪个 revision
推送到哪个系统
外部系统返回了什么 id/status
```

API Push 不反向修改：

```text
artifact
edge
projection
ai_draft
workspace current_revision
```

如果后续需要读取成熟系统修改，应单独设计：

```text
Import Adapter
Sync Adapter
Reconciliation
```

不要让 API Push Adapter 顺手承担同步职责。

## 17. Event / Audit

API Push 过程必须记录事件。

事件示例：

```text
api_push.job.created
api_push.validation.started
api_push.validation.completed
api_push.execute.started
api_push.execute.completed
api_push.execute.failed
api_push.execute.partial_failed
```

事件至少包含：

```text
api_push_job_id
project_id
source_workspace_revision
adapter_id
mode
status
error summary
created_at
```

事件不是事实源。

它用于 UI 展示、审计和问题排查。

## 18. 第一阶段实现边界

第一阶段必须规划：

- `api_push`。
- `validate_only / dry_run`。
- 异步 api_push job。
- export projection freshness check。
- Export Gate Validation。
- payload mapping。
- API Push Adapter Interface。
- idempotency key。
- external response record。
- status tracking。
- error mapping。
- retry policy。

第一阶段暂不规划：

- Excel / CSV / JSON 文件导出。
- package export。
- 手动下载。
- 离线导入包。
- 外部系统反向同步。
- 多成熟系统复杂编排。
- 成熟系统作为平台事实源。
- API Push Adapter 直接读取 artifact / edge。
- API Push Adapter 反向覆盖 canonical state。

## 19. 待决问题

后续需要确认：

- 第一阶段对接哪个成熟系统 API。
- 成熟系统是否支持 validate endpoint。
- 成熟系统是否支持幂等键。
- 外部系统认证方式。
- API Push payload 的最小字段。
- api_push_job 是否需要独立 worker。
- partial_failed 是否第一阶段需要。
- API Push 成功后是否需要 UI 展示外部系统链接。
- Adapter 配置保存在哪里。
