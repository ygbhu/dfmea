# DFMEA Plugin Design

日期：2026-05-01

## 1. 定位

本文定义第一阶段 DFMEA Domain Plugin 的业务逻辑边界。

DFMEA Plugin 的目标不是复刻完整传统 DFMEA 软件，也不是替代成熟 FMEA 系统。

第一阶段目标是让 AI 能围绕一个设计对象快速生成、修改、查询和沉淀 DFMEA 草稿，并把结果进入平台统一数据闭环：

```text
User Goal
  -> Agent Runtime
  -> Workspace Capability Server
  -> dfmea plugin skill
  -> AI Draft Batch
  -> User Confirm / Apply
  -> artifacts / artifact_edges
  -> Workspace Revision +1
  -> Projection Rebuild
  -> Working Tree / Export Projection
```

DFMEA Plugin 只负责 DFMEA 业务语义：

```text
artifact type
edge type
schema
skill handler
validator
projection builder
view metadata
```

平台核心不写死 DFMEA 字段，也不创建 DFMEA 专用业务表。

## 2. 参考旧项目后的取舍

当前 `legacy/dfmea-cli-prototype/` 是早期 DFMEA CLI / skill 原型。

可复用：

```text
SYS / SUB / COMP / FN / REQ / CHAR / FM / FE / FC / ACT 对象模型
父子层级约束
失效链一次性创建思想
FM 关联 REQ / CHAR 的规则
ACT 归属于 FM 且 target_causes 指向同一 FM 下 FC 的规则
FE / FC 跨层 trace 到 FM 的规则
AP 简化计算规则
component bundle / function dossier / by AP / action backlog 等投影视角
冷却风扇真实案例作为 MVP 验收样例
```

不复用：

```text
SQLite 作为事实源
Markdown 作为业务存储
CLI-first 产品形态
rowid 作为业务引用方式
旧项目的文件型版本管理
```

新平台中的替代关系：

| 旧项目概念 | 新平台实现 |
| --- | --- |
| nodes 表 | artifacts |
| fm_links 表 | artifact_edges |
| SQLite 事务写入 | AI Draft apply transaction |
| rowid 引用 | artifact_id / draft temp_ref |
| CLI command | plugin skill handler / platform capability |
| projection table | projections |
| Markdown export | 后续 exporter，不作为事实源 |

## 3. Artifact Types

DFMEA Plugin 第一阶段定义以下 artifact type。

| Type | 含义 | 旧模型 |
| --- | --- | --- |
| `dfmea.system` | 系统 | SYS |
| `dfmea.subsystem` | 子系统 | SUB |
| `dfmea.component` | 零部件 / 组件 | COMP |
| `dfmea.function` | 功能 | FN |
| `dfmea.requirement` | 需求 | REQ |
| `dfmea.characteristic` | 特性 | CHAR |
| `dfmea.failure_mode` | 失效模式 | FM |
| `dfmea.failure_effect` | 失效后果 | FE |
| `dfmea.failure_cause` | 失效原因 | FC |
| `dfmea.action` | 预防 / 探测措施 | ACT |

所有 artifact 都必须有平台生成的稳定 `artifact_id`。

业务显示 ID 只作为可读字段存在，不作为内部主键：

```text
SYS-001
SUB-001
COMP-001
FN-001
FM-001
ACT-001
```

第一阶段允许只有 `dfmea.system`、`dfmea.subsystem`、`dfmea.component`、`dfmea.function`、`dfmea.failure_mode`、`dfmea.action` 分配 display id。

`dfmea.requirement`、`dfmea.characteristic`、`dfmea.failure_effect`、`dfmea.failure_cause` 可以不分配 display id，但仍然必须有稳定 `artifact_id`。

### 3.1 DFMEA Analysis Anchor

DFMEA 的业务分析锚点是 `dfmea.function`。

原因：

```text
DFMEA 关注设计功能如何失效。
失效模式本质上是功能没有正确实现、没有按要求实现，或在不期望场景下发生。
需求、特性、失效模式都应围绕功能组织。
```

因此第一阶段 DFMEA 业务规则采用：

```text
component
  -> function
    -> requirement
    -> characteristic
    -> failure_mode
```

但这只是 DFMEA 插件的业务分析主线，不是平台存储硬约束。

平台仍然使用通用 `artifacts / artifact_edges`：

```text
结构树用于导航。
function 用于 DFMEA 分析聚合。
failure_mode 用于失效链展开。
projection 提供多种读取视角。
```

后续 PFMEA 不应被迫复用 `dfmea.function`。

平台可以在插件层抽象为：

