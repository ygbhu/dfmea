# Agent Runtime Provider 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义平台如何接入外部 Agent Runtime。

平台不自研完整 agent loop，也不绑定某一个具体 agent。

第一阶段参考 AionUi 这类项目的思路：把多个 CLI agent 统一接入、统一管理、统一事件化，但不把业务状态交给 CLI agent。

目标：

```text
Platform Core Services
  负责业务调度、状态边界、AI Draft Batch、User Confirm、Projection、Export

Agent Runtime Provider
  负责 agent 执行、推理、工具调用、流式事件

Domain Plugin Skills
  作为业务能力暴露给 Agent Runtime
```

## 2. 核心定位

Agent Runtime Provider 是外部 agent runtime 的适配层。

第一阶段重点支持 CLI Agent Provider。

候选 CLI agent：

```text
OpenCode CLI
Codex CLI
Claude Code CLI
Qwen Code CLI
Future CLI Agent
```

暂不重点设计：

```text
LangGraph Provider
AutoGen Provider
CrewAI Provider
```

这些后续可以通过新的 provider 接入。

## 3. 参考 AionUi 的点

AionUi 的价值在于统一接入和管理多个 CLI agent。

本平台借鉴：

- Provider Registry
- CLI Process Adapter
- Unified Event Stream
- Session Mapping
- Agent Native Plugin / MCP Capability Adapter
- Capability Detection
- Local-first Runtime

本平台不照搬：

- 不把 UI 做成纯 agent GUI。
- 不让 agent 管理业务状态。
- 不把文件工作区作为主数据层。
- 不让 CLI agent 绕过平台协议写业务数据。

## 4. 总体架构

```text
Platform Core Services
  |
  v
Agent Runtime Hub
  |
  +-- Runtime Provider Registry
  +-- CLI Process Adapter
  +-- Runtime Event Normalizer
  +-- Workspace Capability Server
  +-- Capability Detector
  |
  v
CLI Agent Provider
  |
  +-- OpenCode CLI
  +-- Codex CLI
  +-- Claude Code CLI
  +-- Qwen Code CLI
```

业务能力调用链路：

```text
CLI Agent Runtime
  -> Workspace Capability Server
  -> Workspace Capabilities
  -> Platform Core Services
  -> PostgreSQL
```

CLI agent 可以操作业务数据，但必须通过平台暴露的业务能力或 Platform API。

CLI agent 不能直接连接数据库，不能绕过 AI Draft Batch / User Confirm / Projection 协议。

## 5. 职责边界

### 5.1 Platform Core Services

负责：

- 创建和管理 session。
- 选择 Domain Plugin。
- 选择 Agent Runtime Provider。
- 构建 Execution Context。
- 注册本次可用 capabilities。
- 接收 runtime events。
- 归一化 runtime 输出。
- 创建 AI Draft proposal。
- 进入 User Confirm。
- 写入 Canonical Store。
- 触发 Projection rebuild。

不负责：

- agent loop。
- LLM planning。
- capability selection reasoning。
- runtime-level retry。
- agent memory。

### 5.2 Agent Runtime Provider

负责：

- 启动 agent runtime。
- 向 runtime 发送任务。
- 接收 runtime 输出。
- 映射 runtime events。
- 处理 cancel。
- 声明 runtime capabilities。
- 支持 capability invocation bridge。

不负责：

- 业务状态存储。
- Artifact 写入。
- AI Draft Batch apply。
- User Confirm。
- Projection。
- Export。

### 5.3 Domain Plugin Skill

Skill 是业务能力。

Agent Runtime 可以调用 skill，但 skill 执行仍受平台控制。

Skill handler 可以执行：

- 读取 Execution Context。
- 查询 fresh projection。
- 检索 knowledge。
- 调用 LLM 或确定性逻辑。
- 返回 AI Draft patch / validation result / question。

Skill handler 不直接自由写数据库。

## 6. Provider Interface

第一阶段 Runtime Provider Interface 建议保持简单。

