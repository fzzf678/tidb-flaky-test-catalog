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
  - 当前 `17` 个正式 subpattern JSON 统一放在这里
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
- `WaitGroup Add Done 顺序竞态`
- `并发 callback 共享结果 slice append reset snapshot 未统一加锁`
- `懒初始化映射或指针需要一次性发布`
- `共享摘要收集器 Reset Update 交错竞态`
- `region job refcount 保护的共享 ingest data 生命周期`
- `有状态 mock encoder 被多个 processor 误复用`
- `DDL callback 目标 job 过滤与单次触发控制`

当前草案里列出的稳定候选已经全部落成正式 JSON。下一步如果继续扩展，需要回到 `502` case 台账里继续挖新的高纯度细簇。

另外，17 个正式 subpattern 的完整 case inventory 现在已经直接并回了 `第二轮聚类草案.md`：

- `subpatterns/` 里的正式 JSON `examples.positive`
  - 仍然保留为高纯度锚点子集
- `第二轮聚类草案.md` 里的“17 个正式 subpattern 的当前案例清单”
  - 则负责记录当前 17 个正式 subpattern 在 `逐例梳理台账.tsv` 中已经能明确落下来的完整 case inventory

## 第二轮收敛时的边界约束

- 不要把 `cancel / close / teardown` 生命周期问题强行并入“共享运行时状态”主簇
- 不要把纯 timing / failpoint / Eventually / sleep 窗口问题强行并入主簇
- 不要把 state-machine / owner-transfer / stale-state 问题强行并入主簇
- 不要把 exact-order / exact-count brittle 断言问题误当成 async shared-state race
- 只有在**共享对象、异步路径、缺失同步、稳定修复手法**都高度一致时，才收敛成一个正式 subpattern