```text
Analysis Anchor
```

不同插件可以定义自己的分析锚点：

```text
DFMEA: dfmea.function
PFMEA: pfmea.process_step 或 pfmea.process_function
Control Plan: control_plan.process_operation 或 control_plan.characteristic
```

## 4. Artifact Payload

### 4.1 通用字段

每个 DFMEA artifact 的 payload 至少支持：

```json
{
  "title": "string",
  "description": "string",
  "display_id": "string|null",
  "source": "ai|user|import|migration",
  "confidence": 0.85
}
```

说明：

```text
title 用于树和列表显示。
description 用于业务解释。
display_id 用于人类阅读和成熟系统映射。
source 表示对象来源。
confidence 表示 AI 生成置信度，可选。
```

### 4.2 结构对象

`dfmea.system`、`dfmea.subsystem`、`dfmea.component`：

```json
{
  "title": "Electronic Cooling Fan Controller",
  "description": "Controller assembly used for fan control",
  "display_id": "COMP-001"
}
```

### 4.3 Function

`dfmea.function`：

```json
{
  "title": "Control fan start and stop",
  "description": "Command fan start and stop according to cooling demand",
  "display_id": "FN-001"
}
```

### 4.4 Requirement

`dfmea.requirement`：

```json
{
  "title": "Start fan within demanded cooling window",
  "description": "Start fan within demanded cooling window",
  "requirement_source": "CTRL-REQ-START"
}
```

### 4.5 Characteristic

`dfmea.characteristic`：

```json
{
  "title": "Fan start response time",
  "description": "Fan start response time",
  "target_value": "500",
  "unit": "ms"
}
```

### 4.6 Failure Mode

`dfmea.failure_mode`：

```json
{
  "title": "Fan not started when cooling requested",
  "description": "Fan not started when cooling requested",
  "display_id": "FM-001",
  "severity": 8
}
```

### 4.7 Failure Effect

`dfmea.failure_effect`：

```json
{
  "title": "Required airflow not delivered",
  "description": "Required airflow not delivered",
  "effect_level": "system"
}
```

`effect_level` 第一阶段不做强枚举，可保留为字符串。

### 4.8 Failure Cause

`dfmea.failure_cause`：

```json
{
  "title": "Temperature signal biased low",
  "description": "Temperature signal biased low",
  "occurrence": 4,
  "detection": 4,
  "ap": "High"
}
```

`severity` 属于 FM。

`occurrence`、`detection`、`ap` 属于 FC。

### 4.9 Action

`dfmea.action`：

```json
{
  "title": "Add sensor plausibility and output-stage feedback diagnostics",
  "description": "Add sensor plausibility and output-stage feedback diagnostics",
  "display_id": "ACT-001",
  "kind": "detection",
  "status": "planned",
  "owner": "Controls",
  "due": "2026-07-01",
  "effectiveness_status": "pending",
  "revised_severity": null,
  "revised_occurrence": null,
  "revised_detection": null
}
```

允许值：

```text
kind: prevention / detection
status: planned / in-progress / completed
effectiveness_status: pending / verified-effective / verified-ineffective
```

## 5. Edge Types

DFMEA Plugin 第一阶段定义以下 edge type。

| Edge Type | From | To | 含义 |
| --- | --- | --- | --- |
| `dfmea.subsystem_of_system` | subsystem | system | 子系统属于系统 |
| `dfmea.component_of_subsystem` | component | subsystem | 组件属于子系统 |
| `dfmea.function_of_component` | function | component | 功能属于组件 |
| `dfmea.requirement_of_function` | requirement | function | 需求属于功能 |
| `dfmea.characteristic_of_function` | characteristic | function | 特性属于功能 |
| `dfmea.failure_mode_of_function` | failure_mode | function | 失效模式属于功能 |
| `dfmea.effect_of_failure_mode` | failure_effect | failure_mode | 失效后果属于失效模式 |
| `dfmea.cause_of_failure_mode` | failure_cause | failure_mode | 失效原因属于失效模式 |
| `dfmea.action_of_failure_mode` | action | failure_mode | 措施属于失效模式 |
| `dfmea.action_targets_cause` | action | failure_cause | 措施针对某个原因 |
| `dfmea.fm_violates_requirement` | failure_mode | requirement | 失效模式违反需求 |
| `dfmea.fm_related_characteristic` | failure_mode | characteristic | 失效模式关联特性 |
| `dfmea.trace.effect_to_failure_mode` | failure_effect | failure_mode | 后果追溯到下游失效模式 |
| `dfmea.trace.cause_to_failure_mode` | failure_cause | failure_mode | 原因追溯到上游失效模式 |

