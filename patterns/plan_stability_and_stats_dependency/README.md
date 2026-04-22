# `plan_stability_and_stats_dependency`

这个目录承接 “Plan 稳定性与统计信息依赖” 这条 unified direction 的正式化工作。

它不是单个 smell 的镜像目录，而是从下面三个 smell 的并集出发，经过 `patch-first` 的全量人工复读后，再反向抽机制簇：

- `assert_exact_plan_or_cost`
- `statistics_sensitive_test`
- `plan_cache_dependency`

## 当前状态

- union source set：`140`
- smell 规模：
  - `assert_exact_plan_or_cost = 94`
  - `statistics_sensitive_test = 47`
  - `plan_cache_dependency = 25`
- overlap：
  - `assert + stats = 23`
  - `assert + cache = 2`
  - `stats + cache = 1`
  - triple overlap = `0`
- 模块集中度：
  - `planner = 103`
  - `statistics = 16`
  - `executor = 10`

这说明：

- 这 `140` 只能先作为人工 review 的输入全集，不能直接当成 family inventory。
- 当前已经 patch-first 重读并 formalize 的，只是其中一块更窄的子区域：
  - [`assert_exact_plan_or_cost`](../assert_exact_plan_or_cost/README.md)
- 这条已 formalize 的子区域，当前结论是：
  - `94 / 94` 已人工复读
  - retained `51`
  - 已落盘 `5` 条 sibling JSON

所以这次“扩展”真正新增的 patch-first 阅读增量，主要是：

- `23` 个 `statistics_sensitive_test only`
- `22` 个 `plan_cache_dependency only`
- `1` 个 `statistics_sensitive_test + plan_cache_dependency`

也就是相对现有 `assert_exact_plan_or_cost` 子 family 之外，这次扩展真正新增了 `46` 个需要单独 patch-first 补读的 case。

## 当前扩展进度

目前 `46` 个 non-assert delta case 已经 patch-first 补读完：

- `statistics_sensitive_test only = 23 / 23`
- `plan_cache_dependency only = 22 / 22`
- `statistics_sensitive_test + plan_cache_dependency = 1 / 1`

当前初读结论是：

- provisional retained：`28`
- provisional exclude / migrate：`18`
- 已 formalize umbrella sibling：`5`

读完这 `46` 条之后，当前最像会长成 umbrella sibling / boundary cluster 的机制有 `5` 类：

1. stats 还没真正 load / materialize / apply，就去断言
2. histogram / selectivity / cost / correlation 等导出数值被当成精确常数
3. analyze scope / analyze version / sampling / predicate-column inputs 没有先 pin 住
4. cache-hit / read-from-cache 被当成逐次硬约束，没有先等 cache ready，也没有把“偶发 miss”从“真失败”里分开
5. plan cache / non-prepared cache / prepared stmt cache 会把 execution-time context 藏掉；如果不显式禁用、重算或隔离，测试观测到的就不是它以为自己在验证的那个 runtime state

同时也已经出现了几个明显的边界回流：

- `pr-60333` patch-first 更像现有 `assert_exact_plan_or_cost/b2`
- `pr-66928` 虽然 source smell 同时挂了 `stats + cache`，但 patch-first 主修法仍然是 `h1`：先把 stats 真正 load 到 cache
- `pr-16525` 更像 test isolation / shared suite state
- `pr-29197` 更像 randomized input formatting / string determinism
- `pr-43204` 是 mixed edge：主补丁更像 cached prepared stmt 的 execution-time context，但测试层又顺手补了 `ORDER BY`
- `pr-65619` 更像 random schema generation + concurrent DML deadlock tolerance

另外还观察到一个暂时不够成簇的 singleton：

- `pr-8556`
  - 更像 “如果测试真的要断言 cache 行为，memory / guard / capacity 这类 cache environment knob 也要先 pin 住”
  - 当前只有单点证据，先不急着升成正式 sibling

## 方法论 Hard Rules

1. `140` 个 case 只能定义这条 unified direction 的输入全集，不能直接定义 sibling。
2. 进入人工 review 之后，不能利用下面这些字段做初筛或直接归桶：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
3. 现有 [`assert_exact_plan_or_cost/subpatterns/*.json`](../assert_exact_plan_or_cost/subpatterns/) 只能拿来做边界参考，不能反向拿来给这 `140` 个 case 套标签。
4. 正确顺序只能是：
   - 先读 patch / test diff 本体
   - 再决定是否支持并入这条 unified direction
   - 如果支持，再判断更像现有哪块机制，还是需要新增 sibling
   - 最后才修 `subpattern JSON` / `retrieval_signals.json`

