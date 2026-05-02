# Plugin Registration 详细设计

日期：2026-05-01

## 1. 设计目标

本设计定义第一阶段插件如何被平台发现、校验和注册。

第一阶段不做复杂插件系统。

插件注册采用：

```text
服务启动时扫描本地插件目录
  -> 读取 plugin.json
  -> 最小校验
  -> 注册到 Plugin Service Registry
  -> 当前服务生命周期内可用
```

目标是先让业务插件可插拔，而不是建设 marketplace。

## 2. 第一阶段定位

Plugin Registration 是平台启动过程的一部分。

它负责把本地插件目录转成平台可查询的能力定义。

它不是：

```text
插件市场
远程安装器
热更新系统
复杂版本迁移系统
企业权限系统
运行态状态管理器
```

核心原则：

```text
服务启动时发现。
服务启动时校验。
服务启动时注册。
插件变更后重启生效。
```

## 3. 插件目录

第一阶段使用固定本地目录。

推荐：

```text
plugins/
  dfmea/
    plugin.json
    schemas/
    skills/
    validators/
    projections/
    exporters/
    views/
    prompts/

  pfmea/
    plugin.json
```

目录可以由配置项指定：

```text
PLUGIN_DIR=./plugins
```

平台只扫描该目录下一层插件目录。

不递归扫描任意深层目录。

## 4. 启动扫描流程

服务启动时执行：

```text
1. 读取 PLUGIN_DIR
2. 枚举一级子目录
3. 查找 plugin.json
4. 读取 manifest
5. 执行最小校验
6. 构建 PluginDefinition
7. 注册到内存 Registry
8. 记录加载结果
```

如果目录不存在：

- 没有 required plugin 时，可以继续启动。
- 有 required plugin 时，启动失败。

## 5. 最小校验

第一阶段只做必要校验。

### 5.1 Manifest 校验

必须校验：

```text
manifest_version 存在
plugin.plugin_id 存在
plugin.version 存在
plugin.name 存在
capabilities 结构合法
schemas / skills / validators / projections / exporters / views 类型合法
```

### 5.2 资源路径校验

必须校验：

```text
schema path exists
skill handler_ref exists
validator handler_ref exists
projection handler_ref exists
exporter handler_ref exists
prompt_ref exists if declared
```

### 5.3 引用校验

必须校验：

```text
skill input_schema exists
skill output_schema exists
projection payload_schema exists
exporter source_projection exists
view projection_kind exists
required platform_capabilities known
```

### 5.4 不做的校验

第一阶段暂不做：

```text
复杂依赖解析
schema migration 校验
跨插件依赖版本求解
远程资源签名
插件安全扫描
handler 编译产物校验
```

## 6. Registry 设计

第一阶段以内存 Registry 为主。

注册结果保存在 Plugin Service 内。

建议结构：

```text
PluginRegistry
  plugins: Map<plugin_id, PluginDefinition>
  skills: Map<plugin_id.skill_id, SkillDefinition>
  validators: Map<plugin_id.validator_id, ValidatorDefinition>
  projections: Map<plugin_id.projection_kind, ProjectionDefinition>
  exporters: Map<plugin_id.exporter_id, ExporterDefinition>
  views: Map<plugin_id.view_id, ViewDefinition>
```

Registry 提供查询能力：

```text
getPlugin(plugin_id)
listPlugins()
getSkill(plugin_id, skill_id)
listSkills(plugin_id)
getProjection(plugin_id, kind)
listProjections(plugin_id)
getExporter(plugin_id, exporter_id)
listViews(plugin_id)
```

Registry 不保存运行态业务数据。

## 7. 可选数据库 Snapshot

第一阶段可以选择是否把 manifest snapshot 写入数据库。

可选入库内容：

```text
domain_plugins.manifest
plugin_schemas
plugin_skills
plugin_views
```

用途：

- UI 展示已加载插件。
- 审计当前服务加载了哪些插件。
- 记录 run / AI Draft Batch / projection / export 所用插件版本。

但 MVP 可以先只做内存 Registry。

建议策略：

```text
MVP:
  内存 Registry 必须有。
  manifest snapshot 入库可选。

多实例 / 审计增强后:
  manifest snapshot 入库。
```

## 8. 加载状态

第一阶段只保留简单状态：

```text
loaded
failed
disabled
```

含义：

