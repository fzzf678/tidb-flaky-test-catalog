# `assert_exact_plan_or_cost` 第二轮聚类草案

这份草案不再维护 field-based inventory。

它只记录一件事：

- 在对 `94` 个 patch 做全量人工复读之后，哪些 sibling 真的被 patch-backed 证据支持

## 方法重置

这轮工作的目标不是：

- 用现有 `subpattern JSON`
- 用 case JSON 里的 `root_cause_categories` / `fix_pattern` / `analysis`
- 用 smell 字段直接给 `94` 个 case 贴标签

这轮工作的目标是：

1. 重新读 `94` 个 patch
2. 只根据 patch / test diff 本体回答：
   - 改的是断言表示层、planner input、stats、还是 runtime context
   - 为什么 plan / cost 会漂
   - 它更像哪个 sibling，还是应该直接踢出这个 family
3. 再反过来修正 / 补充 subpattern

## 最终进度

- source set：`94`
- 已人工读 patch：`94`
- patch-backed 支持本 family：`51`
- 当前人工排除：`43`
- family purity（按 patch-first 口径）：`51 / 94 = 54.3%`

这个数字很关键：

- 当前 smell 集合只适合作为人工 review 的输入全集
- 不能再把 `94` 当成已经验证过纯度的 `assert_exact_plan_or_cost` inventory

## 最终保留下来的 5 个 sibling

### 1. 精确断言完整 explain / plan tree / operator 文本，但 patch 把断言降到更稳定的表示层

count：`16`

为什么保留：

- 这是当前最清晰的一条
- patch 主体直接落在测试断言侧
- 典型稳定化动作非常一致：
  - `brief`
  - `plan_tree`
  - normalized plan
  - property-level assertion

代表 case：

- `pr-21657`
- `pr-46849`
- `pr-60980`
- `pr-63148`

完整 case：

`pr-21657`, `pr-22677`, `pr-26481`, `pr-46849`, `pr-51355`, `pr-59745`, `pr-60941`, `pr-60943`, `pr-60980`, `pr-60992`, `pr-63080`, `pr-63148`, `pr-63207`, `pr-65825`, `pr-66202`, `pr-66600`

### 2. 精确断言 `EXPLAIN ANALYZE` / cost / runtime metric / estimate 数值

count：`3`

为什么保留：

- 量不大，但纯度很高
- 检索 / review signal 和 `b1` 明显不同
- 后面不应该和 `b1` 混掉，否则会把“文本稳定化”和“数值稳定化”混成一条

代表 case：

- `pr-21071`
- `pr-48700`

完整 case：

`pr-21071`, `pr-48700`, `pr-60512`

### 3. 精确 plan 断言只有在显式 pin planner inputs 后才稳定

count：`15`

为什么保留：

- 人工复读后，这条的量和纯度都足够
- 原来叫 “pinned knobs” 太窄，实际 patch 里还包含：
  - hint
  - `use index`
  - cost model 版本
  - engine setting
- 所以最终更适合叫 “planner inputs”

代表 case：

- `pr-26550`
- `pr-35114`
- `pr-37038`
- `pr-65770`

完整 case：

`pr-26550`, `pr-35114`, `pr-35244`, `pr-35275`, `pr-37038`, `pr-39065`, `pr-39138`, `pr-40199`, `pr-44139`, `pr-56204`, `pr-58207`, `pr-58546`, `pr-62512`, `pr-65012`, `pr-65770`

### 4. 精确 plan 断言只有在冻结统计信息后才稳定

count：`7`

为什么保留：

- 这条和 `statistics_sensitive_test` 确实有交界
- 但这里保留的前提是：
  - patch 明确是在稳定 exact plan assertion
  - 不是泛泛地说 “stats sensitive”

代表 case：

- `pr-37576`
- `pr-61902`
- `pr-66924`

完整 case：

`pr-37576`, `pr-47146`, `pr-61902`, `pr-62670`, `pr-65119`, `pr-66924`, `pr-67178`

### 5. 精确 plan 断言依赖 runtime context

count：`10`

为什么保留：

- 这条和 `b3` 的边界在人工复读后是稳定的
- `b3` 更像 planner inputs
- `b5` 更像运行期上下文：
  - prepared plan cache
  - binding / stmt summary
  - txn / union scan runtime context
  - replica availability / engine runtime state
  - shared suite state

代表 case：

- `pr-16378`
- `pr-28774`
- `pr-37895`
- `pr-66529`

完整 case：

`pr-16378`, `pr-25138`, `pr-28774`, `pr-37895`, `pr-41356`, `pr-46102`, `pr-46963`, `pr-49338`, `pr-56680`, `pr-66529`

## 为什么剩下的 `43` 条要排除

排除项不是“完全没碰 explain / plan”，而是 patch-first 读完整体 diff 后，不支持把它们保留成这条 family 的干净正例。

反复出现的排除原因主要有 4 类：

### A. planner / optimizer 内部 nondeterminism 或 canonical order 问题

这类 patch 修的是 planner 内部稳定性，不是 test assertion sibling 本身。

代表：

- `pr-8650`
- `pr-11095`
- `pr-66940`

### B. feature / bugfix / large refactor 顺带改了 plan golden

这类 patch 虽然改了 explain output，但重点不是稳定测试。

代表：

- `pr-33359`
- `pr-45252`
- `pr-62851`

### C. test migration / infra 重组 / suite 搬迁

这类更像测试组织结构变化，而不是新的稳定化模式。

代表：

- `pr-48877`
- `pr-62431`
- `pr-66715`

### D. 问题核心不是 exact plan assertion

有的 patch 真正修的是：

