# `plan_stability_and_stats_dependency` 140 case 人工 review 工作板

这个文件只记录一件事：

- 对 `140` 个 patch 做 **patch-first 的全量人工复读**

这里不接受：

- field-based 初筛
- 直接套用已有 `subpattern JSON`
- 根据 case JSON 里的解释字段先做归类

## Hard Rules

1. source set 是当前带有下面任一 smell 的 `140` 个 case：
   - `assert_exact_plan_or_cost`
   - `statistics_sensitive_test`
   - `plan_cache_dependency`
2. 进入人工 review 之后，只看：
   - patch subject
   - 改动到的测试文件 / planner / statistics / executor 路径
   - 实际 diff 行
3. 下面这些字段不能用来决定 case 属于哪个 bucket：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
4. 现有 `assert_exact_plan_or_cost/subpatterns/*.json` 只能做边界参考，不能拿来直接给 `140` 个 case 打标签。
5. 正确顺序只能是：
   - 先读 patch
   - 再决定是否支持并入这条 unified direction
   - 如果支持，再判断更像已有机制，还是需要新 sibling

## 当前进度

- unified source set：`140 / 140`
- 已有窄子 family patch-first 复读：
  - `assert_exact_plan_or_cost` 子集 `94 / 94`
- 当前扩展新增的 delta queue：
  - `46 / 46`
- 当前这轮新增 delta queue 已读：
  - `46 / 46`
- 其中：
  - `statistics_sensitive_test only = 23 / 23`
  - `plan_cache_dependency only = 22 / 22`
  - `statistics_sensitive_test + plan_cache_dependency = 1 / 1`

这意味着：

- 现有可直接复用的人工阅读结论，只覆盖 `94` 个带 `assert_exact_plan_or_cost` smell 的 case
- 但还不能把 umbrella direction 当成“已经 formalize 完”的 family
- 现在已经不缺 patch 阅读本身，真正剩下的是：
  - retained 子集和现有 `b2 / b4 / b5` 的边界复核
  - `h6` 是否会从 singleton 长成小簇

## 当前 bucket 只能先作为 review 轴，不是正式 sibling

| bucket | 当前用途 |
|---|---|
| `a1` | full explain / plan tree / operator 文本过脆，需要降到更稳定表示层 |
| `a2` | `EXPLAIN ANALYZE` / cost / runtime metric / estimate 数值被整串硬编码 |
| `a3` | planner input 没 pin 住，导致 exact plan expectation 漂移 |
| `a4` | stats materialization / analyze / sample / stats load / visibility 没冻结 |
| `a5` | plan cache / binding / prepared stmt / runtime context 没隔离 |
| `ex` | patch-first 阅读后，不支持并入这条 unified direction |

注意：

- `a1-a5` 只是当前 review 轴
- 它们不是已承诺的 umbrella sibling
- 特别是 `a4 / a5` 是否足够集中拆成新的 formalized sibling，必须等 `46` 个 delta patch 全读完

## 先做哪一批

### 第 1 批：`statistics_sensitive_test only`（`23`）

`pr-26468`, `pr-27734`, `pr-30026`, `pr-32017`, `pr-34141`, `pr-34150`, `pr-42482`, `pr-47013`, `pr-54440`, `pr-58039`, `pr-58254`, `pr-60333`, `pr-60514`, `pr-62123`, `pr-62363`, `pr-62725`, `pr-63500`, `pr-63702`, `pr-64119`, `pr-64428`, `pr-65098`, `pr-65329`, `pr-67202`

优先先读这批，因为：

- 它们是对现有 `assert_exact_plan_or_cost` 子 family 的最大增量尾巴
- 很可能决定是否需要把 “stats lifecycle / stats visibility / stats threshold” 拆成更显式的新 sibling

### 第 2 批：`plan_cache_dependency only`（`22`）

`pr-8206`, `pr-8328`, `pr-8556`, `pr-16525`, `pr-29197`, `pr-30139`, `pr-32139`, `pr-33299`, `pr-36855`, `pr-40196`, `pr-41185`, `pr-43204`, `pr-47330`, `pr-47353`, `pr-49584`, `pr-49642`, `pr-49676`, `pr-49756`, `pr-51926`, `pr-65619`, `pr-65771`, `pr-66374`

优先读法：

- 不要因为 patch 里出现 `plan cache` 就直接归到 `a5`
- 要看 patch 主体到底是在：
  - 固定 runtime context
  - 修 param-type / schema-version / reuse invalidation
  - 还是其实更像 test isolation / shared state / serial ordering

### 第 3 批：`statistics_sensitive_test + plan_cache_dependency`（`1`）

`pr-66928`

这条很重要，因为：

- 它最容易暴露 `a4` 和 `a5` 的真实边界
- 也最容易提醒我们：smell overlap 不等于 sibling overlap