方向规则：

```text
树形父子关系统一用 child -> parent。
跨层 trace 保持 source -> target failure_mode。
UI 构建树时按 edge type 反向或正向读取，由 projection handler 统一封装。
```

## 6. 业务规则

### 6.1 层级规则

DFMEA 中 `function` 是分析锚点。

允许的主层级：

```text
system
  -> subsystem
    -> component
      -> function
        -> requirement
        -> characteristic
        -> failure_mode
          -> failure_effect
          -> failure_cause
          -> action
```

约束：

```text
system 只能作为根结构对象。
subsystem 必须属于 system。
component 必须属于 subsystem。
function 必须属于 component。
requirement / characteristic / failure_mode 必须属于 function。
failure_effect / failure_cause / action 必须属于 failure_mode。
```

说明：

```text
Function Dossier 是 DFMEA 的核心业务阅读视角。
Component Bundle 是组件视角的汇总阅读视角。
Risk List 是风险优先级视角。
Trace View 是跨功能或跨层级影响视角。
```

因此，功能是 DFMEA 分析组织中心，但 UI、AI 查询和导出不只能按功能单一视角工作。

### 6.2 失效链原子创建

AI 或用户创建一条失效链时，应该一次性生成以下对象和关系：

```text
FM
optional FE[]
optional FC[]
optional ACT[]
FM -> FN
FE -> FM
FC -> FM
ACT -> FM
ACT -> FC
FM -> REQ
FM -> CHAR
```

一条失效链在 AI Draft 中可以拆成多个 Draft Patch，但 apply 时必须作为一个 batch 事务提交。

如果其中任意对象或关系校验失败，整批 draft 不能部分 apply。

### 6.3 Action Target Cause

`dfmea.action_targets_cause` 必须满足：

```text
action 属于某个 FM。
failure_cause 属于同一个 FM。
action 不能指向其他 FM 下的 cause。
```

AI Draft 中如果 cause 还没有真实 `artifact_id`，必须使用 draft temp ref：

```json
{
  "from_ref": "temp:act:add-diagnostics",
  "to_ref": "temp:fc:temperature-signal-biased-low",
  "edge_type": "dfmea.action_targets_cause"
}
```

apply 时由 AI Draft Service 在同一事务内解析 temp ref。

### 6.4 FM 关联 REQ / CHAR

`dfmea.fm_violates_requirement` 必须满足：

```text
FM 和 REQ 属于同一个 FN，或由插件 validator 允许跨 FN 关联。
第一阶段默认只允许同一个 FN。
```

`dfmea.fm_related_characteristic` 必须满足：

```text
FM 和 CHAR 属于同一个 FN，或由插件 validator 允许跨 FN 关联。
第一阶段默认只允许同一个 FN。
```

### 6.5 S / O / D / AP

第一阶段评分范围：

```text
severity: 1-10
occurrence: 1-10
detection: 1-10
```

AP 规范值：

```text
High
Medium
Low
```

输入兼容值：

```text
H -> High
M -> Medium
L -> Low
```

第一阶段使用旧项目中的简化 AP 计算规则：

```text
if severity >= 9:
  High
else if severity >= 7 and occurrence >= 4 and detection >= 4:
  High
else if severity >= 5 and occurrence >= 7 and detection >= 4:
  High
else if severity <= 3:
  Low
else if severity <= 4 and occurrence <= 4 and detection <= 4:
  Low
else:
  Medium
```

规则：

```text
FC 的 ap 如果缺失，插件 handler 自动计算。
FC 的 ap 如果存在但和计算值不一致，validator 产生 warning。
第一阶段 warning 不阻塞 apply，除非字段越界或枚举非法。
```

### 6.6 Trace Link

跨层 trace 用于表达不同层级失效链之间的影响关系。

允许：

```text
failure_effect -> failure_mode
failure_cause -> failure_mode
```

第一阶段不做复杂循环分析，但 validator 应至少检查：

```text
from / to artifact 存在。
from type 只能是 failure_effect 或 failure_cause。
to type 必须是 failure_mode。
不允许重复 edge。
```

后续可以增加递归 trace projection：

```text
trace_causes
trace_effects
```

### 6.7 删除与修改

第一阶段优先支持：

```text
新增对象
更新对象 payload
新增关系
删除未 apply 的 Draft Patch
```

第一阶段不优先实现复杂级联删除。

如果需要删除已 apply 的 artifact，先按 draft patch 表达为 logical delete：

```text
artifact.status = deleted
edge.status = deleted
```

Projection 默认隐藏 deleted 对象。

