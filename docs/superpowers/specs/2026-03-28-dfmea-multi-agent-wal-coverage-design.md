# DFMEA Multi-Agent WAL Coverage Enhancement Design

## 1. 文档定位

- 上位约束：`docs/requirements/2026-03-15-dfmea-skill-requirements.md`
- 现行架构：`docs/architecture/2026-03-16-dfmea-skill-architecture.md`
- 当前 realistic 测试基线：
  - `tests/helpers_realistic_dfmea.py`
  - `tests/test_realistic_dfmea_end_to_end.py`
  - `tests/test_realistic_dfmea_regression_matrix.py`
  - `tests/test_realistic_agent_session.py`
- 本文目标：在已有单 agent realistic 覆盖之上，增加“多 agent 共享同一 SQLite/WAL 项目文件”的交错会话级测试设计。

本文不新增产品能力，不改变 CLI 契约，只增强测试覆盖。

## 2. 当前覆盖与缺口

当前 realistic 覆盖已证明：

- 单 agent 可以完成完整 DFMEA 生命周期
- 单 agent 可以增量录入、追问查询、修复关系、从失败中恢复
- 单 agent 结束时可以 `projection rebuild`、`validate`、`export`

但当前仍缺少一个关键维度：

1. 多个 agent 共享同一个 SQLite 数据库文件时的交错写读语义
2. WAL 模式下，一个 agent 写入后另一个 agent 的读视图如何体现 dirty/stale
3. 多 agent 连续写入后，projection 的协调与最终收敛
4. 一个 agent 的失败写入是否会污染其他 agent 的读写工作流

这部分正是架构里“支持 10 人以下 AI Agent 并发操作”的核心约束之一，因此必须补上。

## 3. 设计目标

本增强必须同时满足以下目标：

1. 用真实 CLI 命令模拟多个 agent 共享一个 DB 的工作方式
2. 重点验证写后可见性、projection dirty/stale 语义、失败隔离和最终一致性
3. 保持测试稳定可重复，不把其变成依赖随机时序的脆弱并发实验
4. 让测试组织方式贴近“多个 agent 交错协作/竞争”的真实使用路径
5. 最终每条会话都必须以 `validate` clean 收敛

## 4. 非目标

本轮不做以下事情：

1. 不做真实多线程/多进程竞态压测
2. 不覆盖 SQLite 锁等待、超时、死锁恢复等底层压力行为
3. 不扩展新的 CLI 子命令或专用测试后门
4. 不替代现有单 agent realistic 测试
5. 不尝试穷举所有并发排列组合

## 5. 总体方案

新增一个独立模块：`tests/test_realistic_multi_agent_sessions.py`。

该模块与现有 realistic 分层如下：

- `tests/test_realistic_dfmea_end_to_end.py`
  - 真实产品主路径
- `tests/test_realistic_dfmea_regression_matrix.py`
  - 横向回归矩阵
- `tests/test_realistic_agent_session.py`
  - 单 agent 多轮任务链
- `tests/test_realistic_multi_agent_sessions.py`
  - 多 agent 交错会话、一致性与 WAL 语义

新模块不要求真正并发执行；推荐采用“顺序交错式多 agent 会话”设计：

- 同一个 DB 文件
- 明确划分 Agent A / Agent B / Agent C 的操作步骤
- 每个 Agent 步骤都必须是一条新的 CLI 调用，重新打开同一 DB 文件；不得复用内存态 client/session 充当“多 agent”替身
- 用交错顺序模拟真实协作
- 重点验证“共享数据库 + 读写交替 + projection 协调 + 失败隔离”的行为

这样既接近真实 agent 协作，又比多进程并发更稳定、更适合 pytest。

## 6. 四类一致性验证目标

### 6.1 写后可见性

- 一个 agent 完成写操作后，其他 agent 必须能在正确时机观察到 canonical 层变化
- 如果查询依赖 projection，则在 rebuild 前应正确体现 dirty/stale，而不是静默伪装成新鲜数据

### 6.1.1 读路径语义约束

- canonical 读路径（例如直接依赖 canonical 存储而不是 projection 的查询）必须在写入后立即反映最新事实
- projection-backed 读路径在 rebuild 前不要求立刻反映最新事实，但必须通过 dirty/stale 信号可观察到“当前读模型不是最新的”
- projection-backed 查询在 rebuild 前只允许表现为“旧结果 + dirty/stale 标记”或“显式 stale/dirty 提示”，不得伪装成已同步的新鲜结果
- rebuild 后，projection-backed 读路径必须与 canonical 层重新对齐

