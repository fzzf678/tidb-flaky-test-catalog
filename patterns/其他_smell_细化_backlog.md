# 其他 smell 细化 backlog

这个文件记录 `race_condition_in_async_code` 之外，下一批最值得继续细化的 smell backlog。

目标不是再停留在 smell 名字层面，而是把它们整理成：

- 哪些方向最值得优先 formalize
- 每个方向大概还能拆出哪些**机制级** subpattern
- 哪些方向更适合拿来做“历史 flaky case 过滤 / 仓库扫描”

## 排序口径

优先级按下面 4 个维度综合判断：

1. `union_cases`
   - 把同一方向下多个相邻 smell 合并后，按 case 去重得到的规模
2. 机制集中度
   - 是否已经明显围绕同一类 root cause 聚集，而不是一个大杂烩
3. agent 可操作性
   - 能不能比较自然地收敛成 grep / path / code-shape 都稳定的小粒度 subpattern
4. 对“过滤历史 flaky case”的直接收益
   - 是否适合先做 candidate retrieval，再人工逐条判断

注意：

- 下面的 `union_cases` 都是**方向级去重 case 数**
- 不是承诺“全部都能吃下”
- 真正开始做时，仍然要像 `race_condition_in_async_code` 一样，逐例抽机制，不接受 smell 级大桶直接 formalize

## 当前建议优先级

| 优先级 | 方向 | 来源 smell | union_cases | 适合做历史 flaky 过滤 | 当前判断 |
|---|---|---|---:|---|---|
| P0 | 结果顺序确定性 | `unsorted_result_assertion` + `missing_order_by` + `relying_on_map_iteration_order` | 197 | 很强 | 最值得先做 |
| P1 | Plan 稳定性与统计信息依赖 | `assert_exact_plan_or_cost` + `statistics_sensitive_test` + `plan_cache_dependency` | 140 | 很强 | 适合第二波立即跟进 |
| P2 | 测试隔离与全局状态污染 | `global_variable_mutation` + `insufficient_cleanup_between_tests` + `t_parallel_with_shared_state` + `shared_table_without_isolation` | 276 | 中强 | 总收益很大，但必须先细拆 |
| P3 | 异步等待与 schema 传播 | `time_sleep_for_sync` + `async_wait_without_backoff` + `async_schema_propagation` + `ddl_without_wait` + `insufficient_timeout` | 236 | 中强 | 值得做，但要把“症状 smell”压回具体等待机制 |

如果只做 1 个方向，先做 `结果顺序确定性`。

如果只做前 2 个方向，做：

1. `结果顺序确定性`
2. `Plan 稳定性与统计信息依赖`

## P0. 结果顺序确定性

详细规划见：

- `patterns/结果顺序确定性_细化规划.md`
- `patterns/nondeterministic_result_order/README.md`

当前进度：

- 第一批 `3` 条已经正式化到 `patterns/nondeterministic_result_order/`
- 剩下待继续 formalize 的主要是：
  - `runtime / executor` keep-order sibling
  - `sort helper / comparator` sibling

### 为什么排第 1

- `union_cases = 197`
- 方向级规模已经足够大，值得单独开 family
- 但 family purity 不能再靠现有字段口径引用，必须回到 `197` 个 patch 全量人工 review 重建
- grep / code review 信号很硬
- 很适合直接拿来做历史 flaky case 过滤

### 典型模块

- `executor`
- `planner`
- `ddl`
- `domain`
- `statistics`
- `br`

### 建议第一批 subpattern

1. `map / collection / helper` 收集结果后未排序就断言
   - 这条最纯，也最容易做成高精度 subpattern
2. 多行结果断言缺少显式无序归一化
   - 但必须收紧到“多行 + 无 `ORDER BY` + 顺序敏感断言”
   - 不能把“没 `.Sort()`”直接当成 risk
3. ``ORDER BY` 仍然不够：排序键 ties + `LIMIT` / compare`
   - 这是和普通缺 `ORDER BY` 不同的一条 sibling
4. `UNION / JOIN / 并行 scan / partition merge` 的输出顺序被默认当成稳定
   - 这一条更接近 runtime order-preservation bug
5. `sort helper / comparator` 自身不稳定
   - 例如 comparator 不是 strict total order、或 repeated unstable sort

### 代表 case

- `pr-34130`
- `pr-3781`
- `pr-44269`
- `pr-45513`

### 预期收益

- `197` 个 patch 的 patch-first 人工 review 已完成
- 最终保留下来的 `nondeterministic_result_order` family 正例是 `100` 条，排除 `97` 条
- 当前 `5` 个 sibling 的规模分别是：
  - `44 / 35 / 13 / 6 / 2`
- 这是最适合作为“agent 扫历史 flaky case”下一条主线的方向

### 开工建议