## 第 1 批 `statistics_sensitive_test only` 已完成 patch-first 初读

这一批 `23` 条不再继续靠 smell 名字理解，而是按 patch 主修法先做 provisional clustering。

当前初读结论：

- provisional retained：`19`
- provisional exclude / migrate：`4`

### `h1` 断言前必须等 stats load / lazy-load / DDL-applied stats 真正 materialize

当前保留（`7`）：

`pr-26468`, `pr-30026`, `pr-34141`, `pr-34150`, `pr-58039`, `pr-60514`, `pr-65329`

当前共同机制：

- 测试在 `analyze` / `load stats` / `DDL event` 之后，马上断言 stats / plan / usage
- 但 histogram / stats cache / DDL-applied stats 其实还没真正 materialize
- patch 主修法不是换 assertion 风格，而是：
  - 显式 `LoadNeededHistograms()`
  - 显式 `Update(...)` / `HandleDDLEvent(...)`
  - 用 `analyze table ... all columns`
  - 打开 sync-wait / sync-load 路径

这条目前看上去不像现有 `assert_exact_plan_or_cost/b4` 的简单镜像，因为它覆盖的不只是 exact plan，而是更一般的 “stats 尚未 ready 就断言”。

formalization 状态：

- 已 formalize
- 对应 JSON：
  - `patterns/plan_stability_and_stats_dependency/subpatterns/统计信息真正_load_materialize_apply_之前不应断言依赖它的计划或统计输出.json`

### `h2` histogram / selectivity / correlation / cost 等导出数值不应做死值断言

当前保留（`6`）：

`pr-27734`, `pr-60333`, `pr-62123`, `pr-62363`, `pr-64119`, `pr-64428`

当前共同机制：

- 测试把下面这些输出当成精确常数：
  - bucket 数量
  - derived row-count / selectivity
  - correlation
  - cost formula string / numeric detail
  - async stats-load item count
- patch 主修法通常是：
  - `Equals` -> `InDelta` / range
  - exact float -> 单调关系 / 上下界
  - exact count -> existence / lower-bound

边界备注：

- `pr-60333` patch-first 更像现有 `assert_exact_plan_or_cost/b2`
  - 只是它历史 smell 没挂到 `assert_exact_plan_or_cost`
  - 后续很可能应该并回现有 `b2`，而不是在 umbrella 里新开一条只服务它的 sibling

formalization 状态：

- 已 formalize
- 对应 JSON：
  - `patterns/plan_stability_and_stats_dependency/subpatterns/统计派生数值_不应做_exact_constant_assertion.json`

### `h3` analyze scope / stats version / sampling / predicate-column inputs 必须先钉死

当前保留（`6`）：

`pr-32017`, `pr-54440`, `pr-58254`, `pr-62725`, `pr-63500`, `pr-63702`

当前共同机制：

- 测试断言依赖的不是 “stats 已加载” 本身
- 而是 analyze 的输入条件本来就没 pin 住，例如：
  - sample rate
  - analyze version
  - predicate-column collection state
  - 新 feature 打开后 analyze scope 改变
  - 测试数据规模把 case 推到另一侧统计阈值

patch 主修法通常是：

- `0.9 samplerate` -> `1`
- `analyze table` -> `analyze table ... all columns`
- 显式触发 predicate-column collection
- 固定 analyze version 到稳定版本
- 缩小数据规模，避免落在不稳定阈值边界附近

formalization 状态：

- 已 formalize
- 对应 JSON：
  - `patterns/plan_stability_and_stats_dependency/subpatterns/analyze_inputs_sampling_version_predicate_scope_必须先钉死.json`

### 第 1 批排除 / 迁边界（`4`）

`pr-42482`, `pr-47013`, `pr-65098`, `pr-67202`

当前 patch-first 判断：

- `pr-42482`
  - 当前 patch主体是在补一个 join 行为回归测试
  - 看不到稳定的 stats / plan-dependency 修法
- `pr-47013`
  - 当前 patch主体只是加 debug failpoint / logging
  - 更像 evidence collection，不是可复用 subpattern
- `pr-65098`
  - 当前 patch主体是给 `mysql.stats_histograms` 查询加 `table_id` 过滤
  - 更像 test isolation / namespace scoping，不是 plan/stats dependency
- `pr-67202`
  - 当前 patch主体是 global config + stats lease + background refresh timing
  - 更像 async global knob / background loop timing，不是这条方向的主边界

## 第 1 批之后的当前判断

读完 `23` 个 stats-only 之后，当前最像新的 umbrella sibling 的，不是 “statistics_sensitive_test” 这个 smell 名字本身，而是下面 `3` 条 patch-backed 假设：

