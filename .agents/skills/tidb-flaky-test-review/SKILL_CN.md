---
name: tidb-flaky-test-review
description: 帮助 AI Agent 使用 tidb-flaky-test-catalog 的分类体系和 review checklist 来审查 TiDB (Go) PR/diff 中的 flaky test 风险。用于在 Code Review 中识别可能的 flaky test 模式、撰写 review 意见、或建议稳定化修复方案。
---

# TiDB Flaky Test Review

## 快速开始

受众：**AI Agent**。使用此技能生成可操作的 review 意见。

在开始 review 之前，**你必须完整阅读仓库根目录下的字典文件**，了解所有 key 和定义。不要仅依赖本文档中的示例：
- `review_smells.json`
- `taxonomy.json`

1. 获取 review 输入：PR 链接、变更文件列表、或 diff/patch。
2. 使用下方的检查清单识别 diff 中的 flaky test 风险。
3. 将每个风险映射到仓库根目录 `review_smells.json` 和 `taxonomy.json` 中的稳定 key。
4. 使用 **Review 意见模板** 撰写反馈。

本技能基于 `tidb-flaky-test-catalog`（仓库根目录）中的现有结论：
- `review_smells.json`：review checklist 原语（稳定 key）
- `taxonomy.json`：根因分类体系（稳定 key）

## 工作流程（Code Review）

### 0) 确定 review 焦点（避免噪音）

Agent 的目标是以最低的误报率捕获**本 PR 新引入的 flaky 风险**。

- 如果 PR **新增/修改了测试**：优先关注受影响的测试。
- 如果 PR 声称**修复了 flaky test**：检查修复是否解决了根因，还是只是创可贴式修复（如加 sleep / 增大超时）。避免重复报告与本次变更无关的旧 smell。
- 如果 PR 修改了**基础设施/CI/超时/分片**：将其视为一级 flaky 风险面，记录被修改的具体 target/超时值。

### 1) 识别测试面

先对变更进行分类；不同测试类型的 flaky 模式不同：
- **单元测试**：Go `*_test.go` 文件（尤其是 TiDB 中的 `pkg/**/_test.go`）。
- **集成测试**：`tests/integrationtest/t/**`（测试用例）和 `tests/integrationtest/r/**`（golden 结果）。
- **Real TiKV 测试**：`tests/realtikvtest/**`（通常对外部依赖/时序敏感）。
- **测试基础设施/构建**：`BUILD.bazel`、CI 脚本、超时、分片、`flaky = True` 标记。

同时提取**受影响的测试用例**（准确性和沟通所必需）：
- **单元测试**：识别被修改的 `func TestXxx...` / suite 子测试；如果不确定，至少给出 `*_test.go` 文件名。
- **集成测试**：给出 `tests/integrationtest/t/` 下的 `.test` 文件名（以及 `r/` 下对应的 `.result` 文件）。
- **Real TiKV 测试**：给出 `tests/realtikvtest/` 下的测试文件和 `TestXxx`（如果可见）。
- **Bazel / CI**：记录被修改的 target 或 shard/超时值。

### 1.5) 必要时扩展上下文（看 diff 之外的代码）

如果你标记了一个 smell，**必须阅读足够的周围代码**以避免误报：
- 在 Go 测试中，查找 `t.Cleanup(...)`、`defer ...` 清理、suite `TearDown*`、helper 封装，以及测试是否已经使用了 `require.Eventually` / 重试 / 退避工具。
- 如果可疑代码在 helper 函数中，定位 helper 定义并确认实际行为。
- 如果 PR 只修改了几行，但风险取决于 setup/teardown，阅读文件级别的 setup 以确认隔离性。

### 2) 结构化 Smell 扫描（深入彻底）

**重要：本技能要求深度 LLM 推理，而非关键字/模式匹配。** 你必须仔细阅读并理解完整的 PR diff，追踪控制流，理解代码变更的意图，并基于语义理解来推断潜在的 flaky 风险。不要简单地扫描 `time.Sleep` 或 `go func` 等关键字然后机械地映射到 smell key。关键字只是起点——你必须理解周围的上下文（sleep 是否在重试循环中？goroutine 是否被正确同步？）才能做出判断。

