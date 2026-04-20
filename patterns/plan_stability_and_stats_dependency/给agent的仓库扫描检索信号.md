# `plan_stability_and_stats_dependency` 给 agent 的仓库扫描检索信号

这份文档记录的是：

- 当前这条 umbrella family 的 **draft broad `rg_template`**
- 以及它们在 **历史正例 patch 文本** 上的回放结果

它不是：

- 正式的 `retrieval_signals.json`
- verdict / classification 规则

这一步仍然只服务：

- **coarse retrieval / candidate retrieval**

也就是说：

- `rg_template` 只负责“先把可疑候选粗筛出来”
- 最终是不是命中哪条 sibling，仍然必须回到 `subpatterns/*.json` 的 `signals_required / negative_guards` 做人工判断

## Hard Rules

1. 这些 `rg_templates` 只能做粗筛，允许 false positive。
2. 不能因为某条 regex 能 hit 到某个 patch，就反过来把它当成 sibling 定义。
3. 当前仍然**不创建** umbrella 级 `retrieval_signals.json`。
4. 这轮验证的是：
   - **patch-text proxy hit rate**
   - 不是实际仓库 precision

## 当前 full positive set

这里用的是这轮 patch-first 人工复读后保留下来的**完整正例集**，不是 JSON 里只放的代表例子。

| sibling | full positive set |
|---|---|
| `h1` | `pr-26468`, `pr-30026`, `pr-34141`, `pr-34150`, `pr-58039`, `pr-60514`, `pr-65329`, `pr-66928` |
| `h2` | `pr-27734`, `pr-62123`, `pr-62363`, `pr-64119`, `pr-64428` |
| `h3` | `pr-32017`, `pr-54440`, `pr-58254`, `pr-62725`, `pr-63500`, `pr-63702` |
| `h4` | `pr-30139`, `pr-32139`, `pr-33299`, `pr-36855` |
| `h5` | `pr-43204`, `pr-51926`, `pr-65771` |

总计：`26` 条正例。

## 当前 draft broad `rg_templates`

这些模板都按 `rg -n -U -P '<pattern>' <repo_root>` 口径设计。

### `h1` stats 真正 ready 之前不应断言

```regex
(?is)(LoadNeededHistograms|StatsHandle\(\)\.Update|HandleDDLEvent|load\s+stats|sync\s*load|unInitialized|stats\s+cache|histogram|Buckets\)\s*==\s*0|not\s+loaded)
```

意图：

- 覆盖 `LoadNeededHistograms` / `StatsHandle().Update(...)` 这种显式 load / update 形态
- 同时补到 `pr-34150` 这种 “`Buckets` 为空说明还没 loaded” 的 patch 形态

### `h2` stats-derived numeric output 不应做 exact constant

```regex
(?is)(InDelta|LessEqual|GreaterEqual|require\.Less|require\.Greater|len\(items\)\s*>?=|correlation|show\s+stats_buckets|show\s+stats_topn|GetRowCountBy(Index|Column)Ranges|AsyncLoadHistogramNeededItems\.AllItems)
```

意图：

- 覆盖 bucket / correlation / row-count / async-load item count
- 同时覆盖 `Equal -> InDelta/range/monotonic/lower-bound` 这类稳定化修法

### `h3` analyze inputs / scope / threshold-side data scale 必须先 pin

```regex
(?is)(samplerate|sample\s*rate|tidb_analyze_version|analyze\s+table.{0,80}all\s+columns|predicate\s*column|DumpColStatsUsageToKV|stats_ver|analyze\s+version|for\s+i\s*:=\s*0;\s*i\s*<\s*\d+\s*;\s*i\+\+.{0,200}insert\s+into\s+\w+\s*\([^\)]*\)\s*select)
```

意图：

- 覆盖 `samplerate` / `tidb_analyze_version` / `all columns` / predicate-column collection
- 额外补到 `pr-58254` 这种不是直接写 analyze knob，而是**通过缩小 insert-doubling 规模避开 threshold-side** 的 patch 形态

### `h4` cache-hit / read-from-cache 不应逐次硬断言

