# 给 agent 的仓库扫描检索信号

这份文档回答一个很具体的问题：

- 当前这 `51` 个 subpattern，能不能直接给 agent 看？

答案是：

- **能**，但它们现在更适合做“判定层”。
- 如果目标是**覆盖整个仓库**去扫存量测试，仅靠这 `51` 个 JSON 还不够快，也不够像“检索层”。
- 更实用的方式是分成两层：
  - 第一层：**检索层**
    - 用 grep / 路径 / 关键词组合，把全仓里的测试先缩成候选集
  - 第二层：**判定层**
    - 再用现有 JSON 里的 `signals_required / signals_optional / negative_guards / verdict_policy` 做严格判断

也就是说：

- 当前 `51` 个 JSON 不该被废掉
- 但如果要给 agent 做全仓扫描，最好再补一层更硬的“检索信号”
- 现在这层已经有了一个结构化 sidecar 文件：
  - `retrieval_signals.json`

## 这份文档和草案的分工

现在这几个文件的角色已经比较明确：

- `retrieval_signals.json`
  - 当前 agent / 自动化真正执行的结构化检索层
  - 已经落到 `v37`
  - 这里的 `rg_templates` 是当前最权威的可执行入口
- `subpatterns/`
  - 当前 `51` 个正式 subpattern JSON 的集中目录
  - 这部分是 verdict layer，不和 `retrieval_signals.json` 混放
- `第二轮聚类草案.md`
  - 负责维护 `51` 个正式 subpattern 的完整 case inventory
  - 里面已经把更多正例和边界 case 补齐
- 本文档
  - 负责解释“检索层应该怎么用”
  - 当前以扫描流程、字段含义、模板使用方法为主
  - 权威的逐 subpattern 可执行检索信号以 `retrieval_signals.json` 为准
  - 不再重复维护完整 case 列表，避免和草案双份漂移

## 建议新增的“检索层”字段

我建议不要改 `signals_required` 本身，而是额外补一层检索字段，或者单独做 sidecar 文件。

推荐字段：

- `path_globs`
  - 优先搜索的目录 / 文件类型
  - 这是“弱先验 / 搜索优先范围”，不是硬门槛
  - 不同版本可能发生目录重构，所以不能因为没命中 `path_globs` 就直接判断“没有这个 pattern”
- `grep_keywords_any`
  - 命中其中任意一个，就值得进候选池
- `grep_keywords_all_groups`
  - 分组组合；每组至少命中一个，才值得进候选池
- `grep_keywords_exclude`
  - 命中这些时要降权，或暂时排除
- `grepability`
  - `high` / `medium` / `low`
  - 表示这个 subpattern 靠 grep 能不能高质量召回
- `first_pass_query_hint`
  - 给 agent 的第一跳查询提示，不是最终判定
- `rg_templates`
  - 可直接执行的 `rg` 命令模板
  - 目标是让新 agent 不需要自己临场设计 grep 组合，先按模板跑出第一批候选
  - 当前主要使用：
    - `fallback_no_path`
    - `group_intersection`
  - `broad_recall`
    - 仍然保留作兼容模板
    - 但不是默认入口

## 使用方式

让 agent 扫全仓时，不要直接把 `51` 个 JSON 当成 `51` 条逐个硬匹配的规则。

正确顺序应该是：

1. 直接执行 `fallback_no_path`
   - 这是默认入口
   - 如果 scan root 是仓库根，就按**全仓范围**执行
   - 这一步不再把 `path_globs` 当限制条件
2. 如果 `fallback_no_path` 召回结果过大，再执行 `group_intersection` 做粗筛
   - 这一步仍然是检索层
   - 目标是缩小候选，不是做最终判定
3. 对粗筛出来的 candidate，agent 必须**逐个打开代码人工判断**
   - 这一步不能交给脚本自动判定
   - 尤其是 async / goroutine / callback / shared-state 这类模式，必须逐例看代码
   - 这一层允许有一定 false positive，先把可疑候选留下
4. 再把候选文件 / 测试函数交给 `subpatterns/` 里的 JSON 做结构化判定
   - 重点看 `signals_required`
   - 再结合 `signals_optional` 与 `negative_guards`
   - 最后再决定是不是命中该 subpattern
5. 如果还需要补搜，再回退到 `path_globs + grep_keywords_any + grep_keywords_all_groups` 手动拼查询

## 当前落地状态

现在 `retrieval_signals.json` 已经不只是“字段建议”，而是已经落到 `v37`，并覆盖了当前 `51` 个正式 subpattern。

当前默认使用的 `rg_templates` 是：

- `fallback_no_path`
  - 直接做全仓兜底召回
  - 当 scan root 是仓库根时，就是扫整个仓库
  - 不限制 `path_globs`
- `group_intersection`
  - 在 `fallback_no_path` 结果太多时，继续做按组粗筛
- `broad_recall`
  - 仍然保留
  - 但不是默认入口

这一步的目标不是降低误报，而是先让新 agent 在全仓里更稳定地“找得到”。误报控制仍然主要留在 verdict layer，但检索阶段允许先保留一部分 false positive。

另外，`51` 个正式 subpattern 当前更完整的正例 / 边界 case 盘点，已经并回：

- `第二轮聚类草案.md` 里的“51 个正式 subpattern 的当前案例清单”

所以如果要回答“这个 subpattern 目前到底落了哪些 case”，应优先看草案；如果要回答“agent 该怎么检索”，优先看本文和 `retrieval_signals.json`。

## 已正式化 subpattern 的检索信号示例

下面这些信号，都是**检索层**，不是 verdict 层。

说明：

- 当前 `51` 个正式 subpattern 的权威可执行版本，以 `retrieval_signals.json` 为准
- 本文下面保留的是代表性示例，方便人读和理解字段设计
- 真正给 agent 扫仓库时，优先直接读取 `retrieval_signals.json`

### 1. `DDL hook callback 写共享变量或标志无锁`

- `grepability`: `high`
- `path_globs`:
  - `pkg/ddl/**/*_test.go`
  - `tests/realtikvtest/**/*`
- `grep_keywords_any`:
  - `SetHook`
  - `OnJobUpdated`
  - `OnJobRunBefore`
  - `OnJobRunAfter`
  - `checkOK =`
  - `jobID =`
  - `isPaused =`
  - `.hook =`
- `grep_keywords_all_groups`:
  - group A:
    - `SetHook`
    - `OnJobUpdated`
    - `OnJobRunBefore`
    - `OnJobRunAfter`
  - group B:
    - `err =`
    - `checkOK =`
    - `jobID =`
    - `isPaused =`
    - `test =`
  - group C:
    - `go func`
    - `callback`
    - `hook`
- `grep_keywords_exclude`:
  - `atomic.`
  - `sync.Mutex`
  - `CompareAndSwap`
- `first_pass_query_hint`:
  - 先找 “DDL hook 注册点”，如果目录结构变化或 hook 注册词不明显，再补搜 `checkOK/jobID/isPaused/.hook`

### 2. `DDL hook callback 复用共享上下文或事务对象`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/ddl/**/*_test.go`
- `grep_keywords_any`:
  - `SetHook`
  - `OnJobUpdated`
  - `txn`
  - `ctx`
  - `store`
- `grep_keywords_all_groups`:
  - group A:
    - `SetHook`
    - `OnJobUpdated`
  - group B:
    - `ctx`
    - `txn`
    - `store`
  - group C:
    - `MustExec`
    - `Exec`
    - `Txn(`