分析控制流、并发模型和资源生命周期：
- 时序：`time.Sleep(...)`、短超时、无退避的轮询
- 并发：`t.Parallel()`、goroutine、无清理的共享/全局状态
- 确定性：缺少 `ORDER BY`、map 迭代顺序、顺序敏感的断言
- 执行计划/统计信息敏感：断言精确的执行计划/代价、plan cache 依赖、统计信息敏感的断言
- DDL/schema 传播：无等待的 DDL、schema 版本竞争、异步 schema 传播
- 外部依赖：real TiKV/环境依赖、硬编码端口、无重试/超时的网络调用

如果没有明显的问题，你必须系统地追踪测试的 setup、执行和 teardown，排查排序/时序/共享状态风险。

#### Go/TiDB 深度分析模式（可选但推荐）

当你有本地仓库时，系统地分析以下 token 来追踪执行流并识别 flaky 相关的上下文：

- 并发：`t.Parallel`、`go func`、`WaitGroup`、`errgroup`、`chan`、`select`、`atomic.`、`sync.Mutex`、`Lock(`、`Unlock(`、`WithCancel`、`WithTimeout`
- 排序/确定性：`MustQuery(`、`.Check(`、`testkit.Rows`、`ORDER BY`、`Sort`
- 全局/共享状态：包级 `var`、`init()`、`TestMain`、`failpoint.`、全局 `config.` / `variable.` setter
- 清理：`defer`、`t.Cleanup`、`Close()`、`Stop()`、`Disable`、`Drop`、`Remove`
- 执行计划/统计：`EXPLAIN`、`ANALYZE`、`GetTableStats`、`statsHandle`、`plan_cache`、`SetVariable`、`tidb_opt_`

### 3) 全面字典映射（严格）

你必须将结构化分析的发现**详尽地映射到**仓库字典中定义的**完整 key 集合**。不要局限于本文档中列出的常见示例。

对于你发现的每个问题：
1. **搜索完整的 `review_smells.json`（仓库根目录）**：通读完整字典。不要只选第一个看起来相关的。选择与你的结构化发现最精确匹配的 `review_smell` key。
2. **搜索完整的 `taxonomy.json`（仓库根目录）**：评估完整的根因分类列表，分配适当的 `taxonomy` key。
3. 优先选择可操作的、确定性的修复方案（而非"让它通过"的创可贴式修复）。
4. 永远不要发明 key。如果没有匹配的，使用 `unclassified` 并解释症状。

**Primary vs Supporting smell 选择（发现多个 smell 时必须执行）：**

当你在单个 PR 中识别出多个 smell 时，必须指定恰好 **1 个 primary_smell** 和 0-3 个 **supporting_smells**：
- **primary_smell**：最可能是 flaky test 失败**根因**的那个 smell。选择规则：
  1. 优先选择本 PR **新引入**的风险，而非代码库中已存在的问题。
  2. 当 smell 之间存在因果关系时（如 goroutine 竞态导致需要加 `time.Sleep` 作为变通方案），选择**因**（`race_condition_in_async_code`）而非**果**（`time_sleep_for_sync`）。
  3. 当无法判断因果顺序时，选择 `review_smells.json` 中 `related_root_causes` 层级更高/更基础的那个。
  4. **硬规则**：`time_sleep_for_sync` 通常是症状。只要同一 PR 还能合理映射到更底层的异步/并发/Schema/超时类 smell（如 `race_condition_in_async_code`、`ddl_without_wait`、`async_schema_propagation`、`schema_version_race`、`insufficient_timeout`），这些根因 smell 必须作为 `primary_smell`，`time_sleep_for_sync` 只能放 supporting。只有当唯一新增风险就是在**测试代码**里新增固定 sleep 作为同步屏障，且无法归因到更深层原因时，才允许 primary=`time_sleep_for_sync`。
  5. **硬规则**：对查询结果做固定顺序断言时优先 ordering smell。若测试断言固定行序（如 `testkit.Rows(...)` / 对 row slice 做 `require.Equal`），且 query 无 `ORDER BY`（且无显式 sort），`primary_smell` 必须是 `missing_order_by`。`unsorted_result_assertion` 作为 supporting（或当顺序假设来自非 SQL 查询来源，如 Go map/slice 迭代时，可作为 primary）。
  6. **硬规则**：如果 PR 在测试相关代码中新增/修改并发结构（`go func`、channel、worker pool、`t.Parallel` 等），`primary_smell` 应优先 `race_condition_in_async_code`（或 `t_parallel_with_shared_state`），除非更明确的外部依赖 smell 更主导（如 `real_tikv_dependency`、`hardcoded_port_or_resource`）。
  7. **护栏**：`global_variable_mutation` 仅用于真实的全局/包级状态（config/sysvar/failpoint/gofail/singleton）。不要把普通 struct field 或局部变量当成 global。若主要风险是测试间污染/清理不彻底，primary 优先 `insufficient_cleanup_between_tests`，`global_variable_mutation` 放 supporting。
