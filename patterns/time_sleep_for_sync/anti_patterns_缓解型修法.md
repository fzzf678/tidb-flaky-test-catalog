# `time_sleep_for_sync` - anti-pattern（缓解型修法）备忘

本文件不是 subpattern（不进 `subpatterns/*.json`），只用于记录在本 smell 的 `watchlist` 里反复出现、但**不应被当成稳定修法**的缓解型 patch 形态，方便后续复核与迭代。

目标：

- 帮助把 “看起来修了（加大 sleep/timeout）” 与 “真正确定化机制（A/B/C）” 区分开
- 作为后续把 watchlist case 升级到正式 subpattern 的行动清单

注意：

- 这里的条目是“修法 anti-pattern”或“摇摆机制”，不是判定层证据
- 判定层仍以 `subpatterns/*.json` 为准

## AP-1：只把 sleep/timeout/重试次数加大（扩大赌窗）

典型形态：

- `time.Sleep(10ms -> 50ms/100ms/...)`
- `timeout(10s -> 1m)` 或循环次数加倍
- failpoint `sleep(250 -> 1000)` 只做降速

为什么不够：

- 只是扩大 CI 下的“偶发成功窗口”，没有消除不确定性
- 在更慢环境/更拥挤调度下仍会再 flaky

建议升级方向：

- 如果 sleep 在“等异步状态最终可见/最终完成”：升级到 **B**（Eventually/条件轮询，明确 condition + timeout + interval）
- 如果 sleep 在“等 ready/初始化完成/握手屏障”：升级到 **A**（确定性同步原语：WaitGroup/channel/ready-notify/显式 wait-ready API）
- 如果是 stale read / as-of timestamp 的时间语义：升级到 **C**（显式控制 TSO/now：`@@tidb_current_ts`/`tidb_parse_tso`/等待 `current_ts>=expected_ts`/failpoint 固定 now）

## AP-2：通过 sleep 人为制造并发窗口/强行排顺序

典型形态：

- 在一个 goroutine/回调里 `sleep(...)`，希望另一条路径“先跑/后跑”
- 用 sleep “让锁持有一会儿”“让 SQL 先开始跑”“让两连接在某一轮 for-loop 脱离”

为什么不够：

- 这类用例本质是在写并发/时序测试；sleep 让它变成“时钟驱动的随机剧本”
- 越慢/越快的环境都可能打破预期 interleaving

建议升级方向：

- 用显式 barrier（channel/WaitGroup/ready gate）确定开始/阻塞点：通常可归并到 **A** 的一个更具体子方向（“并发编排用 barrier 替代 sleep 窗口”）
- 如果需要“让某个阶段卡住”，优先用 failpoint pause + 显式 release（不要用 failpoint sleep）

## AP-3：删除/跳过/弱化断言来“稳定”

典型形态：

- 直接删掉不稳定的检查逻辑
- `if !cached { return }`、`Skip(...)`、把强断言改成弱断言但没补稳定观察方式

为什么不够：

- 可能掩盖真实 bug；回归时只能“测不出来”
- 对 flaky 识别也没有增量：它既不提供稳定机制，也不提供可复查边界

建议升级方向：

- 若原断言依赖异步状态：补 **B**（Eventually）或拆成多阶段等待
- 若断言依赖时间语义：补 **C**
- 若断言依赖并发 interleaving：补 **A**（barrier）或迁移到并发 race family 做更强的同步建模

## AP-4：无上界的 polling + sleep（或无 timeout 的 Eventually）

典型形态：

- `for { ...; time.Sleep(1s) }` 没有显式 timeout

为什么不够：

- 易引入 hang；CI 上 failure 形态从 flaky 变成“卡死”

建议升级方向：

- 统一加 timeout 上界，并输出 last-observed state（便于诊断）
- 按 B 的标准写（condition + timeout + interval）