## 这条 unified direction 当前承认的已知子区域

目前只承认一块已经 patch-backed 且 formalized 的子区域：

- [`assert_exact_plan_or_cost`](../assert_exact_plan_or_cost/README.md)

它已经覆盖了 `5` 条稳定 sibling：

1. 精确 explain / plan tree / operator 文本断言应降到更稳定表示层
2. `EXPLAIN ANALYZE` / cost / runtime metric / estimate 数值不应做整串硬编码
3. 精确 plan 断言前必须显式 pin planner inputs
4. 精确 plan 断言前必须先冻结统计信息
5. 精确 plan 断言前必须固定 runtime context

但这不等于：

- `statistics_sensitive_test only` 的 `23` 个 case 已经自动被吃下
- `plan_cache_dependency only` 的 `22` 个 case 已经自动被吃下
- umbrella family 已经完成 formalization

相反，当前合理的判断是：

- 现有 `5` 条 sibling 很可能只覆盖了这条 unified direction 的一部分
- 新增 `46` 个 delta case 读完之后，才有资格决定：
  - 是继续并入现有 `b4 / b5`
  - 还是拆出新的 sibling

## 当前已 formalize 的 umbrella sibling

| sibling | count | 机制摘要 | formalization 状态 |
|---|---:|---|---|
| 统计信息真正 `load / materialize / apply` 之前不应断言依赖它的计划或统计输出 | `8` | `analyze` / `load stats` / DDL 后 stats 尚未真正 ready，就去断言 stats-backed plan 或 stats output | 已 formalize |
| histogram / selectivity / correlation / async-load item count 这类统计派生数值不应做 exact constant assertion | `5` | 测试真正关心的是统计性质或趋势，但原断言把 bucket 数、row-count、correlation、async-load item 数写成精确常数 | 已 formalize |
| analyze inputs / sampling / version / predicate-column scope 必须先钉死 | `6` | stats 虽然 ready，但 `samplerate` / version / all-columns / predicate-column scope 没 pin，导致收集出来的 stats 合法变化 | 已 formalize |
| cache-hit / read-from-cache 不应写成逐次硬断言；必须先等 cache ready，再断稳定性质 | `4` | 测试真正想验证的是 cache 行为，但原断言把 `last_plan_from_cache` / `UnionScan` / 每轮 hit 当成硬不变量 | 已 formalize |
| cache reuse 不应遮蔽 execution-time context | `3` | prepared / non-prepared cache / constant fold 把 stale-read ts、binding、side effect、privilege 这类执行期上下文藏掉 | 已 formalize |

## 当前扩展策略

1. 保留现有 `assert_exact_plan_or_cost` family 不动
   - 它已经是一块 patch-first 读完并 formalize 的子区域
2. 先把 `46` 个 non-assert delta case 全量 patch-first 复读
   - 这一步已经完成
3. 边界复核已经完成，stats 侧三条、cache 侧两条 generalized sibling 已经落盘
4. 下一步继续 formalize：
   - 当前没有比 `h6` 更强的新候选；先继续观察 singleton 是否成簇
5. 先把当前 `5` 条已 formalize sibling 的 retrieval layer 补齐
   - 已新增 [retrieval_signals.json](./retrieval_signals.json)
   - 这层仍然只服务 coarse retrieval，不代表 umbrella boundary 已经彻底封板

## retrieval 当前状态

- 当前已新增 family-level [retrieval_signals.json](./retrieval_signals.json)
  - 覆盖当前 `5` 条已 formalize sibling
  - broad `rg_template` 直接从 [给agent的仓库扫描检索信号.md](./%E7%BB%99agent%E7%9A%84%E4%BB%93%E5%BA%93%E6%89%AB%E6%8F%8F%E6%A3%80%E7%B4%A2%E4%BF%A1%E5%8F%B7.md) 里的 patch-backed draft 提升而来
- 这版 retrieval 仍然只做 **coarse retrieval**
- 用当前 `26` 条 full positive patch 文本回放，patch-proxy hit rate 是：
  - `26 / 26 = 100%`

需要强调：

- 这里的 `100%` 是正例 patch-proxy recall
- 不是实际仓库扫描 precision
- 所以后续仍然要去真实 TiDB 仓库测炸量，而不是把 broad hit 直接当 verdict

## 当前剩余最值得 formalize 的候选机制

这里只能作为 review 假设，不是既定 sibling：

1. cache environment knob 也要先 pin 住（当前仍只有 `pr-8556` 这一个 singleton）

现在 `46` 个 delta case 已经 patch-first 读完，stats/cache 两侧值得 formalize 的主簇也都已经落盘；当前真正剩下的是继续观察 `h6` 是否会形成可复用小簇。