- **supporting_smells**：在同一 PR 中发现的其他真实风险，属于次要或派生的。它们提供有用的上下文，但不是 flaky 的主要驱动因素。

示例：
- 示例 A：`go func(){...}; time.Sleep(...)` → primary=`race_condition_in_async_code`，supporting=`time_sleep_for_sync`
- 示例 B：`tk.MustQuery("select ...").Check(testkit.Rows(...))` 且 query 无 `ORDER BY` → primary=`missing_order_by`，supporting=`unsorted_result_assertion`

当证据较弱时，使用：
- `root_cause_categories: ["insufficient_evidence"]`
- `review_smells: ["needs_more_evidence"]`
…并要求提供失败签名 / CI 链接 / 复现提示。

### 4) 撰写 review 反馈

使用 smell 定义中的 review 问题和建议修复来撰写简洁的评论。

## Review 意见模板（拦截器输出）

使用以下结构（保持简短；必须能让作者直接按建议修）：

- **主要发现 (Primary Finding)**：`<smell_key>` — `<smell_title>`
- **受影响的测试**：`<测试标识符>`
- **Flaky 机理 (Mechanism)**：1–2 句话讲清因果链（根因 → 为什么会不稳定）。
- **证据 (Evidence)**：`path:line` + 简短代码片段（来自本次 diff）
- **修复方案草图 (Fix sketch，优先确定性)**：
  - 2–3 条可执行的步骤。必须至少包含 **1** 条来自 repo root `review_smells.json` 中该 smell 的 `suggested_fixes`，但要结合本 PR 改写成具体建议。
  - 如果 `confidence != high`，把修复写成 **候选方案**，并说明“需要什么证据才能确认是哪一个原因/方案”。（修复建议仍然要给，不能只说不确定）
- **如何验证 (How to verify)**：
  - 1 条最小可复现/自证稳定的方法（例如：`go test ./... -run TestXxx -count=50 -race`）
- **辅助发现 (Supporting Findings)**（如有）：`<smell_key_2>`、`<smell_key_3>`（0–3）。每个 supporting 只写 1 句机制 + 1 条 fix（避免评论膨胀）。
- **置信度 (Confidence)**：`high` | `medium` | `low`
- **推荐动作 (Recommended action)**：`blocker` | `non_blocker` | `needs_more_evidence`
- **问题（来自 `review_smells.json`）**：
  - 必须至少包含 **1** 条来自该 smell 的 `review_questions`，并改写成贴合本 PR 的具体问题。
- **（可选）根因标签**：`<taxonomy_key1>, <taxonomy_key2>`

语气指导（Agent）：
- 使用客观 + 协作的措辞（如"看起来……"、"这可能是时序敏感的，因为……"、"我们能否……？"）。
- 当证据较弱时避免过度自信的断言；要求提供 CI 链接 / 失败签名 / 复现提示。

推荐动作指导（Agent）：
- `blocker`：仅当 `confidence=high` 且你给出了明确的 **机制 + 可执行的确定性修复**（而不是“加大 timeout/加 sleep”）时才建议阻塞。
- `needs_more_evidence`：当 `confidence=medium/low` 或缺少关键上下文时使用。必须明确列出需要补充的内容（CI failure signature/log、是否并行、teardown/cleanup、外部依赖状态等）。
- `non_blocker`：风险存在但本 PR 已显式缓解/影响较小（仍需给机制 + fix sketch + verify）。

置信度指导（Agent）：
- **high**：diff 中直接、明确的信号（如固定 `time.Sleep` 用于同步、goroutine 生命周期未被确定性约束、`t.Parallel()` + 共享/全局状态、硬编码端口/资源、无 sort/order-by 的顺序敏感断言）。修复建议要具体且优先确定性。
- **medium**：可能的 smell 但需要上下文确认（如缺少 `ORDER BY` 但断言可能在其他地方排序）。仍需给出“候选修法”，并明确缺什么上下文来确认。
- **low**：弱或间接的证据。仍给最小安全修法，但更推荐 `needs_more_evidence`，并明确要求 CI 日志 / 失败签名 / 复现提示后再阻塞。