```regex
(?is)(last_plan_from_cache|ReadFromTableCache|HasPlan\(|UnionScan|cache\s+ready|helperCheckPlanCache|missedPlanCache|cache\s+table|alter\s+table.{0,40}cache)
```

意图：

- 覆盖 `@@last_plan_from_cache`
- 覆盖 `HasPlan(..., "UnionScan") -> ReadFromTableCache`
- 覆盖 cache warmup / miss-rate 容忍 / cached table 场景

### `h5` cache reuse 不应遮蔽 execution-time context

```regex
(?is)(as\s+of\s+timestamp|stale\s*read|SetSkipPlanCache|tidb_enable_non_prepared_plan_cache|extension\s+function|constant[_ ]fold|ConstNone|checkPrivileges|prepare\s+stmt|ExecutePreparedStmt|binding)
```

意图：

- 覆盖 stale-read prepared stmt
- 覆盖 non-prepared plan cache + binding
- 覆盖 extension function side effect / privilege / constant-fold / skip-plan-cache

## 2026-04-18 用 full positive set 回验当前 broad `rg_templates`

这一步验证的不是：

- 当前仓库 literal repo-scan recall

这一步验证的是：

- 把当前 draft broad `rg_templates` 原样拿出来
- 回放到这轮人工复读保留下来的 `26` 条真实正例 patch 文本上
- 看这些模板能不能重新“看见”这些真实机制

### `v0` 初稿结果

| sibling | 正例数 | broad hit | miss |
|---|---:|---:|---|
| `h1` | `8` | `7 / 8 = 87.5%` | `pr-34150` |
| `h2` | `5` | `5 / 5 = 100%` | none |
| `h3` | `6` | `5 / 6 = 83.3%` | `pr-58254` |
| `h4` | `4` | `4 / 4 = 100%` | none |
| `h5` | `3` | `3 / 3 = 100%` | none |

总计：

- `24 / 26 = 92.3%`

miss 原因：

- `pr-34150`
  - patch 主形态是：
    - `if len(idxStats.Buckets) == 0 { continue // it's not loaded }`
  - 说明 `h1` 不能只盯显式 `LoadNeededHistograms/Update`，还要容纳 “bucket 尚未 loaded” 的 patch 形态

- `pr-58254`
  - patch 主形态是：
    - 把 `for i := 0; i < 14; i++` 改成 `for i := 0; i < 4; i++`
  - 说明 `h3` 不能只盯 analyze knobs，还要容纳 “通过缩小数据规模避开 threshold-side” 的 patch 形态

### `v1` 最小 widening 后结果

| sibling | 正例数 | broad hit | 结论 |
|---|---:|---:|---|
| `h1` | `8` | `8 / 8 = 100%` | `Buckets == 0` / `not loaded` widening 生效 |
| `h2` | `5` | `5 / 5 = 100%` | 当前 broad 已足够 |
| `h3` | `6` | `6 / 6 = 100%` | threshold-side 数据规模 widening 生效 |
| `h4` | `4` | `4 / 4 = 100%` | 当前 broad 已足够 |
| `h5` | `3` | `3 / 3 = 100%` | 当前 broad 已足够 |

总体：

- `26 / 26 = 100%`

## 当前结论

1. 对这 `26` 条 full positive patch 文本来说，当前 broad `rg_templates` 的 **patch-proxy 正例命中率** 是：
   - `26 / 26 = 100%`
2. 这个 `100%` 只说明：
   - 当前 broad regex 没有明显的正例形态盲区
3. 它**不说明**：
   - 实际 repo-scan precision 也会高
4. 所以当前最合理的状态是：
   - broad `rg_template` 可以先留作 draft
   - 继续维持“只做 coarse retrieval，不做 verdict”
   - 后续如果要进入真实 repo-scan，再专门测 precision / 炸量情况

## 下一步

1. 在真实 TiDB 仓库上回放这 `5` 条 broad `rg_template`
   - 看 candidate 量级是否可接受
2. 如果某条 broad 明显炸量：
   - 优先补 path hint / group narrowing
   - 不要回头缩 sibling 定义
3. 在真实 repo-scan precision 没过一轮之前：
   - 仍然不要把这条 umbrella 直接升成正式 `retrieval_signals.json`
