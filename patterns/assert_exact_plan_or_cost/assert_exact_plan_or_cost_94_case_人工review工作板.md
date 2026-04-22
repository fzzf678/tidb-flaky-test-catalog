# `assert_exact_plan_or_cost` 94 case 人工 review 工作板

这个文件只记录一件事：

- 对 `94` 个 patch 做 **patch-first 的全量人工复读**

这里不接受：

- field-based 归桶
- 直接套用还没验证过的 `subpattern JSON`
- 根据 case JSON 里的解释字段先做初筛

## Hard Rules

1. source set 是当前带有 `assert_exact_plan_or_cost` smell 的 `94` 个 case。
2. 进入人工 review 后，只看：
   - patch subject
   - 改动到的测试文件 / helper / planner/runtime 路径
   - 实际 diff 行
3. 下面这些字段不能用来决定 case 属于哪个 bucket：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
4. 先读完 patch，再决定：
   - 是否支持并入这条 family
   - 如果支持，更像下面哪一个 bucket

## 当前 bucket 草案

| bucket | 暂定含义 |
|---|---|
| `b1` | 精确断言完整 `EXPLAIN` / plan tree / operator 文本，但 patch 把断言降到更稳定的表示层 |
| `b2` | 精确断言 `EXPLAIN ANALYZE` / cost / runtime metric / estimate 数值 |
| `b3` | 精确 plan 断言只有在显式 pin planner inputs 后才稳定，例如 knob / hint / cost-model / engine setting |
| `b4` | 精确 plan 断言只有在冻结统计信息后才稳定，例如 analyze/sample/auto-analyze/stats load/version/selectivity boundary |
| `b5` | 精确 plan 断言依赖 runtime context，例如 plan cache / binding / txn state / replica availability / global runtime state |
| `ex` | patch-first 阅读后，不支持并入这 5 条的排除项 |

## 完成状态

- 已人工 review：`94 / 94`
- patch-backed 支持本方向：`51 / 94`
- 人工排除：`43 / 94`
- 待 review：`0 / 94`

## 最终 bucket 概览

| bucket | count | 当前人工结论 | 典型修法 |
|---|---:|---|---|
| `b1` | `16` | 测试过度断言完整 explain / plan tree / plan-id 文本 | 改 `brief` / `plan_tree` / normalized plan / property-level assertion |
| `b2` | `3` | 精确断言 cost / runtime stat / ratio 等数值 | 改成 parse 后做区间 / 大小比较，而不是写死字符串 |
| `b3` | `15` | 断言的 plan 只有在显式 pin planner inputs 后才稳定 | `set` session/global var、cost model、engine setting、hint、`use index` |
| `b4` | `7` | 断言的 plan 其实受统计信息可见性 / sampling / stats version 影响 | 控制 analyze、sample size、stats load、auto analyze、mock stats |
| `b5` | `10` | 断言的 plan 依赖 runtime context，而不是单个 planner knob | 关 plan cache、固定 txn/runtime/replica/global state、重置 shared state |
| `ex` | `43` | patch-first 阅读不支持继续保留在这条 family | 保持排除 |

## 最终正例清单

### `b1` 精确断言完整 `EXPLAIN` / plan tree / operator 文本，但 patch 把断言降到更稳定的表示层

适用边界：

- patch 主体还在测试断言侧
- 典型修法是：
  - `explain` -> `explain format='brief'`
  - `brief` -> `plan_tree`
  - raw explain rows -> normalized plan
  - full row-by-row tree -> `HasPlan` / operator-level property check

完整正例（`16`）：

`pr-21657`, `pr-22677`, `pr-26481`, `pr-46849`, `pr-51355`, `pr-59745`, `pr-60941`, `pr-60943`, `pr-60980`, `pr-60992`, `pr-63080`, `pr-63148`, `pr-63207`, `pr-65825`, `pr-66202`, `pr-66600`

### `b2` 精确断言 `EXPLAIN ANALYZE` / cost / runtime metric / estimate 数值

适用边界：

- 数值本身就是断言对象
- 典型形态：
  - `copr_cache_hit_ratio: 0.67`
  - `estCost` / runtime stat 直接拿字符串比
- patch 常见修法是：
  - parse float
  - 做 `>` / `<` / `==` 的数值断言
  - 用 regex 匹配结构，不再比死具体数值文本