- `loaded`：加载成功，可被使用。
- `failed`：加载失败，不可使用。
- `disabled`：配置禁用，不加载。

不引入复杂状态：

```text
discovered
validated
registered
enabled
upgrading
deprecated
```

这些后续需要时再扩展。

## 9. Required Plugins

平台可以配置 required plugins。

示例：

```text
REQUIRED_PLUGINS=dfmea
```

启动策略：

```text
required plugin 加载失败
  -> 服务启动失败

非 required plugin 加载失败
  -> 记录错误
  -> 跳过该插件
  -> 服务继续启动
```

这样可以避免非核心插件阻塞整个平台。

## 10. Runtime 使用

插件注册成功后，被以下模块使用：

```text
Plugin Service
  查询插件能力。

Workspace Capability Service
  根据 skills 生成 Capability Descriptor / Capability Manifest。

Projection Service
  根据 projections 调用 projection handler。

API Push Service
  根据 exporters 调用 exporter handler。

Validation Service
  根据 validators 调用 validator handler。

Workspace UI
  根据 views metadata 展示入口。
```

典型运行链路：

```text
Service Start
  -> Plugin Registry loaded
  -> User starts session with plugin_id
  -> Runtime Service creates Run Context
  -> Workspace Capability Server resolves plugin skills
  -> Agent invokes plugin skill capability
  -> Workspace Capability Server invokes handler
```

## 11. 版本记录

即使第一阶段不做复杂升级，也必须记录版本。

运行时应记录：

```text
plugin_id
plugin_version
skill_id
skill_version
schema_version
projection_handler_version
exporter_version
```

记录位置：

```text
run
capability_invocation
ai_draft
projection
export
```

原因：

- AI 结果需要可解释。
- 插件变更后旧结果仍可追溯。
- 后续支持 migration 时有基础数据。

## 12. 错误模型

插件加载失败应返回结构化错误。

示例：

```json
{
  "code": "PLUGIN_HANDLER_NOT_FOUND",
  "message": "Skill handler file does not exist.",
  "details": {
    "plugin_id": "dfmea",
    "handler_ref": "skills/generate_initial_analysis.ts"
  }
}
```

常见错误码：

```text
PLUGIN_DIR_NOT_FOUND
PLUGIN_MANIFEST_NOT_FOUND
PLUGIN_MANIFEST_INVALID
PLUGIN_ID_DUPLICATED
PLUGIN_VERSION_INVALID
PLUGIN_SCHEMA_NOT_FOUND
PLUGIN_HANDLER_NOT_FOUND
PLUGIN_REFERENCE_INVALID
PLUGIN_REQUIREMENT_UNSATISFIED
PLUGIN_DISABLED
```

错误应写入启动日志。

如果有数据库 snapshot，也可以写入插件加载记录。

## 13. 禁用插件

第一阶段可以通过配置禁用插件。

示例：

```text
DISABLED_PLUGINS=fmea.pfmea
```

禁用后：

- 不注册到可用 Registry。
- 不出现在可选插件列表。
- 不能被 session/run 使用。

## 14. 不做什么

第一阶段不做：

```text
插件 marketplace
远程插件安装
热更新
在线升级
复杂 schema migration
跨插件依赖求解
插件权限审批
插件签名校验
多版本并行运行
插件卸载保留策略
```

插件代码或 manifest 变更后：

```text
重启服务生效
```

## 15. 第一阶段实现边界

第一阶段必须实现：

- 本地插件目录扫描。
- `plugin.json` 读取。
- 最小 manifest 校验。
- 资源路径校验。
- 引用校验。
- 内存 Plugin Registry。
- required plugin 启动策略。
- disabled plugin 配置。
- 结构化加载错误。
- plugin / skill / projection / exporter 版本记录。

第一阶段可选实现：

- manifest snapshot 入库。
- 插件加载结果 UI 展示。

第一阶段暂不实现：

- 热更新。
- 远程安装。
- marketplace。
- 自动 migration。
- 多版本并行。
- 插件签名。
- 插件 sandbox。

## 16. 待决问题

后续需要确认：

- 默认插件目录路径。
- required plugins 是否第一阶段就配置。
- manifest snapshot 是否第一阶段入库。
- 插件加载失败是否提供 UI 页面查看。
- handler_ref 是否支持 TypeScript、Python，还是双语言。
- 多实例部署时 Registry 如何保持一致。
- 插件变更后是否需要启动前构建步骤。