1. stats 还没真正 load / materialize / apply，就去断言 plan 或 stats
2. histogram / selectivity / cost / correlation / queue-size 这类导出数值被当成精确常数
3. analyze 的输入条件没有 pin 住，例如 version / sample / predicate-column scope / threshold-side

接下来读 `22` 个 cache-only 时，最重要的不是继续扩这 `3` 条名字，而是看：

- `cache-only` 里有多少 actually 并进现有 `a5`
- 有没有 case 会把 `h1` 和 `a5` 连成同一条 sibling
- `pr-60333` 这种应回流到现有 `assert` family 的 case 到底还有多少

## 第 2 批 `plan_cache_dependency only` 已完成 patch-first 初读

这一批 `22` 条当前初读结论：

- provisional retained：`8`
- provisional exclude / migrate：`14`

### `h4` cache-hit / read-from-cache 不应做逐次硬断言；必须先等 cache ready，再断稳定 property

当前保留（`4`）：

`pr-30139`, `pr-32139`, `pr-33299`, `pr-36855`

当前共同机制：

- patch 主修法不是“把 SQL 文本改一改”，而是在修测试对 cache 行为的观测方式
- 原测试把下面这些东西写成逐次硬约束：
  - `@@last_plan_from_cache = 1`
  - `HasPlan(..., "UnionScan")`
  - 每轮循环都必须命中 cache
- 但真实运行里，cache hit / read-from-cache 往往还依赖：
  - cache 是否已经 load ready
  - 某类表 / 某类访问路径是否本来就不支持 cache
  - 后台刷新 / analyze / range rebuild 带来的偶发 miss

patch 主修法通常是：

- 先等 cache ready，再断言
- 用 `StmtCtx.ReadFromTableCache` 这类更直接的 runtime signal，而不是 plan 文本
- 按 table/path 区分 expected cacheability，而不是全都硬写成 `1`
- 对偶发 miss 做阈值容忍，只把“明显超标”当真失败

formalization 状态：

- 已 formalize
- 对应 JSON：
  - `patterns/plan_stability_and_stats_dependency/subpatterns/cache_hit_read_from_cache_不应写成逐次硬断言_必须先等_cache_ready.json`

### `h5` cache reuse 不应遮蔽 execution-time context

当前保留（`3`）：

`pr-43204`, `pr-51926`, `pr-65771`

当前共同机制：

- patch 主修法不是“换更稳定的 plan 文本”，而是在阻止 cache 把本该每次执行重新计算的 runtime context 藏掉
- 当前看到的具体形态包括：
  - cached prepared stmt 复用第一次求出来的 stale-read ts
  - non-prepared plan cache 把 session binding 变化遮住
  - extension function 的 side effect / privilege context 被 constant fold / plan cache 提前吃掉

patch 主修法通常是：

- 显式禁用某条 cache 路径
- 要求 per-execution 重新计算 runtime context
- 避免把 side-effectful / privilege-sensitive expression 进入 fold / cache

边界备注：

- `pr-43204` 测试层还顺手加了 `ORDER BY`
  - 这说明它和 `nondeterministic_result_order` 有混边界
  - 但 patch 主机制仍然更像 execution-time context 被 prepared statement cache 遮蔽

formalization 状态：

- 已 formalize
- 对应 JSON：
  - `patterns/plan_stability_and_stats_dependency/subpatterns/cache_reuse_不应遮蔽_execution_time_context.json`

### `h6` cache environment knob 也要先 pin 住

当前保留（`1`）：

`pr-8556`

当前共同机制：

- patch 直接把 `PreparedPlanCacheMaxMemory` 钉到 `math.MaxUint64`
- 主目的不是调 planner input，也不是改 assertion 表示层
- 而是把 memory-pressure 这类 cache environment 干扰先排掉，再谈 cache 行为断言

当前判断：

- 这条现在还是 singleton
- 先放在观察池，不急着升成正式 sibling

### 第 2 批排除 / 迁边界（`14`）

`pr-8206`, `pr-8328`, `pr-16525`, `pr-29197`, `pr-40196`, `pr-41185`, `pr-47330`, `pr-47353`, `pr-49584`, `pr-49642`, `pr-49676`, `pr-49756`, `pr-65619`, `pr-66374`

当前 patch-first 判断：

- `pr-8206`, `pr-8328`, `pr-40196`, `pr-41185`, `pr-66374`
  - 更像 plan-cache 功能/覆盖面扩展，不是这条 unified direction 里“测试依赖 plan/stats/runtime context”那类修法
- `pr-16525`
  - 更像 shared suite state / serial ordering
- `pr-29197`
  - 更像 randomized input formatting
- `pr-47330`, `pr-47353`
  - 更像测试迁移；其中 `pr-47353` 还显式暴露出 unstable error message 的另一条边界