- query result nondeterminism
- importer / executor bug
- checksum / cancellation
- unrelated runtime bug

代表：

- `pr-47078`
- `pr-53362`
- `pr-67118`

完整排除清单（`43`）：

`pr-8650`, `pr-9866`, `pr-11095`, `pr-25345`, `pr-33359`, `pr-39210`, `pr-41416`, `pr-41537`, `pr-43465`, `pr-44324`, `pr-44985`, `pr-45252`, `pr-46329`, `pr-46780`, `pr-46927`, `pr-46947`, `pr-47078`, `pr-47200`, `pr-48100`, `pr-48877`, `pr-51203`, `pr-53268`, `pr-53362`, `pr-54980`, `pr-55195`, `pr-56196`, `pr-56203`, `pr-58397`, `pr-60648`, `pr-61129`, `pr-62431`, `pr-62786`, `pr-62851`, `pr-62910`, `pr-62952`, `pr-62956`, `pr-64774`, `pr-66156`, `pr-66268`, `pr-66714`, `pr-66715`, `pr-66940`, `pr-67118`

## bucket 边界修正

### `b3` 不应再叫 “pinned knobs”

人工复读后，`b3` 里除了 knob 还反复出现：

- hint
- `use index`
- cost model version
- engine read setting

所以更稳的叫法是：

- `plan_assertion_requires_pinned_planner_inputs`

### `b5` 不应和 `b3` 混写

`b5` 里反复出现的是：

- prepared plan cache
- stmt summary / binary plan global state
- txn / union scan runtime context
- TiFlash replica runtime availability
- suite 共享状态

所以它不是 “另一种 knob”，而是 runtime context 依赖。

### `b2` 虽然只有 `3` 条，但建议保留

原因：

- 纯度很高
- 和 `b1` 的文本表示层修法不同
- 后面 `rg_template` / review signal 也应该独立

## formalize 顺序建议

如果下一步要开始把这 5 条写成真正的 sibling / JSON，我建议按这个顺序：

1. `b1`
2. `b3`
3. `b4`
4. `b5`
5. `b2`

原因：

- `b1` 和 `b3` 的量最大，也最容易转成 agent 可执行规则
- `b4` 的量不小，而且和 stats 家族边界已经足够清楚
- `b5` 值得做，但检索信号会比 `b3` 更散
- `b2` 只有 `3` 条，建议保留，但不必先做

## 2026-04-17 broad `rg_template` patch-proxy 回验

这一步验证的不是当前 TiDB 仓库上的 literal recall。

这一步验证的是：

- 先用上面人工复读得到的 `51` 个 patch-backed 正例做 source set
- 再起一版 **broad / coarse retrieval** 级别的 draft `rg_template`
- 直接回放到 patch diff body
- 看这些模板，能不能先把真实 sibling 机制“看见”

### 第一轮 broad draft

初版 broad draft 的 patch-proxy coverage：

| bucket | 正例数 | broad 命中 | recall |
|---|---:|---:|---:|
| `b1` | `16` | `14` | `87.5%` |
| `b2` | `3` | `3` | `100%` |
| `b3` | `15` | `15` | `100%` |
| `b4` | `7` | `6` | `85.7%` |
| `b5` | `10` | `9` | `90.0%` |

整体 target coverage：`47 / 51 = 92.2%`

明确 miss：

- `b1`
  - `pr-26481`
  - `pr-51355`
- `b4`
  - `pr-62670`
- `b5`
  - `pr-16378`

### 第二轮最小 widening

只补了 3 个很小的 widening：

1. `b1`
   - 在原 broad 基础上补：
     - `ordered_result_mode_suite`
     - `LateMaterializationFilterCondition`
   - 目的是补回：
     - testdata 里直接改整段 ordered-result / explain 计划文本
     - 不再用 full explain rows，而是改成更稳定的物理计划内部结构断言

2. `b4`
   - 不直接放宽成泛化的 `where a > 2|3`
   - 最终保留成更像 explain-testdata sibling 的窄一点 heuristic：
     - `explain format='brief' ... where ... > (2|3)`
   - 目的只是补回 `pr-62670` 这种 **stats-driven selectivity boundary drift**

3. `b5`
   - 在原 broad 基础上补：
     - `UseCache = false`
     - `PreparedStmts[`
     - `CachedPrepareStmt`
   - 目的是补回 prepared-plan-cache runtime context 这类字面锚点

### widening 后结果

第二轮最小 widening 后，patch-proxy coverage 变成：

| bucket | 正例数 | broad 命中 | recall |
|---|---:|---:|---:|
| `b1` | `16` | `16` | `100%` |
| `b2` | `3` | `3` | `100%` |
| `b3` | `15` | `15` | `100%` |
| `b4` | `7` | `7` | `100%` |
| `b5` | `10` | `10` | `100%` |

整体 target coverage：`51 / 51 = 100%`

### repo-scan 量级 spot-check

为了避免出现“patch 上好看、仓库里炸掉”的 widening，又在 TiDB `v8.5.0` worktree 上粗看了一次 literal 文件命中量级。

结论：

- `b1`
  - base：`244` files
  - widening 后：`251` files
  - 增量：`+7`
- `b4`
  - base：`1477` files
  - widening 后：`1483` files
  - 增量：`+6`
- `b5`
  - base：`750` files
  - widening 后：`750` files
  - 增量：`0`

这说明：

- 这 3 个 widening 至少在当前 `v8.5.0` worktree 上没有把 broad retrieval 的量级明显放大
- 仍然应该把这些 broad 模板只当作 **coarse retrieval**
- 不应该把 broad hit 当成 sibling verdict