```text
detect()
getCapabilities()
startRun(request)
sendInput(run_id, input)
streamEvents(run_id)
cancel(run_id)
```

### 6.1 detect

检测 provider 是否可用。

返回：

```text
installed
binary_path
version
health_status
missing_dependencies
```

### 6.2 getCapabilities

返回 provider 能力。

示例：

```json
{
  "provider_id": "opencode",
  "provider_type": "cli_agent",
  "supports_streaming": true,
  "supports_workspace_capabilities": true,
  "supports_cancel": true,
  "supports_resume": false,
  "supports_multimodal": false,
  "supports_mcp": true,
  "supports_local_file_access": true
}
```

平台根据能力决定是否启用某些功能。

### 6.3 startRun

启动一次 runtime 执行。

输入是 Runtime Request。

输出：

```text
run_id
provider_id
status
started_at
```

`status` 必须使用统一 Run Lifecycle 状态。

### 6.4 sendInput

向运行中的 runtime 发送用户输入或平台反馈。

用于：

- 用户追加说明。
- User Confirm 后继续。
- runtime 请求澄清。

### 6.5 streamEvents

返回统一事件流。

不同 CLI agent 的 stdout、stderr、capability events、message events 都必须被映射为平台 runtime event。

### 6.6 cancel

取消运行中的 runtime。

取消后必须产生统一事件：

```text
runtime.cancelled
```

## 7. Runtime Request

Platform Core Services 发送给 Runtime Provider 的请求。

示例：

```json
{
  "run_id": "run_001",
  "workspace_id": "ws_001",
  "project_id": "proj_001",
  "session_id": "sess_001",
  "plugin_id": "dfmea",
  "goal": "生成冷却风扇系统 DFMEA 初稿",
  "execution_context": {},
  "capabilities": [],
  "knowledge_capabilities": [],
  "draft_policy": "propose_changes",
  "output_contract": {},
  "runtime_options": {}
}
```

关键约束：

- `execution_context` 由平台裁剪。
- `capabilities` 由平台显式暴露。
- `knowledge_capabilities` 由平台按 policy 暴露。
- `draft_policy` 由平台决定。
- `output_contract` 约束 runtime 最终输出。

Runtime 不应自行扩大数据读取范围。

## 8. Run Lifecycle

每次 runtime 执行都必须有统一生命周期。

建议状态：

```text
created
starting
running
waiting_for_input
waiting_for_capability
completed
failed
cancelled
timeout
```

状态含义：

- `created`：平台已创建 run，但 provider 尚未启动。
- `starting`：provider 正在启动进程或连接 runtime。
- `running`：runtime 正在执行。
- `waiting_for_input`：runtime 需要用户或平台补充输入。
- `waiting_for_capability`：runtime 已请求平台能力调用，等待平台返回结果。
- `completed`：runtime 正常完成。
- `failed`：runtime 执行失败。
- `cancelled`：用户或平台取消。
- `timeout`：超过运行时间限制。

每次状态变化都必须产生 runtime event。

Platform Session 与 Runtime Run 是不同概念。

一个 Session 可以包含多个 Run。

## 9. Workspace Capability Server

Workspace Capability Server 用于把平台业务能力暴露给 Agent Runtime。

Capability 可以来自：

- Workspace Capabilities
- Domain Plugin Skills
- Knowledge Capabilities
- Validation Capabilities
- Export Preparation Capabilities

### 9.1 Capability 声明

Capability 必须结构化声明：

```json
{
  "capability_id": "dfmea.generate_initial_analysis",
  "name": "Generate DFMEA Initial Draft",
  "description": "Generate an initial DFMEA draft for the selected project scope",
  "input_schema": {},
  "output_schema": {}
}
```

### 9.2 Capability Invocation Protocol

Agent Runtime 发起能力调用时，必须被平台归一成统一 Capability Invocation Envelope。

建议结构：

