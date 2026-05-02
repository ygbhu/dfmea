# Runtime Sandbox 详细设计

日期：2026-05-01

## 1. 设计目标

Runtime Sandbox 定义 Agent Runtime 执行时的文件、命令、网络和临时工作目录边界。

它解决的是：

```text
Agent Runtime 运行时能接触什么环境资源？
CLI Agent 是否可以读写文件？
是否允许 shell / network？
Agent 生成的临时文件如何处理？
```

它不解决：

```text
业务权限
企业审批
业务数据写入
AI Draft apply
API Push execute
```

业务能力入口仍然是 Workspace Capability Server。

## 2. 核心定位

Runtime Sandbox 和 Workspace Capability Server 是两层边界。

```text
Workspace Capability Server
  控制 Agent 能调用哪些工作区业务能力。

Runtime Sandbox
  控制 Agent Runtime 进程能访问哪些系统资源。
```

Agent 可以通过 Workspace Capability Server 使用业务能力，但不能因为获得 sandbox 文件访问权就绕过平台协议写业务数据。

## 3. 默认策略

第一阶段默认保守：

```text
database_access = false
filesystem_write = false
shell_command = false
network_access = false
secret_access = false
```

Runtime 默认只能访问：

```text
Execution Context
Capability Manifest
Workspace Capability Server
Knowledge Capability
runtime options
```

## 4. Sandbox Workspace

如果某个 CLI Agent 必须依赖工作目录运行，平台为每次 run 创建独立 sandbox workspace。

原则：

- 每个 run 独立目录。
- 不放数据库凭证。
- 不放完整业务数据。
- 只放本次 run 必需的上下文摘要、schema 引用和临时材料。
- Agent 在目录内生成的文件不是事实源。
- 需要进入业务状态的内容必须通过 AI Draft Batch。

建议结构：

```text
.runtime-sandbox/
  run_001/
    context/
    schemas/
    temp/
    outputs/
    logs/
```

## 5. 文件访问策略

第一阶段建议只支持三档：

```text
none
read_only_sandbox
read_write_sandbox
```

不允许：

```text
读取项目根目录任意文件
读取数据库配置
读取系统用户目录
写入插件目录
写入平台源代码目录
```

如果用户上传临时资料，应由平台复制或投影到 sandbox 的受控目录，而不是把原始项目目录直接暴露给 Agent。

## 6. Shell 策略

第一阶段默认不开放 shell。

如果后续必须开放，应采用 allowlist：

```text
allowed_commands
max_runtime_seconds
max_output_size
working_directory = sandbox workspace
env_allowlist
```

禁止：

```text
读取 secret
启动后台服务
访问数据库命令行
修改平台代码
修改插件代码
删除 sandbox 外文件
```

## 7. Network 策略

第一阶段默认不开放外网访问。

Agent 需要知识检索时，应通过：

```text
workspace.knowledge.retrieve
workspace.knowledge.get_evidence
```

如果后续开放网络，应采用 allowlist：

```text
allowed_hosts
allowed_methods
timeout
max_response_size
```

成熟系统 API Push 不应由 Runtime Sandbox 直接访问，应由 API Push Service / Adapter 执行。

## 8. 环境变量和密钥

Runtime Provider 不应把平台密钥注入 Agent 进程。

禁止注入：

```text
database url
database password
external system token
secret store credential
admin token
```

如果某个 provider 需要模型密钥，应由 Runtime Provider 自己的配置管理，且不能被 Agent capability 返回或写入 sandbox 输出。

## 9. 运行事件

第一阶段记录轻量事件：

```text
sandbox.created
sandbox.policy_applied
sandbox.cleaned
sandbox.failed
```

记录内容：

```text
run_id
provider_id
sandbox_id
policy
workspace_path hash
created_at
cleaned_at
status
```

事件用于问题排查，不作为业务事实源。

## 10. 生命周期

建议流程：

```text
Runtime Service creates run
  -> Sandbox Service creates sandbox workspace
  -> Runtime Provider starts Agent in sandbox
  -> Agent uses Workspace Capability Server
  -> Runtime finishes
  -> Platform persists run result / AI Draft proposal
  -> Sandbox Service cleans or archives logs
```

清理策略：

```text
completed run: 清理临时文件，保留必要日志摘要
failed run: 保留短期诊断材料
cancelled run: 尽快终止进程并清理
```

## 11. 与 AI Draft 的关系

Sandbox 文件不是业务数据源。

Agent 在 sandbox 中生成的任何内容，只有通过以下路径才进入工作区：

```text
Workspace Capability Server
  -> workspace.ai_draft.propose
  -> AI Draft Batch
  -> User Confirm / Edit / Apply
  -> Workspace Current Data
```

这保证 Agent 看起来能自然工作，但业务状态仍由平台统一管理。

## 12. 第一阶段实现边界

第一阶段必须定义：

- sandbox policy。
- per-run sandbox workspace。
- 默认禁止 database / shell / network / unrestricted filesystem。
- sandbox 生命周期。
- sandbox 事件。
- Runtime Provider 启动时绑定 sandbox。

第一阶段暂不实现：

- remote sandbox。
- container 编排。
- 复杂命令 allowlist UI。
- 企业级安全审计。
- sandbox 内文件作为事实源。
- Agent 直接访问成熟系统 API。

## 13. 待决问题

后续需要确认：

- 第一阶段是否创建真实 sandbox 目录，还是只做 policy 占位。
- 本地 CLI Agent 是否需要 read_write_sandbox。
- failed run 的 sandbox 日志保留多久。
- 是否需要按 provider 定义不同默认策略。
- shell 能力是否永久不开放，还是作为开发模式能力。
