# 给 agent 的仓库扫描检索信号

这份文档回答的是：

- 现在这 `5` 个**已 formalize** 的 `nondeterministic_result_order` subpattern，能不能直接给 agent 用来扫仓库？

答案是：

- **能**
- 但必须分成“检索层”和“判定层”两步

## 当前分工

- `retrieval_signals.json`
  - 当前最权威的结构化检索层
  - 负责告诉 agent 先怎么召回 candidate
- `subpatterns/*.json`
  - verdict layer
  - 负责最终判断是否命中该 subpattern
- `第二轮聚类草案.md`
  - 负责维护 sibling bucket、正例和边界 case 工作记录
- 本文档
  - 解释检索层怎么用
  - 强调哪些信号只是弱召回，不是 verdict

## full positive inventory 放在哪里

如果要看这条 family 的完整正例，不要去 `subpatterns/*.json` 里找穷举 `examples`。

当前 canonical 放置位置是：

- `第二轮聚类草案.md`
  - 维护 `b1~b5` sibling 级别的最终计数、完整正例清单、边界 case 和排除理由
- `197_case_人工review工作板.md`
  - 维护 `197` 个 patch 的全量人工复读记录，以及完整 bucket 落位
- `subpatterns/*.json`
  - 只保留 verdict layer 所需的机制描述和代表性示例

## 这条 family 里哪些信号只是弱召回

下面这些都不能单独直接判 risk：

- `MustQuery(...).Check(testkit.Rows(...))`
- 没 `.Sort()`
- SQL 没 `ORDER BY`
- SQL 有 `ORDER BY`
- 看到 `sort.Strings` / `sort.Slice`
- 看到 `require.Equal` / `reflect.DeepEqual`

原因很简单：

- 它们都只是症状或局部信号
- 只有回到“顺序是怎么产生的、为什么不稳定、测试为什么错把它当稳定、修法为什么能稳定”这 4 件事，才能做最终 verdict

## 建议字段

这里继续沿用和其他 family 一致的检索层字段：

- `path_globs`
  - 软优先范围，不是硬限制
- `grep_keywords_any`
  - 弱召回关键词，任意命中即可进候选池
- `grep_keywords_all_groups`
  - 分组组合；每组至少命中一个，候选优先级更高
- `grep_keywords_exclude`
  - 软降权信号，不是默认硬排除
- `grepability`
  - `high` / `medium` / `low`
- `first_pass_query_hint`
  - 第一跳怎么搜
- `rg_templates`
  - 可直接执行的检索模板

## 使用方式

先记一条总原则：

- `rg_templates` 的职责是**粗筛 / candidate retrieval**
- 默认目标是 **recall 优先，不是 precision 优先**
- 因此允许出现一定量的 false positives
- 不要把 `rg_template` 校准成“几乎只有命中才会出现”的高精度判定器
- 这条原则不只是文档口号，`retrieval_signals.json` 里的默认语义和各条模板的使用方式也都应该服从它

真正应该严格的是：

- verdict layer（`subpatterns/*.json`）
- 人工打开代码后的机制判断

对 retrieval layer，只有两类情况值得继续收紧：

- 会系统性拉出明显相邻 sibling 的整类噪声
- 会让候选量级膨胀到 agent 根本无法人工消化

### 1. 默认先跑 `broad_recall`

- 默认入口先用 `broad_recall`
- 目的不是“更准”，而是：
  - 先用较低成本拿到一批 path-prioritized candidates
  - 再判断是否需要扩大到全仓
- 不把 `path_globs` 当硬门槛

### 2. 如果 `broad_recall` 为空、明显过 sparse，或怀疑路径漂移，再跑 `fallback_no_path`

- `fallback_no_path` 是 recall 兜底，不是默认常驻入口
- 它的价值是补 path/layout drift，不是追求更高 precision
- 如果 `fallback_no_path` 量级明显膨胀但几乎不补 coverage，就不要把它当常规第一跳

### 3. 如果结果太多，再跑 `group_intersection`

- 这一步只是粗筛
- 目标是轻度缩候选，不是做最终判定
- `group_intersection` 命不中，不得反向否定已经被 `broad_recall` / `fallback_no_path` 召回的候选

### 4. 对候选逐个打开代码人工判断

- 这一步不能交给脚本自动定性
- 尤其是结果顺序问题，必须逐个看：
  - 顺序来自 SQL 还是 Go collection
  - 有没有稳定顺序契约
  - `ORDER BY` 是否真的足够
  - `LIMIT` / ties / compare 是否让顺序仍然不稳定

### 5. 最后再套 `subpatterns/*.json`

- 核对 `signals_required`
- 再看 `signals_optional`
- 最后用 `negative_guards` 排除相邻 sibling

## 2026-04-17 实仓校准结论