```json
{
  "invocation_id": "ci_001",
  "run_id": "run_001",
  "session_id": "sess_001",
  "capability_id": "dfmea.generate_initial_analysis",
  "arguments": {},
  "status": "accepted",
  "timeout_ms": 60000,
  "created_at": "2026-05-01T00:00:00Z"
}
```

Capability result 建议结构：

```json
{
  "invocation_id": "ci_001",
  "status": "completed",
  "result": {},
  "error": null,
  "completed_at": "2026-05-01T00:00:01Z"
}
```

失败时：

```json
{
  "invocation_id": "ci_001",
  "status": "failed",
  "result": null,
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Capability input does not match schema"
  },
  "completed_at": "2026-05-01T00:00:01Z"
}
```

Capability invocation 状态：

```text
accepted
running
completed
failed
cancelled
timeout
denied
invalid_arguments
```

### 9.3 Capability 执行边界

Agent Runtime 可以发起 capability invocation。

实际执行由平台 Workspace Capability Server 完成。

```text
Agent Runtime
  -> capability invocation
  -> Workspace Capability Server
  -> Skill Handler / Platform Service
  -> structured capability result
  -> Agent Runtime
```

这样 agent 可以操作业务数据，但不会绕过平台协议。

### 9.4 高层业务能力

不要只暴露低级 CRUD。

应优先暴露高层业务能力：

```text
workspace.projection.get
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
workspace.ai_draft.propose
workspace.ai_draft.validate
workspace.question.ask_user

dfmea.generate_initial_analysis
dfmea.expand_failure_chains
dfmea.suggest_actions
dfmea.validate_analysis
```

`workspace.api_push.validate` 在 API Push 阶段再开放。

这些 capability 背后可以写数据库，但必须经过：

- scope 校验
- schema 校验
- AI Draft Batch
- User Confirm
- Event
- Projection dirty

### 9.5 Workspace Capability Server 实现策略

不同 CLI agent 支持外部能力接入的方式不同。

可能方式：

```text
MCP
stdio protocol
HTTP callback
native capability calling
shell command wrapper
text protocol adapter
```

第一阶段优先选择一种实现方式，并保持 Workspace Capability Server 内部可替换。

默认建议：

```text
优先支持 Agent Native Plugin、MCP Server 或平台托管的 HTTP/stdio Capability Server。
```

平台核心不依赖某一个具体 runtime 能力协议。

## 10. Runtime Output

Runtime 最终输出必须被归一成 Runtime Result。

推荐结果类型：

```text
ai_draft_proposal
question
validation_result
no_op
failed
```

示例：

```json
{
  "run_id": "run_001",
  "status": "completed",
  "result_type": "ai_draft_proposal",
  "result": {},
  "events": [],
  "usage": {},
  "warnings": []
}
```

Runtime 不直接创建正式 AI Draft Batch 表记录。

Runtime 只输出 proposal payload。

Platform Core Services 接收结果后，再交给 AI Draft Service 创建正式 AI Draft Batch。

随后进入：

```text
AI Draft Service
User Confirm UI
Artifact Service
Projection Service
```

Runtime 不直接决定最终写入。

### 10.1 结构化输出失败

CLI agent 可能输出自然语言或不符合 schema 的 JSON。

平台必须处理结构化输出失败。

建议策略：

```text
parse failed
  -> 尝试一次 repair
  -> 仍失败则 runtime.failed

schema invalid
  -> 返回 validation error 给 runtime
  -> 可重试一次
  -> 仍失败则 runtime.failed

ambiguous result
  -> 生成 question 或交给用户确认
```

失败不能直接写入 canonical store。

## 11. Runtime Event

不同 provider 的事件必须统一。

建议基础事件：

```text
runtime.started
runtime.message
runtime.thinking
runtime.capability_invocation.started
runtime.capability_invocation.completed
runtime.result.proposed
runtime.failed
runtime.cancelled
runtime.completed
```

事件至少包含：

```text
event_id
run_id
provider_id
session_id
event_type
payload
created_at
```