- `pr-49584`, `pr-49642`, `pr-49676`, `pr-49756`
  - 更像 expression 内部 cache / const 语义重构 + regression coverage
- `pr-65619`
  - 更像 random schema generation + concurrent DML deadlock tolerance

## 第 3 批 `statistics_sensitive_test + plan_cache_dependency` 已完成 patch-first 初读

这一批只有 `1` 条：

`pr-66928`

当前判断：

- 这条虽然 source smell 同时挂了 `stats + cache`
- 但 patch-first 主修法非常单一：
  - `analyze table` 之后显式 `StatsHandle().Update(...)`
  - 先把 stats 真正 load / materialize 到 cache 再断言
- 所以当前应并到 `h1`
- 它更像“smell overlap 不等于 sibling overlap”的提醒，而不是一个新的 mixed sibling

## 读完 `46` 个 delta patch 之后，当前能先回答的问题

1. `statistics_sensitive_test only` 这 `23` 个 case 里，确实不止是现有 `b4` 的简单镜像
   - `h1 / h3` 都比现有 `b4` 更宽，因为它们覆盖的不只是 exact plan assertion
2. `plan_cache_dependency only` 这 `22` 个 case 里，也不适合一股脑塞回现有 `b5`
  - 当前至少已经分出：
     - `h4` cache-hit/assertion 观测方式太脆
     - `h5` cache reuse 遮蔽 execution-time context
   - 这两条虽然都属于 cache/runtime 侧，但 patch 主修法并不相同，而且现在都已经可以单独 formalize
3. `46` 个 delta patch 读完后，确实已经出现了新增 sibling 的资格
   - stats 侧 `h1 / h2 / h3` 和 cache 侧 `h4 / h5` 都已经可以落正式 JSON
   - 当前剩下的主要是 `h6` 是否能成簇

## retained-only 边界复核结果

### 1. 并回现有 `assert_exact_plan_or_cost` sibling

- 回流 `b2`：`1`
  - `pr-60333`

当前没有任何整簇可以直接并回现有 `b4` 或现有 `b5`。

### 2. 与现有 sibling 相邻，但不应硬并回

- `h1`（`8`，含 `pr-66928`）：
  - 与 `b4` 最近
  - 但 scope 更宽，覆盖 “stats 尚未 materialize / load / apply 就断言”，不只服务 exact plan assertion

- `h3`（`6`）：
  - 也与 `b4` 最近
  - 但主修法是 pin analyze inputs / version / sample / predicate-column scope
  - 不应被压缩成 exact-plan-only 的 wording

- `h5`（`3`，已 formalize）：
  - 与 `b5` 最近
  - 但现在看到的是 generalized runtime-context 机制：
    - cache 把 execution-time context 藏掉
  - 不只局限于 exact plan assertion

### 3. 继续观察

- `h6` singleton：`1`
  - `pr-8556`

## 当前推荐的 formalize 顺序

1. `h6`

排序理由：

- stats 侧的 `h1 / h2 / h3` 和 cache 侧的 `h4 / h5` 现在都已经 formalize 完
- `h6` 目前还只有 `pr-8556`，先观察是否还能补到更多 patch-backed 证据

## 与现有 `assert_exact_plan_or_cost` 子 family 的关系

当前可以把现有 `assert_exact_plan_or_cost` 的 `5` 条机制簇当作边界参考：

1. 表示层太脆
2. 数值整串硬编码
3. planner input 没 pin
4. stats 没冻结
5. runtime context 没固定

但不能反过来做成自动分类器。

正确用法只能是：

- delta case patch-first 读完后
- 看它是否真的和现有 `b1-b5` 同机制
- 如果不是，再新增 sibling 草案

## 当前最重要的边界提醒

- 不能因为 patch 改了 `analyze` / `stats` / `bucket` / `sample`，就自动归 `a4`
- 不能因为 patch 里出现 `plan cache` / `prepared` / `binding`，就自动归 `a5`
- 不能因为 patch 改了 `explain` / `.result` / golden file，就自动归 `a1`
- 不能因为 patch 改了 `cost` / selectivity / ratio，就自动归 `a2`

必须回到 patch 主修法：

- 是在降 assertion 的表示层？
- 还是在 pin planner inputs？
- 还是在冻结 stats lifecycle？
- 还是在隔离 runtime cache/context？

## 这轮扩展读完后，已经拿到的 3 个答案

1. `statistics_sensitive_test only` 这 `23` 个 case 里，不能简单等同于现有 `b4`
2. `plan_cache_dependency only` 这 `22` 个 case 里，也不能简单一股脑并回现有 `b5`
3. `46` 个 delta patch 读完之后，umbrella 级新增 sibling 已经有讨论资格，但还没到直接写 JSON 的阶段