- `b1` / `b5` 的 `rg_template` 不能允许正则跨到下一条 `MustQuery`，否则会把相邻语句串起来，制造明显假阳性。
- `b1` 还需要尽量把已经 `.Sort().Check(...)` 的链路排掉；否则召回里会混入大量“其实已经做了无序归一化”的 case。
- `b3` 不能只靠行内 `UnionScan|IndexLookUp + ORDER BY/LIMIT` 的近邻共现；真实正例里很常见的是：
  - 上面动态拼 SQL / `order by`
  - 下面 `MustHavePlan(q, "UnionScan" / "IndexLookUp")`
- `b4` 的 `group_intersection` 要保证正则本身能编译通过；这条现在已经在 `retrieval_signals.json v3` 修正。

## 2026-04-17 基于 `100` 个正例的 patch-proxy 覆盖反查

这一步不是“拿现有 subpattern 去给 case 贴标签”。

这一步做的是：

- 先用 patch-first 人工复读，得到 `100` 个 patch-backed 正例
- 再把当前 `retrieval_signals.json v3` 里的 `rg_templates` 原样拿出来
- 对每个历史正例只取 patch 文本里的 `diff --git` 及其后续内容做匹配
- 看这些检索模板，是否至少能在 patch 形态上“看见”这些真实机制

这里必须强调：

- 这是 **patch-text proxy coverage**
- 不是当前仓库上的 literal recall
- 它的用途是发现“regex 形态盲区”，不是直接给 `retrieval_signals.json` 做机械改写

### 覆盖结果总表

| bucket | 正例数 | `broad_recall` | `group_intersection` | 当前结论 |
|---|---:|---:|---:|---|
| `b1` | `44` | `36 / 44 = 81.8%` | `24 / 44 = 54.5%` | broad 已可用；group 明显偏窄 |
| `b2` | `35` | `34 / 35 = 97.1%` | `14 / 35 = 40.0%` | broad 很强；group 只是高纯度锚点 |
| `b3` | `13` | `9 / 13 = 69.2%` | `3 / 13 = 23.1%` | 明显 under-recall |
| `b4` | `6` | `3 / 6 = 50.0%` | `3 / 6 = 50.0%` | 仍明显偏弱 |
| `b5` | `2` | `0 / 2 = 0%` | `1 / 2 = 50.0%` | 当前最弱，不适合靠字面 grep 高置信命中 |

### 代表性 miss 原因

#### `b1`

- broad 召回已经能覆盖大多数“`MustQuery(...).Check(testkit.Rows(...))` + 无顺序契约”形态
- 但仍会漏掉一些不是同一窗口字面量展开的 case，例如：
  - `pr-34130`
    - 修点在 SQL 结果表达本身的顺序契约，例如 `group_concat(... order by ...)`
  - `pr-64279`
    - patch 形态不完全长成当前正则偏好的 `MustQuery(...).Check(testkit.Rows(...))` 链式字面量
- 这说明 `b1 group_intersection` 适合拿来缩候选，不适合当 recall 主入口

#### `b2`

- broad 只漏了 `pr-55365`
- 这个 patch 的修法是 helper-object 自己暴露 `.Sort()`：
  - `dumpJSONTable.Sort()`
  - `jsonTbl.Sort()`
- 当前 broad 主要盯 `sort.Strings` / `sort.Slice` / `ElementsMatch` / `require.Equal`
- 因此它对“helper 自带 Sort 方法”这类稳定化修法还不够敏感

#### `b3`

- 这条的 miss 不是正例太少，而是 regex 还过度依赖少数字面锚点
- 代表性漏例：
  - `pr-8251`
    - `UNION ... ORDER BY ... LIMIT 1` 的 runtime/order-path 问题，但 patch 里没有今天偏好的 `MustHavePlan(..., \"UnionScan\" / \"IndexLookUp\")` 形态
  - `pr-31359`
    - 真实修法在 runtime 路径：`buildTableReaderFromHandles(..., true)`，而不是测试断言侧补 `.Sort()`
  - `pr-46367`
    - patch 能看见 `keep order:true` 这样的 ordered-path 语义，但仍不一定命中当前 group 模板
- 所以 `b3` 下一轮需要扩的是“ordered path 语义锚点”，不是继续加更多测试断言字面量

#### `b4`

- 当前模板对 `sort.Stable` / `Less` / `topNSorter` 这类锚点过拟合
- 但历史正例里还有不少“已经在排序，但排序 helper 自身不稳定”的其他形态：
  - `pr-5044`
    - 修的是 `Result.Sort()` helper 自身 comparator
  - `pr-15536`
    - 修的是 `sort.Slice` + 明确 tie-breaker（按 `ID` 等字段稳定比较）
  - `pr-25092`
    - 修的是先语义化解析再 `sort.Float64s`
- 所以 `b4` 现在的 broad/group 都还偏保守

#### `b5`

- 这条本来就不适合靠 grep 做高置信召回
- `pr-45513` 就是典型例子：
  - patch 不是简单的 `MustQuery(...).Check(testkit.Rows(...))`
  - 而是 `queryRegular := ...`
  - `regularResult := tk.MustQuery(queryRegular).Sort().Rows()`
  - 再加 plan 检查和 tie-cutoff 逻辑 `maxEle`