本轮多 agent 会话中，至少明确按以下方式使用读路径：

- canonical 读验证：`query get`、`query list`、`query search`
- projection-backed 读验证：`query summary`、`query dossier`、`query actions`、`query by-severity`
- trace 读验证：`trace causes/effects` 作为重建后的一致性证据，不要求在 dirty 状态下承担读后立刻可见性证明

### 6.2 Projection 协调

- 多个 agent 连续写入后，`projection status` 必须可靠体现 dirty
- rebuild 后，projection-backed 读模型必须与最新 canonical 数据一致

### 6.3 失败隔离

- 一个 agent 的非法写入失败后，不应污染共享 DB
- 其他 agent 随后仍能 query、仍能合法写入、最终仍能 rebuild/validate clean

### 6.4 最终收敛

- 无论中途如何交错写入、读取和失败，最终都必须收敛到：
  - `validate == {errors: 0, warnings: 0}`
- 至少一种关键 query/trace 结果正确可用

## 7. 三条多 Agent 会话主线

### 7.1 会话 A：交错录入与读后可见性

模拟方式：

1. Agent A：`init` + `structure add`
2. Agent B：立即 `query list/get/search`
3. Agent C：补 `add-function` / `add-requirement` / `add-characteristic`
4. Agent A：查看 `projection status`
5. Agent B：在 rebuild 前执行 projection-backed 查询，验证 dirty/stale 语义
6. Agent C：`projection rebuild`
7. Agent A/B：再次 `query summary/dossier`
8. 最终 `validate`

重点验证：

- 多 agent 共享 DB 时，读侧不会悄悄吞掉 dirty/stale 信号
- rebuild 前后，读取结果有可解释的语义差异
- rebuild 后所有 agent 看到一致的读模型

建议断言示例：

- Agent B 在步骤 2 的 `query list/get/search` 能立即看到 Agent A 已创建的结构节点
- Agent B 在步骤 5 之前读取 `query summary` 或 `query dossier` 时，不以“新数据已完全可见”为断言目标，而是以 `projection status` 的 dirty/stale 证据为主
- Agent C 在步骤 6 rebuild 后，Agent A/B 对 `query summary/dossier` 的关键计数或对象集合断言必须一致

### 7.2 会话 B：交错维护与读模型一致性

模拟方式：

1. 固定复用 `tests/helpers_realistic_dfmea.py` 中的 full realistic seed helper 作为起点
2. Agent A：更新 action status
3. Agent B：更新 FM/FC 或 requirement/characteristic/trace 关系
4. Agent C：立刻查询 `actions` / `by-severity` / `dossier`
5. Agent A：查看 `projection status`
6. Agent B 或 C：`projection rebuild`
7. Agent A/B/C：再次查询 `actions` / `by-severity` / `dossier` / `trace`
8. 最终 `validate`

重点验证：

- 多 agent 连续维护同一项目时，projection 不会悄悄失真
- rebuild 后读模型能够重新和 canonical 层对齐

建议断言示例：

- rebuild 前 `projection status` 明确显示 dirty
- rebuild 后 `query actions --status completed`、`query by-severity --gte 8`、`query dossier` 的关键字段与 Agent A/B 更新后的 canonical 事实一致
- 如会话中包含 trace 关系维护，则 rebuild 后 `trace causes/effects` 必须恢复为预期链路

### 7.3 会话 C：失败写入不影响其他 Agent

模拟方式：

1. Agent A：执行非法写入，例如非法 `structure add` 或非法 `link-trace`
2. Agent B：紧接着执行 `query get/list`，验证项目仍可读、状态未污染
3. Agent C：执行合法写入
4. Agent A/B：查看 `projection status` 或执行关键 query
5. rebuild
6. validate

重点验证：

- 一次失败不会留下部分写入副作用
- 其他 agent 不会因为别人的失败而进入不可工作状态

会话 C 必须至少包含一种“应触发事务整体回滚”的失败类型，并对失败前后状态做会话级硬断言：

- `canonical revision` 不增长
- 节点列表/节点计数不变
- `fm_links` 不变（如该失败与 trace 相关）

## 8. 命令覆盖目标

新模块只覆盖支撑多 agent 会话主线的最小必需命令集，不重复承担单命令契约测试。

