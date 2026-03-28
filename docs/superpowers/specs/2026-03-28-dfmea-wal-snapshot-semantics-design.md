# DFMEA WAL Snapshot Semantics Enhancement Design

## 1. 文档定位

- 上位约束：`docs/requirements/2026-03-15-dfmea-skill-requirements.md`
- 现行架构：`docs/architecture/2026-03-16-dfmea-skill-architecture.md`
- 当前 relevant 覆盖：
  - `tests/test_realistic_dfmea_end_to_end.py`
  - `tests/test_realistic_dfmea_regression_matrix.py`
  - `tests/test_realistic_agent_session.py`
  - `tests/test_realistic_multi_agent_sessions.py`
- 本文目标：补足 SQLite WAL 的低层读写快照语义验证，使测试不仅证明“提交后共享可见”，还能证明“旧 reader 保持旧快照、新 reader 看见新提交、reader 不阻塞 writer”。

本文不新增产品能力，不改变 CLI 契约，只增强测试覆盖。

## 2. 当前覆盖与缺口

当前多 agent 相关覆盖已经证明：

- 多个 agent 可以顺序交错操作同一 DB 文件
- 写入提交后，其他 agent 可以继续读取和维护同一项目
- projection dirty/stale 与 rebuild 收敛可被 CLI 观察到
- 失败写入不会污染共享项目

但最终审查指出仍缺一个底层语义层：

1. 旧 reader 事务持有期间是否保持旧快照
2. writer 提交后，新 reader 是否看到新事实
3. reader 是否不会阻塞通过 CLI 发起的 writer 提交

这些正是 WAL 模式区别于简单串行文件访问的关键行为，因此需要专门测试。

## 3. 设计目标

本增强必须同时满足以下目标：

1. 用最小、稳定、可重复的测试直接验证 WAL 快照语义
2. 低层快照验证要和现有 CLI 工作流接上，而不是孤立做数据库技巧测试
3. 不依赖随机调度或真实多线程竞争
4. 能明确区分“旧 reader 视图”和“新 reader 视图”
5. 最终仍通过 CLI `projection rebuild` / `validate` 证明系统收敛正常

## 4. 非目标

本轮不做以下事情：

1. 不做高并发压测
2. 不做锁等待/超时/死锁恢复基准测试
3. 不扩展新的 runtime API 或 CLI 选项
4. 不替代现有 multi-agent session 测试

## 5. 总体方案

新增一个独立模块：`tests/test_wal_snapshot_semantics.py`。

分层职责：

- `tests/test_realistic_multi_agent_sessions.py`
  - 保留 CLI 视角下的多 agent 交错语义
- `tests/test_wal_snapshot_semantics.py`
  - 专门验证 SQLite WAL 的读写快照语义

职责边界必须明确：

- `tests/test_realistic_multi_agent_sessions.py` 证明 CLI-first 多 agent 业务流可交错执行
- `tests/test_wal_snapshot_semantics.py` 只证明 SQLite/WAL 为这种交错提供的底层 reader snapshot / reader-writer coexistence 保障，不重复承载业务故事线

新模块应保持很小，只做 1-2 条聚焦测试，不承载业务故事线复杂度。

## 6. 推荐测试主线

### 6.1 测试 A：旧 Reader 保持旧快照，新 Reader 看见新提交

预期过程：

1. 通过 CLI 创建最小 DFMEA 项目
2. reader A 打开 sqlite3 连接，并在显式读事务内完成第一次 canonical SELECT
3. 记录 reader A 观察到的 canonical 基线状态
4. writer 通过 CLI 完成一个真实写入并提交
5. reader A 在不关闭连接/不重开事务的前提下再次执行相同 canonical SELECT，仍应看到旧快照
6. 新开 reader B，读取同一 canonical 对象，应看到新提交
7. 最后通过 CLI 执行 `projection rebuild` / `validate`

这条测试直接验证 WAL 的核心 snapshot 语义。

建议观测点示例：

