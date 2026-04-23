# readiness wait 扩样与迁移判定（patch-first）

目标：解决未决项 `pr-33610`（MinIO 启动/ready 等待）是否应从 `network_without_retry` 迁到未来 `async_wait_without_backoff` unified direction。

约束：本文所有结论均以 **patch-first 阅读**为主；metadata/rg 仅用于候选召回，不作为证据。

---

## 1) `pr-33610`（patch-first）一句话：共享失稳机制 / 修法机制

`pr-33610` 的共享失稳机制是 **外部服务（MinIO）ready 是异步的，测试脚本用一次性/弱 predicate 的 HTTP 探活容易“过早认为 ready”或在连接失败时误处理**；修法机制是 **把探活改成基于 `curl` 的 HTTP status code 判断，并用有界轮询（`sleep 2s`，最多 30 次）等待 endpoint 达到“可用码”后再继续**。  
Patch URL：https://github.com/pingcap/tidb/pull/33610.patch

> 备注（同样基于 patch-first）：`pr-33610` 的 while 条件写法在 bash 里存在 **operator precedence** 风险，后续 `pr-33666` 专门用 `{ ...; }` 括号修正该条件（见下文样本），这意味着 `pr-33610` 更像“readiness wait 方向的未完成版本”，但机制族仍然清晰。

---

## 2) 从 `async_wait_without_backoff`（45 个）里抽样：与“ready 等待/探活”同族的候选（patch-first 读过）

判定口径（只看 patch）：

- **同族（readiness/probe wait）**：出现“显式 predicate + bounded poll（固定 interval，无 backoff 也可）”，或用显式 barrier/信号消除对 timing 的依赖。
- **非同族**：纯粹拉长 sleep/timeout，或修的是别的问题（但被标了 async_wait smell）。

| case_id / PR | patch_url | 判定 | patch-first 机制摘录（只写最关键的 wait/probe 机制） |
|---|---|---|---|
| `pr-33666` / 33666 | https://github.com/pingcap/tidb/pull/33666.patch | 同族 | `br/tests/br_s3/run.sh`：以 `curl -w '%{http_code}'` 得到 status；`while ! { status>0 && status<500; }` + `sleep 2` + bounded 重试（30 次）等待 MinIO endpoint ready。 |
| `pr-29499` / 29499 | https://github.com/pingcap/tidb/pull/29499.patch | 同族 | `waitGCDeleteRangeDone`：轮询 `mysql.gc_delete_range_done`（predicate：count != 0）+ `time.Sleep(interval)` + bounded rounds；等 GC delete-range 异步完成再断言数据清理。 |
| `pr-29900` / 29900 | https://github.com/pingcap/tidb/pull/29900.patch | 同族 | for 循环重试 etcd `Get`（predicate：`len(resp.Kvs) != 0`）+ `Sleep(100ms)` + 20 次上限；显式承认 “writing to etcd is async”。 |
| `pr-43273` / 43273 | https://github.com/pingcap/tidb/pull/43273.patch | 同族 | `require.Eventually` 等待 goroutine 退出（predicate：`!checkGoroutineExists(...)`），`timeout=5s`，`interval=100µs`。 |
| `pr-44168` / 44168 | https://github.com/pingcap/tidb/pull/44168.patch | 同族 | `require.Eventually` 等待 `StmtCtx.ReadFromTableCache` 变为 true；用 bounded polling 代替短循环一次性断言。 |
| `pr-50824` / 50824 | https://github.com/pingcap/tidb/pull/50824.patch | 同族 | `require.Eventually` 反复查询 `information_schema`，predicate：结果等于期望 rows（包含 `last_access_time is not null`）；`timeout=5s`，`interval=100ms`。 |
| `pr-58164` / 58164 | https://github.com/pingcap/tidb/pull/58164.patch | 同族 | `require.Eventually` 等待 stats sync-load 完成（predicate：`statsTbl.ColNum()` 达到期望值）；`timeout=5s`，`interval=100ms`。 |
| `pr-65114` / 65114 | https://github.com/pingcap/tidb/pull/65114.patch | 同族 | `require.Eventually` 重试“触发 retry 行为”的并发压测，predicate：`len(testResults) > concurrency`；避免 one-shot 偶发“没触发到 retry”导致 flaky。 |
| `pr-29477` / 29477 | https://github.com/pingcap/tidb/pull/29477.patch | 同族（弱） | 通过重复执行查询/`HasPlan` 等方式等待 cache 状态生效（bounded loop，无 sleep）；predicate：`StmtCtx.CacheTableUsed()` 或 `HasPlan(..., \"UnionScan\")` 为真。 |
| `pr-64942` / 64942 | https://github.com/pingcap/tidb/pull/64942.patch | 同族（barrier） | 不做 sleep/poll，而是显式 `admin reload bindings`，把“异步加载绑定”变成同步 barrier 后再断言。 |
| `pr-15119` / 15119 | https://github.com/pingcap/tidb/pull/15119.patch | 同族（边界） | 仍是 bounded polling + sleep（`mustGetDDLBinlog` 循环 + `time.Sleep`），但同时清理共享 payload（减少跨用例干扰）；属于“wait predicate 存在，但主要靠轮询+sleep”的早期形态。 |
| `pr-15065` / 15065 | https://github.com/pingcap/tidb/pull/15065.patch | 非同族 | 仅把轮询里的 `Sleep(10ms)` 改成 `Sleep(30ms)`；没有补充 predicate、没有 barrier、也没有更强的 bounded 语义（典型“靠拉长 sleep”）。 |