- 这说明 `b5 broad_recall` 目前过度绑定某一种断言字面形态

### patch-proxy 阶段结论（后续已被真实 repo-scan `v4` 校准覆盖）

- `item 3` 已完成：`100` 个 patch-backed 正例都已经拿来反查当时的 `rg_templates`
- 当时的结论是：
  - 先不要只根据 patch miss 直接改 regex
  - 需要再做一轮真实仓库 repo-scan 校准
- 下面的 `v4` 章节就是在这个前提下继续完成的下一步

## 2026-04-17 继续校准：真实 repo-scan（TiDB master）

上面那一轮只是 patch-proxy。

这一步继续做的是：

- 直接拿 `retrieval_signals.json` 去当前 TiDB 仓库跑真实 `rg`
- 先看每条 `rg_template` 的命中量级
- 再看头部命中是不是被明显的通用锚点放大了
- 再决定哪些模板值得收紧到 `v4`

这轮 repo-scan 的仓库是：

- `/Users/fanzhou/workspace/github/tidb`

### 从 `v3` 到 `v4` 的真实 repo-scan 变化

| bucket | `v3 broad` | `v4 broad` | `v3 group` | `v4 group` | 这轮动作 |
|---|---:|---:|---:|---:|---|
| `b1` | `8002` | `2732` | `1614` | `80` | 收紧 |
| `b2` | `20960` | `357` | `636` | `94` | 明显收紧 |
| `b3` | `2622` | `625` | `248` | `248` | 只收紧 broad |
| `b4` | `397` | `85` | `290` | `11` | 明显收紧 |
| `b5` | `129` | `129` | `20` | `20` | 保持不变 |

### `v4` 为什么这样改

#### `b2` `map / collection / helper`

`v3` 最大的问题是：

- broad 直接把 `require.Equal` / `sort.Slice` / `sort.Sort` 这些全仓通用锚点 OR 进来
- 在真实仓库上会立刻膨胀到 `20960` 条

所以 `v4` 改成两层：

- broad / fallback
  - 第一跳只抓 collection / helper 变量锚点本身
  - 例如 `visitInfo` / `details` / `orderedHandles` / `partDefs` / `tagLabels` / `schemaNames`
- group
  - 第二跳只看更高纯度的 subset：
    - `visitInfo` / `orderedHandles` / `partDefs` / `tagLabels` / `schemaNames`
  - 再要求它们与 `require.Equal` / `DeepEqual` / `ElementsMatch` / `sort.*` 在局部窗口里共现

这样做之后：

- broad 从 `20960` 降到 `357`
- group 从 `636` 降到 `94`

这轮还额外加了一个 soft exclude：

- `execdetails`

原因是 `details` 这个词在真实仓库里很容易撞到 `execdetails` 这一类无关符号。

#### `b1` 多行 SQL 结果做精确顺序断言

`v3` 的 broad 问题是：

- 任何 `MustQuery(...).Check(testkit.Rows(...))` 都会被扫进来
- 单行 / 常规确定性断言太多，量级直接来到 `8002`

所以 `v4` broad 只保留：

- `MustQuery(...).Check(testkit.Rows(...))`
- 且 `Rows(...)` 至少看起来像多行 exact-order：
  - 形态上至少有第二个 row 参数
- 同时继续避免跨到下一条 `MustQuery`
- 继续排掉已经 `.Sort().Check(...)` 的链路

group 再进一步收紧：

- 只看更像 order-sensitive SQL family 的字面量：
  - `UNION` / `JOIN` / `GROUP BY` / `SHOW` / `LIMIT`
- 给 `LIMIT` / `SHOW` 加词边界
- 额外排掉同一行里已经 `.Sort().Check(...)` 的链路

这样做之后：

- broad 从 `8002` 降到 `2732`
- group 从 `1614` 降到 `80`

这里要注意一个残余边界：

- 个别单行 `Rows("...")` 里如果字符串内容本身带逗号，仍可能伪装成“多行”
- 但在真实 repo-scan 量级上，这已经比 `v3` 可控很多

#### `b3` runtime / executor ordered path

`v3` broad 的主要问题不是 regex 编不过，而是第一跳扫得太宽：

- 直接在全仓 `*.go` 上搜 ordered-path 关键词
- 真实量级是 `2622`

这轮 `v4` 没有急着重写 group，而是只做一件低风险的事：

- broad_recall 第一跳限制到 `*_test.go`
- 并优先看测试里真的留下过的 ordered-path 证据：
  - `MustHavePlan(`
  - `KeepOrder`
  - `keep order:true`
  - `UnionScan`
  - `IndexLookUp`
  - `PhysicalTableScan`
  - `double read`
  - `direct reading`

结果：

- broad 从 `2622` 降到 `625`
- group 先保持 `248` 不动

原因很简单：

- 这条的 hard part 还是 ordered-path 语义本身
- broad 先缩到测试层即可
- group 还需要下一轮专门看 precision / miss 结构再改