- writer 通过 CLI 新增一个 `FN` 或 `REQ`
- reader A 断言 canonical 行数、rowid 集合或业务 ID 集合不变
- reader B 断言 canonical 行数、rowid 集合或业务 ID 集合包含新对象
- 最后 CLI `projection rebuild` + `validate` 证明应用层仍能收敛

### 6.2 测试 B：Reader 不阻塞 Writer，Writer 提交后系统仍可闭环

预期过程：

1. 通过 CLI 建立最小项目或 partial realistic 项目
2. 保持一个 reader 连接打开并读取项目状态
3. 另一个 agent 通过 CLI 发起写入并成功提交
4. 验证 writer 没有因为 reader 存在而失败
5. 关闭 reader 后，通过 CLI 执行 `projection status/rebuild/validate`
6. 断言最终系统 clean

这条测试验证 WAL 的“读写共存”能力，以及 CLI 层最终仍可正常工作。

补充说明：

- 第 5 步的 CLI 闭环用于证明 writer 提交后的系统仍可恢复为 clean
- 本测试不额外承诺“reader 打开期间 projection 也必须可重建”，避免范围扩张

## 7. 文件与职责

### 7.1 新文件

- `tests/test_wal_snapshot_semantics.py`
  - 承担低层 WAL 快照语义测试

### 7.2 允许复用的现有 helper

- `tests/helpers_realistic_dfmea.py` 中的最小 DB/CLI helper
- `invoke_json`
- `read_project_data`

如需额外低层 sqlite helper，应优先写在 `tests/test_wal_snapshot_semantics.py` 内，避免污染共享 helper。

## 8. 设计原则

1. CLI 负责真实写入，sqlite3 连接负责验证 reader snapshot
2. WAL 断言只能基于 sqlite3 对 canonical SQLite 数据的直读观测，例如：
   - `projects.data` 中的 revision / dirty 信息
   - `nodes` 行数、rowid、业务 ID、name 或 JSON data
   - `fm_links` 记录
3. CLI 不承载 WAL 快照断言本身；CLI 只负责建项目、提交写入、以及最终 `projection rebuild` / `validate` 闭环
4. 旧 reader 与新 reader 的角色必须清晰区分
5. 不用随机 sleep 或竞态窗口做脆弱判断
6. 最终必须接回 CLI 层验证，而不是停留在 DB 观察
7. 所有测试都要以 CLI `projection rebuild` + `validate` 收尾；`validate` 必须没有 error 级问题

## 9. 通过标准

### 9.1 WAL 快照完整性

- reader A 在其事务生命周期内不应看到 writer 后续提交的新数据
- reader B 在 writer 提交后必须能看到新数据

### 9.2 WAL 可用性

- reader 存在时，writer 仍能通过 CLI 成功提交
- writer 成功后，系统仍能继续 `projection rebuild` / `validate`

### 9.3 与 CLI 闭环一致

- 低层 WAL 测试完成后，至少有一次 CLI 读或校验结果证明应用层仍然一致
- `validate` 必须无 error 级问题；若要进一步约束 warning，需确保这些 warning 与夹具稳定性直接相关，而非 WAL 语义本身

## 10. 风险与约束

1. 如果测试过度依赖 sqlite3 事务细节写法，可能在不同连接模式下脆化
2. 如果测试只看 DB 视图，不回到 CLI 验证，会和产品行为脱节
3. 如果把低层 WAL 测试塞进 multi-agent session 文件，会让职责混乱

因此推荐：

- 单独新建 `tests/test_wal_snapshot_semantics.py`
- 每条测试先证明 snapshot 语义，再接 CLI rebuild/validate 闭环

## 11. 预期结果

完成本增强后，仓库将同时具备：

1. CLI 级多 agent 交错语义测试
2. SQLite WAL 级读写快照语义测试

这样测试体系就不仅能证明“多个 agent 能交错工作”，还能证明“其底层共享数据库确实具备 WAL 快照行为，而不是偶然通过顺序调用”。
