# `race_condition_in_async_code`

这个目录目前处于“首轮 502 case 逐例梳理已完成，第二轮正式 subpattern 已开始落盘”的状态。

## 当前结论

- 之前那两个 seed subpattern 已删除
- 原因是它们的力度仍然太大，而且在没有把 `review_smells.json` 中 `race_condition_in_async_code` 的全部 `502` 个 case 逐个过完之前，不应先固定 subpattern 结构
- 从现在开始，这个 family 的 subpattern 必须从 **502 个 case 的逐例梳理** 中重新归纳出来
- 目前这一步已经完成：`逐例梳理台账.tsv` 的 `502 / 502` case 都已完成首轮 review
- 下一步不是再补台账，而是基于台账里反复出现的**具体代码机制**收敛中文细粒度 subpattern

## 拆分原则

- 先逐个 review case，再归纳 subpattern
- subpattern 必须尽可能细，不接受“大而泛”的机制描述
- 只有当多个 case 在 **代码形态、共享对象类型、异步路径类型、缺失同步方式、稳定修复方式** 上高度一致时，才允许合并为同一个 subpattern
- 归纳粒度应接近下面这种层级：
  - `DDL hook callback（OnJobUpdated）写共享变量无锁`
  - `goroutine 闭包捕获循环变量`
  - `concurrent map write`

## 工作方式

1. 先把 `race_condition_in_async_code` 的 `502` 个 case 建成逐例梳理台账
2. 逐条阅读 case / patch，记录最细的可观察代码机制
3. 暂时只沉淀“候选机制”，不急着正式落 subpattern 文件
4. 等全量 case 至少过完一轮，再把稳定、细粒度、可操作的候选机制收敛成正式 subpattern

其中第 1-3 步已完成；当前进入第 4 步。

## 目录说明

- `README.md`
  - 记录当前 family 的拆分约束和方法
- `逐例梳理台账.tsv`
  - `race_condition_in_async_code` 全量 case 的工作台账
- `第二轮聚类草案.md`
  - 第二轮开始后，按“确定性代码信号 + 正例 / 边界 case”整理出来的候选子模式工作板
- `给新agent的标准prompt模板.md`
  - 用于让全新 agent 在某个分支 / worktree 上扫描存量测试，按当前 subpattern 做结构化判断
- `给agent的仓库扫描检索信号.md`
  - 给全仓扫描场景使用的检索层设计，说明每个 subpattern 应如何做 grep 召回和关键词组合
- `retrieval_signals.json`
  - 结构化 sidecar 检索文件，给 agent / 自动化扫描使用；承载全仓扫描时的路径、关键词、组合和降权信号
- `subpatterns/`
  - 当前 `56` 个正式 subpattern JSON 统一放在这里
  - `retrieval_signals.json` 不放进这个目录，避免把检索层和判定层混在一起

## 第一批正式 subpattern

第二轮已经开始把第一批高纯度候选落成正式 JSON。当前已经正式化的第一批子模式有：

