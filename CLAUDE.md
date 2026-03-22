# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库现状与命令判断

- 当前仓库仍是 DFMEA skill 的需求/架构基线仓库，不是已落地实现仓库。
- 当前快照未发现 `README.md`、Cursor/Copilot 规则、`package.json`、`bun.lockb`、`pyproject.toml`、`Cargo.toml`、`go.mod`、`Makefile`、`src/`、`tests/`。
- 因此当前仓库没有可验证的本地 `build` / `lint` / `test` / 单测命令；不要臆造命令。

## 文档权威顺序

1. `docs/requirements/2026-03-15-dfmea-skill-requirements.md`
2. `docs/architecture/2026-03-16-dfmea-skill-architecture.md`
3. `implementation_plan.md`（历史草案，仅供参考）

修改或回答架构问题时，先读前两者；只有补历史背景时再看 `implementation_plan.md`。

## 系统大图景

目标是提供一个可供任意 Agent 使用的 DFMEA skill 包，支持 10 人以下 AI Agent 并发操作。

四层结构：
- 技能路由层：主 `SKILL.md` 路由到子 skill
- 数据层：SQLite 单文件数据库（WAL 模式），唯一事实来源
- 导出层：Markdown 文件，按需生成，用于人类审阅和 Git 审计
- 校验层：数据完整性、引用有效性和业务规则约束检查

## 数据库设计（3 张表）

- `projects`：项目元数据
- `nodes`：所有节点（单表继承，type 区分对象类型）
  - `rowid`：DB 内部主键
  - `id`：业务 ID（仅 SYS/SUB/COMP/FN/FM/ACT 有，FE/FC/REQ/CHAR 为 NULL）
  - `parent_id`：主归属上级的 rowid
  - `data`：JSON，各类型特有字段
- `fm_links`：跨层溯源链接（FC→FM、FE→FM 的多对多关系），支持递归查询

## 核心建模约束

- `FN` 是分析层主聚合单元；逻辑上承载功能描述、Requirements、Characteristics 和完整失效分析链。
- `REQ` / `CHAR` 是 FN 的子记录，无业务 ID，仅有 DB rowid。
- `FM` / `FE` / `FC` / `ACT` 均为 `nodes` 表中的行，通过 `parent_id` 建立主归属层级。
- `FE` / `FC` 无业务 ID（不被外部独立引用），仅有 DB rowid。
- 业务 ID 规则：`^(SYS|SUB|COMP|FN|FM|ACT)-\d{3,6}$`；事务内原子分配，删除后不复用。
- `ACT` 主归属于 `FM`，不是 `FC`；通过 `data.target_causes` 关联同一 FM 内的 FC rowid 数组。

## 引用关系分层

- **主归属**：`nodes.parent_id` 列，树遍历核心
- **跨层溯源**：`fm_links` 表，FC/FE 到跨层 FM 的多对多链接，支持 `WITH RECURSIVE` 递归查询根因链和后果链
- **局部引用**：`data` JSON 字段（`target_causes`、`violates_requirements`、`related_characteristics`），不参与 JOIN
- FE/FC 采用混合式策略：保留独立 description（局部可读快照）+ fm_links 溯源链接（跨层追溯），校验层检测描述漂移报 warning

## 操作语义要点

- 所有写操作必须在 SQLite 事务内完成，保证原子性
- 删除利用 `trg_cascade_delete_node` 触发器递归级联，`fm_links` 通过外键 CASCADE 自动清理
- `ACT.target_causes`（JSON 内）删除 FC 时需应用层清理
- 结构节点禁止非空删除
- SYS 节点的 `parent_id = 0`（顶级哨兵值），通过 `project_id` 关联项目
- 校验分三类：schema（字段格式）、graph（归属/引用有效性）、integrity（唯一性）

## 目标 Skill 包结构（计划态）

```text
dfmea/
  SKILL.md
  node-schema.md
  storage-spec.md
  skills/
    dfmea-init/
    dfmea-structure/
    dfmea-analysis/
    dfmea-query/
    dfmea-maintenance/
```

- `dfmea/SKILL.md`：主入口、任务路由、全局一致性约束
- `dfmea-init`：项目初始化（创建 DB 文件和 projects 记录）
- `dfmea-structure`：结构层维护
- `dfmea-analysis`：Function / Requirement / Characteristic / 失效链维护
- `dfmea-query`：查询、搜索、递归追溯
- `dfmea-maintenance`：校验、Markdown 导出

## 给后续 Claude Code 的工作方式

- 先读需求文档，再读架构文档。
- SQLite 是唯一事实来源，Markdown 是导出视图。
- 在仓库出现真实实现和清单文件前，不要把 workflow 里的 Bun 命令当成本仓库事实。