#### `b4` sort / comparator / tie-breaker

`v3` 最大的问题是：

- `Less(` 太泛
- `sort.Slice(` 也太泛
- 在真实仓库上会把大量完全正常的 comparator / heap / helper 排序逻辑一起扫进来

所以 `v4` broad 只保留更强的 stability anchors：

- `sort.Stable(`
- `sort.SliceStable(`
- `sort.Float64s(`
- `SortSampleItems`
- `Result.Sort(`
- `compareType(`
- `topNSorter`
- `func ... Less(i, j int)`
- `stable sort`
- `unstable order`
- `tie-breaker`

并且明确把下面这个作为 soft exclude：

- `require.Less(`

结果：

- broad 从 `397` 降到 `85`
- group 从 `290` 降到 `11`

这条 `v4 group` 现在等价于一个 short list：

- `SortSampleItems`
- `compareType(`
- `sort.Stable(`
- `sort.Float64s(`
- `Result.Sort(`
- `stable sort`
- `unstable order`
- `tie-breaker`

#### `b5` `ORDER BY` ties + `LIMIT`

这条在真实 repo-scan 里的量级本来就不大：

- broad `129`
- group `20`

而且它本身就是 low-grepability / weak-recall only。

所以这轮 `v4` 先保持不动，不为了“看起来统一”而硬改。

## 2026-04-17 用历史正例回验当前 `v4 rg_templates`

这一步验证的不是“当前仓库 literal recall”。

这一步验证的是：

- 把当前 `retrieval_signals.json v4` 里的 `rg_templates` 原样取出
- 回放到这轮人工复读得到的历史正例 patch 文本上
- 看这些模板，能不能在 patch 形态上重新“看见”这些真实机制

这轮继续只看 patch 文本里的 `diff --git` 及其后续内容，因此结论仍然是：

- **patch-text proxy coverage**
- 目的是看 regex 有没有形态盲区
- 不是直接拿来代替真实 repo-scan

### `v4` patch-proxy 覆盖结果

| bucket | 正例数 | `broad_recall` | `fallback_no_path` | `group_intersection` | 结论 |
|---|---:|---:|---:|---:|---|
| `b1` | `44` | `23 / 44 = 52.3%` | `23 / 44 = 52.3%` | `8 / 44 = 18.2%` | 相比 `v3` 明显掉 recall，当前偏严 |
| `b2` | `35` | `11 / 35 = 31.4%` | `11 / 35 = 31.4%` | `3 / 35 = 8.6%` | 相比 `v3` 大幅掉 recall，当前偏严 |
| `b3` | `13` | `10 / 13 = 76.9%` | `9 / 13 = 69.2%` | `3 / 13 = 23.1%` | `broad` 比 `v3` 略好 |
| `b4` | `6` | `5 / 6 = 83.3%` | `5 / 6 = 83.3%` | `3 / 6 = 50.0%` | 比 `v3` 明显更好 |
| `b5` | `2` | `0 / 2 = 0%` | `0 / 2 = 0%` | `1 / 2 = 50.0%` | 仍然不适合靠 grep 做高 recall |

### 相比 `v3` 的变化

- `b1`
  - broad: `36 -> 23`
  - group: `24 -> 8`
- `b2`
  - broad: `34 -> 11`
  - group: `14 -> 3`
- `b3`
  - broad: `9 -> 10`
  - group: `3 -> 3`
- `b4`
  - broad: `3 -> 5`
  - group: `3 -> 3`
- `b5`
  - 基本不变

### 这轮回验说明了什么

#### `b1` 的问题不是机制错了，而是 regex 字面形态收得太死

代表性 miss：

- `pr-10837`
  - patch 里是：
    - `tk.MustQuery("SHOW PROCESSLIST;").Check(`
    - 下一行才接 `testkit.Rows(...)`
  - 当前 `v4` 更偏好 `.Check(testkit.Rows(...))` 紧邻展开，因此会漏掉这种“链式调用换行”的真实正例

所以 `b1` 现在的问题更像：

- broad 对 multiline `.Check(` 形态还不够宽
- group 更明显偏严，只适合高纯度粗筛

#### `b2` 的问题是锚点集合被收得过窄

这轮 miss 的代表形态包括：

- `pr-30235`
  - `OptimizerCETrace` + `require.ElementsMatch(...)`
- `pr-55322`
  - `resultRows` / `sortRows` / `sort.Slice(...)`
- `pr-5256`
  - schema decode 后 `sort.Strings(names)` + `DeepEquals`
- `pr-25910`
  - `TimestampList` / `CPUTimeMsList` + `sort.Slice(...)`

也就是说，`v4` 为了控制真实 repo 噪音，把 `b2` broad 收到一小组 collection 变量名上，确实把 noise 压下来了，但也把很多真实 helper / collection sibling 一起裁掉了。

#### `b3 / b4` 这轮是正向变化

