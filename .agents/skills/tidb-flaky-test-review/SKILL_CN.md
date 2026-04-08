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
- **supporting_smells**：在同一 PR 中发现的其他真实风险，属于次要或派生的。它们提供有用的上下文，但不是 flaky 的主要驱动因素。

当证据较弱时，使用：
- `root_cause_categories: ["insufficient_evidence"]`
- `review_smells: ["needs_more_evidence"]`
…并要求提供失败签名 / CI 链接 / 复现提示。

### 4) 撰写 review 反馈

使用 smell 定义中的 review 问题和建议修复来撰写简洁的评论。

## Review 意见模板

使用以下结构（保持简短；链接到证据）：

- **主要发现 (Primary Finding)**：`<smell_key>` — `<smell_title>`
- **辅助发现 (Supporting Findings)**（如有）：`<smell_key_2>`、`<smell_key_3>`（0-3 个额外 smell）
- **受影响的测试**：`<测试标识符>`
- **证据**：`path:line` + 简短代码片段
- **置信度**：`high` | `medium` | `low`
- **为什么有风险**：1 句话
- **问题**：
  - Q1
  - Q2
- **建议修复**：
  - 修复 1
  - 修复 2
- **（可选）根因标签**：`<taxonomy_key1>, <taxonomy_key2>`

语气指导（Agent）：
- 使用客观 + 协作的措辞（如"看起来……"、"这可能是时序敏感的，因为……"、"我们能否……？"）。
- 当证据较弱时避免过度自信的断言；要求提供 CI 链接 / 失败签名 / 复现提示。

置信度指导（Agent）：
- **high**：diff 中直接、明确的信号（如 `time.Sleep` 用于同步、`t.Parallel()` 在有共享/全局状态的测试中、goroutine 访问共享状态但无同步/join、硬编码端口/资源、无 sort/order-by 的顺序敏感断言）。
- **medium**：可能的 smell 但需要上下文确认（如缺少 `ORDER BY` 但断言可能在其他地方排序；超时可能是合理的；异步等待可能已有退避）。
- **low**：弱或间接的证据；使用 `needs_more_evidence` / `insufficient_evidence` 并要求提供 CI 日志 / 失败签名 / 复现提示。

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
