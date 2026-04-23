# `time_sleep_for_sync` - watchlist 机制簇工作板（patch-first）

本文件只处理 `watchlist`（当前 `34` 条），目标是把它们按 **共享失稳机制 / 共享修法机制** 收敛成可继续迭代的簇，并明确每簇下一步如何升级为已 formalize 的 A/B/C，或迁移到其他 family。

注意：

- 本文件不是 `subpatterns/*.json`，不作为 verdict 规则。
- 这里的簇主要是“未完成的修法”或“混合/缓解型修法”；正式 subpattern 仍以 `subpatterns/*.json` 为准。
- `watchlist` 本身允许低纯：我们优先给出“升级路径”而不是强行 formalize。

关联文件：

- 全量台账：`逐例梳理台账.tsv`（`final_disposition=watchlist`）
- 缓解型 anti-pattern 备忘：`anti_patterns_缓解型修法.md`

## watchlist 总览

- watchlist：`34` 条
- 主要进入 watchlist 的原因（在 patch 文本可复现）：
  1. **只扩大赌窗**：加长 sleep / timeout / 重试次数（缓解型修法）
  2. **用 sleep 编排并发剧本**：为了“让另一方先跑/先阻塞/先完成”
  3. **时间语义靠 sleep 赌**：stale read / as-of timestamp / create_time/update_time 的粒度问题
  4. **删断言/跳过测试**：通过弱化验证来“稳定”
  5. **patch 太混杂**：无法提炼高纯机制

下面按机制簇列出。

---

## W-A：用 sleep 编排并发/时序剧本（缺少确定性 barrier）

**共享失稳机制**

- `time.Sleep(...)` 被用来“制造并发窗口/排顺序”：让某 goroutine 先开始/先阻塞/先 break out loop，或者让锁持有一会儿。
- 失稳本质不是“机器慢”，而是 **没有确定性同步点**；调度不同会改变 interleaving。

**共享修法机制（当前仍未完成）**

- patch 仍保留 sleep（甚至把 `runtime.Gosched()` 换成 sleep），只是让剧本“更可能发生”。

**典型 case_ids**

- `pr-15094`：sleep 让锁持有一会儿，赌另一事务进入等待路径
- `pr-16610`：在 oneflight 的 loadFunc 里 sleep 拉长重叠窗口
- `pr-18227`：sleep 确保 connection 在 hook 的 for-loop 里走到某阶段
- `pr-21733`：sleep 让 tk2 先执行，用 channel 值判断是否被阻塞
- `pr-32949`：引入 WaitGroupWrapper 收口 goroutine，但仍用 sleep 等“阻塞窗口”
- `pr-38198`：sleep 确保 SQL 已 running，再并发分配内存触发 OOM action
- `pr-44709`：sleep 等 watcher “准备好”再 Notify（属于 ready-barrier 缺失）
- `pr-36583`：failpoint `mockBackfillSlow` 仅加长 sleep，确保 cancel 更容易撞上
- `pr-59100`：把 `runtime.Gosched()` 换成 sleep，试图固定 worker pool 的事件顺序

注：其中 `pr-18227` / `pr-44709` / `pr-38198` / `pr-16610` / `pr-59100` 已被加入 subpattern A 的 `examples.boundary`，用于压实“机制像 A，但修法仍是时间窗/调度赌”的 sibling 边界。

**为什么暂不 formalize**

- 这些 patch 的共同点是“仍然依赖 sleep 作为 barrier”，属于 `anti_patterns_缓解型修法.md` 的 AP-2/AP-1。
- 如果 formalize，会把“错误修法”误当成稳定机制，污染 A 的边界。

**下一步升级路径**

- 统一升级到 **A（确定性同步原语）**：把 sleep barrier 换成显式握手。
  - 用 channel/WaitGroup 确保“某阶段已到达”再继续（例如在 tk2 开始执行前先发 `started` 信号；或在关键点用 failpoint pause+release）。
  - 对“确保 SQL 已 running”类用例，优先用可观测条件（例如 hook/trace/ProcessInfo 或 failpoint）而不是 sleep。
