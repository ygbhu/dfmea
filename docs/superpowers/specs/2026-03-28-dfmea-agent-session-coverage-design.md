# DFMEA Agent Session Coverage Enhancement Design

## 1. 文档定位

- 上位约束：`docs/requirements/2026-03-15-dfmea-skill-requirements.md`
- 现行正式架构：`docs/architecture/2026-03-16-dfmea-skill-architecture.md`
- 当前 realistic 测试基线：`tests/helpers_realistic_dfmea.py`、`tests/test_realistic_dfmea_end_to_end.py`、`tests/test_realistic_dfmea_regression_matrix.py`
- 本文目标：把现有“真实产品 CLI 主路径覆盖”增强为“更贴近真实 agent 多轮问答、增量录入、完整性修复和最终审阅输出”的测试设计。

本文不引入新的产品能力，也不改变 CLI 对外契约；它只增强测试组织方式和 realistic 覆盖深度。

## 2. 当前覆盖与缺口

当前仓库已经具备以下 realistic 覆盖：

- 真实产品项目初始化、结构录入、功能/REQ/CHAR/失效链录入
- 跨组件 trace 建模
- `projection status/rebuild`
- `query summary/map/bundle/dossier/by-ap/by-severity/actions`
- `trace causes/effects`
- `validate`
- `export markdown --layout review`
- 少量完整性异常，例如 stale projection 和同组件非法 trace

但当前 realistic 测试仍有明显缺口：

1. 测试组织方式仍以“命令主路径”和“横向矩阵”视角为主，不够像真实 agent 会话
2. 缺少“边录入边回答问题”的增量测试节奏
3. 缺少“发现问题 -> 修复 -> 重建 -> 再验证”的完整闭环测试
4. 缺少把多个命令串成真实 agent 任务链的场景，例如解释高风险项、补录 requirement、重连 trace、再导出审阅
5. 对完整性覆盖仍偏局部，没有把 update/link/unlink/delete/rebuild/validate/query 串成连续维护故事线

## 3. 设计目标

本增强设计必须同时满足以下目标：

1. 保持 SQLite 为唯一事实源，CLI 为唯一正式操作接口
2. 不引入测试专用后门；所有业务写入和查询都走真实 CLI
3. 让测试更接近真实 agent 会话，而不是单条命令校验
4. 覆盖增量录入、追问查询、维护变更、完整性修复三类核心 agent 行为
5. 让最终结果既可验证数据正确，也可验证对人/agent 的可读输出仍然一致

## 4. 非目标

本设计不做以下事情：

1. 不模拟自然语言模型本身的推理或提示词
2. 不测试聊天框 UI 或外部 orchestrator
3. 不扩展新的 CLI 子命令
4. 不引入多线程/多进程并发作为本次第一阶段目标
5. 不把所有现有通用命令测试迁移到会话测试中

## 5. 总体方案

新增一个独立测试模块：`tests/test_realistic_agent_session.py`。

该模块与现有两类 realistic 测试形成分层：

- `tests/test_realistic_dfmea_end_to_end.py`
  - 负责真实产品主路径是否打通
- `tests/test_realistic_dfmea_regression_matrix.py`
  - 负责横向查询、校验、导出、异常矩阵
- `tests/test_realistic_agent_session.py`
  - 负责真实 agent 如何分步录入、追问、修复、复核并完成一次完整任务

新模块不追求“每个命令都重新覆盖一遍”，而是把关键命令编织进三条 agent 会话故事线，让测试更接近真实任务执行顺序。

## 6. 三条 Agent 会话主线

### 6.1 会话 A：增量录入与实时问答

这条会话模拟真实 agent 在信息不一次性完整时逐步录入数据，并在录入过程中回答用户追问。

预期节奏如下：

1. `init` 创建项目
2. `structure add` 建立 `SYS -> SUB -> COMP`
3. 先只建立 controller 的部分 function，而不是一口气录完整个项目
4. 追加 `add-requirement` / `add-characteristic`
5. 用户追问时，agent 直接调用读命令回答问题：
   - `query get`
   - `query list`
   - `query search`
   - `query summary`
   - `query dossier`
