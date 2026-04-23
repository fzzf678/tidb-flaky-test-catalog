# `time_sleep_for_sync`

这个目录承接 `review_smells.json` 里的 smell：`time_sleep_for_sync`，并把 “补丁里出现了 `time.Sleep`” 这种**症状级标签**，反向拆成更可复查的、机制一致的子簇（subpatterns）。

核心原则：

- 必须 `patch-first` 全量人工复读 source set（不靠既有字段/脚本/regex 先筛）
- 聚类依据只能是：
  - **共享失稳机制**（sleep 在同步什么、为什么会不稳）
  - 或 **共享修法机制**（最终如何去掉/替代这类 sleep）
- `time.Sleep` 本身不是机制；机制是它在承担的“同步角色”

## Source set

- source smell：`time_sleep_for_sync`
- source case set：`cases/**/pr-*.json` 中挂了该 smell 的全量 case
- source case 总数：`85`
- 已人工阅读总数：`85 / 85`（全量覆盖）

## 全量处置结果（必须每条有去向）

| disposition | count | 说明 |
|---|---:|---|
| `retain` | `37` | 能落到稳定高纯的共享机制簇（已 formalize） |
| `exclude` | `13` | `time.Sleep` 出现在产品语义 / backoff / 节流等场景，不属于“测试用 sleep 同步异步路径”的失稳机制 |
| `migrate` | `1` | patch-first 更像其他 family/subpattern，已明确迁移目标 |
| `watchlist` | `34` | 仅做缓解（加长 sleep/timeout/重试次数）、patch 过于混杂、或 singleton/边界摇摆，暂不 formalize |

全量逐例台账见：`逐例梳理台账.tsv`。

### migrate 去向

- `pr-27235` →
  - `patterns/test_isolation_and_state_pollution/subpatterns/test_注入的_hook_filter_matcher_必须缩作用域并在_cancel_切阶段时解绑`

## 当前已形成的稳定 subpatterns（已落盘 JSON）

这轮只把**稳定高纯**的簇落成正式 JSON（避免把 watchlist 的摇摆想法写死）。

1. `固定 sleep 当同步屏障必须改成确定性同步原语`（`13`）
2. `sleep 等异步状态传播必须改成 Eventually/条件轮询`（`21`）
3. `stale read / as-of timestamp 测试必须显式控制 TSO/now，而不是短 sleep`（`3`）

对应文件均在 `subpatterns/` 下。

## 关键边界关系（A/B/C 怎么分）

### A vs B：同步屏障 vs 异步收敛

- **A（确定性同步原语）**：sleep 被当成“屏障/握手”，用来赌 goroutine 已启动、初始化已完成、某个 ready 事件已发生。稳定修法是引入**确定性同步**（channel/WaitGroup/ready-notify/failpoint pause+显式 release 等）。
- **B（Eventually/条件轮询）**：sleep 被当成“等待异步状态传播/可见性”的固定窗口。稳定修法是把断言改成 `Eventually`/轮询条件（带 timeout + interval），把 “偶发慢” 从 “真失败” 里分离出来。

经验法则：如果你能让被等待的一方**显式发信号**，优先 A；否则只能 B（但必须有明确的 condition 与 timeout）。

补充：有一批 `watchlist`（见 `watchlist_机制簇工作板.md` 的 W-A）机制上“很像 A”，因为它们用 sleep 编排 interleaving / 制造并发窗口（让对端更可能进入阻塞、完成订阅、SQL 开始 running）。但这些 patch 的修法仍然依赖时间窗，而不是引入确定性门禁，因此**不能算 A 的 retained 正例**，应继续留在 watchlist（代表：pr-18227/pr-44709/pr-38198/pr-16610/pr-59100）。

### C vs B：TSO/时间语义是专门分支

- **C** 是 stale read / as-of timestamp 相关测试的专门分支：sleep 的目的不是等“某个异步任务完成”，而是希望 **TSO/now** 往前走，从而让 snapshot / timestamp 语义成立。
- 稳定修法必须显式控制时间来源或 TSO 条件（例如 `@@tidb_current_ts`、`tidb_parse_tso`、failpoint 注入 `NOW()`、等待 `current_ts >= expected_ts`），而不是靠 “sleep 几毫秒” 赌时钟粒度与调度。
  - 注意：出现 `GetTimestamp/@@tidb_current_ts` 不等于 C；flashback/DDL/cluster 的 TSO 落点选择属于其他机制，不应并入 C（代表：pr-40291）。

### exclude 与 watchlist 的基本边界

- **exclude**：patch 主轴是产品语义（例如 SQL `SLEEP()` 可被 KILL 中断）、或生产代码 backoff/节流（sleep 是业务逻辑的一部分），不是“测试用 sleep 同步导致 flaky”。
- **watchlist**：主要是 mitigation-only（加长 sleep/timeout/重试次数、Skip）、或 patch 太混杂导致低纯度；这些先不 formalize，避免污染 subpattern 边界。

## 未决问题 / 下一步建议

1. 已把缓解型修法（加长 sleep/timeout/重试次数、删断言/跳过）单独记录为 anti-pattern：`anti_patterns_缓解型修法.md`。
2. 已把 `watchlist` 的 `34` 条按共享机制收敛成可迭代簇，并给出升级到 A/B/C 的路径：`watchlist_机制簇工作板.md`。
3. 已对 `retrieval_signals.json`（`v1`）在真实 TiDB 仓库做炸量/噪声校准并落盘：`retrieval_真实仓库校准记录.md`；当前 retrieval 仍只服务 candidate retrieval，不做 verdict。
4. 下一步最有价值的增量工作是：从 `W-A/W-B/W-C` 三个 watchlist 主簇各挑 2-3 个代表用例，做“真正升级修法”（barrier/Eventually/TSO 控制），把它们从 watchlist 迁回 retained，并沉淀更强的 sibling 边界。