物理删除、级联清理、恢复删除属于后续增强。

## 7. Plugin Skills

用户之前已经明确：skill 不应定义过多业务细节，细节应交给代码 handler。

因此第一阶段 DFMEA Plugin 只提供少量任务级 skill。

### 7.1 `dfmea.generate_initial_analysis`

用途：

```text
从用户目标、项目资料、历史资料中生成 DFMEA 初稿。
```

输入：

```json
{
  "project_id": "string",
  "goal": "Generate cooling fan controller DFMEA draft",
  "scope": {
    "system": "Engine Thermal Management System",
    "subsystem": "Cooling Fan System",
    "components": ["Electronic Cooling Fan Controller"]
  },
  "knowledge_refs": ["optional"]
}
```

输出：

```text
AI Draft Proposal
```

Proposal 内含：

```text
artifact create/update patches
edge create patches
draft preview events
validation summary
evidence refs
```

### 7.2 `dfmea.expand_failure_chains`

用途：

```text
围绕已有 component / function 继续补充 FM / FE / FC / ACT。
```

输入重点：

```text
target artifact id
generation depth
knowledge refs
```

输出仍为 AI Draft Proposal。

### 7.3 `dfmea.suggest_actions`

用途：

```text
针对高 AP / 高 severity 的 FC 补充预防或探测措施。
```

输出：

```text
action artifacts
action_of_failure_mode edges
action_targets_cause edges
```

### 7.4 `dfmea.validate_analysis`

用途：

```text
执行 DFMEA 插件业务校验。
```

说明：

```text
平台 Validation Service 负责统一调度。
DFMEA Plugin 提供 schema / rule handler。
```

### 7.5 `dfmea.build_projection`

用途：

```text
构建 DFMEA working / export / preview projection。
```

说明：

```text
通常由 Projection Service 调用，不直接暴露给用户。
```

## 8. AI Draft Patch 规范

DFMEA skill 不直接写 artifacts / artifact_edges。

Skill handler 产出 AI Draft Proposal，平台转成 `ai_draft_batches` 和 `draft_patches`。

### 8.1 Artifact Create Patch

```json
{
  "op": "create_artifact",
  "artifact_type": "dfmea.failure_mode",
  "temp_ref": "temp:fm:fan-not-started",
  "after_payload": {
    "title": "Fan not started when cooling requested",
    "description": "Fan not started when cooling requested",
    "severity": 8,
    "display_id": "FM-001"
  }
}
```

### 8.2 Edge Create Patch

```json
{
  "op": "create_edge",
  "edge_type": "dfmea.failure_mode_of_function",
  "from_ref": "temp:fm:fan-not-started",
  "to_ref": "artifact:fn-existing-id"
}
```

### 8.3 Intra Draft References

同一 draft batch 内新建对象之间的关系必须使用 `temp_ref`。

示例：

```text
temp:fm:fan-not-started
temp:fc:temperature-signal-biased-low
temp:act:add-diagnostics
```

apply 顺序：

```text
1. create artifacts
2. resolve temp_ref -> artifact_id
3. create edges
4. run plugin validation
5. increment workspace revision
6. mark projection stale
```

## 9. Projection

Projection 是 AI 和 UI 的优先读取模型，不是事实源。

DFMEA Plugin 第一阶段至少提供以下 projection。

### 9.1 `dfmea.working_tree`

用途：

```text
左侧结构树
AI 快速读取当前工作区结构
```

节点层级：

```text
system
  subsystem
    component
      function
        requirement
        characteristic
        failure_mode
          failure_effect
          failure_cause
          action
```

每个 tree node 至少包含：

```json
{
  "artifact_id": "string",
  "type": "dfmea.failure_mode",
  "title": "Fan not started when cooling requested",
  "display_id": "FM-001",
  "badges": {
    "severity": 8,
    "ap": "High"
  },
  "children": []
}
```

### 9.2 `dfmea.function_dossier`

用途：

```text
按功能查看完整分析包。
```

内容：

```text
function
requirements
characteristics
failure_modes
effects / causes / actions
evidence links
validation issues
```

### 9.3 `dfmea.component_bundle`

用途：

```text
按组件审阅所有功能和失效链。
```

内容：

```text
component
functions
failure mode count
high AP cause count
open action count
top risks
```

### 9.4 `dfmea.risk_list`

用途：

```text
按 AP / severity 快速筛选风险。
```

第一阶段至少支持：

```text
by_ap
by_severity
action_backlog
```

### 9.5 `dfmea.export_payload`

用途：

```text
生成可给后续成熟系统 API Push adapter 消费的结构化 payload。
```