- `b3 broad` 新增打中 `pr-46367`
  - 说明 `keep order:true` 这类 ordered-path 语义锚点是值得保留的
- `b4 broad` 新增打中 `pr-15536`、`pr-25092`
  - 说明当前对 tie-breaker / helper sort 失稳的字面锚点比 `v3` 更贴近真实修法

### 当前校准判断

- 如果目标是**真实 repo-scan 降噪**，当前 `v4` 是有效的
- 如果目标是**让 `rg_templates` 对历史正例也保留更强可见性**，那 `b1` / `b2` 还需要再放宽一小步
- 因此当前最合理的结论不是“推翻 `v4`”，而是：
  - 保留 `v4` 作为当前 repo-scan 版本
  - 明确认定 `b1` / `b2` 还存在 patch-proxy recall 盲区
  - 下一轮优先补：
    - `b1` 的 multiline `.Check(` -> `testkit.Rows(...)` 形态
    - `b2` 的更通用 helper / collection anchors，而不是只靠当前这组变量名

## 2026-04-17 继续校准：把两条最小 tweak 收进 `v5`

在上面的 `v4` 结论基础上，这轮继续做了两条**最小改动**，并已经落到 `retrieval_signals.json v5`：

### 这轮实际改了什么

#### `b1` 多行 SQL 结果精确顺序断言

- 只改了 `broad_recall` / `fallback_no_path`
- 核心改动是把：
  - `.Check(testkit.Rows(...))`
- 放宽为：
  - `.Check(\\s*testkit.Rows(...))`

这样只允许：

- `.Check(` 和 `testkit.Rows(...)` 之间出现空白 / 换行

但**没有**把整段 SQL-family `group_intersection` 一起放宽成大窗口 multiline：

- 因为那样虽然 patch-proxy recall 会涨
- 但真实 repo-scan 会被明显放大

所以 `b1` 这轮是一个很克制的 tweak：

- 只补 `Check(` 链式换行的真实正例盲区
- 不去碰更敏感的 SQL-family 粗筛边界

#### `b2` map / collection / helper sibling

- broad / fallback / group 都补了一小组更通用的 helper-side anchors：
  - `OptimizerCETrace`
  - `TimestampList`
  - `CPUTimeMsList`
  - `resultRows`
  - `sortRows`
  - `sort.Strings(names)`

这轮**没有**把更 repo-specific 的 helper object literal 一起收进来，例如：

- `jsonTbl`
- `dumpJSONTable`

原因是：

- 它们确实还能再补回一两个历史正例
- 但更像单仓库 / 单实现的对象名
- 先不急着把 family-level retrieval 写成 patch-literal overfit

### `v5` patch-proxy 回验结果

| bucket | `v4 broad` | `v5 broad` | `v4 group` | `v5 group` | 变化 |
|---|---:|---:|---:|---:|---|
| `b1` | `23 / 44 = 52.3%` | `24 / 44 = 54.5%` | `8 / 44 = 18.2%` | `8 / 44 = 18.2%` | broad `+1` |
| `b2` | `11 / 35 = 31.4%` | `15 / 35 = 42.9%` | `3 / 35 = 8.6%` | `6 / 35 = 17.1%` | broad `+4`，group `+3` |

对应补回来的代表性正例：

- `b1`
  - `pr-10837`
    - 典型的 `.Check(` 换行后才接 `testkit.Rows(...)`
- `b2`
  - `pr-30235`
    - `OptimizerCETrace` + `ElementsMatch`
  - `pr-25910`
    - `TimestampList` / `CPUTimeMsList`
  - `pr-55322`
    - `resultRows` / `sortRows`
  - `pr-5256`
    - `sort.Strings(names)`

### `v5` 真实 repo-scan 粗量级

为了避免多行 `-U` regex 的 match 行数失真，这里优先看**命中文件数**：

| bucket | `v4 broad files` | `v5 broad files` | `v4 group files` | `v5 group files` | 结论 |
|---|---:|---:|---:|---:|---|
| `b1` | `142` | `145` | `18` | `18` | broad 只小幅增加 |
| `b2` | `41` | `51` | `6` | `14` | 有增加，但仍在可控范围 |

如果按 `rg -n` 的粗量级看：

- `b1 broad`: `2732 -> 2837`
- `b2 broad`: `357 -> 398`
- `b2 group`: `94 -> 175`

这说明：

- `b1` 这条 tweak 的成本非常小
- `b2` 的 recall 提升是拿一些额外候选换来的
- 但还没有回到 `v3` 那种明显放大的量级

### 这轮 `v5` 的判断

- `b1` 这条已经证明：
  - multiline `.Check(` -> `testkit.Rows(...)` 值得正式收进 retrieval layer
- `b2` 这条已经证明：
  - 继续只靠 `visitInfo/details/trace/...` 这一小组变量名是不够的
  - 补少量 helper-side anchors 是值得的

但同时也保留了两个边界：

- `b1 group_intersection`
  - 暂时不跟着一起放宽
  - 因为更宽的 multiline SQL-family group 会明显放大 repo-scan
