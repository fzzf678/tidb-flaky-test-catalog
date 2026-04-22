# `async_wait_without_backoff`

本目录是对 `review_smells.json` 里的 smell **Async wait without backoff/retry**（key：`async_wait_without_backoff`）做“patch-first 全量复读 → 机制聚类 → 只落稳定高纯 subpattern”的落盘产物。

> 重要：这里的产物目标不是“提高表面命中量”，而是把 **真正共享失稳机制 / 共享修法机制** 的簇梳理清楚，支撑后续更准确的识别与复核。

## Source set

- source smell：`async_wait_without_backoff`
- source case set：当前 catalog 中 `review_smells` 含该 key 的 **全量 case**
- source case 总数：`45`
- 已人工 patch-first 复读：`45 / 45`

## 本轮人工复读结论（逐例台账口径）

- `retain`：`12`
- `exclude`：`0`
- `migrate`：`14`
- `watchlist`：`19`

说明：

- `45` 只是输入全集，不等于该 family 的“纯库存”。
- 本轮的 `migrate` 主要流向：
  - `plan_stability_and_stats_dependency`（stats/cache/binding/plan-cache 侧的 “cache/stats readiness” 机制簇）
  - `time_sleep_for_sync`（纯 sleep/等待窗口加长的缓解型修法）
  - `randomized_test_input`（随机模拟导致概率失败）
  - `race_condition_in_async_code`（测试缺少同步屏障导致的并发时序竞态）

## Family 边界（scope v1）

这个 family 的目的不是把所有“等异步”的 patch 都收编，而是聚焦在下面两类 **可复查、可复用** 的机制：

1. **等待语义不完整**：等待/轮询/Eventually 依赖调度运气（缺 completion condition / 缺可观测信号），导致 timeout/偶发失败。
2. **等待实现本身不稳**：等待循环不可取消（ctx/killed 不贯穿）、或等待条件存在 TOCTOU（baseline capture → missed-event），导致 hang/永远等不到。

典型的“稳定修法机制”是：引入更硬的 completion signal（系统表/状态机/显式屏障）、bounded retry/Eventually、failpoint/显式触发去掉“碰运气”、或把等待做成可中断（ctx/killed/WithTimeout）。

显式排除/迁移（避免跨 family 重复 formalize）：

- stats/cache/binding/plan-cache 的 **readiness/可见性** → `patterns/plan_stability_and_stats_dependency/`
- 只调大 `time.Sleep`/等待窗口（无更硬信号）→ `time_sleep_for_sync`（当前仍在 `patterns/其他_smell_细化_backlog.md` 的 P3 方向里）
- 并发时序竞态/缺同步原语（barrier/锁/WaitGroup 的典型 race）→ `patterns/race_condition_in_async_code/`
- 随机输入/随机模拟导致概率失败 → `randomized_test_input`（同样属于 backlog 方向）
- “baseline/delta 只是为了规避共享表 pre-existing rows” 的 shared-state 污染 → 更像 `patterns/test_isolation_and_state_pollution/`

## 已正式落盘的 subpatterns

本轮只把 **边界清楚、可复用、且有多条 patch-backed 正例支撑** 的机制簇落成 `subpatterns/*.json`：

1. `disttask cleanup 完成前不要做清理断言（等 task 消失 / 双 cleanup 信号）`
2. `DDL delete-range 清理由异步 GC 驱动：用 mysql.gc_delete_range(_done) 取代扫 KV/盲等`
3. `GC/MemoryLimit 触发型等待：Eventually 谓词内主动 runtime.GC()（并等待 tuner 退出）`
4. `验证 retry 的测试不要“碰运气”：用 failpoint 强制触发，或 Eventually 重试直到触发`
5. `等待/重试循环必须可中断：检查 ctx/killed，并用 WithTimeout/ExecWithContext 接上取消链路`

各 subpattern 的正例与边界样本，见对应 JSON 的 `examples` 字段；全量 case 去向见 `逐例梳理台账.tsv`。

## 候选簇（watchlist，不落 JSON）

watchlist 中目前已经完成跨 case 对齐、但仍不满足“在本 smell source set 内稳定成簇”要求的候选方向有：

- **候选簇 A**：delta-based wait 的 baseline capture（TOCTOU / missed-event）
- **候选簇 B**：async publish 的 read-after-write 可见性滞后（visibility lag）
- **候选簇 C**：`require.Eventually` 的 poisoned retries（EventuallyWithT）
- **候选簇 D**：外部服务 readiness 探测（MinIO/S3）
- **候选簇 E**：异步 goroutine/worker completion barrier（join）

这些方向的“机制边界 + patch-backed 样本 + coarse retrieval 草案”集中在：`watchlist_候选_subpattern_草案.md`（明确不落 JSON）。

## 关键边界（与相邻 family 的关系）

### 1) 与 `plan_stability_and_stats_dependency`

如果 patch 的主机制是：

- stats/cache/binding/plan-cache 的 **readiness/可见性**（例如 `LoadNeededHistograms()`、`TableStatsFromStorage`、`ReadFromTableCache`、plan cache view、binding 生效时序）

则优先迁移到：

- `patterns/plan_stability_and_stats_dependency/`

避免把 “plan/stats/cache readiness” 机制簇在两个 family 里重复 formalize。

### 2) 与 `time_sleep_for_sync`

如果 patch 主修法只是：

- 调大 `time.Sleep` / 轮询次数 / 等待窗口（没有引入更硬的 completion barrier，也没有把等待条件改成可复核的状态机信号）

则更像：

- `time_sleep_for_sync`

本轮已把 `binlog` 相关的两条 sleep-tuning case 迁移出去。

### 3) 与 `race_condition_in_async_code`

如果 patch 主机制是：

- 用 channel / WaitGroup / barrier 修复“测试线程与异步 callback/goroutine 的时序竞态”

且失稳本质是并发时序（而不是“等待策略缺 backoff/缺 completion condition”），则迁移到：

- `patterns/race_condition_in_async_code/`

### 4) 与 `randomized_test_input`

如果 patch 直接在修：

- 随机模拟 / 随机输入导致的概率失败（如 `rand()%256` 可能为 0）

则迁移到：

- `randomized_test_input`

## 未决问题 / 下一步建议

1. `watchlist` 里仍有不少 **高价值但暂时不成簇** 的机制（如：TopSQL mock server 等待基线捕获、etcd/global-config 异步写入可见性、外部服务 readiness 探测、conn event logs 等）。后续如果补到更多同型 patch，再考虑升格为正式 JSON。
   - watchlist 里目前已做跨 case 对齐的草案方向包括：TopSQL baseline / etcd sync / `EventuallyWithT`（poisoned retries）/ 外部服务 readiness / goroutine 退出验证，见 `watchlist_候选_subpattern_草案.md`（仍不落 JSON）。
2. 已补齐结构化检索层产物 `retrieval_signals.json`（v1）：
   - 只覆盖已正式落盘的 5 条稳定 subpattern（不包含 watchlist 候选簇 A/B/C/D/E）。
   - `给agent的仓库扫描检索信号.md` 继续作为人读版的设计说明与 patch-proxy 回放记录。
3. 建议下一轮优先做两件事：
   - 对 `disttask cleanup` 与 `DDL gc_delete_range` 这两条机制，在真实 TiDB 仓库做一次 scan 校准（炸量/误报）。
   - 对 “Eventually 使用方式” 的 singleton（如 `EventuallyWithT` 防 poisoned retries）继续观察是否能在更多 case 里复现后再 formalize（草案对齐也在 `watchlist_候选_subpattern_草案.md`）。