6. 随着分析深入，再追加 `add-failure-chain`
7. 用户继续追问风险和根因链时，agent 串联：
   - `query by-ap`
   - `query by-severity`
   - `trace causes`
   - `trace effects`
8. 最后 `projection rebuild`、`validate`、`export markdown`

这条会话的重点不是一次性建立全量项目，而是验证“增量录入 + 即时回答 + 继续补录”这一真实工作流。

### 6.2 会话 B：变更请求与完整性修复

这条会话模拟用户在 DFMEA 已建立后又提出修订要求，agent 需要维护而不是重建。

预期覆盖这些维护动作：

- `analysis update-fm`
- `analysis update-fe`
- `analysis update-fc`
- `analysis update-act`
- `analysis update-action-status`
- `analysis link-fm-requirement` / `unlink-fm-requirement`
- `analysis link-fm-characteristic` / `unlink-fm-characteristic`
- `analysis link-trace` / `unlink-trace`
- `analysis delete-requirement`
- `analysis delete-characteristic`

预期节奏如下：

1. 基于 realistic cooling-fan 项目作为起点
2. 模拟用户变更需求、风险描述、措施状态和 trace 关系
3. 每次变更后检查 projection dirty 状态
4. `projection rebuild`
5. `validate`
6. 使用 `query dossier/bundle/actions/by-severity` 验证修复后的读侧结果
7. 最终 `export markdown --layout review` 仍可生成且链接正确

这条会话的重点是：agent 必须能从“变更后的不稳定中间态”回到“数据与导出一致的稳定态”。

### 6.3 会话 C：错误操作与自恢复

这条会话模拟 agent 在上下文不完整时做出一次错误操作，然后依靠结构化错误进行恢复。

首批建议覆盖的失败场景：

1. 非法父子归属被拒绝
2. 非空结构删除被拒绝
3. 同组件 trace 被拒绝

预期节奏如下：

1. 先执行一个非法动作，断言结构化错误 payload
2. agent 改为合法动作，继续录入或修复
3. `projection rebuild`
4. `validate`
5. 关键 `query` / `trace` / `export` 仍可完成

这条会话的重点是：一步失败不能让项目进入半损坏状态，agent 也必须能继续完成任务。

## 7. 命令覆盖目标

在新增会话测试中，只覆盖支撑三条会话主线的最小必需命令集，不重新承担全命令树契约测试。单命令 payload、参数边界、错误码细节继续由现有命令级和 regression matrix 测试负责。

### 7.1 会话 A 必需命令集

- `init`
- `structure add`
- `analysis add-function`
- `analysis add-requirement`
- `analysis add-characteristic`
- `analysis add-failure-chain`
- `query get/list/search/summary/dossier/by-ap/by-severity`
- `trace causes/effects`
- `projection status/rebuild`
- `validate`
- `export markdown`

### 7.2 会话 B 必需命令集

- `analysis update-fm`
- `analysis update-fe`
- `analysis update-fc`
- `analysis update-act`
- `analysis update-action-status`
- `analysis link-fm-requirement` / `unlink-fm-requirement`
- `analysis link-fm-characteristic` / `unlink-fm-characteristic`
- `analysis link-trace` / `unlink-trace`
- `analysis delete-requirement`
- `analysis delete-characteristic`
- `projection status/rebuild`
- `validate`
- `query bundle/dossier/actions/by-severity`
- `export markdown`

### 7.3 会话 C 必需命令集

- `structure add`（用于非法父子归属场景）
- `structure delete`（用于非空结构删除场景）
- `analysis link-trace`（用于同组件 trace 非法场景）
- 至少一种后续合法恢复动作
- `projection rebuild`
- `validate`
- 至少一个成功的 `query` 或 `export markdown`

会话 C 中的错误断言只验证 agent 做恢复决策所需的最小信息，例如 `code`、恢复所依赖的 `target` 片段或消息关键字；不重复承担完整错误契约测试。

### 7.4 明确不在新模块重复承担的职责

- `structure update/move` 的完整契约覆盖仍留在 `tests/test_structure_commands.py`
- `analysis delete-node` 的细粒度删除语义仍留在 `tests/test_analysis_links_and_delete.py`
- 通用错误码/target payload 细节仍以现有命令级测试为主