## retained-only 边界复核：与现有 `b2 / b4 / b5` 的关系

这一步的目标不是立刻写新 JSON，而是先回答一个更硬的问题：

- 这些 retained case，哪些真的只是现有 `assert_exact_plan_or_cost` sibling 的外延？
- 哪些虽然机制相邻，但 scope 已经明显超出 exact-plan family？

当前复核结论可以先落成 3 类：

### A. 可以明确并回现有 sibling

- 并回现有 `b2`：`1`
  - `pr-60333`
  - 原因：
    - patch 主修法就是把 derived numeric output 从 exact constant 改成更稳的 numeric assertion
    - 更像现有 `EXPLAIN ANALYZE` / cost / estimate numeric normalization 的边界回流

当前没有 delta 子簇可以直接整体并回现有 `b4` 或 `b5`。

### B. 机制相邻，但不应硬并回现有 sibling

- `h1`（`8`，含 `pr-66928`）
  - 与现有 `b4` 最近
  - 但不应硬并回 `b4`
  - 原因：
    - `b4` 的前提是“exact plan assertion before stats freeze”
    - `h1` 覆盖的是更一般的 “stats 尚未 materialize / load / apply 就断言”
    - 它不只服务 exact plan，也覆盖 stats output / usage / cardinality 断言

- `h3`（`6`）
  - 也和现有 `b4` 相邻
  - 但不应硬并回 `b4`
  - 原因：
    - `h3` 主修法是 pin analyze inputs / sampling / version / predicate-column scope
    - 这比 `b4` 的 “freeze stats for exact plan” 更宽
    - 若直接并回 `b4`，会把 umbrella family 再次缩回 exact-plan 视角

- `h5`（`3`，已 formalize）
  - 与现有 `b5` 机制最近
  - 但当前更适合视为 “generalized runtime-context sibling”
  - 原因：
    - `b5` 是 exact plan assertion 受 runtime context 污染
    - `h5` 更宽，覆盖 cached prepared stmt / non-prepared cache / extension side effect 把 execution-time context 遮蔽
    - 这些 patch 不一定在断 exact plan，但主修法仍然是“不能让 cache 把 runtime context 藏掉”

### C. 暂放观察池

- `h6` singleton：`1`
  - `pr-8556`
  - 当前更像：
    - cache environment knob 也要先 pin 住
  - 但现在只有单点 patch-backed 证据，不急着 formalize

## 基于这轮复核的推荐 formalization 顺序

如果下一步要继续收敛成正式 sibling，而不是继续做宽泛讨论，当前建议顺序是：

1. `h6`
   - 当前仍只有 `pr-8556`
   - 先看后续是否还能补到第二、第三个 patch-backed 正例

## 当前目录结构

- [../plan_stability_and_stats_dependency_140_case_source_set.tsv](../plan_stability_and_stats_dependency_140_case_source_set.tsv)
  - 这条 unified direction 的 `140` 个 case 输入全集
- [../plan_stability_and_stats_dependency_140_case_人工review工作板.md](../plan_stability_and_stats_dependency_140_case_%E4%BA%BA%E5%B7%A5review%E5%B7%A5%E4%BD%9C%E6%9D%BF.md)
  - 当前这轮扩展的人工作业入口
- [../assert_exact_plan_or_cost/README.md](../assert_exact_plan_or_cost/README.md)
  - 当前已 formalize 的窄子 family
- [../assert_exact_plan_or_cost/assert_exact_plan_or_cost_94_case_人工review工作板.md](../assert_exact_plan_or_cost/assert_exact_plan_or_cost_94_case_%E4%BA%BA%E5%B7%A5review%E5%B7%A5%E4%BD%9C%E6%9D%BF.md)
  - 已经完成的 `94` case patch-first 复读记录
- [给agent的仓库扫描检索信号.md](./%E7%BB%99agent%E7%9A%84%E4%BB%93%E5%BA%93%E6%89%AB%E6%8F%8F%E6%A3%80%E7%B4%A2%E4%BF%A1%E5%8F%B7.md)
  - 当前这条 umbrella 的 broad `rg_template` 校准说明与正例回放结果
- [retrieval_signals.json](./retrieval_signals.json)
  - 当前 `5` 条已 formalize sibling 的正式 retrieval layer
- `subpatterns/`
  - 当前已 formalize 的 umbrella sibling JSON

## 下一步优先级

1. 继续观察 `h6` 是否能成簇
2. 先在真实 TiDB 仓库上校准当前 `retrieval_signals.json` 的 candidate 量级、precision 和炸量
