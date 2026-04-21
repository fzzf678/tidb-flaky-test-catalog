# `nondeterministic_result_order` 197 case 人工 review 工作板

这个文件只记录一件事：

- 对 `197` 个 patch 做 **patch-first 的全量人工复读**

这里不接受：

- field-based 归桶
- 直接套用已有 `subpatterns/*.json`
- 根据 case JSON 里的解释字段先做初筛

## Hard Rules

1. source set 仍然是 `unsorted_result_assertion`、`missing_order_by`、`relying_on_map_iteration_order` 三个 smell 的并集，共 `197` 个 case。
2. 进入人工 review 后，只看：
   - patch subject
   - 改动到的测试文件 / helper / runtime 路径
   - 实际 diff 行
3. 下面这些字段不能用来决定 case 属于哪个 sibling：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
4. 现有 `subpatterns/*.json` 只能当假设稿，不能当分类器。

## 完成状态

- 已人工 review：`197 / 197`
- patch-backed 支持本 family：`100 / 197`
- 人工排除：`97 / 197`
- 待 review：`0 / 197`

## 最终 bucket 概览

| bucket | count | 当前人工结论 | 典型修法 |
|---|---:|---|---|
| `b1` | `44` | 多行 SQL 结果做精确顺序断言，但缺少稳定顺序契约 | 补 `ORDER BY` / 用 `Result.Sort()` 明确做无序归一化 |
| `b2` | `35` | `map / collection / helper` 收集结果后未排序就断言 | `sort.*`、`ElementsMatch`、集合 membership |
| `b3` | `13` | `runtime / executor` 路径本身应该保序 | 修运行时顺序语义，并补 ordered path 回归测试 |
| `b4` | `6` | `sort / comparator / tie-breaker / repeated sort` 本身不稳定 | 改稳定排序 / 加 tie-breaker / 避免 repeated unstable sort |
| `b5` | `2` | 已有 `ORDER BY`，但排序键不唯一，`LIMIT` / 边界裁剪仍会不稳定 | 把 order contract 收紧到唯一顺序 |
| `ex` | `97` | 当前 patch 阅读不支持并入 `nondeterministic_result_order` | 保持排除 |

## 最终正例清单

### `b1` 多行 SQL 结果做精确顺序断言，但缺少稳定顺序契约

适用边界：

- patch 直接修测试断言侧的“固定行序假设”
- 修法通常是：
  - 给 query 补 `ORDER BY`
  - 或保留 query 无序，但在结果断言前显式 `.Sort()`
- 这条里也包括 SQL 内部结果表达本身缺少顺序契约的 case，例如 `group_concat(... order by ...)`

完整正例（`44`）：

`pr-1591`, `pr-1899`, `pr-2195`, `pr-3781`, `pr-4001`, `pr-4987`, `pr-5715`, `pr-6067`, `pr-7680`, `pr-8442`, `pr-10581`, `pr-10837`, `pr-13229`, `pr-14238`, `pr-25168`, `pr-25617`, `pr-26839`, `pr-26987`, `pr-28160`, `pr-34130`, `pr-37721`, `pr-37751`, `pr-39015`, `pr-39138`, `pr-39522`, `pr-45485`, `pr-45646`, `pr-46731`, `pr-46944`, `pr-47415`, `pr-47803`, `pr-47817`, `pr-51489`, `pr-51670`, `pr-53932`, `pr-55804`, `pr-56304`, `pr-56314`, `pr-56555`, `pr-57095`, `pr-57282`, `pr-57972`, `pr-59031`, `pr-64279`

### `b2` `map / collection / helper` 收集结果后未排序就断言

适用边界：

- 不一定是 SQL 查询直接缺 `ORDER BY`
- 问题发生在 Go test helper / slice / map / callback collection 层
- patch 修法通常是先排序，再比较；或直接改成顺序无关断言

完整正例（`35`）：

`pr-2423`, `pr-5256`, `pr-5831`, `pr-10743`, `pr-13063`, `pr-13127`, `pr-22305`, `pr-25910`, `pr-30235`, `pr-30257`, `pr-30335`, `pr-30671`, `pr-30816`, `pr-40472`, `pr-43177`, `pr-44269`, `pr-44358`, `pr-44600`, `pr-44667`, `pr-45904`, `pr-46406`, `pr-46940`, `pr-47496`, `pr-50762`, `pr-50779`, `pr-51152`, `pr-51531`, `pr-55322`, `pr-55365`, `pr-55774`, `pr-55871`, `pr-56512`, `pr-56813`, `pr-57244`, `pr-58862`