### 8.1 会话 A 必需命令集

- `init`
- `structure add`
- `analysis add-function`
- `analysis add-requirement`
- `analysis add-characteristic`
- `query list/get/search/summary/dossier`
- `projection status/rebuild`
- `validate`

### 8.2 会话 B 必需命令集

- `analysis update-action-status`
- 至少一种结构化维护写入：
  - `analysis update-fm` 或 `analysis update-fc`
  - 以及至少一种关系维护命令（如 `unlink-trace` / `link-trace` 或 `unlink-fm-requirement` / `link-fm-requirement`）
- `query actions/by-severity/dossier`
- `trace causes/effects`（至少一种）
- `projection status/rebuild`
- `validate`

### 8.3 会话 C 必需命令集

- 至少一种非法 `structure add` 或非法 `link-trace`
- 至少一种合法后续写入
- `query get/list`
- `projection status/rebuild`
- `validate`

### 8.4 明确不在新模块重复承担的职责

- 全命令参数边界、错误 target payload、详细契约仍由现有命令级测试负责
- 真实多进程锁冲突行为不在本轮覆盖

## 9. 文件与职责

### 9.1 新文件

- `tests/test_realistic_multi_agent_sessions.py`
  - 承担三条多 agent 会话测试

### 9.2 允许修改的现有文件

- `tests/helpers_realistic_dfmea.py`
  - 只允许增加最小复用 helper，例如：
    - 多 agent 会话读取 project metadata 的轻量 helper
    - 读节点 JSON / `fm_links` / canonical revision 的 helper
    - 必要的 partial seed 或 projection helper 复用

### 9.3 不建议修改

- `tests/test_realistic_dfmea_end_to_end.py`
- `tests/test_realistic_dfmea_regression_matrix.py`
- `tests/test_realistic_agent_session.py`

除非发现一个提取 helper 就能明显减少重复，否则这些文件应保持职责稳定。

## 10. 测试设计原则

1. 用“Agent A/B/C”分段注释明确交错语义
2. 不要求真的并发，但每个 Agent 步骤都必须是新的 CLI 调用，并真实共享同一个 DB 文件
3. 尽量使用真实 CLI 命令，而不是直接 SQL 改 canonical 层
4. SQLite 直读只用于验证中间状态，例如：
   - canonical revision
   - project data 中的 dirty 状态
   - `fm_links` 是否被污染
5. 每条会话必须以 `validate` 收尾，且 `errors == 0 && warnings == 0`
6. 至少一种 query 或 trace 结果作为最终业务证据

## 11. 通过标准

### 11.1 并发完整性

- 任一关键交错写入后，`projection status` 必须可靠反映 dirty
- rebuild 后，projection-backed query 结果必须与最新 canonical 数据一致

### 11.2 共享可用性

- 一个 agent 失败后，其他 agent 仍能继续 query 或合法写入
- 失败前后的 canonical revision、节点列表、`fm_links` 不发生意外污染

### 11.3 最终一致性

- 每条多 agent 会话最终都必须 `validate == {errors: 0, warnings: 0}`
- 至少一个 `summary/dossier/actions/trace` 结果作为最终业务证据

## 12. 风险与约束

1. 如果把“多 agent”理解成真实多线程，测试会变脆且不稳定
2. 如果测试只验证错误码而不验证失败后的共享状态，会误报恢复能力
3. 如果把过多命令树契约塞进多 agent 测试，会和现有命令测试职责混淆

因此推荐：

- 用顺序交错模拟共享 DB，而不做随机时序并发
- 用最小中间状态断言证明“失败不污染、dirty 可见、rebuild 后一致”
- 让新模块只负责多 agent 语义，不重复命令契约

## 13. 推荐落地顺序

1. 先实现会话 A：交错录入与读后可见性
2. 再实现会话 B：交错维护与 projection 协调
3. 最后实现会话 C：失败写入不影响其他 agent
4. 最后跑 realistic 测试全集与全量 pytest

## 14. 预期结果

完成本增强后，仓库会形成四层互补 coverage：

1. 命令主路径 coverage
2. 横向回归矩阵 coverage
3. 单 agent 会话 coverage
4. 多 agent / 共享 DB / WAL 语义 coverage

这样测试体系就不仅能证明“一个 agent 能做完 DFMEA”，还能证明“多个 agent 围绕同一个 DFMEA 项目交错工作时，系统仍然能保持完整性和最终一致性”。