UI 只消费统一 runtime event，不直接解析不同 CLI agent 的原始输出。

## 12. Session Mapping

平台 session 与 runtime run 是不同概念。

```text
Platform Session
  用户业务分析会话。

Runtime Run
  某次 agent runtime 执行。
```

一个 Platform Session 可以包含多个 Runtime Run。

例如：

```text
session_001
  run_001 generate initial draft
  run_002 revise after user confirm
  run_003 export preparation
```

Runtime run 不拥有业务状态。

业务状态仍由平台 session、artifact、AI Draft Batch、User Confirm、projection 管理。

## 13. Capability Detection

Provider 必须声明能力，平台不能假设所有 runtime 能力一致。

常见能力：

```text
streaming
workspace_capabilities
mcp
cancel
resume
multimodal
local_file_access
network_access
structured_output
```

平台根据能力决定：

- 是否启用流式事件。
- 是否启用 Workspace Capability Server。
- 是否允许 resume。
- 是否允许文件访问。
- 是否需要 fallback provider。

## 14. CLI Sandbox / 安全与数据边界

Runtime Provider 不应获得数据库连接。

Runtime Provider 只能访问：

- Execution Context。
- 平台暴露的 capabilities。
- 平台暴露的 knowledge capabilities。
- 本次 runtime options。

如果某个 CLI agent 支持文件、命令或网络访问，必须由平台 policy 控制。

平台必须控制：

- 可访问 workspace。
- 可访问 project。
- 可访问 knowledge base。
- 可调用 capabilities。
- 是否允许 file access。
- 是否允许 network access。
- 是否允许 force apply。

### 14.1 默认安全策略

第一阶段默认策略应保守。

建议默认：

```text
file_access = false
network_access = false
shell_command = false
database_access = false
```

只允许 runtime 访问：

```text
Execution Context
Workspace Capability Server
Knowledge Capabilities
Runtime Options
```

如果某个 CLI agent 必须使用工作目录，应使用平台创建的 sandbox workspace。

### 14.2 CLI Sandbox Workspace

每个 runtime run 应有独立 sandbox workspace。

原则：

- 不放数据库凭证。
- 不放完整项目资料。
- 只放本次 run 必需的上下文。
- 由平台控制生命周期。
- run 结束后可清理或归档日志。

sandbox workspace 不是业务主存储。

CLI agent 在 sandbox 中产生的文件不是事实源。

需要进入业务状态的内容，必须通过 Workspace Capability Server / Platform API 进入 canonical store。

## 15. 审计信息

每次 Runtime Run 应记录审计信息。

建议记录：

```text
run_id
provider_id
provider_version
agent_name
agent_version
model_name
model_version
prompt_version
capability_list
knowledge_refs
execution_context_hash
token_usage
started_at
completed_at
status
```

这些信息用于解释 AI 当时为什么产生某个结果。

## 16. 第一阶段实现边界

第一阶段目标：

- 实现 Runtime Provider Interface。
- 实现一个 CLI Agent Provider。
- 实现 Workspace Capability Server。
- 实现统一 Capability Invocation Envelope。
- 实现 run lifecycle。
- 实现统一 Runtime Event。
- 支持 provider capability detection。
- 支持 cancel。
- 支持 Runtime Result 归一。
- 支持 CLI sandbox workspace。

第一阶段暂不实现：

- 多 provider 同时运行。
- agent-to-agent 协作。
- 完整 checkpoint / resume。
- 长期 agent memory。
- 复杂 runtime fallback 策略。
- LangGraph / AutoGen / CrewAI provider。

## 17. 待决问题

后续需要确认：

- 第一阶段选择哪个 CLI agent 作为默认 provider。
- 是否优先支持 MCP Bridge。
- CLI agent 的工作目录如何隔离。
- CLI agent 是否允许文件访问。
- Runtime events 如何映射不同 CLI agent 的原始输出。
- Capability invocation 协议采用 provider 原生能力还是平台包装协议。
- 是否需要支持 runtime run 的持久化 resume。