1. 已完成 `197` 个历史 case 的全量 patch-first 人工 review，并已归到 `5` 个机制桶
2. 第一批已 formalize：
   - `map / collection / helper` 收集结果后未排序就断言
   - 多行结果断言缺少显式无序归一化
   - runtime keep-order / should-preserve-order
   - sort helper / comparator / tie-breaker instability
   - ``ORDER BY` ties + `LIMIT` / compare``
3. 下一步优先做：
   - 校准 `runtime keep-order` 这条的 retrieval precision
   - 校准 `sort helper / comparator / tie-breaker instability` 这条的 retrieval precision
4. 只有在当前 TiDB 仓库 precision 检查通过后，再继续扩更细的 sibling 或追加 negative guards

## P1. Plan 稳定性与统计信息依赖

### 为什么排第 2

- `union_cases = 140`
- 高度集中在 `nondeterministic_plan_selection`（当前统计里有 `126` 个）
- 模块非常集中，`planner` 一家就占了 `103`
- 很容易转成 agent 可执行的 plan-test 子模式

### 典型模块

- `planner`
- `statistics`
- `executor`

### 建议第一批 subpattern

1. 断言精确 `EXPLAIN` 文本 / plan tree / operator 顺序
   - 只要优化器、编码器、格式器略有变化就容易炸
2. 断言精确 cost / runtime metric / `EXPLAIN ANALYZE` 数值
   - 例如 `copr_cache_hit_ratio`、精确耗时、精确 cost
3. 测试没有冻结统计信息，却断言特定 plan
   - 应拆成“依赖 stats 可见性 / analyze 结果”的独立模式
4. 测试受 plan cache / prepared stmt cache / optimizer 全局开关影响
   - 相当适合跟 `global_variable_mutation` family 做 sibling 区分
5. plan 期望其实只是“性质正确”，却写成“输出完全一致”
   - 这条偏 assertion style，但在 planner 里收益很高

### 代表 case

- `pr-16378`
- `pr-21071`
- `pr-21657`
- `pr-22677`

### 预期收益

- 首轮建议做 `4-6` 个 subpattern
- 保守估计可先吃下 `90-120` 个方向内 case
- 对 `planner` / `executor` 历史 flaky 过滤特别有价值

### 开工建议

1. 先做“精确 explain / plan 文本断言”
2. 再做“精确 cost / runtime metric 断言”
3. 然后补“统计信息未冻结”和“plan cache 依赖”

## P2. 测试隔离与全局状态污染

### 为什么排第 3

- `union_cases = 276`，是当前几个方向里最大的
- 但它内部明显更散，不能把 smell 本身直接当 family 用
- 真正高收益的是把它细拆成一批 test isolation 子模式

### 典型模块

- `executor`
- `ddl`
- `server`
- `planner`
- `domain`
- `session`
- `config`

### 建议第一批 subpattern

1. 测试改全局 `config / flag / logger / timezone / sysvar` 后没有 restore
2. `domain / store / session / background worker` 没有在 test 结束时关干净
3. goroutine / iterator / watcher / leak 类资源没 cleanup，污染后续测试
4. `t.Parallel()` 或并行 suite 下运行 shared-state 测试
5. 共享 table / db / fixture name，没有隔离命名空间
6. suite setup 改 process-global 状态，应该迁到 `TestMain`、serial suite 或 per-test cleanup

### 代表 case

- `pr-3414`
- `pr-4591`
- `pr-14296`
- `pr-14681`

### 预期收益

- 首轮建议做 `5-7` 个 subpattern
- 保守估计可先吃下 `120-180` 个方向内 case
- 这条线总收益很高，但不建议在没有明确细粒度机制之前直接 formalize

### 开工建议

1. 先把“改全局状态要 restore”和“domain/store/session 没 cleanup”拆出来
2. 再做“parallel 下 shared state”与“shared fixture/table 没隔离”
3. 最后再回头处理更分散的 suite/test infra 边角样本

## P3. 异步等待与 schema 传播

### 为什么排第 4

- `union_cases = 236`
- root cause 很集中在 `async_timing_issue`（当前统计里有 `196` 个）
- 但这里面有一部分 smell 仍然偏“症状”，尤其 `insufficient_timeout`
- 所以值得做，但要强制往“具体等待机制”收，不要停在 timeout/sleep 级别

### 典型模块

- `ddl`
- `executor`
- `domain`
- `server`
- `txn`
- `br`

### 建议第一批 subpattern

1. 用固定 `time.Sleep` 等待 DDL / schema / async task 完成
2. 轮询没有 backoff，没有明确终止条件或事件信号
3. DDL 后没等 schema change / owner version / schema sync 就断言
4. 没等 GC / delete-range / async commit / 后台任务真正完成就断言
5. 把“超时太短”降级为 sibling，而不是独立 family
   - 只有能落回具体等待机制时才收进来

### 代表 case

- `pr-14805`
- `pr-18205`
- `pr-24082`
- `pr-29499`

### 预期收益

- 首轮建议做 `4-6` 个 subpattern
- 保守估计可先吃下 `100-150` 个方向内 case
- 如果近期目标偏 `ddl / domain / txn`，这条线可以和 P2 互换顺序

### 开工建议

1. 先做“sleep 等异步事件”与“DDL/schema propagation 没等”
2. 再做“轮询无 backoff / 无终止条件”
3. 最后才处理 `insufficient_timeout` 这类症状样本

## 当前不建议优先开的方向

### `needs_more_evidence`

- 量很大，但这是证据桶，不是机制桶
- 更适合做 triage 质量治理，不适合直接 formalize 成 subpattern family

### `insufficient_timeout`

- 不建议单独开 family
- 应优先吸收到“异步等待与 schema 传播”里，按具体等待机制拆

### `deprecated_test_framework_usage`

- 这是迁移/框架使用问题
- 有价值，但对“过滤历史 flaky case”的直接收益不如前 4 组

### `real_tikv_dependency` / `randomized_test_input` / `hardcoded_port_or_resource`

- 可以留作后续专项
- 但当前规模、集中度和 agent 可操作性都不如前 4 组

## 建议排期

### 第一阶段

1. `结果顺序确定性`
2. `Plan 稳定性与统计信息依赖`

### 第二阶段

1. `测试隔离与全局状态污染`
2. `异步等待与 schema 传播`

### 如果只想先验证“agent 能不能扫历史 flaky”

先做：

1. `结果顺序确定性`
2. `Plan 稳定性与统计信息依赖`

这两条的共同特点是：

- case 足够多
- 机制集中
- grep / code-shape 更稳
- 最容易转成 candidate retrieval + 人工判定 的工作流