- `grep_keywords_exclude`:
  - `context.Background()`
  - `context.WithCancel(`
  - `context.WithTimeout(`
- `first_pass_query_hint`:
  - 找 “DDL callback + 复用外层 ctx/txn/store”

### 3. `DDL hook callback 复用共享测试会话执行 SQL`

- `grepability`: `high`
- `path_globs`:
  - `pkg/ddl/**/*_test.go`
- `grep_keywords_any`:
  - `SetHook`
  - `TestKit`
  - `MustExec`
  - `MustQuery`
  - `session`
- `grep_keywords_all_groups`:
  - group A:
    - `SetHook`
    - `OnJobUpdated`
  - group B:
    - `tk.`
    - `testkit`
    - `session`
  - group C:
    - `MustExec`
    - `Exec`
    - `MustQuery`
- `grep_keywords_exclude`:
  - `testkit.NewTestKit(`
  - `create new session`
- `first_pass_query_hint`:
  - 找 “DDL callback + 复用 tk/session 执行 SQL”

### 4. `goroutine 闭包复用外层错误变量`

- `grepability`: `high`
- `path_globs`:
  - `**/*_test.go`
- `grep_keywords_any`:
  - `go func`
  - `err =`
- `grep_keywords_all_groups`:
  - group A:
    - `go func`
  - group B:
    - `err =`
  - group C:
    - `wg`
    - `Wait(`
    - `require`
- `grep_keywords_exclude`:
  - `err :=`
- `first_pass_query_hint`:
  - 找 “go func + err =”

### 5. `goroutine 闭包捕获循环变量`

- `grepability`: `high`
- `path_globs`:
  - `**/*_test.go`
- `grep_keywords_any`:
  - `for `
  - `range `
  - `go func`
  - `t.Run(`
- `grep_keywords_all_groups`:
  - group A:
    - `for `
    - `range `
  - group B:
    - `go func`
    - `t.Run(`
  - group C:
    - `i`
    - `store`
    - `sql`
    - `plan`
    - `tc`
    - `case`
- `grep_keywords_exclude`:
  - `i := i`
  - `tc := tc`
  - `go func(`
    - 仅作为参数传值时应降权，需要 agent 二次看代码窗口
- `first_pass_query_hint`:
  - 找 “循环 + go func/t.Run”

### 6. `BindHandle 单例 sctx 并发复用`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/bindinfo/**/*`
  - `pkg/planner/**/*`
- `grep_keywords_any`:
  - `BindHandle`
  - `sctx`
  - `capture`
  - `Update(`
  - `prepare`
- `grep_keywords_all_groups`:
  - group A:
    - `BindHandle`
  - group B:
    - `sctx`
  - group C:
    - `Update(`
    - `capture`
    - `prepare`
    - `filter`
- `grep_keywords_exclude`:
  - `Lock()`
  - `Unlock()`
  - `NewSession`
- `first_pass_query_hint`:
  - 找 “BindHandle + sctx + 多路径调用”

### 7. `BindHandle 共享 parser 并发使用`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/bindinfo/**/*`
- `grep_keywords_any`:
  - `BindHandle`
  - `parser`
- `grep_keywords_all_groups`:
  - group A:
    - `BindHandle`
  - group B:
    - `parser`
  - group C:
    - `Update(`
    - `capture`
    - `prepare`
    - `Parse`
- `grep_keywords_exclude`:
  - `parser.New()`
  - `new parser`
- `first_pass_query_hint`:
  - 找 “BindHandle + parser 字段复用”

### 8. `同一 session 的上一个 RecordSet 未 Close 就执行下一条 SQL`

- `grepability`: `medium`
- `path_globs`:
  - `**/*_test.go`
- `grep_keywords_any`:
  - `RecordSet`
  - `ExecutePreparedStmt`
  - `Close()`
  - `MustQuery`
  - `MustExec`
- `grep_keywords_all_groups`:
  - group A:
    - `RecordSet`
    - `ExecutePreparedStmt`
  - group B:
    - `MustExec`
    - `Exec`
    - `MustQuery`
  - group C:
    - `session`
    - `tk.`
- `grep_keywords_exclude`:
  - `defer rs.Close()`
  - `rs.Close()`
- `first_pass_query_hint`:
  - 找 “拿到 RecordSet 后继续在同一 session 上执行 SQL”

### 9. `测试改写全局 lease 干扰后台 refresh / loader`

- `grepability`: `high`
- `path_globs`:
  - `pkg/bindinfo/**/*_test.go`
  - `pkg/statistics/**/*_test.go`
  - `pkg/ttl/**/*_test.go`
  - `pkg/domain/**/*_test.go`
- `grep_keywords_any`:
  - `Lease`
  - `schema lease`
  - `stats lease`
  - `CreateMockStoreAndDomain`
  - `BootstrapSession`
- `grep_keywords_all_groups`:
  - group A:
    - `Lease =`
    - `SetLease`
    - `schema lease`
    - `stats lease`
  - group B:
    - `CreateMockStoreAndDomain`
    - `BootstrapSession`
    - `domain`
  - group C:
    - `defer`
    - `Cleanup`
    - `Close`
- `grep_keywords_exclude`:
  - `set before bootstrap`
  - `restore after teardown`
- `first_pass_query_hint`:
  - 找 “lease 改写 + domain/bootstrap + defer restore/clean”

### 10. `多个 cop iterator 共享可变 KV request / RequestBuilder`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/executor/**/*`
  - `pkg/store/**/*`
- `grep_keywords_any`:
  - `RequestBuilder`
  - `kv.Request`
  - `cop iterator`
  - `buildKVReq`
- `grep_keywords_all_groups`:
  - group A:
    - `RequestBuilder`
    - `kv.Request`
  - group B:
    - `iterator`
    - `worker`
  - group C:
    - `build`
    - `send`
    - `cop`
- `grep_keywords_exclude`:
  - `Clone(`
  - `new builder`
  - `build per iterator`
- `first_pass_query_hint`:
  - 找 “RequestBuilder / kv.Request 在 iterator 间复用”

### 11. `WaitGroup Add/Done 顺序竞态`

- `grepability`: `high`
- `path_globs`:
  - `**/*.go`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `WaitGroup`
  - `.Add(`
  - `.Done(`
  - `jobToWorkerCh`
  - `go func`
- `grep_keywords_all_groups`:
  - group A:
    - `.Add(`
  - group B:
    - `.Done(`
  - group C:
    - `jobToWorkerCh <-`
    - `go func`
    - `start worker`
- `grep_keywords_exclude`:
  - `.Add(1)` 紧挨在 `go func` 或 send 之前时要降权
- `first_pass_query_hint`:
  - 找 “send/go func 在 Add 前”

### 12. `并发 callback 共享结果 slice append/reset/snapshot 未统一加锁`

- `grepability`: `medium`
- `path_globs`:
  - `**/*_test.go`
- `grep_keywords_any`:
  - `append(`
  - `reset`
  - `snapshot`
  - `testResults`
  - `callback`
- `grep_keywords_all_groups`:
  - group A:
    - `callback`
    - `hook`
  - group B:
    - `append(`
  - group C:
    - `reset`
    - `snapshot`
    - `copy(`
- `grep_keywords_exclude`:
  - `mu.Lock()`
  - `mu.Unlock()`
- `first_pass_query_hint`:
  - 找 “callback append + 主线程 reset/snapshot 同一 slice”

### 13. `懒初始化映射或指针需要一次性发布`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/**/*`
  - `pkg/**/*_test.go`
