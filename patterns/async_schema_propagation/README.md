# `async_schema_propagation`

这个目录承接 review smell `async_schema_propagation`（Async schema propagation issue）的 **patch-first** 全量人工复读与机制簇抽取工作，目标是把“异步 schema 传播导致的测试不稳”细化成可复查、可迭代、可用于后续更准确识别 flaky case 的 subpattern family。

> 强调：这里的 subpattern 不是关键词分类，也不是把已有字段/已有 subpattern 套回 case；唯一允许的聚类依据是 **共享失稳机制** 或 **共享修法机制**（以 patch 为证据）。

## Source set

- source smell：`async_schema_propagation`
- source case set：`cases/**/pr-*.json` 中 `review_smells` 含该 smell 的全量 cases
- source set 总数：`31`
- 人工复读：`31 / 31`（patch-first）
- 全量台账：[`全量人工review台账.md`](./%E5%85%A8%E9%87%8F%E4%BA%BA%E5%B7%A5review%E5%8F%B0%E8%B4%A6.md)

## 本轮结论（去向统计）

- retain：`6`
- exclude：`9`
- migrate：`6`
- watchlist：`10`

> 这些数字只对本 smell 的 source set 有效，不代表整个“schema 传播方向”的全局规模。

## 已形成并落盘的稳定 subpatterns

目前只把 **边界清楚、可复用、高纯度** 的机制簇落成正式 JSON。对应的 sibling 有 4 条：

1. `s1`：DDL 完成不等于 domain infoschema 已加载；断言前必须等 `SchemaMetaVersion` 推进（`3`）
   - 正例：`pr-54447`、`pr-54695`、`pr-59974`
2. `s2`：InfoSchema internal cache/TS 不能断言 sentinel；断言应基于 snapshot 或只校验不变量（`2`）
   - 正例：`pr-65786`、`pr-66732`
3. `s3`：SchemaOutOfDate/InfoSchemaChanged 的容错旋钮被测试调大（RetryTimes / max_delta_schema_count）（`2`）
   - 正例：`pr-14305`、`pr-14976`
4. `s4`：`Domain.Reload()` 作为 schema/cache 同步屏障：DDL/lock 状态变更后断言前必须 reload（`4`）
   - 正例：`pr-19580`、`pr-21491`、`pr-21624`、`pr-21664`

对应文件位于：[`subpatterns/`](./subpatterns/)

## Union 扩展复读（把相邻 smell 并入后再反向抽簇）

为尝试把 watchlist 里的 singleton 拉成可落盘 sibling，本轮额外做了一次 union 扩展复读：

- union smells：`async_schema_propagation` + `ddl_without_wait` + `schema_version_race`
- union 总数：`50`
- patch-first 人工复读：`50 / 50`
- union 全量台账：[`union_50_case_全量人工review台账.md`](./union_50_case_%E5%85%A8%E9%87%8F%E4%BA%BA%E5%B7%A5review%E5%8F%B0%E8%B4%A6.md)

union 去向统计（仅对该 union 有效）：

- retain：`11`
- exclude：`16`
- migrate：`12`
- watchlist：`11`

> 结果：`schema lease` 旋钮与 `ErrInfoSchemaChanged` 容忍策略仍不足以成簇；但 union 复读反向抽出了一个新的稳定簇（`s4`：测试侧显式 `dom.Reload()` 作为可见性/缓存释放的同步屏障），并为 `s1` 增加了一个额外正例（`pr-59974`）。

## 关键边界判断（为什么大量 case 不 retain）

这个 smell 的 source set 里混入了不少“看起来与 schema 相关”但机制并不属于本 family 的 case。patch-first 复读后，本轮明确了几条高频边界：

1. **DDL callback 误触发/重复触发**（迁移到 `race_condition_in_async_code`）
   - 典型修法：按 `job.Type` / `job.State==synced` / `job.MultiSchemaInfo==nil` 做过滤 + once 控制
   - 迁移正例：`pr-43832`、`pr-46899`、`pr-64397`

2. **stats ready / DDL event 异步消费**（迁移到 `plan_stability_and_stats_dependency`）
   - 典型修法：`HandleDDLEvent(<-DDLEventCh())`、显式 update/load stats
   - 迁移正例：`pr-6950`

3. **通用异步等待（sleep → pause/eventually/channel sync）**（迁移到待 formalize 的 async-wait 方向）
   - 典型修法：用 failpoint `pause` + channel 或 `Eventually` 替代固定 sleep
   - 迁移正例：`pr-24082`、`pr-46932`

4. **大型产品语义/feature patch（多机制混杂）**
   - 这类 patch 的“schema 中间态”只是实现细节或 feature 主线的一部分，难以提炼成高纯 sibling；本轮多选择 `exclude` 或 `watchlist`，避免把机制边界搞糊。

## Watchlist（尚未足够高纯/可复用的候选簇）

以下 case 目前更像“值得继续追”的候选机制，但证据不足以落正式 JSON：

- **schema lease 旋钮稳定化**：`pr-16511`、`pr-54958`
- **schema sync/version 语义 bugfix（`==`/`>=`、hook 顺序等）**：`pr-18205`、`pr-18468`
- **schema validator test 去随机化**：`pr-37447`
- **repair list 清理 vs public state 的可见性 race**：`pr-53688`
- **infoschema v1↔v2 full reload 触发 `ErrInfoSchemaChanged` 的容忍策略**：`pr-54367`
- **多 domain / global index / partition 方向的大 patch**：`pr-46855`、`pr-55831`、`pr-56029`

## 下一步建议

1. **继续扩 union 到 infoschema v2/cache 相关方向**：本轮 union 只并入了 `ddl_without_wait` + `schema_version_race`。如果目标是把 `ErrInfoSchemaChanged`（v1↔v2 full reload / validator reset）这条 singleton 拉成 sibling，建议下一步把 infoschema v2/cache 相关 smell/候选 case 一并纳入，再做 patch-first 全量复读。
2. **继续追 `schema lease` 旋钮稳定化**：当前仍只有 `pr-16511`、`pr-54958` 两个正例；建议扩展到更多 “测试显式调 lease / SetSchemaLease” 的 patch-backed case 后再决定是否落盘。
3. **把“async stats load 的 schema 快照漂移”单独开方向**：union 中出现 `pr-54514`/`pr-55730` 这类“异步统计加载遇到 schema 漂移”的修法（drop missing column/load item）。它不属于本 family 的核心机制，但看起来像能形成独立簇，建议后续单独 union 到 statistics 相关 smell 再 formalize。
4. **避免把 feature 大 patch 强行纳入**：像 global index / partition 的大 patch（多 domain、多状态机、多访问路径）如果目标是“测试稳定性机制”，建议单独开一个更贴近该领域的 family，否则会污染本 family 的边界。

## retrieval 层交付策略

- 本目录已提供：[`给agent的仓库扫描检索信号.md`](./%E7%BB%99agent%E7%9A%84%E4%BB%93%E5%BA%93%E6%89%AB%E6%8F%8F%E6%A3%80%E7%B4%A2%E4%BF%A1%E5%8F%B7.md)（broad draft + patch-proxy 回放）
- 本轮已补：[`retrieval_signals.json`](./retrieval_signals.json)
  - 仅覆盖已稳定落盘的 sibling（`s1`-`s4`），用于 **candidate retrieval**；不覆盖 watchlist 候选（如 `schema lease`/`ErrInfoSchemaChanged`），避免把尚未封板的方向误固化进检索层。