完整正例（`3`）：

`pr-21071`, `pr-48700`, `pr-60512`

### `b3` 精确 plan 断言只有在显式 pin planner inputs 后才稳定

适用边界：

- patch 没有换掉整套断言，而是把 planner input 钉住
- planner input 包括：
  - session/global knob
  - optimizer cost model / threshold
  - engine setting
  - hint / `use index`
- 这条和 `b5` 的边界是：
  - 如果修法核心是“显式设置输入”，归 `b3`
  - 如果修法核心是“runtime context 本身要固定”，归 `b5`

完整正例（`15`）：

`pr-26550`, `pr-35114`, `pr-35244`, `pr-35275`, `pr-37038`, `pr-39065`, `pr-39138`, `pr-40199`, `pr-44139`, `pr-56204`, `pr-58207`, `pr-58546`, `pr-62512`, `pr-65012`, `pr-65770`

### `b4` 精确 plan 断言只有在冻结统计信息后才稳定

适用边界：

- patch 核心在 stats 侧，而不是单纯 planner knob
- 常见机制：
  - 增大 sample size / bucket / analyze 参数
  - 关闭 auto analyze
  - 强制 stats sync load
  - `DumpStatsDeltaToKV`
  - 注入 mock stats
  - 改 query selectivity boundary，让计划不再跨临界点漂移

完整正例（`7`）：

`pr-37576`, `pr-47146`, `pr-61902`, `pr-62670`, `pr-65119`, `pr-66924`, `pr-67178`

### `b5` 精确 plan 断言依赖 runtime context

适用边界：

- patch 的稳定化动作不是“再设一个 planner knob”
- 而是固定某种 runtime context：
  - prepared plan cache / binding / stmt summary
  - txn / union scan runtime context
  - TiFlash replica / engine availability
  - shared suite/runtime state
- 这条和 `b3` 的边界是：
  - `b3` 更像显式 planner inputs
  - `b5` 更像运行期上下文和状态依赖

完整正例（`10`）：

`pr-16378`, `pr-25138`, `pr-28774`, `pr-37895`, `pr-41356`, `pr-46102`, `pr-46963`, `pr-49338`, `pr-56680`, `pr-66529`

## 排除清单

这些 case 在这轮 patch-first 人工复读后，不再保留在 `assert_exact_plan_or_cost` family：

`pr-8650`, `pr-9866`, `pr-11095`, `pr-25345`, `pr-33359`, `pr-39210`, `pr-41416`, `pr-41537`, `pr-43465`, `pr-44324`, `pr-44985`, `pr-45252`, `pr-46329`, `pr-46780`, `pr-46927`, `pr-46947`, `pr-47078`, `pr-47200`, `pr-48100`, `pr-48877`, `pr-51203`, `pr-53268`, `pr-53362`, `pr-54980`, `pr-55195`, `pr-56196`, `pr-56203`, `pr-58397`, `pr-60648`, `pr-61129`, `pr-62431`, `pr-62786`, `pr-62851`, `pr-62910`, `pr-62952`, `pr-62956`, `pr-64774`, `pr-66156`, `pr-66268`, `pr-66714`, `pr-66715`, `pr-66940`, `pr-67118`

## 边界备注

- `pr-46849`
  - 最终归 `b1`
  - 虽然测试里有 fix-control knob，但 patch 主体是在把 full explain row 比较降成 `HasPlan` / `MustIndexLookup`
- `pr-46963`
  - 最终归 `b5`
  - 这里核心不是又加了一个 knob，而是 fix-control 生效带有 runtime propagation / eventual consistency 味道，patch 用 `EventuallyMustIndexLookup`
- `pr-56204`、`pr-65770`
  - 先保留在 `b3`
  - 一个是显式 pin `tidb_isolation_read_engines`，一个是加 `use index`
  - 说明 `b3` 的边界不能只叫 “knob”，更像 “planner inputs”
- `pr-62670`
  - 最终归 `b4`
  - patch 不是换 explain format，而是把查询选择性从 `a>2` 改到 `a>3`，本质是在避开统计驱动的 plan 临界点
- `pr-41356`
  - 最终归 `b5`
  - 这里的稳定化动作是 restore global var、清 stmt summary memory、避免 shared runtime state 污染

## 剩余队列

- 无
- `94 / 94` 已完成