## 高质量评论示例（可直接复制改写）

### 示例 1 — `missing_order_by`（+ `unsorted_result_assertion`）

- **主要发现**：`missing_order_by` — Missing ORDER BY in SELECT queries
- **受影响的测试**：`executor/diagnostics_test.go:TestInspectionResult`（PR 14114）
- **Flaky 机理**：这里对 `SELECT * ...` 的返回结果做了**固定行序**断言，但 SQL 没有 `ORDER BY`。在不同执行/并发/内部遍历顺序下，结果行序可能变化，导致 `result.Check(testkit.Rows(...))` 偶发不一致。
- **证据**：
  - `executor/diagnostics_test.go`：`sql: "select * from information_schema.inspection_result ..."`（无 `ORDER BY`）+ `result.Check(testkit.Rows(cs.rows...))`
- **修复方案草图（优先确定性）**：
  - 为每条被断言顺序的查询补 `ORDER BY`（例如 `ORDER BY rule, item, type`），并在必要时补 tie-breaker 保证严格顺序。（参考 `review_smells.json`: “Add explicit ORDER BY clause to the query”）
  - 若顺序本不重要，把断言改为对顺序不敏感（例如 `.Sort().Check(...)` 或在 check 前对结果排序）。（参考 `review_smells.json`: “Use .Sort() before .Check() in test assertions”）
- **如何验证**：
  - `go test ./executor -check.f TestInspectionResult -count=50`
- **辅助发现**：`unsorted_result_assertion`
- **置信度**：high
- **推荐动作**：blocker
- **问题（来自 `review_smells.json`）**：
  - 这个用例是否确实需要“有序结果”来做断言？如果需要，是否可以在这里加稳定的 `ORDER BY`？

### 示例 2 — `race_condition_in_async_code`（+ `time_sleep_for_sync`）

- **主要发现**：`race_condition_in_async_code` — Race condition in async code
- **受影响的测试**：`util/topsql/reporter/pubsub_test.go:TestPubSubDataSink`（PR 31340）
- **Flaky 机理**：测试里把 `ds.run()` 放到 goroutine 异步跑，然后用固定 `time.Sleep(1s)` 作为“同步屏障”，再去断言 `mockStream` 收到的数据条数。在 CI 负载高/调度不同的情况下，1s 可能不够或时序变化，断言就会和异步处理竞争而偶发失败。
- **证据**：
  - `util/topsql/reporter/pubsub_test.go`：`go func() { _ = ds.run() }()` + `time.Sleep(1 * time.Second)` + `assert.Len(..., 1)`（等）
- **修复方案草图（优先确定性）**：
  - 用确定性同步替换 sleep：例如 mock stream 在 `Send()` 时通过 channel/回调发信号，测试等待该信号（带超时上界）。（参考 `review_smells.json`: “Use channels for goroutine communication” / “Replace sleep with channel/condition variable”）
  - 若无法直接拿到事件信号，用有界 wait loop 或 `require.Eventually`（合理 interval + max timeout），避免“一次 sleep 赌运气”。（参考 `review_smells.json`: “Use wait loop with backoff”）
- **如何验证**：
  - `go test ./util/topsql/reporter -run TestPubSubDataSink -count=50 -race`
- **辅助发现**：`time_sleep_for_sync`
- **置信度**：high
- **推荐动作**：blocker
- **问题（来自 `review_smells.json`）**：
  - 这里是否有比 `time.Sleep()` 更好的同步方式（channels/mutex/condition/event notification）？

## 评测建议（可选）

如果把这个 skill 当作合入前的 **拦截器**，成功标准不应只看 “smell 精准命中”，建议同时跟踪：
- **Recall**：是否能稳定把真实引入 flaky 风险的 PR 判为 `risk`？
- **评论可修复性（Actionability）**：作者是否能仅凭评论就定位问题并按建议修复？

建议一个轻量抽样评分（例如抽 N=10 个 PR；每项 0–2 分）：
- **证据具体性**：是否指向明确的变更点（文件/测试/行号/关键语句）？
- **机理清晰度**：是否解释清楚因果链（根因 vs 症状），避免泛泛而谈？
- **修复可执行性**：是否给出可直接实现的“确定性优先”步骤（而不是只提“加大 timeout/加 sleep”）？