- `b2 helper object literal`
  - 暂时不收 `jsonTbl` / `dumpJSONTable` 这种对象名
  - 先避免 family-level retrieval 过拟合单仓库对象名

## 2026-04-17 继续校准：把 `b1 group` 和 `b2 group` 再收一小步进 `v6`

在 `v5` 的基础上，这轮继续只做两条很克制的修正：

### `b1 group_intersection`

`v5` 时我没有放宽 `b1 group`，因为更宽的 multiline 版本会明显放大 repo-scan。

这轮继续往下压窗口后，找到一版更平衡的版本：

- 仍然要求 query line 本身带：
  - `UNION`
  - `JOIN`
  - `GROUP BY`
  - `SHOW`
  - `LIMIT`
- 但允许从这些 SQL-family 锚点到 `.Check(\\s*testkit.Rows(...))` 之间有一个**很短的 multiline 窗口**
  - 当前收的是 `{0,60}`

也就是说：

- 这不是“整段随便跨行”
- 只是允许真实链式调用里常见的短距离换行

#### `b1 group` 的实际效果

- `v5 group`: `8 / 44 = 18.2%`
- `v6 group`: `16 / 44 = 36.4%`

新增补回的代表性正例包括：

- `pr-10837`
- `pr-1591`
- `pr-1899`
- `pr-2195`
- `pr-3781`
- `pr-39138`
- `pr-4001`
- `pr-7680`

真实 repo-scan 量级：

- `v5 group`
  - repo files: `18`
- `v6 group`
  - repo files: `38`

这个量级确实变大了，但相比更宽的 multiline 版本（`39~42+ files`，甚至更高）已经是当前比较稳的折中点：

- patch recall 翻倍
- repo-scan 仍明显小于 broad

### `b2 group_intersection`

`v5` 已经把 `OptimizerCETrace` / `TimestampList` / `resultRows` 这些 helper-side anchors 收进来了。

这轮再补的不是对象名，而是 compare 侧补一个更通用的 gocheck comparator：

- `DeepEquals`

之所以只收这一个，是因为：

- `pr-5256` 就是很典型的 `sort.Strings(names)` + `DeepEquals`
- 继续加 `c.Assert(` 这种更泛的 anchor，虽然还能再补一点，但语义太宽，容易把很多非 compare 语境一起卷进来

#### `b2 group` 的实际效果

- `v5 group`: `6 / 35 = 17.1%`
- `v6 group`: `7 / 35 = 20.0%`

新增补回：

- `pr-5256`

真实 repo-scan 量级：

- `v5 group`
  - repo files: `14`
- `v6 group`
  - repo files: `14`

也就是说，这个增益几乎是白拿的：

- patch recall `+1`
- repo file 数不变

### 这轮 `v6` 的判断

- `b1 group`
  - 值得收一版短窗口 multiline 版本
  - 但不要再继续往大窗口放宽
- `b2 group`
  - `DeepEquals` 值得正式收进 compare anchors
  - `c.Assert(` 这类更泛的框架级锚点暂时不收

因此当前比较稳的结论是：

- `v6` 可以作为这条 family 当前更平衡的版本
- 后续如果再继续校准，优先级应当是：
  - 继续人工检查 `b1 group` 新增命中的 repo files 质量
  - 而不是继续靠更宽 regex 去堆 recall

## 2026-04-17 继续校准：把 `b1 group` 里的系统性噪声正式排掉进 `v7`

`v6` 的主要收益已经拿到了：

- `b1 group` patch-proxy coverage 从 `8 / 44` 提到 `16 / 44`

但 `v6` 还有一个明显问题：

- repo-scan files 从 `18` 增到 `38`
- 新增文件里有一批已经人工确认的“相邻 sibling / metadata / 已稳定化”噪声

这轮不是再去放宽 regex，而是把这几类**已知大类噪声**正式写进 `group_intersection` 的负例约束：

- query line 直接是 `EXPLAIN`
- query line 直接是 `SHOW WARNINGS`
- query line 直接是 `SHOW COLUMNS`
- query line 直接是 `SHOW DATABASES`
- query line 直接是 `SHOW GRANTS`
- query line 直接是 `SHOW STATS_TOPN` / `SHOW STATS_BUCKETS`
- `.Check(...)` 前的短窗口里已经出现 `.Sort(`

### 为什么这几类值得硬排

人工 spot-check 后，这几类命中基本都不是 `b1`：

- `EXPLAIN ... Check(testkit.Rows(...))`
  - 本质更像 plan golden / brittle regression，不是“结果顺序契约缺失”
- `SHOW WARNINGS`
  - 更像 warning emission order，不是目标 subpattern
- `SHOW COLUMNS` / `SHOW DATABASES` / `SHOW GRANTS` / `SHOW STATS_*`
  - 大多是 metadata-style `SHOW`，顺序往往来自实现约定或展示语义，不应默认归到 `b1`