第一阶段只要求能构建 fresh export projection。

不要求调用成熟系统 API。

## 10. Draft Preview 与 UI 映射

AI 生成过程中，DFMEA Plugin skill 可以发送 draft preview event。

这些事件只服务 UI 实时展示，不是事实源。

左侧结构树应同时支持：

```text
Working Tree: 来源 dfmea.working_tree projection
Draft Preview Tree: 来源 AI Draft Batch / runtime draft preview events
```

DFMEA tree node 的状态：

```text
confirmed: 已 apply 的当前事实
candidate_new: AI 草稿新增
candidate_updated: AI 草稿修改
candidate_removed: AI 草稿删除或隐藏
invalid: 当前草稿存在 blocking validation issue
warning: 当前草稿存在 warning validation issue
```

Apply 后：

```text
Draft Preview Tree 清空或归档。
Projection Service rebuild dfmea.working_tree。
左侧 Working Tree 展示 confirmed 数据。
```

## 11. Validation

DFMEA Plugin validator 第一阶段分为 blocking 和 warning。

### 11.1 Blocking

以下问题阻止 apply：

```text
artifact payload 不符合 schema。
edge from / to 不存在。
edge type 与 artifact type 不匹配。
层级关系非法。
评分字段不在 1-10。
枚举字段非法。
action target cause 不属于同一个 FM。
同一 workspace 内 display id 重复。
同一 batch 内 temp_ref 无法解析。
```

### 11.2 Warning

以下问题不阻止 apply，但需要展示：

```text
AP 手填值与计算值不一致。
高 severity 没有 action。
High AP cause 没有 action。
FM 没有关联 requirement。
FM 没有关联 characteristic。
action 没有 owner 或 due。
AI confidence 过低。
evidence 缺失。
```

## 12. MVP 验收样例

MVP 使用旧项目中的冷却风扇案例作为业务验收样例。

目标：

```text
生成乘用车电子冷却风扇控制器 DFMEA 初稿。
```

结构：

```text
SYS: Engine Thermal Management System
SUB: Cooling Fan System
COMP: Electronic Cooling Fan Controller
COMP: Cooling Fan Motor Assembly
COMP: Coolant Temperature Sensing Path
```

功能示例：

```text
Control fan start and stop
Modulate fan speed
Enter overtemperature protection and report faults
Generate airflow under controller command
Provide coolant temperature signal
```

失效模式示例：

```text
Fan not started when cooling requested
Fan speed below target
Overtemperature protection not entered
Required airflow not delivered
Temperature signal biased low
```

原因示例：

```text
Temperature signal biased low
Driver output stage stuck low
PWM clamp calibrated too low
Low-voltage fallback logic incorrect
Overtemperature threshold set too high
Motor bearing drag high
Sensor pull-up open circuit
```

措施示例：

```text
Add sensor plausibility and output-stage feedback diagnostics
Tighten PWM calibration and low-voltage fallback test coverage
Add threshold boundary tests and watchdog coverage
Add bearing drag screening
Add sensor input plausibility monitor
```

验收：

```text
1. mock runtime 调用 dfmea.generate_initial_analysis。
2. skill 生成包含结构、功能、失效链、措施的 AI Draft Batch。
3. 生成过程中左侧 Draft Preview Tree 能看到候选节点。
4. 用户 apply 后生成 artifacts / artifact_edges。
5. workspace revision +1。
6. dfmea.working_tree projection fresh。
7. dfmea.export_payload projection fresh。
8. AI 能通过 projection 查询 function dossier / risk list。
```

## 13. 后续增强

第一阶段暂不实现，但架构需要兼容：

```text
完整 AIAG-VDA 字段体系
更完整 AP 表
DFMEA 与 PFMEA / Control Plan 之间的跨插件 trace
历史成熟 FMEA 导入并作为 historical_fmea knowledge
成熟系统 API Push adapter
复杂级联删除和恢复
多视图编辑器
插件自定义 UI 组件
```

## 14. 实现边界

开发第一版 DFMEA Plugin 时，必须遵守：

```text
不新增 DFMEA 专用物理业务表。
不把整个 DFMEA 项目塞进一个 JSON 字段。
不让 Agent 直接写数据库。
不把 Markdown 作为业务存储。
不在第一阶段实现成熟系统 API Push。
不把 DFMEA 做成独立 Agent。
```

推荐实现优先级：

```text
1. artifact schemas
2. edge schemas
3. generate_initial_analysis skill handler
4. AI Draft proposal builder
5. DFMEA validator
6. working_tree projection
7. export_payload projection
8. cooling fan MVP test fixture
```