原有命令树中的其它命令，只有在三条会话测试确实需要支撑连续故事线时才应出现：

- `query map/actions` 可作为会话补充证据，但不是必需入口

这里的“覆盖”指命令作为真实 agent 任务链的一部分被使用，而不是要求每个命令都做全套契约断言。精细 payload 契约仍由现有通用测试负责。

## 8. 文件与职责

### 8.1 新文件

- `tests/test_realistic_agent_session.py`
  - 承担三条会话级测试

### 8.2 允许修改的现有文件

- `tests/helpers_realistic_dfmea.py`
  - 只允许增加会话测试复用所需的轻量 helper
  - 例如：
    - 构建“结构已建立但分析未完成”的局部场景
    - 读取项目修订元数据
    - 提供小型命令包装，避免新测试重复太多样板代码

### 8.3 不建议修改

- `tests/test_realistic_dfmea_end_to_end.py`
- `tests/test_realistic_dfmea_regression_matrix.py`

除非新增 helper 抽取确实能明显减少重复，否则这两个文件应保持现有职责不变。

## 9. 测试设计原则

1. 会话测试关注“真实任务链”，不是重复做所有 payload 契约测试
2. 尽量使用真实 CLI 命令，而不是直接 SQL 改 canonical 层
3. 仅在读取验证状态时使用 SQLite 查询辅助断言
4. 新模块只验证“多轮录入、追问、修复、恢复”的连续任务链；单命令 payload、参数边界、错误码细节继续留给现有命令级和 regression matrix 测试
5. 每个测试都必须有清晰结尾，且必须包含一次 `validate` 结果作为完整性证据
6. 避免把所有动作塞进一个超长测试，失败时应能快速定位到“录入”“修复”或“恢复”哪个阶段出了问题

## 10. 通过标准

### 10.1 录入完整性

- 增量录入后，用户追问的对象必须可被 `query get/list/search` 找到
- 补录 `REQ/CHAR/FM/trace` 后，`dossier/summary` 必须反映最新状态
- 会话 A 的最终验收必须包含：`validate` 无 error，且至少一个关键 query 或 review export 成功

### 10.2 修复完整性

- 关键修复阶段的写操作之后，`projection status` 必须能体现 dirty 状态
- `projection rebuild` 后，`validate` 不应出现 error 级问题
- 修复后的 `query/actions/by-severity/dossier` 必须与最新 canonical 数据一致
- 会话 B 的最终验收必须包含：修复后 `validate` 无 error，且至少一个 query 视图与一个 review export 结果仍然可用

### 10.3 会话完整性

- 每条测试都必须以一次 `validate` 结果收尾，且该结果不得包含 error 级问题
- `query` / `trace` / `export` 是补充证据，用于证明 agent 任务完成后结果仍可被读取、追溯和审阅，但不能替代 `validate`
- 会话 C 的重点是：首次非法命令返回结构化错误后，后续合法动作仍可完成，且最终 `validate` 证明系统没有留下半损坏状态
- 不允许出现命令 individually 成功但最终状态不可查询、不可追溯、不可导出、或 `validate` 仍报 error 的情况

## 11. 风险与约束

1. 如果会话测试写得过长，会导致失败定位成本过高
2. 如果会话测试断言过多内部 rowid/顺序细节，会降低后续可维护性
3. 如果 helper 过度膨胀，会把测试辅助代码变成新的复杂系统

因此，推荐做法是：

- 保持三条测试主线，而不是一个超级场景
- 保持 helper 只提供场景搭建和最小读取能力
- 把通用 payload 契约继续留给现有命令级测试

## 12. 推荐落地顺序

1. 先为 `tests/test_realistic_agent_session.py` 写会话 A 的失败测试
2. 再补会话 B 的维护与修复链路
3. 最后补会话 C 的失败恢复链路
4. 所有新增测试通过后，再跑全量 pytest

## 13. 预期结果

完成本增强后，仓库将同时拥有三种互补的 realistic 覆盖：

1. 命令主路径覆盖
2. 横向回归矩阵覆盖
3. agent 会话级真实工作流覆盖

这样测试体系不仅能证明“命令能用”，也能证明“真实 agent 可以把一件 DFMEA 任务从录入、追问、修复一路做完整”。