---

## 3) 机制簇是否成型：能否作为未来 `async_wait_without_backoff` 的 subpattern 种子？

结论：**簇是成型的**，而且和 “external service readiness wait” 高度同构。

patch-first 观察到的“稳定机制簇”主要有两类（两者都比纯 sleep 更稳）：

1) **显式 predicate + bounded polling（固定间隔，通常无 backoff）**
   - 典型形态：`require.Eventually(timeout, interval, predicate)` 或自写 for-loop + `Sleep(interval)` + 上限次数。
   - 关键不是“睡多久”，而是 **predicate 明确且可被反复验证**（HTTP code、etcd kv 可见性、goroutine 消失、stats 条目出现/数量到位、表缓存状态位变真等）。
   - 与 `pr-33666`/`pr-33610` 的 MinIO HTTP 探活完全同构：都是“服务/状态最终会变 ready，需要 bounded poll 等它到位”。

2) **显式 barrier/信号化，消除对 timing 的依赖**
   - 代表：`pr-64942` 通过 `admin reload bindings` 强制同步；不靠 sleep/poll。
   - 在“ready 等待/探活”语境下，对应的是：能否把“ready 事件”变成可等待的信号（文件、channel、hook、明确的 API）而不是盲等。

反例簇（不建议作为 seed）：

- **纯 sleep/timeout 调参**（如 `pr-15065`）：不引入更强 predicate，也不引入同步点，通常只能“缓解而非根治”。

因此：未来若要把 `async_wait_without_backoff` 进一步 unified/family 化，这个簇完全可以作为 subpattern 种子，例如：

- `readiness_wait_with_explicit_predicate_and_bounded_poll`（包含 HTTP/etcd/状态位/日志事件等）
- `replace_timing_wait_with_barrier_or_signal`（将 async 变 sync）

（这里只给建议，不新建目录。）

---

## 4) 对 `pr-33610` 的迁移建议：retain 在 network vs migrate 到 async_wait？

建议：**migrate 到未来的 `async_wait_without_backoff` unified direction**（并在 network family 侧保留“相邻但不归类”的引用即可）。

理由（全部可由 patch 直接观察到）：

1) `pr-33610`/`pr-33666` 的核心是 **“启动后等待 ready”**：脚本先启动 MinIO，再用 HTTP 探活去等 endpoint ready —— 这是典型的 *readiness wait*，本质上是 async state convergence，而不是“网络请求失败时没有 retry”。
2) 修法是 **bounded polling（固定 interval，无 backoff）+ 更明确的 predicate（HTTP status code 范围）**，其形态与上述 async_wait 样本中大量 `Eventually`/poll loop 完全一致。
3) 从 family 边界看：`network_without_retry` 更像“对外部服务发请求遇到 transient error 时缺 retry/backoff/fallback”；而 `pr-33610` 是“服务尚未 ready，不该发后续测试流程”，语义更接近 `async_wait_without_backoff`。

补充对照（用于理解 br_s3/run.sh 的演进，不计入 async_wait 45 的样本）：`pr-47156` 也改了 `br/tests/br_s3/run.sh`，核心是把固定 `sleep`/粗暴 kill 时序改为“failpoint 触发信号文件 -> `wait_sig` 再做 kill/重启”，进一步印证 br_s3 这类问题更像 **等待机制/同步机制**，而非 network family 的典型“请求重试策略”。  
Patch URL：https://github.com/pingcap/tidb/pull/47156.patch