可自动化的低成本回归护栏：
- 模板合规率：是否包含 Mechanism/Evidence/Fix/Verify + 推荐动作。\n- 字典落地：primary smell 至少包含 1 条来自 `review_smells.json` 的问题和 1 条修复建议，并且改写成贴合本 PR 的具体内容。

## 常见高信号 Smell（代表性示例）

这些能捕获大部分 flaky test 回归，但**并非详尽无遗**。你仍然必须查阅完整的 `review_smells.json` 进行精确映射。使用 `review_smells.json` 获取：描述 → 为什么有风险 → review 问题 → 建议修复 → 相关根因。

- 确定性 / 排序：
  - `missing_order_by`、`unsorted_result_assertion`、`relying_on_map_iteration_order`
  - **需要验证的结构化模式（TiDB 测试）**：
    - 查找 `tk.MustQuery(...).Check(testkit.Rows(...))` / `tk.MustQuery(...).Sort().Check(...)` 并确认排序确实已稳定。
    - 如果查询被断言为有序列表但缺少 `ORDER BY`，通常是 `missing_order_by` / `unsorted_result_assertion`。
    - 如果 `ORDER BY` 存在但排序键**不唯一**，tie 排序仍可能是不确定的 → 降级为 `medium` 并要求提供稳定的 tie-breaker。
    - 如果结果来自遍历 `map[...]...` 到 slice（或打印输出），怀疑 `relying_on_map_iteration_order`。
    - 集成测试：检查 `tests/integrationtest/t/` 下的 `.test` 文件中没有 `ORDER BY` 但 `.result` 文件假设固定行顺序的查询。
- 并发 / 共享状态：
  - `t_parallel_with_shared_state`、`race_condition_in_async_code`、`global_variable_mutation`、`insufficient_cleanup_between_tests`
  - **需要验证的结构化模式（Go 测试）**：
    - `race_condition_in_async_code`：`go func` / 后台 worker + 共享变量/结构体/map/slice 在无 mutex/atomic/channel 传递的情况下被访问；或 goroutine 已启动但测试没有**确定性地等待**它（无 `WaitGroup`、无 channel 同步、无 context cancel）。还要注意注册到系统中异步运行的回调/hook 函数。
    - `t_parallel_with_shared_state`：`t.Parallel()` + 共享 DB/schema/端口/临时目录/全局 config/failpoint。确认隔离确实是每个测试独立的。
    - `global_variable_mutation`：包级 `var`、`init()`、`TestMain`、或全局 setter（`config`/`variable`/failpoint）在测试中被修改；确保通过 `defer` / `t.Cleanup` 恢复。常见 TiDB 模式：`config.UpdateGlobal(...)`、`variable.SetSysVar(...)`、`failpoint.Enable(...)` 没有对应的 disable/restore。
    - `insufficient_cleanup_between_tests`：创建了资源（表/文件/goroutine/failpoint/server）但没有可靠地清理。注意 `CREATE TABLE` 没有 `DROP`、`failpoint.Enable` 没有 `defer failpoint.Disable`、启动了 goroutine 但没有 join。

- 异步 / 时序：
  - `time_sleep_for_sync`、`insufficient_timeout`、`async_wait_without_backoff`、`clock_skew_dependency`
  - **需要验证的结构化模式（Go 测试）**：
    - `time_sleep_for_sync`：裸 `time.Sleep(...)` 用作同步屏障（不在重试/eventually 循环中）。
    - `insufficient_timeout`：测试中等待异步操作时使用硬编码的短超时（`time.Second`、`time.Millisecond * 100`）；查找 `context.WithTimeout`、`time.After`、`time.NewTimer` 中的紧凑边界。
    - `async_wait_without_backoff`：轮询循环（`for { ... time.Sleep(...) }`）没有指数退避或有界重试次数；也包括 `require.Eventually` 使用非常短的轮询间隔，可能没有给操作足够的时间。
    - `clock_skew_dependency`：测试使用 `time.Now()` 进行排序/比较、`time.Since()` 进行断言、或 `AS OF TIMESTAMP` / stale read 功能依赖时钟精度。