- `DDL hook callback 写共享变量或标志无锁`
- `DDL hook callback 复用共享上下文或事务对象`
- `DDL hook callback 复用共享测试会话执行 SQL`
- `goroutine 闭包复用外层错误变量`
- `goroutine 闭包捕获循环变量`
- `BindHandle 单例 sctx 并发复用`
- `BindHandle 共享 parser 并发使用`
- `同一 session 的上一个 RecordSet 未 Close 就执行下一条 SQL`
- `测试改写全局 lease 干扰后台 refresh loader`
- `多个 cop iterator 共享可变 KV request RequestBuilder`
- ``twoPhaseCommit.doActionOnBatches` 并行 batch goroutine 复用父 `Backoffer``
- ``IndexJoin / IndexLookupJoin / IndexLookupMergeJoin` 每个 inner worker 复制自己的 `indexRanges``
- ``IndexJoin / IndexMergeJoin / IndexHashJoin` 每个 inner worker 重建自己的 `TmpConstant``
- ``buildUnionScanForIndexJoin` 直接改写共享 `builder.Plan`` 
- ``executorBuilder.forDataReaderBuilder` 预取隔离 read TS，避免并发复用会话态``
- ``IndexHashJoin.keepOuterOrder` 每处理一个 task 都重新 `getNewJoinResult`，避免复用已发送的 `joinResult` holder``
- `同一个 TestKit/session 被两个 goroutine 或后台路径并发复用`
- `共享 SessionVars/StmtCtx 字段 save-and-restore 临时改写，应改成显式参数传递`
- `异步 resource tag / TopSQL 回调直接读取共享 StmtCtx 的 SQLDigest/planDigest，应先取局部快照`
- ``cursor fetch` 期间不得复用 cached `StatementContext`；后台 coprocessor 仍持有旧 `memtracker``
- ``ProcessInfo/GenLogFields` 不能直接引用共享 `StmtCtx.TableIDs/IndexNames`；应在 `SetProcessInfo` 时复制快照``
- `WaitGroup Add Done 顺序竞态`
- `并发 callback 共享结果 slice append reset snapshot 未统一加锁`
- `懒初始化映射或指针需要一次性发布`
- ``SysVar` 模板对象不能共享可变 `Value`；读取方 deep copy，写入方重新注册新对象``
- `后台 refresh/reload 更新共享 cache 时先 clone 副本再 atomic swap 发布`
- `共享摘要收集器 Reset Update 交错竞态`
- `region job refcount 保护的共享 ingest data 生命周期`
- `有状态 mock encoder 被多个 processor 误复用`
- `DDL callback 目标 job 过滤与单次触发控制`
- `长期存活的 manager/handler 共享 map 被多个并发入口直接读写`
- ``MPPTaskHandler.TunnelSet` 在 `HandleEstablishConn/registerTunnel/getAndActiveTunnel` 之间并发读写``
- ``RunawayManager.DeriveChecker` 访问 `metricsMap` 必须用 `SyncMap.Load/Store```
- `只读 helper/List/IsXxx 访问共享 map 却漏掉读侧锁`
- `cleanup/reuse/reset 路径清空共享 map 时漏锁`
- ``TimerStore.memoryStoreCore` 的 `namespaces/id2Timers/watchers` 必须统一互斥并拆分 notifier``
- `测试/helper 直接 reset 或 replace 共享 cache/handle 指针`
- `解锁后继续使用共享 cache entry / pointer`
- ``stmtSummaryByDigestElement.authUsers` 赋给 `BindableStatement.Users` 前必须 copy-on-read``
- `执行期 helper/pruning 内部的懒建查找 map 被并发查询路径同时读写`
- `TopSQL mock sink/server 的上报结果缓存被后台 worker 与断言线程并发访问`
- `异步 global stats merge 直接共享 partitionStats/statsInfo，缺少 copy-on-read 快照`
- `从共享 stats cache 取 Table 后，在 tableStatsFromStorage 补写字段前漏掉 table.copy`
- `UpdateStatsByLocalFeedback 在共享 Table/Index/Column 上原地回写 Histogram/CMSketch`
- `stats Handle / SessionStatsCollector 在 dump/clear 路径直接重置 live feedback/globalMap/collector state，缺少锁内 snapshot-swap`
- ``SessionStatsCollector.rateMap -> Handle.rateMap -> UpdateErrorRate` 链路直接聚合共享误差率 map，缺少统一互斥`
- ``Handle.pid2tid/schemaVersion` 分区 physicalID 到 tableID 映射缓存被并发读写，缺少统一锁保护`
- ``Handle.statsCache` 整体 snapshot 以 version 做 copy-on-write 发布，缺少串行 store 门禁`
- ``LFU.cache.Set` 触发 `reject/onEvict` 时，`resultKeySet/cost` 更新顺序交错`
- ``stats cache internal LRU/map cache` 共享结构被 `Get/Put/Del/Values/Copy` 路径并发访问，缺少统一 `RWMutex``
- ``GetPartitionStats` miss 后临时构造 `PseudoTable` 却回填共享 `statsCache``
- ``全局 `lease/TTL` 数值旋钮不能裸读写；必须封装 `atomic` getter/setter``
- `全局 bool/seed 配置开关不能裸读写；要么走 atomic accessor，要么降到 session scope`
- `测试更新全局 config 必须 UpdateGlobal/StoreGlobalConfig，并配对 RestoreFunc`
- `全局 config 的嵌套 map（如 Labels）不能原地改写，必须 clone 后再 StoreGlobalConfig`
- `测试不要改 process-global logger；需要串行隔离或带互斥的 log capturer`

当前草案里列出的稳定候选已经全部落成正式 JSON。下一步如果继续扩展，需要回到 `502` case 台账里继续挖新的高纯度细簇。

当前第二轮的继续细化，不再泛泛地“继续找”，而是已经收敛成 6 条优先主线：

- `manager / handle / cache` 级共享 map 并发读写
- 共享 `session / TestKit / StmtCtx / SessionVars / TimeZone` 被并发复用或临时改写
- 共享 `stats / cache / histogram / feedback / collector` 对象被原地补写
- 共享 `request / iterator / backoffer / range / holder` 被多个 worker 误复用
- `copy-on-write / atomic swap / publish-once / lazy init`
- 全局 `config / singleton / feature flag / lease / TTL` 被测试线程与后台路径并发读写

这 6 条都还是 `race_condition_in_async_code` family 内部的继续细化，不是跨 family 的通用 backlog。更细的 seed case 和预期子方向，统一记录在 `第二轮聚类草案.md`。

另外，56 个正式 subpattern 的完整 case inventory 现在已经直接并回了 `第二轮聚类草案.md`：

- `subpatterns/` 里的正式 JSON `examples.positive`
  - 仍然保留为高纯度锚点子集
- `第二轮聚类草案.md` 里的“56 个正式 subpattern 的当前案例清单”
  - 则负责记录当前 56 个正式 subpattern 在 `逐例梳理台账.tsv` 中已经能明确落下来的完整 case inventory

## 第二轮收敛时的边界约束

- 不要把 `cancel / close / teardown` 生命周期问题强行并入“共享运行时状态”主簇
- 不要把纯 timing / failpoint / Eventually / sleep 窗口问题强行并入主簇
- 不要把 state-machine / owner-transfer / stale-state 问题强行并入主簇
- 不要把 exact-order / exact-count brittle 断言问题误当成 async shared-state race
- 只有在**共享对象、异步路径、缺失同步、稳定修复手法**都高度一致时，才收敛成一个正式 subpattern
