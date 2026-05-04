# OpenCode Quality Assistant

这是一个 **绑定 OpenCode 使用** 的质量管理助理。OpenCode 是产品宿主和主要交互入口；
Python engine 是内部质量引擎，负责 DFMEA/PFMEA 方法、项目文件、校验、投影、导出和 Git
工作流。

## 产品边界

- 用户入口：OpenCode / OpenCode UI。
- 产品插件：`plugin/`，提供 `opencode-quality` 和 OpenCode npm plugin。
- 内部引擎：`engine/`，Python 3.11+、Typer CLI、本地 YAML/JSON 项目文件。
- 当前 active 方法：DFMEA。
- PFMEA：仅保留 planned 占位，后续单独实现。
- 存储：`projects/<slug>/` 下的 Git-friendly 文件。
- 不使用 SQLite/PostgreSQL 作为目标存储。

## 目录

```text
plugin/                     # OpenCode 产品入口，npm plugin + opencode-quality CLI
engine/                     # Python quality engine and CLI package
  src/quality_core/         # workspace/project/resource/validation/projection/Git
  src/quality_methods/      # dfmea active, pfmea placeholder
  src/quality_adapters/     # CLI and generated OpenCode templates
ui/                         # OpenCode UI host for standard manual testing
scripts/quality_cli.py      # repo-root development runner
.opencode/                  # generated OpenCode commands, skills, and hook for this checkout
docs/                       # requirements, architecture, design, development plan
```

## 最重要的目录规则

当前源码开发和 OpenCode UI 联调时，先进入本项目根目录：

```powershell
cd E:\study\dfmeaDemo
```

原因是 OpenCode 和开发脚本需要从这个目录读取：

- `.opencode/`
- `scripts/quality_cli.py`
- `plugin/`
- `engine/`
- `ui/`

如果在其他目录启动 `opencode serve`，OpenCode 可能读不到 `.opencode/commands` 和
`.opencode/plugins/quality-assistant.js`，slash commands 就不会出现。

后续正式交付给其他用户后，用户不需要进入你的源码目录。用户应该在自己的质量项目目录执行：

```powershell
opencode-quality init --workspace .
opencode serve --cors http://localhost:5173
```

简单区分：

```text
开发这个产品：进入 E:\study\dfmeaDemo
使用这个产品：进入用户自己的质量项目目录
```

## 第一次开发准备

在源码根目录执行：

```powershell
cd E:\study\dfmeaDemo
npm run engine:install
npm run opencode:init
npm run opencode:doctor
```

`opencode:init` 会刷新：

- `.opencode/commands/*.md`
- `.opencode/skills/*/SKILL.md`
- `.opencode/plugins/quality-assistant.js`
开发模式默认不写 `opencode.json`，而是让 OpenCode 直接加载 `.opencode/plugins/*.js`。发布后的
npm 插件模式使用：

```powershell
npm run opencode:init:npm
```

这会额外写入 `opencode.json`：

```json
{
  "plugin": ["opencode-quality-assistant"]
}
```

`npm run opencode:doctor` 会检查 Node、Python、OpenCode CLI 和质量方法发现状态。当前如果看到
`opencode: not found`，说明还需要先安装 OpenCode CLI。

## 核心 CLI 测试

不依赖 OpenCode，先确认 Python 质量引擎能跑：

```powershell
cd E:\study\dfmeaDemo
python .\scripts\quality_cli.py quality method list --workspace .
python .\scripts\quality_cli.py quality workspace init --workspace .run\dev-test --force
python .\scripts\quality_cli.py quality project create demo --workspace .run\dev-test
python .\scripts\quality_cli.py dfmea init --workspace .run\dev-test --project demo
python .\scripts\quality_cli.py dfmea validate --workspace .run\dev-test --project demo
```

期望：

- DFMEA 是 `active`
- PFMEA 是 `planned`
- `dfmea validate` 可以返回成功，允许 warning

## OpenCode / UI 联调

终端 1：

```powershell
cd E:\study\dfmeaDemo
opencode serve --cors http://localhost:5173 --port 4096
```

终端 2：

```powershell
cd E:\study\dfmeaDemo\ui
npm install
npm run dev
```

在 UI 里测试：

```text
查看当前质量方法列表，并说明 DFMEA 和 PFMEA 当前状态
/dfmea-smoke
/quality-bootstrap demo
/quality-status demo
```

期望：

- Agent 能识别 DFMEA active、PFMEA planned placeholder。
- `/dfmea-smoke` 能在 `.run/` 下创建隔离测试项目。
- `/quality-bootstrap demo` 能创建 workspace/project/DFMEA。
- `/quality-status demo` 能汇总方法、插件、项目状态、校验和投影状态。

如果 slash commands 不出现，先检查：

```powershell
cd E:\study\dfmeaDemo
Test-Path .\.opencode\commands\dfmea-smoke.md
Test-Path .\.opencode\plugins\quality-assistant.js
```

并确认 `opencode serve` 是从 `E:\study\dfmeaDemo` 启动的。

## 开发命令

```powershell
cd E:\study\dfmeaDemo
npm run quality -- method list --workspace .
npm run dfmea -- --help
npm run check:engine
```

也可以直接使用 root runner：

```powershell
python .\scripts\quality_cli.py quality method list --workspace .
python .\scripts\quality_cli.py dfmea validate --workspace . --project demo
```

Python engine 内部检查：

```powershell
cd engine
python -m ruff check src\quality_adapters src\dfmea_cli src\quality_core src\quality_methods tests
python -m compileall -q src tests
python -m pytest
```

## 交付方向

短期交付：

```powershell
npm install -g opencode-quality-assistant
opencode-quality init --workspace .
opencode serve --cors http://localhost:5173
```

这时用户应该在自己的项目目录执行，不需要进入 `E:\study\dfmeaDemo`。

长期 UI：

- OpenCode UI 继续作为对话和宿主入口。
- 后续自研质量管理 UI 可以二开 OpenCode UI。
- UI 不直接实现 DFMEA/PFMEA 业务写逻辑，只消费 Python engine 的 CLI/投影/未来本地 API。

## 权威文档

- `docs/requirements/local-first-quality-assistant-requirements.md`
- `docs/architecture/local-first-quality-assistant-architecture.md`
- `docs/design/local-first-quality-assistant-detailed-design.md`
- `docs/design/current-dfmea-cli-migration-map.md`
- `docs/development/local-first-quality-assistant-development-plan.md`