- 执行计划 / 统计信息敏感：
  - `assert_exact_plan_or_cost`、`statistics_sensitive_test`、`plan_cache_dependency`
  - **需要验证的结构化模式（TiDB 测试）**：
    - `assert_exact_plan_or_cost`：`tk.MustQuery("EXPLAIN ...")` 断言精确的执行计划算子名称、行数或代价值；`tk.MustQuery("EXPLAIN ANALYZE ...")` 检查精确的执行统计。任何 `EXPLAIN` 输出与 `Check(testkit.Rows(...))` 比较都是可疑的，除非执行计划被 hint 固定。
    - `statistics_sensitive_test`：依赖优化器统计信息处于特定状态的测试——查找 `ANALYZE TABLE` 的存在/缺失、行估计的断言、`INSERT` 数据后立即断言执行计划但没有 `ANALYZE` 的测试。还有：设置 `tidb_opt_*` session 变量或修改统计相关配置的测试。
    - `plan_cache_dependency`：执行 prepared statement 或 `EXECUTE` 且假设冷/热 plan cache 状态的测试。查找没有显式 `ADMIN FLUSH PLAN_CACHE` 或 plan cache 变量切换的 `PREPARE`/`EXECUTE` 序列。
- DDL / schema 传播：
  - `ddl_without_wait`、`schema_version_race`、`async_schema_propagation`
  - **需要验证的结构化模式（TiDB 测试）**：
    - `ddl_without_wait`：在异步 DDL 模式下发出 DDL 语句（`ALTER`、`CREATE INDEX`、`ADD COLUMN`）但没有等待完成。
    - `schema_version_race`：测试发出 DDL 后立即读取 `information_schema` 或使用新 schema，但没有确保 schema 版本已传播。多域测试或多 TiDB 实例的测试尤其可疑。
    - `async_schema_propagation`：测试在 goroutine 或回调中创建/修改 schema 对象，传播时序不确定。
- 外部依赖 / 资源：
  - `real_tikv_dependency`、`network_without_retry`、`hardcoded_port_or_resource`

## 准确性护栏（误报防护）

使用以下检查来减少噪音/错误标记。如果无法确认，保持置信度 `medium/low` 并要求提供上下文。

- `time_sleep_for_sync`：
  - 确认它被用作**固定的同步屏障**。
  - 如果 sleep 是**重试/退避/eventually** 模式的一部分（且有界），可能是可接受的——不要自动标记为 flaky。
- `missing_order_by` / `unsorted_result_assertion`：
  - 验证测试是否已经对结果排序（或查询对断言的字段有确定性排序）。
  - 如果排序在其他地方处理，降级为 `medium` 并指出需要确认的位置。
- `t_parallel_with_shared_state`：
  - 如果测试使用 `t.Parallel()`，检查资源是否真正隔离（唯一 DB/schema/临时目录）以及是否存在包级/共享状态。
  - 如果隔离是显式且完整的，避免标记或降低置信度。
- `global_variable_mutation` / `insufficient_cleanup_between_tests`：
  - 查找 `t.Cleanup`、`defer` 重置和 suite teardown 来恢复全局状态。
  - 如果清理存在但脆弱，精确指出（什么被重置，何时重置）。
- `race_condition_in_async_code`：
  - 优先在能指出跨 goroutine **无同步**的具体共享状态访问、或 goroutine 生命周期未被测试确定性约束时标记。
  - 如果代码明确使用了正确的同步（`WaitGroup`/channel/mutex/atomic）且测试等待完成，降级或避免标记。
- `assert_exact_plan_or_cost` / `statistics_sensitive_test`：
  - 如果测试使用优化器 hint（`/*+ USE_INDEX(...) */`、`/*+ HASH_JOIN(...) */`）来固定执行计划，执行计划断言可能是稳定的——不要标记。
  - 如果在断言前调用了 `ANALYZE TABLE` 且数据是确定性的，统计依赖是受控的——最多降级为 `medium`。
  - 当执行计划/代价断言**没有 hint** 且没有显式 `ANALYZE` 时标记，尤其是在数据修改之后。
- `hardcoded_port_or_resource`：
  - 如果代码使用临时端口（`:0`）或端口分配器 / 每个测试唯一的临时目录，可能不是这个 smell。

## 输出优先级（Agent）

- 优先输出**更少、更高置信度**的发现，而非一长串列表。
- 按**受影响的测试**分组发现；每个测试最多几条可操作的评论。