- 如果目标是等待某个后台状态最终可见（不是并发编排），则应转到 W-B（Eventually/条件轮询）。

---

## W-B：异步状态传播/最终可见的等待，只做了扩大 sleep/timeout（B-but-mitigation）

**共享失稳机制**

- sleep 或“固定次数+sleep”的循环在等待异步状态：binlog 写入、cache admission、重连 epoch、DDL job 入表、finalizer 回调、tiflash replica progress 等。
- 不确定性来自异步路径时延：CI 抖动/GC/IO/调度/网络都会打穿固定窗口或导致无界等待。

**共享修法机制（当前仍未完成）**

- 把 sleep 拉长、把循环次数/timeout 加大，或写了 polling 但缺少清晰的 timeout 上界与 last-observed 输出。

**典型 case_ids**

- `pr-13381`：等待 syncer start（调整 timeout + for-loop + sleep；仍依赖时间窗）
- `pr-13824`：ristretto `Set` 异步可见，sleep 从 10ms 拉到 50ms
- `pr-15065` / `pr-15119`：binlog 轮询把 sleep/次数调大
- `pr-19815`：等待 history DDL job（poll+sleep，属于“写法像 Eventually，但仍是手搓窗口”）
- `pr-23243`：等待 batchClient reconnection epoch（sleep 轮询，但缺少显式超时门槛）
- `pr-38906`：sleep 2s 认为 DDL job 已入表
- `pr-41322`：waitForSend 只把 sleep(10ms) 拉到 50ms
- `pr-42138`：finalizer 测试在 `runtime.GC()` 后 sleep 10ms 等回调
- `pr-46301`：等待 TiFlash replica ready 的无限循环 + sleep(1s)，脚本侧再 sleep(3s) 等 tick
- `pr-53225`：failpoint `sleep(250->1000)` 降速（本质也是扩大窗口）

注：其中 `pr-23243` / `pr-46301` / `pr-42138` / `pr-53225` 已被加入 subpattern B 的 `examples.boundary`（以及更严格的 `negative_guards`），用于压实“B-like 但仍靠窗口/缺 timeout 上界”的边界。

**为什么暂不 formalize**

- 这些 case 的“真实机制”其实已经被 B 覆盖，但 patch 自身只做到 mitigation：还没把等待表达成 **明确 condition + timeout + interval** 的 Eventually/轮询。
- 少量 case（如 `pr-46301`）存在无界循环风险；如果把它们直接当正例，会把“可能 hang”引入标准修法。

**下一步升级路径**

- 升级到 **B（Eventually/条件轮询）** 的最低标准：
  - condition：能复查的可观测状态（query/flag/epoch/progress/job state）
  - timeout：明确上界（避免 hang）
  - interval：可控（避免 busy loop）
  - last-observed：失败时输出最后观测值（便于诊断）
- 对第三方库（如 ristretto）优先用库提供的同步原语（例如 `cache.Wait()`）或轮询 `Get`（有上界），不要靠固定 sleep。

---

## W-C：时间语义（TSO/now/时间戳粒度）靠 sleep 赌“时间已推进”

**共享失稳机制**

- sleep 的目的不是等异步任务完成，而是让 **时间/TSO/系统表时间字段**发生可观察变化：
  - stale read / `AS OF TIMESTAMP` 需要保证 read ts 与 write/DDL ts 有严格先后关系
  - create_time/update_time 等字段粒度较粗，连续操作可能落在同一秒
  - 真实集群（realtikvtest）里 wall clock 与 TSO 的关联更复杂，固定 sleep 更脆

**共享修法机制（当前仍未完成）**

- 加长 sleep、加 buffer（例如 1s→3s），或在关键点前插入短 sleep(10ms/100ms) 来规避“同粒度”。
- 少量 patch 引入了 TSO 读取，但仍保留固定 sleep 来拉开窗口。

**典型 case_ids**

