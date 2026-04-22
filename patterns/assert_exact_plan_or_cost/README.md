# `assert_exact_plan_or_cost`

这个目录承接 `assert_exact_plan_or_cost` 这条 family 的正式化工作。

它不再把当前 catalog 里所有带这个 smell 的 case 直接当成“已经验证过的同类 inventory”。

这条 family 目前只接受下面这套口径：

- 先把历史 source set 全量 patch-first 人工复读
- 只根据 patch / test diff 本体判断：
  - 断言是不是在写死完整 explain / plan / cost
  - plan / cost 漂移到底来自表示层、planner input、stats、还是 runtime context
- 再反过来 formalize sibling / retrieval signals

## 当前状态

- source set：`94`
- 已人工复读：`94 / 94`
- patch-backed 保留在本 family：`51`
- patch-first 排除：`43`
- 当前 family purity：`54.3%`

这意味着：

- `94` 只能继续作为人工 review 的输入全集
- 不能再把 `94` 当成已经验证过纯度的 family inventory
- 不能用 case JSON 的现成字段直接归桶

## 这轮人工 review 的最终 sibling

| sibling | count | 机制摘要 | formalization 状态 |
|---|---:|---|---|
| 精确 explain / plan tree / operator 文本断言应降到更稳定表示层 | `16` | full explain / plan rows 过脆，修法是改到 normalized / brief / property-level assertion | 已 formalize |
| `EXPLAIN ANALYZE` / cost / runtime metric / estimate 数值不应做整串硬编码 | `3` | runtime stat / cost / estimate 数值被硬编码成字符串 | 已 formalize |
| 精确 plan 断言前必须显式 pin planner inputs | `15` | 不先固定 knob / hint / cost model / engine setting，计划本身会漂 | 已 formalize |
| 精确 plan 断言前必须先冻结统计信息 | `7` | 统计信息采样 / selectivity boundary / stats load 影响 exact plan | 已 formalize |
| 精确 plan 断言前必须固定 runtime context | `10` | plan cache / binding / stmt summary / replica / shared runtime state 会干扰 exact plan assertion | 已 formalize |

## 方法论 Hard Rules

1. source set 继续定义为当前带有 `assert_exact_plan_or_cost` smell 的 `94` 个 case。
2. 进入人工 review 之后，不能再利用下面这些字段做初筛或直接归桶：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
3. 现有 `subpatterns/*.json` 不能拿来反向给 `94` 个历史 case 套标签。
4. 正确顺序只能是：
   - 先读 patch
   - 再抽共同机制
   - 最后修 JSON / retrieval

## 当前最重要的边界

- 不能因为 patch 改了 `EXPLAIN` / plan 文本，就自动算进这条 family。
- 不能因为 patch 里有 `set @@tidb_*`，就自动算作 planner input sibling。
- 不能因为 patch 里出现 `analyze table` / `stats:pseudo`，就自动算作 stats sibling。
- 不能因为 patch 里出现 `plan cache` / `binding`，就自动算作 runtime-context sibling。

必须回到 patch-first 的主修法：

- 断言表示层是否被降级为更稳定的 plan 表示
- planner inputs 是否被显式 pin 住
- stats 是否被固定
- runtime context 是否被隔离 / 固定

## retrieval 当前状态

- `retrieval_signals.json` 已起草
- broad `rg_template` 已做过一轮 patch-proxy 回验
- 在这轮 `51` 个 patch-backed 正例上：
  - widening 前：`47 / 51 = 92.2%`
  - widening 后：`51 / 51 = 100%`

需要强调：

- 这些 `rg_templates` 的职责是 **coarse retrieval / candidate retrieval**
- broad hit 不能直接当作 sibling verdict
- 当前 broad widening 是按“允许 false positive，但不要明显炸量”来调的

## 当前目录结构

- [assert_exact_plan_or_cost_94_case_人工review工作板.md](./assert_exact_plan_or_cost_94_case_%E4%BA%BA%E5%B7%A5review%E5%B7%A5%E4%BD%9C%E6%9D%BF.md)
  - `94` 个 patch 的人工工作板、完整正例与排除清单
- [assert_exact_plan_or_cost_第二轮聚类草案.md](./assert_exact_plan_or_cost_%E7%AC%AC%E4%BA%8C%E8%BD%AE%E8%81%9A%E7%B1%BB%E8%8D%89%E6%A1%88.md)
  - sibling 边界、formalize 顺序、retrieval calibration 记录
- `subpatterns/`
  - 当前 `5` 个正式 sibling JSON
- `retrieval_signals.json`
  - sibling 级别的 candidate retrieval hints

## 后续优先级

1. 用真实 TiDB 仓库继续校准 `b3 / b4 / b5` 的 retrieval precision
2. 在 open-PR / repo-scan agent 流程里试接这条 family
3. 再根据真实 scan 噪声回收 `group_intersection`，而不是继续硬收 broad