- `.Sort(` 已经出现
  - 这类通常已经在断言前做了无序归一化；继续留在 `b1 group` 里只会制造明显伪命中

### `v7` 的实际效果

按 `197_case_人工review工作板.md` 里 `b1` 的完整 `44` 个正例回归：

- `v6 group`: `16 / 44 = 36.4%`
- `v7 group`: `16 / 44 = 36.4%`

也就是说：

- patch-proxy coverage **不掉点**

真实 repo-scan 量级：

- `v6 group`
  - repo files: `38`
- `v7 group`
  - repo files: `21`

也就是说：

- repo candidate files 进一步从 `38 -> 21`
- 被去掉的基本就是已经人工确认的大类噪声

### `v7` 后剩下的 repo 候选长什么样

剩下的 `21` 个文件里，主体已经更集中到这几类：

- 真正像 `b1` 的 unsorted SQL result assertions
  - 例如 `union_scan_test.go`
  - 例如 `distribute_table_test.go`
- 仍值得人工判断的 `SHOW ...` 结果顺序测试
  - 例如 `show_placement_test.go`
  - 例如 `show_test.go`
- 与 `b3 runtime/executor keep-order` 相邻、但仍可作为 candidate 打开的 join/order cases
  - 例如 `executor/test/jointest/join_test.go`
  - 例如 `planner/core/tests/null/null_test.go`

因此这轮 `v7` 的结论很明确：

- `b1 group_intersection` 值得正式保留这些负例约束
- 下一步不该再继续堆更宽的 multiline regex
- 更值得做的是：
  - 继续人工分拣剩余 `21` 个 repo files
  - 再看是否还存在新的“整类噪声”值得抽成额外 negative guard

## 2026-04-17 继续校准：把 `b2 group` 里两个弱 helper anchor 收回 broad 侧

在 `b2 group_intersection` 的 repo-scan 里，我又人工抽查了一轮当前 `14` 个命中文件。

这里面有 `3` 个比较典型的伪命中：

- `pkg/ddl/schematracker/info_store_test.go`
  - `schemaNames` + `require.Equal`
  - 实际是在做很局部的 schema/table name 点查，不是“收集后排序再整体 compare”
- `pkg/infoschema/issyncer/loader_test.go`
  - `schemaNames` 更多表现为 membership / existence 语义
  - 不是 `b2` 想抓的 collection-order normalization
- `pkg/executor/resource_tag_test.go`
  - `tagLabels` 命中后，附近真正的 `require.Equal` 大多在比对 digest / 标量
  - 更像“相邻变量共现”造成的噪声

这三个噪声有一个共同点：

- 它们都来自 `schemaNames` / `tagLabels` 这两个 helper anchor
- 这两个词做 **broad_recall** 还可以
- 但进到 **group_intersection** 就太弱了，容易把“成员存在性 / 标量点查”一并带进来

所以这轮的做法不是继续缩窗口，而是把：

- `schemaNames`
- `tagLabels`

从 `b2 group_intersection` 里拿掉，但仍保留在 broad / fallback。

### 这轮效果

按 `197_case_人工review工作板.md` 里 `b2` 的完整 `35` 个正例回归：

- 调整前：`7 / 35 = 20.0%`
- 调整后：`7 / 35 = 20.0%`

真实 repo-scan 量级：

- 调整前
  - repo files: `14`
- 调整后
  - repo files: `11`

被稳定去掉的就是：

- `pkg/ddl/schematracker/info_store_test.go`
- `pkg/infoschema/issyncer/loader_test.go`
- `pkg/executor/resource_tag_test.go`

### 这轮判断

所以当前更稳的结论是：

- `schemaNames` / `tagLabels`
  - 适合留在 `broad_recall`
  - 不适合继续留在 `group_intersection`
- `b2 group_intersection`
  - 当前更像“高纯度缩候选器”
  - 不应该再为了 recall 把太弱的 helper 名继续塞回来

## 当前 5 条已 formalize subpattern 的检索提示

### 1. `map / collection / helper 收集结果后未排序就断言`

- `grepability`: `medium`
- 重点不是搜 SQL，而是搜：
  - 先 `append/collect`
  - 后 `require.Equal / DeepEqual / Check`
  - 中间没有稳定归一化
- 高信号锚点：
  - `visitInfo`
  - `details`
  - `orderedHandles`
  - `partDefs`
  - `trace`
  - `tagLabels`
  - `sort.Strings`
  - `sort.Slice`
  - `sort.Sort`
  - `require.Equal`
  - `reflect.DeepEqual`

这条在这轮 `197` patch 人工复读后，边界比之前更宽：

- 不要再只盯 `GetAllServerInfo` / `serverInfo`
- 真实正例里，`details` / `trace` / `orderedHandles` / `partDefs` / label collection 这些 helper-side collection 也很多

### 2. `多行 SQL 结果做精确顺序断言时，必须显式 ORDER BY 或 Result.Sort`