- `pr-33093`：as-of timestamp 场景插入 sleep(100ms) 拉开 now 与 DDL
- `pr-33351`：plan cache stale read 用例围绕 now()/sleep 调整窗口
- `pr-40291`：flashback 测试在取 TSO 前 sleep(10ms) 拉开时间戳
- `pr-41643`：binding 重复 create/cover 的 create_time/update_time 粒度问题，用 sleep(10ms) 避免同一秒
- `pr-55588`：realtikv flashback + add unique index 测试含多段 sleep(1s)（注释 Fixme）
- `pr-63196`：realtikv stale read 组合测试把 sleep(1s) 拉长到 3s + buffer
- `pr-30716`：通过加长 sleep 来让 tracing span 耗时更大，以匹配正则断言（本质也是时间语义/粒度赌窗）

注：其中 `pr-33093` / `pr-33351` / `pr-63196`（窗口缓解）以及 `pr-40291` / `pr-41643` / `pr-30716`（机制外溢）已被加入 subpattern C 的 `examples.boundary` 与 `negative_guards`，用于压实“C 只覆盖 stale read/snapshot 的 TSO/时间语义确定化”的 sibling 边界。

**为什么暂不 formalize**

- C 的正式子模式要求“显式控制 TSO/now”，而这些 patch 多数仍在扩大 sleep 窗口（缓解型）。
- `create_time/update_time` 这类“墙钟字段粒度”与 stale read 的 TSO 语义相邻但不完全相同；需要更多正例后再决定是否拆出 C 的 sibling（或迁移到另一 family）。

**下一步升级路径**

- stale read / as-of timestamp：优先升级到 **C（显式控制 TSO/now）**
  - 用 `@@tidb_current_ts`/`tidb_parse_tso`/`oracle.GetTimeFromTS` 等把“先后关系”变成可验证条件
  - 必要时等待 `current_ts >= expected_ts`（有 timeout），而不是固定 sleep
- 系统表时间字段（create_time/update_time/duration）：优先把断言从“严格单调时间”降级到更稳定的属性（ID/计数/内容），或引入可控时间源（若基础设施支持）

---

## W-D：删断言/跳过/弱化验证来“稳定”（验证层退化）

**共享修法机制**

- 通过删除检查、提前 return、移除 failpoint/sleep 触发条件、或只留下不校验的调用，来消除 flakiness。

**典型 case_ids**

- `pr-26840`：删掉动态 timestamp stale select 的关键断言
- `pr-38106`：删除“等待 timeout task 被处理完并断言结果”的逻辑
- `pr-38822`：cached=false 直接 return，跳过后续验证
- `pr-42364`：移除并发/时间比较与最后断言，仅保留串行 DDL（仍留 sleep）
- `pr-42392`：移除 failpoint delay 与断言（曾一度直接删测试，后又恢复但不再检查）

**为什么暂不 formalize**

- 这类 patch 不是“共享失稳机制”的稳定修法，而是把验证退化成“不会失败”。
- 正式化会误导后续识别与修复方向（会鼓励更多 Skip/删除断言）。

**下一步建议**

- 对应机制应回到 A/B/C 的正确修法路径（补上确定性同步/Eventually/TSO 控制），再恢复必要断言。
- 如果某断言本身不合理（过于精确/依赖时间粒度），应明确写成“断言层 anti-pattern”并迁移到更合适的 family（例如 brittle assertion / time-based assertion 方向）。

---

## W-E：patch 过于混杂/难以提炼高纯机制（需要拆分后再判断）

**典型 case_ids**

- `pr-41096`：超大 patch 混入多个 sleep/Eventually/backoff/测试改动，单看 diff 难以归到单一共享机制簇
- `pr-49805`：分布式任务框架重构 + owner change 场景；sleep 用途混合（随机化/等待），难以直接映射到 A/B/C 的单一机制

**下一步建议**

- 需要把 patch 拆成“与 sleep 同步相关的最小子 diff”再复核：
  - 如果主轴是等待异步状态收敛：归到 B
  - 如果主轴是并发编排：归到 A
  - 如果主轴是时间语义：归到 C
- 若拆分后发现主轴已明显属于其他 family（例如 race_condition_in_async_code 的共享对象竞态），应考虑迁移（需要重新修改台账与 README 计数）。
