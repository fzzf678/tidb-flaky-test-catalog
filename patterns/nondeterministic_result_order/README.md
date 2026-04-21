# `nondeterministic_result_order`

这个目录承接“结果顺序确定性”这条 family 的正式化工作。

它不是单个 smell 的镜像目录，而是把下面 `3` 个相邻 smell 背后的同类问题收在一起：

- `unsorted_result_assertion`
- `missing_order_by`
- `relying_on_map_iteration_order`

## 当前状态

- `197` 个历史 case 的 source set 仍然成立。
  - 它只表示：历史 catalog 中，带上述 `3` 个 smell 之一的去重 case 全集。
  - 它只适合作为人工 review 的输入全集。
- 之前基于 case JSON 字段做的二次归桶结论，现已全部撤回。
  - 包括但不限于：`195 / 197`、`176 / 197`、`84 / 85 / 7`
- 当前唯一接受的方法是：
  - 逐条重读这 `197` 个 patch
  - 只根据 patch / test diff 本体归类
  - 再反过来提炼、补充、修正 subpattern

## 这轮人工 review 的最终结果

- 已人工重读：`197 / 197`
- patch-backed 支持本 family：`100`
- 当前人工排除：`97`
- patch-first 口径下的 family purity：`50.8%`

这说明：

- `197` 不是“已经验证过的 family inventory”
- 这条 family 不能继续靠字段合并
- 只有大约一半 case 真正属于“结果顺序不稳定”这一机制簇

## 最终保留下来的 sibling

| sibling | count | 机制摘要 | formalization 状态 |
|---|---:|---|---|
| 多行 SQL 结果做精确顺序断言，但缺少稳定顺序契约 | `44` | query 无稳定 order contract，或断言侧未做无序归一化 | 已 formalize |
| `map / collection / helper` 收集结果后未排序就断言 | `35` | helper / slice / map / callback collection 顺序不稳定 | 已 formalize |
| `runtime / executor` 路径本身应该保序 | `13` | 运行时 ordered path 的顺序语义没有被正确保持 | 已 formalize |
| `sort / comparator / tie-breaker / repeated sort` 本身不稳定 | `6` | 已经在排序，但排序语义本身不稳定 | 已 formalize |
| 已有 `ORDER BY`，但排序键不唯一，`LIMIT` / 边界裁剪仍会不稳定 | `2` | order contract 存在但不够唯一 | 已 formalize |

## 方法论 hard rules

1. `197` 这个全集可以继续用 `3` 个 smell 的并集来定义。
2. 但进入人工 review 之后，不能再利用现成字段做初筛或归桶。
3. 不能用下面这些字段决定 case 属于哪个 sibling：
   - `root_cause_categories`
   - `fix_pattern`
   - `root_cause_explanation`
   - `analysis`
4. 现有 `subpatterns/` 不能拿来反向“套标签”。
   - 正确顺序是：先看 patch，再总结共同机制，再修 JSON。

## 这条 family 当前最重要的边界

- 不能因为 patch 里出现了 `ORDER BY`，就自动把它算作本 family 正例。
- 不能因为测试里没 `.Sort()`，就自动判定它属于这条线。
- 不能因为 patch 里用了 `sort.Slice` / `sort.Strings`，就自动判为结果顺序 family。
- 需要保留 patch-first 的排除能力：
  - 新 feature / 新测试脚手架自带 deterministic query
  - 大型迁移 / infra patch 顺带带出顺序代码
  - 计划 / canonicalization / internal order 但不是测试结果顺序契约

## 当前目录结构

- [197_case_人工review工作板.md](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/nondeterministic_result_order/197_case_人工review工作板.md)
  - `197` 个 patch 的最终人工工作板与完整 case 清单
- [第二轮聚类草案.md](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/nondeterministic_result_order/第二轮聚类草案.md)
  - 最终的 sibling 聚类与边界说明
- `subpatterns/`
  - 当前已 formalize 的 JSON
  - 包括：
    - `map / collection / helper` 收集结果后未排序就断言
    - 多行 SQL 结果做精确顺序断言时，必须显式 `ORDER BY` 或 `Result.Sort`
    - `runtime / executor` 路径本身应该保序
    - `sort / comparator / tie-breaker / repeated sort` 本身不稳定
    - `ORDER BY` 键不唯一时，`LIMIT` / 结果比对不能断言精确顺序

## 后续优化优先级

1. 校准 `b3` / `b4` 的 retrieval precision
   - 这两条都刚 formalize
   - 需要在真实仓库扫描里确认 `rg_templates` 的 precision / recall
2. 继续收紧 `b1` 与 `b5` 的边界
   - 尤其是“已有 `ORDER BY` 但 contract 仍不够唯一”的误判点

## 使用方式

如果目标是继续细化这条 family，正确顺序是：

1. 用 `197` 个历史 case 全集作为输入集合
2. 逐条重读 patch / test diff
3. 只从 patch 本体抽共同机制
4. 再回头补充、合并、拆分 `subpatterns/*.json`

在此之前，不要再引用旧的 `176 / 197` 或 `84 / 85 / 7` 口径。