- `grepability`: `medium`
- 第一跳先看：
  - `MustQuery(...).Check(testkit.Rows(...))`
  - 多行
  - 没有 `Result.Sort()`
  - SQL 看起来也没有稳定顺序契约
- 注意：
  - 单行 / 空结果不应优先怀疑
  - 只看“没 `.Sort()`”会有很多误报
  - 也不要把 runtime keep-order 问题误归到这里

### 3. `ORDER BY 键不唯一时，LIMIT / 结果比对不能断言精确顺序`

- `grepability`: `low`
- 第一跳先找：
  - 已经有 `ORDER BY`
  - 同时又有 `LIMIT` / compare / result equality
  - 测试数据里排序键可能重复
- 这条必须人工看：
  - `ORDER BY` 是否只有单列
  - ties 是否合法存在
  - patch 是补二级排序键 / 去重数据，还是 simply `.Sort()`

这条是当前 5 条里**最不适合靠 grep 直接高置信命中**的一条：

- `ORDER BY + LIMIT` 只能做弱召回
- “排序键是否真的不唯一”这件事，通常必须回到 patch / test data / compare 语义里人工确认

### 4. `runtime / executor` 路径本身应该保序

- `grepability`: `medium`
- 第一跳先找：
  - `KeepOrder`
  - `UnionScan`
  - `double read`
  - `PhysicalTableScan`
  - `IndexLookUp`
  - `partition direct reading`
- 这条必须人工看：
  - 顺序契约是否已经显式存在
  - 主修法到底在 runtime path，还是只是断言侧补 `Sort()`
  - 是否真的是 keep-order / ordered path 没守住

### 5. `sort / comparator / tie-breaker / repeated sort` 本身不稳定

- `grepability`: `medium`
- 第一跳先找：
  - `sort.Stable`
  - `sort.SliceStable`
  - `Less`
  - `topNSorter`
  - `SortSampleItems`
  - `unstable order`
- 这条必须人工看：
  - patch 是在修 sort implementation，还是只是给 collection 补排序
  - comparator / tie-breaker 是否真的决定最终顺序稳定性
  - 是否属于 repeated unstable sort

## 2026-04-17 按 recall-first 原则重看当前模板后的直接调整

这轮重新看的标准不再是“还能不能继续提纯”，而是：

- broad / fallback 有没有明显收得过严
- 是否已经漏掉了当前 bucket 里很典型的正例形态
- 放宽后 repo candidate 量级是否仍然在可人工 review 的范围里

### 这轮实际落的两处 widen

#### `b4` sort/comparator/tie-breaker

之前的 broad / fallback / group 主要只认：

- `Result.Sort(`
- `sort.Stable(`
- `SortSampleItems`
- `topNSorter`

但 `pr-5044` 这种真实正例，修法是在 helper 定义侧：

- `func (*Result) Sort()`

这轮把 `func (*Result) Sort()` 这类 helper method definition 也收进来了。

结果：

- `b4 broad_recall`
  - `5 / 6 -> 6 / 6`
  - repo files `54 -> 55`
- `b4 group_intersection`
  - `4 / 6 -> 5 / 6`
  - repo files `9 -> 10`

这是很典型的 recall-first、且代价很小的放宽，值得保留。

#### `b5` ORDER BY 键不唯一 + LIMIT

之前 broad / fallback 过度绑定：

- `MustQuery(...).Check(testkit.Rows(...))`

但这条 bucket 的真实正例更常见的是：

- `regularResult := tk.MustQuery(queryRegular).Sort().Rows()`
- 先 materialize rows，再做后续 compare / plan check

这轮 broad / fallback 改成至少兼容 `.Rows()` / `.Sort().Rows()` 这类 variable-based compare 形态。

结果：

- `b5 broad_recall`
  - `0 / 2 -> 2 / 2`
  - repo files `14 -> 32`
- `b5 fallback_no_path`
  - `0 / 2 -> 2 / 2`
  - repo files `14 -> 32`

这条 repo 量级虽然变大，但仍然在可人工 review 的范围里，而且终于不再是 `0 / 2` 的不可用状态，所以这步 widen 是值得的。

### 这轮没有立刻改的

- `b1`
  - 还有不少 miss，但其中一部分是 shell / integration script 形态，另一部分是 fix-side 已经 `.Sort()` / `ORDER BY` 的 patch 文字，不宜直接机械放宽 broad
- `b2`
  - broad 仍偏窄，但下一步更像要补 helper-object / method-style anchors，而不是简单继续放宽窗口
- `b3`
  - broad 确实还能再放宽一小步（例如补 runtime anchor），但候选 repo files 会明显上升，所以暂时先不机械落盘

## 当前落地状态

- `retrieval_signals.json`
  - 当前版本：`v8`
  - 已覆盖当前 `5` 个已 formalize subpattern
- verdict layer
  - 当前就是 `subpatterns/` 里的这 `5` 个正式 JSON

当前下一步不再是“补 formalization”，而是继续验证这 `5` 条在真实仓库扫描里的 recall / candidate 量级，并继续收紧相邻 sibling 的边界。