- `grep_keywords_any`:
  - `atomic.Pointer`
  - `CompareAndSwap`
  - `sync.Once`
  - `sync.Map`
  - `usedStatsInfo`
  - `mergedInputIdxToOutputIdxes`
- `grep_keywords_all_groups`:
  - group A:
    - `lazy`
    - `init`
    - `nil`
  - group B:
    - `map`
    - `pointer`
    - `cache`
  - group C:
    - `atomic.Pointer`
    - `CompareAndSwap`
    - `sync.Once`
- `grep_keywords_exclude`:
  - `copy-on-write`
  - `clone`
- `first_pass_query_hint`:
  - 找 “懒初始化共享结构 + CAS/Once”

### 14. `共享摘要收集器 Reset/Update 交错竞态`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/disttask/**/*`
  - `pkg/lightning/**/*`
  - `tests/realtikvtest/**/*`
- `grep_keywords_any`:
  - `summary`
  - `collector`
  - `Reset`
  - `Update`
- `grep_keywords_all_groups`:
  - group A:
    - `summary`
    - `collector`
  - group B:
    - `Reset`
  - group C:
    - `Update`
    - `collect`
- `grep_keywords_exclude`:
  - `local copy`
  - `per worker collector`
- `first_pass_query_hint`:
  - 找 “同一个 summary collector 上同时出现 Reset 和 Update”

### 15. `region job refcount 保护的共享 ingest data 生命周期`

- `grepability`: `medium`
- `path_globs`:
  - `pkg/lightning/**/*`
  - `pkg/ddl/ingest/**/*`
- `grep_keywords_any`:
  - `refcount`
  - `jobToWorkerCh`
  - `ingest data`
  - `done()`
  - `region job`
- `grep_keywords_all_groups`:
  - group A:
    - `refcount`
    - `Ref`
  - group B:
    - `jobToWorkerCh`
    - `worker`
  - group C:
    - `ingest`
    - `done()`
    - `cleanup`
- `grep_keywords_exclude`:
  - `all jobs ref before send`
  - `batch ref first`
- `first_pass_query_hint`:
  - 找 “refcount + jobToWorkerCh + ingest cleanup”

### 16. `有状态 mock encoder 被多个 processor 误复用`

- `grepability`: `high`
- `path_globs`:
  - `pkg/lightning/**/*_test.go`
  - `pkg/importer/**/*_test.go`
- `grep_keywords_any`:
  - `NewEncoder`
  - `mock`
  - `processor`
  - `DoAndReturn`
  - `same encoder`
- `grep_keywords_all_groups`:
  - group A:
    - `NewEncoder`
  - group B:
    - `processor`
    - `chunk processor`
  - group C:
    - `mock`
    - `DoAndReturn`
- `grep_keywords_exclude`:
  - `return new`
  - `new instance`
  - `clone`
- `first_pass_query_hint`:
  - 找 “NewEncoder + processor + 返回同一实例”

### 17. `DDL callback 目标 job 过滤与单次触发控制`

- `grepability`: `high`
- `path_globs`:
  - `pkg/ddl/**/*_test.go`
  - `pkg/ddl/**/*`
- `grep_keywords_any`:
  - `ActionTruncateTable`
  - `job.Query`
  - `JobStateSynced`
  - `sync.Once`
  - `OnJobUpdated`
- `grep_keywords_all_groups`:
  - group A:
    - `SetHook`
    - `OnJobUpdated`
    - `afterWaitSchemaSynced`
  - group B:
    - `ActionTruncateTable`
    - `job.Query`
    - `JobStateSynced`
  - group C:
    - `once`
    - `sync.Once`
    - `only once`
- `grep_keywords_exclude`:
  - `mutex`
  - `atomic`
    - 这里只是降权，不是排除，因为它们解决的是共享状态，不是目标 job 过滤
- `first_pass_query_hint`:
  - 找 “DDL callback + job.Query/ActionTruncateTable/JobStateSynced + once”

### 18. `长期存活的 manager/handler 共享 map 被多个并发入口直接读写`

- `grepability`: `high`
- `path_globs`:
  - `store/mockstore/**/*`
  - `domain/infosync/**/*`
  - `domain/resourcegroup/**/*`
  - `pkg/domain/infosync/**/*`
  - `pkg/domain/resourcegroup/**/*`
  - `ddl/tests/resourcegroup/**/*`
  - `pkg/ddl/tests/resourcegroup/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `TunnelSet`
  - `metricsMap`
  - `groups`
  - `registerTunnel`
  - `getAndActiveTunnel`
  - `DeriveChecker`
  - `ListResourceGroups`
- `grep_keywords_all_groups`:
  - group A:
    - `TunnelSet`
    - `metricsMap`
    - `groups`
  - group B:
    - `registerTunnel`
    - `getAndActiveTunnel`
    - `DeriveChecker`
    - `register`
    - `derive`
    - `List`
    - `ListResourceGroups`
  - group C:
    - `manager`
    - `Manager`
    - `handler`
    - `Handler`
    - `mock`
    - `Mock`
    - `client`
    - `Client`
- `grep_keywords_exclude`:
  - `valueMap`
  - `DirtyDB`
  - `IsTableLocked`
  - `rootStats`
  - `id2Timers`
- `first_pass_query_hint`:
  - 先找长期存活对象上的共享 map 字段，再看 register/get/list/activate/derive 这类并发入口是否直接访问它

### 19. `只读 helper/List/IsXxx 访问共享 map 却漏掉读侧锁`

- `grepability`: `high`
- `path_globs`:
  - `statistics/handle/**/*`
  - `pkg/statistics/handle/**/*`
  - `timer/api/**/*`
  - `pkg/timer/api/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `IsTableLocked`
  - `List(`
  - `tableLocked`
  - `id2Timers`
  - `memoryStoreCore`
- `grep_keywords_all_groups`:
  - group A:
    - `IsTableLocked`
    - `List(`
  - group B:
    - `tableLocked`
    - `id2Timers`
  - group C:
    - `RWMutex`
    - `sync.Mutex`
    - `syncutil.RWMutex`
    - `h.mu.Lock()`
    - `s.mu.Lock()`
    - `mu.Lock()`
- `grep_keywords_exclude`:
  - `rootStats`
  - `metricsMap`
  - `TunnelSet`
  - `groups`
- `first_pass_query_hint`:
  - 先找 `IsXxx/List` 这类只读 helper，再看同文件里写路径是否已经围绕同一把 `mu` 加锁，而 helper 自己直接读取 `tableLocked/id2Timers` 这类 live shared state

### 20. `cleanup/reuse/reset 路径清空共享 map 时漏锁`