### `b3` `runtime / executor` 路径本身应该保序

适用边界：

- 问题不只是 test 断言层忘了 `.Sort()`
- patch 主体在修运行时应保留的顺序语义
- 常见于 `KeepOrder`、`UNION ... ORDER BY`、`UnionScan`、partition direct read 等路径

完整正例（`13`）：

`pr-1612`, `pr-4470`, `pr-8251`, `pr-10673`, `pr-24455`, `pr-24877`, `pr-31359`, `pr-36108`, `pr-41615`, `pr-42024`, `pr-44360`, `pr-45140`, `pr-46367`

### `b4` `sort / comparator / tie-breaker / repeated sort` 本身不稳定

适用边界：

- 已经在排序，但排序 helper / comparator / tie-breaker 本身不稳定
- 这类 patch 不是“没排序”，而是“排序方式本身不构成稳定语义”

完整正例（`6`）：

`pr-5044`, `pr-9696`, `pr-11095`, `pr-15536`, `pr-15898`, `pr-25092`

### `b5` 已有 `ORDER BY`，但排序键不唯一，`LIMIT` / 边界裁剪仍会不稳定

适用边界：

- patch 里已经有 `ORDER BY`
- 但 order key 不能唯一决定结果顺序
- 一旦叠加 `LIMIT`、边界裁剪、只取头部若干行，测试仍会漂

完整正例（`2`）：

`pr-45513`, `pr-64083`

## 排除清单

这些 case 在这轮 patch-first 人工复读后，不再保留在 `nondeterministic_result_order` family：

`pr-1652`, `pr-2557`, `pr-3177`, `pr-7643`, `pr-8640`, `pr-8885`, `pr-10007`, `pr-18633`, `pr-22859`, `pr-25336`, `pr-25652`, `pr-25653`, `pr-27082`, `pr-27743`, `pr-28036`, `pr-29001`, `pr-33498`, `pr-34409`, `pr-34519`, `pr-35147`, `pr-36532`, `pr-36637`, `pr-36925`, `pr-36973`, `pr-37828`, `pr-38377`, `pr-38386`, `pr-38595`, `pr-42411`, `pr-42433`, `pr-42565`, `pr-42817`, `pr-42914`, `pr-43163`, `pr-44185`, `pr-44305`, `pr-44409`, `pr-44801`, `pr-44874`, `pr-45926`, `pr-46447`, `pr-46633`, `pr-46763`, `pr-46887`, `pr-46979`, `pr-47002`, `pr-47021`, `pr-47059`, `pr-47118`, `pr-47131`, `pr-47150`, `pr-47185`, `pr-47234`, `pr-47296`, `pr-47319`, `pr-47612`, `pr-47740`, `pr-47746`, `pr-48030`, `pr-48035`, `pr-48306`, `pr-49195`, `pr-49758`, `pr-50341`, `pr-51231`, `pr-52052`, `pr-52235`, `pr-53208`, `pr-53277`, `pr-53301`, `pr-53341`, `pr-53544`, `pr-54110`, `pr-54608`, `pr-54806`, `pr-55519`, `pr-55620`, `pr-55787`, `pr-56307`, `pr-56917`, `pr-57336`, `pr-57673`, `pr-57699`, `pr-57950`, `pr-58808`, `pr-58945`, `pr-59054`, `pr-60132`, `pr-60903`, `pr-61633`, `pr-62540`, `pr-62905`, `pr-63140`, `pr-63796`, `pr-64927`, `pr-66803`, `pr-67089`

## 边界备注

- `pr-34130`
  - 仍归到 `b1`
  - 原因是 patch 修的是 SQL 结果表达本身的顺序契约：`group_concat(v order by v)`，不是 helper 排序
- `pr-44269`
  - 归到 `b2`
  - 关键机制是 helper/test 侧对 `details` slice 排序后再比较
- `pr-45513`、`pr-64083`
  - 单独归为 `b5`
  - 这两条不是“完全没 `ORDER BY`”，而是“`ORDER BY` 已存在但不够唯一，叠加 `LIMIT` / 边界选择后仍然会漂”
- `pr-47002`、`pr-47131`、`pr-47746`、`pr-48306`、`pr-49195`、`pr-49758`、`pr-61633`
  - 最终保持排除
  - patch 里虽然出现了 `ORDER BY` / `Sort` / 顺序相关代码，但读完整体 diff 后，更像 feature 演进、迁移、内部 canonicalization 或其他机制，不是这条 family 的干净正例

## 剩余队列

- 无
- `197 / 197` 已完成