- `grepability`: `medium`
- `path_globs`:
  - `util/execdetails/**/*`
  - `pkg/util/execdetails/**/*`
  - `statistics/handle/**/*`
  - `pkg/statistics/handle/**/*`
  - `timer/api/**/*`
  - `pkg/timer/api/**/*`
  - `timer/tablestore/**/*`
  - `pkg/timer/tablestore/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `NewRuntimeStatsColl`
  - `rootStats`
  - `reuse`
  - `delete(`
  - `ClearForTest`
  - `watchers`
- `grep_keywords_all_groups`:
  - group A:
    - `NewRuntimeStatsColl`
    - `ClearForTest`
    - `Close(`
    - `Notify(`
  - group B:
    - `rootStats`
    - `copStats`
    - `watchers`
    - `id2Timers`
    - `namespaces`
    - `mapper`
  - group C:
    - `delete(`
    - `mu.Lock()`
    - `reuse.mu.Lock()`
    - `Lock()`
- `grep_keywords_exclude`:
  - `TunnelSet`
  - `metricsMap`
  - `tableLocked`
- `first_pass_query_hint`:
  - 先找 `reuse/clear/reset/close` 这类 cleanup 入口，再看它是否对 live shared map 做 `delete`/清空/复位；最后确认正常读写路径是否已经围绕同一把 `mu` 建立锁纪律

### 21. `测试/helper 直接 reset 或 replace 共享 cache/handle 指针`

- `grepability`: `high`
- `path_globs`:
  - `store/tikv/**/*`
  - `pkg/store/tikv/**/*`
  - `domain/**/*`
  - `pkg/domain/**/*`
  - `infoschema/**/*`
  - `pkg/infoschema/**/*`
  - `executor/**/*`
  - `pkg/executor/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `ClearRegionCache`
  - `MockInfoCacheAndLoadInfoSchema`
  - `regionCache`
  - `infoCache`
  - `NewRegionCache`
  - `NewCache`
  - `Reset(`
- `grep_keywords_all_groups`:
  - group A:
    - `ClearRegionCache`
    - `MockInfoCacheAndLoadInfoSchema`
  - group B:
    - `regionCache`
    - `infoCache`
  - group C:
    - `NewRegionCache`
    - `NewCache`
    - `Reset(`
- `grep_keywords_exclude`:
  - `rootStats`
  - `tableLocked`
  - `metricsMap`
  - `TunnelSet`
- `first_pass_query_hint`:
  - 先找测试/helper 入口函数，再看它是否直接对共享 `regionCache/infoCache/cache/handle` 重新赋值或 new 新对象；最后确认修复是不是改成删除 helper 或改为对象内线程安全 `Reset`

### 22. `解锁后继续使用共享 cache entry / pointer`

- `grepability`: `medium`
- `path_globs`:
  - `store/tikv/**/*`
  - `pkg/store/tikv/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `GetRPCContext`
  - `getCachedRegion`
  - `searchCachedRegion`
  - `should not be used after`
  - `meta, peer :=`
  - `RegionCache`
- `grep_keywords_all_groups`:
  - group A:
    - `GetRPCContext`
    - `getCachedRegion`
    - `searchCachedRegion`
  - group B:
    - `RLock()`
    - `RUnlock()`
  - group C:
    - `meta, peer :=`
    - `should not be used after`
    - `clone it to avoid data race`
- `grep_keywords_exclude`:
  - `workTiFlashIdx`
  - `atomic.StoreInt32`
  - `atomic.LoadInt32`
- `first_pass_query_hint`:
  - 先找 cache getter / RPC context 之类的读取路径，再看是否在锁内拿到共享对象后、解锁后继续用该对象字段；优先命中那些显式写了“unlock 后不要继续使用内部对象”的注释或修法

### 23. `执行期 helper/pruning 内部的懒建查找 map 被并发查询路径同时读写`

- `grepability`: `high`
- `path_globs`:
  - `executor/**/*`
  - `pkg/executor/**/*`
  - `table/**/*`
  - `pkg/table/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `DirtyDB`
  - `GetDirtyTable`
  - `ForListColumnPruning`
  - `LocatePartition`
  - `LocateRanges`
  - `valueMap`
  - `tables map`
  - `buildPartitionValueMapAndSorted`
- `grep_keywords_all_groups`:
  - group A:
    - `DirtyDB`
    - `GetDirtyTable`
    - `ForListColumnPruning`
    - `LocatePartition`
    - `LocateRanges`
  - group B:
    - `valueMap`
    - `tables map`
    - `buildPartitionValueMapAndSorted`
    - `udb.tables`
    - `lp.valueMap`
  - group C:
    - `parallel`
    - `concurrent map`
    - `index join`
    - `Lock()`
    - `RLock()`
- `grep_keywords_exclude`:
  - `SessionVars`
  - `userVars`
  - `SetUserVar`
  - `DecodeSessionStates`
  - `TunnelSet`
  - `groups`
- `first_pass_query_hint`:
  - 先找执行期 helper / pruning 结构上的 map 字段，再看 `Get*`/`Locate*` 查询路径是否会按需填充这个 map；最后确认这些查询路径是否可能被并发执行

### 24. `TopSQL mock sink/server 的上报结果缓存被后台 worker 与断言线程并发访问`

- `grepability`: `high`
- `path_globs`:
  - `util/topsql/**/*`
  - `pkg/util/topsql/**/*`
  - `util/tracecpu/**/*`
  - `pkg/util/tracecpu/**/*`
  - `**/*_test.go`
- `grep_keywords_any`:
  - `mockAgentServer`
  - `mockPubSubDataSinkStream`
  - `mockDataSink`
  - `mockDataSink2`
  - `WaitServerCollect`
  - `WaitCollectCnt`
  - `GetLatestRecords`
  - `GetRecords`
  - `GetSQLMetas`
  - `GetPlanMetas`
  - `GetSQLMetaByDigestBlocking`
  - `GetPlanMetaByDigestBlocking`
  - `GetTotalSQLMetas`
  - `ReportData`
  - `DataRecords`
  - `sqlMetas`
  - `planMetas`
- `grep_keywords_all_groups`:
  - group A:
    - `mockAgentServer`
    - `mockPubSubDataSinkStream`
    - `mockDataSink`
    - `mockDataSink2`
    - `DataSink`
  - group B:
    - `records`
    - `sqlMetas`
    - `planMetas`
    - `ReportData`
    - `DataRecords`
  - group C:
    - `WaitServerCollect`
    - `WaitCollectCnt`
    - `GetLatestRecords`
    - `GetRecords`
    - `GetSQLMetas`
    - `GetPlanMetas`
    - `GetSQLMetaByDigestBlocking`
    - `GetPlanMetaByDigestBlocking`
    - `GetTotalSQLMetas`
    - `Lock()`
    - `chan *ReportData`
    - `time.After(`
- `grep_keywords_exclude`:
  - `StatementStatsMap`
  - `Merge(data)`
  - `testResults`
  - `audit`
- `first_pass_query_hint`:
  - 先找 TopSQL 的 mock sink/mock stream/mock server 类型，再看它是否把 `records/sqlMetas/planMetas/ReportData` 缓存在内存字段里；最后确认测试线程是不是直接读取这些缓存断言，而后台上报路径仍可能并发写入

### 25. `异步 global stats merge 直接共享 partitionStats/statsInfo，缺少 copy-on-read 快照`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle/globalstats/**/*`
  - `pkg/statistics/handle/globalstats/**/*`
  - `statistics/handle/storage/**/*`
  - `pkg/statistics/handle/storage/**/*`
  - `pkg/statistics/handle/util/**/*`
- `grep_keywords_any`:
  - `MergePartitionStats2GlobalStats`
  - `AsyncMergePartitionStats2GlobalStats`
  - `blockingMergePartitionStats2GlobalStats`
  - `partitionStats`
  - `allPartitionStats`
  - `statsInfo`
  - `GetStatsInfo`
  - `loadHistogramAndTopN`
  - `LoadTablePartitionStats`
  - `tidb_enable_async_merge_global_stats`
- `grep_keywords_all_groups`:
  - group A:
    - `MergePartitionStats2GlobalStats`
    - `AsyncMergePartitionStats2GlobalStats`
    - `blockingMergePartitionStats2GlobalStats`
  - group B:
    - `partitionStats`
    - `allPartitionStats`
    - `statsInfo`
  - group C:
    - `GetStatsInfo`
    - `loadHistogramAndTopN`
    - `LoadTablePartitionStats`
- `grep_keywords_exclude`:
  - `MergeGlobalStatsTopNByConcurrency`
  - `merge_worker.go`
  - `disjointNDV`
  - `topn.go`
- `first_pass_query_hint`:
  - 先找 global stats merge 主线入口，再看异步 worker 是否直接消费 `partitionStats/allPartitionStats/statsInfo`；如果同文件还出现 `GetStatsInfo/loadHistogramAndTopN/LoadTablePartitionStats`，通常就是这条 snapshot/copy-on-read 子模式

### 26. `从共享 stats cache 取 Table 后，在 tableStatsFromStorage 补写字段前漏掉 table.copy`

- `grepability`: `high`
- `path_globs`:
  - `statistics/statscache.go`
  - `statistics/table.go`
  - `statistics/handle.go`
  - `statistics/handle/**/*`
  - `pkg/statistics/handle/**/*`
- `grep_keywords_any`:
  - `tableStatsFromStorage`
  - `TableStatsFromStorage`
  - `table.copy()`
  - `table.Copy()`
  - `We copy it before writing to avoid race`
  - `cmSketchFromStorage`
  - `indexStatsFromStorage`
  - `columnStatsFromStorage`
  - `Histogram: *hg`
  - `CMSketch: cms`
  - `col2Idx`
  - `colNameID`
- `grep_keywords_all_groups`:
  - group A:
    - `tableStatsFromStorage`
    - `TableStatsFromStorage`
  - group B:
    - `table.copy()`
    - `table.Copy()`
    - `We copy it before writing to avoid race`
  - group C:
    - `Histogram: *hg`
    - `CMSketch: cms`
    - `cmSketchFromStorage`
    - `indexStatsFromStorage`
    - `columnStatsFromStorage`
    - `col2Idx`
    - `colNameID`
    - `ErrorRate: errorRate`
- `grep_keywords_exclude`:
  - `updateStatsCache`
  - `latestVersion`
  - `statsCache struct`
  - `internal/cache`
  - `globalstats`
- `first_pass_query_hint`:
  - 先找 `tableStatsFromStorage` / `TableStatsFromStorage`，再看它是否从共享 `statsCache` 取出现有 `Table` 并立即 `table.copy()`；最后确认同一段逻辑是否继续补写 `Histogram/CMSketch/col2Idx/colNameID` 等字段。这个检索对 `6565/13647` 这类相邻 case 也会有召回，所以适合粗筛，最终仍要让 agent 做 verdict 判断

### 27. `UpdateStatsByLocalFeedback 在共享 Table/Index/Column 上原地回写 Histogram/CMSketch`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/update.go`
  - `statistics/handle/update.go`
  - `pkg/statistics/handle/update.go`
- `grep_keywords_any`:
  - `UpdateStatsByLocalFeedback`
  - `local feedback`
  - `newTblStats := tblStats.copy()`
  - `newIdx := *idx`
  - `newCol := *col`
  - `UpdateHistogram(`
  - `UpdateCMSketch(`
  - `UpdateTableStats(`
  - `splitFeedbackByQueryType`
  - `GetPartitionStats(`
- `grep_keywords_all_groups`:
  - group A:
    - `UpdateStatsByLocalFeedback`
    - `local feedback`
  - group B:
    - `newTblStats := tblStats.copy()`
    - `newIdx := *idx`
    - `newCol := *col`
  - group C:
    - `UpdateHistogram(`
    - `UpdateCMSketch(`
    - `UpdateTableStats(`
- `grep_keywords_exclude`:
  - `tableStatsFromStorage`
  - `TableStatsFromStorage`
  - `rateMap`
  - `globalMap`
  - `GetStatsInfo`
- `first_pass_query_hint`:
  - 先找 `UpdateStatsByLocalFeedback` / `local feedback` 回写入口，再看同一函数里是否同时出现 `tblStats.copy + newIdx/newCol + UpdateHistogram/UpdateCMSketch/UpdateTableStats`。这组检索对 `pr-6859` 很稳，但不会把 `pr-6565` 那种 from-storage / pseudo 更新和 `pr-6901` 那种 `rateMap` 互斥保护混进来。

### 28. `stats Handle / SessionStatsCollector 在 dump/clear 路径直接重置 live feedback/globalMap/collector state，缺少锁内 snapshot-swap`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle/handle.go`
  - `statistics/handle/update.go`
  - `pkg/statistics/handle/handle.go`
  - `pkg/statistics/handle/update.go`
  - `statistics/handle.go`
  - `statistics/update.go`
- `grep_keywords_any`:
  - `SessionStatsCollector`
  - `globalMap`
  - `feedback`
  - `ClearForTest`
  - `sweepList`
  - `DumpStatsDeltaToKV`
  - `DumpStatsFeedbackToKV`
  - `UpdateStatsByLocalFeedback`
  - `h.feedback.Lock()`
  - `h.globalMap.Lock()`
  - `statistics.NewQueryFeedbackMap()`
- `grep_keywords_all_groups`:
  - group A:
    - `SessionStatsCollector`
    - `globalMap`
    - `feedback`
  - group B:
    - `ClearForTest`
    - `sweepList`
    - `DumpStatsDeltaToKV`
    - `DumpStatsFeedbackToKV`
    - `UpdateStatsByLocalFeedback`
  - group C:
    - `h.feedback.Lock()`
    - `h.globalMap.Lock()`
    - `feedback := h.feedback.data`
    - `deltaMap := h.globalMap.data`
    - `h.feedback.data = statistics.NewQueryFeedbackMap()`
    - `h.globalMap.data = make(tableDeltaMap)`
    - `s.feedback = statistics.NewQueryFeedbackMap()`
    - `s.colMap = make(colStatsUsageMap)`
- `grep_keywords_exclude`:
  - `pid2tid`
  - `schemaVersion`
  - `tableStatsFromStorage`
  - `newTblStats := tblStats.copy()`
  - `UpdateHistogram(`
  - `UpdateCMSketch(`
- `first_pass_query_hint`:
  - 先找 stats handle / collector 的 dump 或 clear 入口，再看它是否先对 `globalMap/feedback/collector state` 做锁内 snapshot-swap。命中 `ClearForTest`、`feedback := h.feedback.data`、`deltaMap := h.globalMap.data` 这类锚点时，基本就在这条子模式上。

### 29. ``SessionStatsCollector.rateMap -> Handle.rateMap -> UpdateErrorRate` 链路直接聚合共享误差率 map，缺少统一互斥`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/update.go`
  - `statistics/handle/update.go`
  - `pkg/statistics/handle/update.go`
  - `statistics/handle.go`
  - `statistics/handle/handle.go`
  - `pkg/statistics/handle/handle.go`
- `grep_keywords_any`:
  - `rateMap`
  - `errorRateDeltaMap`
  - `StoreQueryFeedback`
  - `UpdateErrorRate`
  - `rateMap.update(`
  - `rateMap.merge(`
  - `delete(h.mu.rateMap, id)`
  - `for id, item := range h.mu.rateMap`
- `grep_keywords_all_groups`:
  - group A:
    - `rateMap`
    - `errorRateDeltaMap`
  - group B:
    - `StoreQueryFeedback`
    - `UpdateErrorRate`
  - group C:
    - `h.mu.rateMap.merge(`
    - `for id, item := range h.mu.rateMap`
    - `delete(h.mu.rateMap, id)`
- `grep_keywords_exclude`:
  - `globalMap.data`
  - `feedback := h.feedback.data`
  - `deltaMap := h.globalMap.data`
  - `tableStatsFromStorage`
  - `ClearForTest`
  - `pid2tid`
  - `schemaVersion`
- `first_pass_query_hint`:
  - 先找 feedback update 主线里的 `rateMap` / `errorRateDeltaMap`，再确认是否同时出现 `StoreQueryFeedback`、`UpdateErrorRate` 与 `merge/range/delete rateMap` 这三段链路。命中 `h.mu.rateMap.merge(`、`for id, item := range h.mu.rateMap`、`delete(h.mu.rateMap, id)` 这组锚点时，基本就在这条子模式上。

### 30. ``Handle.pid2tid/schemaVersion` 分区 physicalID 到 tableID 映射缓存被并发读写，缺少统一锁保护`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle.go`
  - `statistics/boostrap.go`
  - `statistics/bootstrap.go`
  - `statistics/dump.go`
  - `statistics/table.go`
  - `statistics/handle/handle.go`
  - `statistics/handle/bootstrap.go`
- `grep_keywords_any`:
  - `pid2tid`
  - `schemaVersion`
  - `buildPartitionID2TableID`
  - `getTableByPhysicalID`
  - `SchemaMetaVersion()`
  - `PhysicalID`
  - `GetPartitionStats(`
  - `h.mu.pid2tid`
  - `h.mu.schemaVersion`
- `grep_keywords_all_groups`:
  - group A:
    - `pid2tid`
    - `schemaVersion`
  - group B:
    - `getTableByPhysicalID`
    - `buildPartitionID2TableID`
    - `SchemaMetaVersion()`
  - group C:
    - `h.mu.pid2tid`
    - `h.mu.schemaVersion`
    - `h.mu.Lock()`
- `grep_keywords_exclude`:
  - `rateMap`
  - `globalMap`
  - `feedback := h.feedback.data`
  - `deltaMap := h.globalMap.data`
  - `ClearForTest`
  - `newTblStats := tblStats.copy()`
  - `UpdateHistogram(`
- `first_pass_query_hint`:
  - 先找 partition stats 加载主线里的 `pid2tid/schemaVersion`，再确认是否同时出现 `getTableByPhysicalID/buildPartitionID2TableID/SchemaMetaVersion()` 与 `h.mu.pid2tid/h.mu.schemaVersion/h.mu.Lock()` 这组锚点。命中“字段迁入 `h.mu` + 根据 schema version 重建映射”时，基本就在这条子模式上。

### 31. ``Handle.statsCache` 整体 snapshot 以 version 做 copy-on-write 发布，缺少串行 store 门禁`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle.go`
  - `statistics/handle/statscache.go`
  - `statistics/handle/handle.go`
  - `statistics/handle/statscacheinner.go`
  - `pkg/statistics/handle/handle.go`
  - `pkg/statistics/handle/cache/statscache.go`
- `grep_keywords_any`:
  - `statsCache`
  - `StatsCache`
  - `version uint64`
  - `updateStatsCache`
  - `statsCache.update(`
  - `CopyAndUpdate(`
  - `statsCache.Load()`
  - `statsCache.Store(`
  - `oldCache.version`
  - `newCache.version`
- `grep_keywords_all_groups`:
  - group A:
    - `statsCache`
    - `StatsCache`
    - `version uint64`
  - group B:
    - `updateStatsCache`
    - `statsCache.update(`
    - `CopyAndUpdate(`
  - group C:
    - `oldCache.version`
    - `newCache.version`
    - `statsCache.Lock()`
    - `statsCache.Store(`
- `grep_keywords_exclude`:
  - `pid2tid`
  - `schemaVersion`
  - `rateMap`
  - `globalMap`
  - `cacheInternalItem`
  - `StatsCacheInner`
  - `lfu`
  - `lru`
  - `mapcache`
- `first_pass_query_hint`:
  - 先找整包 `statsCache/StatsCache` 的 snapshot/update/publish 逻辑，再确认是否同时出现 `updateStatsCache` 或 `CopyAndUpdate` 一类派生入口，以及 `oldCache.version/newCache.version/statsCache.Lock()/Store` 这组发布门禁锚点。命中“旧快照派生新快照 + 带 version 门禁的集中 publish”时，基本就在这条子模式上。

### 32. ``LFU.cache.Set` 触发 `reject/onEvict` 时，`resultKeySet/cost` 更新顺序交错`

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle/cache/internal/lfu/lfu_cache.go`
  - `statistics/handle/cache/internal/lfu/key_set.go`
  - `statistics/handle/cache/internal/lfu/key_set_shard.go`
  - `pkg/statistics/handle/cache/internal/lfu/lfu_cache.go`
  - `pkg/statistics/handle/cache/internal/lfu/key_set.go`
- `grep_keywords_any`:
  - `lfu`
  - `resultKeySet`
  - `keySet`
  - `cache.Set(`
  - `onReject`
  - `onEvict`
  - `reject`
  - `evict`
  - `cost.Add(`
  - `resultKeySet.AddKeyValue`
  - `resultKeySet.Get(`
- `grep_keywords_all_groups`:
  - group A:
    - `lfu`
    - `resultKeySet`
    - `keySet`
  - group B:
    - `cache.Set(`
    - `onReject`
    - `onEvict`
    - `reject`
    - `evict`
  - group C:
    - `resultKeySet.AddKeyValue`
    - `cost.Add(`
    - `Values()`
    - `resultKeySet.Get(`
- `grep_keywords_exclude`:
  - `updateStatsCache`
  - `CopyAndUpdate`
  - `statsCache.Store(`
  - `oldCache.version`
  - `newCache.version`
  - `sync.RWMutex`
  - `MapCache`
  - `StatsCacheInner`
- `first_pass_query_hint`:
  - 先找 LFU 实现里的 `resultKeySet` / `cache.Set` / `onEvict`，再确认是否同时出现“`Put` 改 `resultKeySet/cost`”与“`reject/onEvict` 也会改同一组状态”这两段逻辑。命中 `resultKeySet.AddKeyValue`、`cost.Add(`、`cache.Set(`、`onReject/onEvict`，且 `Values()` 改成走 `resultKeySet.Get(` 时，基本就在这条子模式上。

### 33. ``stats cache internal LRU/map cache` 共享结构被 `Get/Put/Del/Values/Copy` 路径并发访问，缺少统一 `RWMutex``

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle/internal/cache/lru/lru_cache.go`
  - `statistics/handle/internal/cache/mapcache/map_cache.go`
  - `statistics/handle/statscache.go`
  - `pkg/statistics/handle/internal/cache/lru/lru_cache.go`
  - `pkg/statistics/handle/internal/cache/mapcache/map_cache.go`
- `grep_keywords_any`:
  - `sync.RWMutex`
  - `RWMutex`
  - `StatsCacheInner`
  - `MapCache`
  - `innerItemLruCache`
  - `elements map`
  - `GetByQuery`
  - `PutByQuery`
  - `FreshMemUsage`
  - `Front()`
  - `RLock()`
  - `RUnlock()`
  - `Lock()`
  - `Unlock()`
- `grep_keywords_all_groups`:
  - group A:
    - `sync.RWMutex`
    - `RWMutex`
    - `RLock()`
    - `RUnlock()`
    - `Lock()`
    - `Unlock()`
  - group B:
    - `StatsCacheInner`
    - `MapCache`
    - `innerItemLruCache`
    - `elements map`
  - group C:
    - `GetByQuery`
    - `Get(`
    - `PutByQuery`
    - `Put(`
    - `Del(`
    - `Values()`
    - `Keys()`
    - `Copy()`
    - `FreshMemUsage`
    - `Front()`
- `grep_keywords_exclude`:
  - `resultKeySet`
  - `onReject`
  - `onEvict`
  - `cache.Set(`
  - `updateStatsCache`
  - `CopyAndUpdate`
  - `oldCache.version`
  - `newCache.version`
- `first_pass_query_hint`:
  - 先找 cache internal 实现里的 `sync.RWMutex/RLock/Lock`，再确认是否同时出现 `StatsCacheInner/MapCache/innerItemLruCache` 这类 internal type 锚点，以及 `Get/Put/Del/Values/Copy/FreshMemUsage/Front` 这一整串 API。三组都在时，基本就在这条 internal cache 通用锁子模式上。

### 34. ``GetPartitionStats` miss 后临时构造 `PseudoTable` 却回填共享 `statsCache``

- `grepability`: `medium`
- `path_globs`:
  - `statistics/handle.go`
  - `statistics/handle/handle.go`
  - `statistics/handle/statscache.go`
  - `pkg/statistics/handle/handle.go`
  - `pkg/statistics/handle/cache/statscache.go`
- `grep_keywords_any`:
  - `GetPartitionStats(`
  - `PseudoTable(`
  - `GetPartitionInfo()`
  - `partition`
  - `PhysicalID = pid`
  - `updateStatsCache`
  - `statsCache.update(`
  - `statsCacheLen()`
- `grep_keywords_all_groups`:
  - group A:
    - `GetPartitionStats(`
    - `PseudoTable(`
  - group B:
    - `GetPartitionInfo()`
    - `partition`
    - `PhysicalID = pid`
  - group C:
    - `updateStatsCache`
    - `statsCache.update(`
    - `statsCacheLen()`
- `grep_keywords_exclude`:
  - `oldCache.version`
  - `newCache.version`
  - `CopyAndUpdate(`
  - `StatsCacheInner`
  - `sync.RWMutex`
  - `resultKeySet`
  - `onEvict`
- `first_pass_query_hint`:
  - 先找 `GetPartitionStats` miss 路径里的 `PseudoTable` 构造，再确认同一分支里是否同时出现 `PhysicalID = pid` / `GetPartitionInfo()` 这类 partition 身份锚点，以及 `updateStatsCache(statsCache.update(...))` 或 `statsCacheLen()` 这组共享 cache 写回信号。命中“miss 时造 pseudo table + 绑定 partition + 顺手回填 cache”时，基本就在这条子模式上。

### 35. ``twoPhaseCommit.doActionOnBatches` 并行 batch goroutine 复用父 `Backoffer``

- `grepability`: `medium`
- `path_globs`:
  - `store/tikv/2pc.go`
  - `store/tikv/backoff.go`
  - `pkg/store/tikv/2pc.go`
  - `pkg/store/tikv/backoff.go`
  - `util/execdetails/execdetails.go`
  - `pkg/util/execdetails/execdetails.go`
- `grep_keywords_any`:
  - `doActionOnBatches(`
  - `actionCommit`
  - `batches`
  - `Backoffer`
  - `singleBatchBackoffer`
  - `Clone()`
  - `Fork()`
  - `totalSleep`
  - `CommitBackoffTime`
  - `BackoffTypes`
  - `atomic.AddInt64`
  - `go func`
  - `concurrent goroutines`
  - `same backoffer`
- `grep_keywords_all_groups`:
  - group A:
    - `doActionOnBatches(`
    - `actionCommit`
    - `batches`
  - group B:
    - `singleBatchBackoffer`
    - `Clone()`
    - `Fork()`
  - group C:
    - `go func`
    - `concurrent goroutines`
    - `same backoffer`
    - `totalSleep`
    - `CommitBackoffTime`
    - `BackoffTypes`
    - `atomic.AddInt64`
- `grep_keywords_exclude`:
  - `secondaryBo := NewBackoffer`
  - `NewBackoffer(context.Background(), CommitMaxBackoff)`
  - `getTxnStatusFromLock`
  - `ResolveLocks(`
  - `CheckTxnStatus`
  - `RequestBuilder`
- `first_pass_query_hint`:
  - 先找 `doActionOnBatches` 这类 2PC 并行 batch 主线，再确认每个 batch goroutine 是否通过 `singleBatchBackoffer = backoffer.Clone()/Fork()` 派生独立 `Backoffer`，以及同一 patch 是否还在处理 `totalSleep/CommitBackoffTime/BackoffTypes` 这些共享回退统计。命中“batch goroutine + singleBatchBackoffer + backoff 统计聚合”时，基本就在这条子模式上。

### 36. ``IndexJoin / IndexLookupJoin / IndexLookupMergeJoin` 每个 inner worker 复制自己的 `indexRanges``

- `grepability`: `high`
- `path_globs`:
  - `executor/index_lookup_join.go`
  - `executor/new_index_lookup_join.go`
  - `executor/index_lookup_merge_join.go`
  - `executor/index_lookup_hash_join.go`
  - `planner/core/exhaust_physical_plans.go`
  - `planner/core/physical_plans.go`
  - `pkg/executor/index_lookup_join.go`
  - `pkg/executor/index_lookup_merge_join.go`
  - `pkg/executor/index_lookup_hash_join.go`
  - `pkg/planner/core/exhaust_physical_plans.go`
  - `pkg/planner/core/physical_plans.go`
- `grep_keywords_any`:
  - `IndexLookUpJoin`
  - `IndexLookUpMergeJoin`
  - `newInnerWorker`
  - `newInnerMergeWorker`
  - `indexHashJoinInnerWorker`
  - `indexRanges`
  - `MutableRanges`
  - `Range()`
  - `copiedRanges :=`
  - `ran.Clone()`
  - `copy join's indexRanges`
  - `multiple inner workers run concurrently`
  - `buildExecutorForIndexJoin`
  - `keyOff2IdxOff`
- `grep_keywords_all_groups`:
  - group A:
    - `IndexLookUpJoin`
    - `IndexLookUpMergeJoin`
    - `newInnerWorker`
    - `newInnerMergeWorker`
    - `indexHashJoinInnerWorker`
  - group B:
    - `indexRanges`
    - `MutableRanges`
    - `Ranges`
    - `Range()`
  - group C:
    - `copiedRanges :=`
    - `ran.Clone()`
    - `copy join's indexRanges`
    - `multiple inner workers run concurrently`
- `grep_keywords_exclude`:
  - `buildUnionScanFromReader`
  - `builder.Plan`
  - `TmpConstant`
  - `joinResult`
  - `resultCh`
  - `joinChkResourceCh`
- `first_pass_query_hint`:
  - 先找 index join inner worker 主线上的 `indexRanges/MutableRanges`，再确认 worker 初始化里是否显式构造 `copiedRanges` 并逐个 `ran.Clone()`。如果同一 patch 同时出现 `copy join's indexRanges` 或 `multiple inner workers run concurrently` 这类注释，通常就是这条 range 复用子模式。

### 37. ``IndexJoin / IndexMergeJoin / IndexHashJoin` 每个 inner worker 重建自己的 `TmpConstant``

- `grepability`: `high`
- `path_globs`:
  - `executor/index_lookup_join.go`
  - `executor/index_lookup_merge_join.go`
  - `executor/index_lookup_hash_join.go`
  - `planner/core/exhaust_physical_plans.go`
  - `pkg/executor/index_lookup_join.go`
  - `pkg/executor/index_lookup_merge_join.go`
  - `pkg/executor/index_lookup_hash_join.go`
  - `pkg/planner/core/exhaust_physical_plans.go`
- `grep_keywords_any`:
  - `lastColHelper`
  - `nextColCompareFilters`
  - `ColWithCmpFuncManager`
  - `TmpConstant`
  - `nextCwf`
  - `TargetCol`
  - `make([]*expression.Constant`
  - `newInnerWorker`
  - `newInnerMergeWorker`
  - `indexHashJoinInnerWorker`
  - `inner worker`
  - `concurrently`
- `grep_keywords_all_groups`:
  - group A:
    - `newInnerWorker`
    - `newInnerMergeWorker`
    - `indexHashJoinInnerWorker`
  - group B:
    - `lastColHelper`
    - `nextColCompareFilters`
    - `ColWithCmpFuncManager`
  - group C:
    - `TmpConstant`
    - `nextCwf`
    - `make([]*expression.Constant`
    - `TargetCol`
- `grep_keywords_exclude`:
  - `indexRanges`
  - `MutableRanges`
  - `copiedRanges :=`
  - `joinResult`
  - `resultCh`
  - `buildUnionScanFromReader`
- `first_pass_query_hint`:
  - 先找 inner worker 主线上的 `lastColHelper/nextColCompareFilters`，再确认同一 patch 是否显式做了 `nextCwf := *e.lastColHelper` 和 `nextCwf.TmpConstant = make(...)`。命中这两步时，基本就是 per-worker scratch helper 重建这条子模式。

### 38. ``buildUnionScanForIndexJoin` 直接改写共享 `builder.Plan``

- `grepability`: `medium`
- `path_globs`:
  - `executor/builder.go`
  - `executor/index_lookup_join.go`
  - `pkg/executor/builder.go`
  - `pkg/executor/index_lookup_join.go`
- `grep_keywords_any`:
  - `buildUnionScanForIndexJoin`
  - `buildUnionScanFromReader`
  - `builder.Plan`
  - `dataReaderBuilder`
  - `childBuilder := &dataReaderBuilder`
  - `UnionScanExec`
  - `buildAndSortAddedRows()`
  - `local child builder`
  - `Plan of dataReaderBuilder directly`
  - `Be careful to avoid data race`
- `grep_keywords_all_groups`:
  - group A:
    - `buildUnionScanForIndexJoin`
    - `buildUnionScanFromReader`
    - `UnionScanExec`
  - group B:
    - `builder.Plan`
    - `dataReaderBuilder`
    - `childBuilder := &dataReaderBuilder`
  - group C:
    - `Plan of dataReaderBuilder directly`
    - `local child builder`
    - `Be careful to avoid data race`
    - `buildAndSortAddedRows()`
- `grep_keywords_exclude`:
  - `forDataReaderBuilder`
  - `getSnapshotTS`
  - `forUpdateTS`
  - `indexRanges`
  - `TmpConstant`
- `first_pass_query_hint`:
  - 先找 union scan 的 `buildUnionScanForIndexJoin/buildUnionScanFromReader`，再确认是否直接改写共享 `builder.Plan` 或共享 `b.err`，以及补丁是否引入局部 `childBuilder` 来隔离 plan。命中这三步时，基本就是这条 builder 复用子模式。

### 39. ``executorBuilder.forDataReaderBuilder` 预取隔离 read TS，避免并发复用会话态``

- `grepability`: `medium`
- `path_globs`:
  - `executor/builder.go`
  - `executor/index_lookup_join.go`
  - `executor/index_lookup_merge_join.go`
  - `executor/index_lookup_hash_join.go`
  - `pkg/executor/builder.go`
  - `pkg/executor/index_lookup_join.go`
  - `pkg/executor/index_lookup_merge_join.go`
  - `pkg/executor/index_lookup_hash_join.go`
- `grep_keywords_any`:
  - `forDataReaderBuilder`
  - `getSnapshotTS`
  - `dataReaderTS`
  - `snapshotReadTS`
  - `forUpdateTS`
  - `newDataReaderBuilder`
  - `dataReaderBuilder`
  - `thread safe`
  - `issue #30468`
  - `dataReaderBuilder can be used in concurrent goroutines`
- `grep_keywords_all_groups`:
  - group A:
    - `forDataReaderBuilder`
    - `getSnapshotTS`
    - `newDataReaderBuilder`
  - group B:
    - `dataReaderTS`
    - `snapshotReadTS`
    - `forUpdateTS`
  - group C:
    - `thread safe`
    - `issue #30468`
    - `dataReaderBuilder can be used in concurrent goroutines`
- `grep_keywords_exclude`:
  - `builder.Plan`
  - `buildUnionScanFromReader`
  - `indexRanges`
  - `TmpConstant`
  - `joinResult`
- `first_pass_query_hint`:
  - 先找 `forDataReaderBuilder/getSnapshotTS/newDataReaderBuilder`，再确认同一 patch 是否显式冻结 `dataReaderTS`，以及提交说明/注释里是否直接写了 `thread safe` / `issue #30468` / `dataReaderBuilder can be used in concurrent goroutines`。这三组同时出现时，基本就是 data reader 私有 read TS 这条子模式。

### 40. ``IndexHashJoin.keepOuterOrder` 每处理一个 task 都重新 `getNewJoinResult`，避免复用已发送的 `joinResult` holder``

- `grepability`: `medium`
- `path_globs`:
  - `executor/index_lookup_hash_join.go`
  - `executor/join_test.go`
  - `pkg/executor/index_lookup_hash_join.go`
  - `pkg/executor/join_test.go`
- `grep_keywords_any`:
  - `keepOuterOrder`
  - `getNewJoinResult`
  - `joinResult`
  - `resultCh`
  - `joinChkResourceCh`
  - `result holder`
  - `after handling a task`
  - `orded IndexHashJoin`
  - `ordered IndexHashJoin`
  - `has been sent to the resultCh`
  - `has been sent to the joinChkResourceCh`
- `grep_keywords_all_groups`:
  - group A:
    - `keepOuterOrder`
    - `orded IndexHashJoin`
    - `ordered IndexHashJoin`
  - group B:
    - `result holder`
    - `after handling a task`
    - `WITHOUT getNewJoinResult`
  - group C:
    - `resultCh`
    - `joinChkResourceCh`
    - `has been sent to the resultCh`
    - `has been sent to the joinChkResourceCh`
- `grep_keywords_exclude`:
  - `ctx.Done()`
  - `select {`
  - `chunk resource channel`
  - `limit`
  - `indexRanges`
  - `TmpConstant`
- `first_pass_query_hint`:
  - 先找 ordered `IndexHashJoin` 的 `keepOuterOrder` 路径，再确认同一 patch 是否显式写了 `after handling a task` / `result holder` / `WITHOUT getNewJoinResult` 这类 bugfix 语义锚点，以及旧 `joinResult` 已经发到 `resultCh` / `joinChkResourceCh`。这三组同时出现时，基本就是 holder handoff 后误复用这条子模式。

## 最后结论

如果问题是：

- “这 `51` 个能不能直接给 agent 看？”

答案是：

- **能**
- 但直接给 agent 看，只适合做“慢但准”的判定

如果问题是：

- “能不能让 agent 更可操作地全仓扫？”

答案是：

- **能**
- 但应该补一层“检索信号层”
- 最好把 grep 关键词、关键词组合、目录范围、排除词与现有 JSON 分开管理
- 目前已经落地的做法就是：
  - 现有 `40` 个 JSON 继续保留做 verdict layer
  - `retrieval_signals.json` 单独承载 retrieval layer
