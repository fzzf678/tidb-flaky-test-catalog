# 给 agent 的仓库扫描检索信号

这份文档回答一个很具体的问题：

- 当前这 `17` 个 subpattern，能不能直接给 agent 看？

答案是：

- **能**，但它们现在更适合做“判定层”。
- 如果目标是**覆盖整个仓库**去扫存量测试，仅靠这 `17` 个 JSON 还不够快，也不够像“检索层”。
- 更实用的方式是分成两层：
  - 第一层：**检索层**
    - 用 grep / 路径 / 关键词组合，把全仓里的测试先缩成候选集
  - 第二层：**判定层**
    - 再用现有 JSON 里的 `signals_required / signals_optional / negative_guards / verdict_policy` 做严格判断

也就是说：

- 当前 `17` 个 JSON 不该被废掉
- 但如果要给 agent 做全仓扫描，最好再补一层更硬的“检索信号”
- 现在这层已经有了一个结构化 sidecar 文件：
  - `retrieval_signals.json`

## 这份文档和草案的分工

现在这几个文件的角色已经比较明确：

- `retrieval_signals.json`
  - 当前 agent / 自动化真正执行的结构化检索层
  - 已经落到 `v3`
  - 这里的 `rg_templates` 是当前最权威的可执行入口
- `subpatterns/`
  - 当前 `17` 个正式 subpattern JSON 的集中目录
  - 这部分是 verdict layer，不和 `retrieval_signals.json` 混放
- `第二轮聚类草案.md`
  - 负责维护 17 个正式 subpattern 的完整 case inventory
  - 里面已经把更多正例和边界 case 补齐
- 本文档
  - 负责解释“检索层应该怎么用”
  - 以及概括每个 subpattern 该关注什么类型的 grep/path/关键词组合
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
  - 当前建议至少包含：
    - `broad_recall`
    - `fallback_no_path`
    - `group_intersection`

## 使用方式

让 agent 扫全仓时，不要直接把 `17` 个 JSON 当成 `17` 条逐个硬匹配的规则。

正确顺序应该是：

1. 如果是跨版本扫描，或者怀疑不同版本发生了目录迁移，默认先执行 `fallback_no_path`
2. 如果只是想先做更快的当前版本试跑，再把 `broad_recall` 当可选第一跳
3. 如果还需要进一步收窄，再执行 `group_intersection`
4. 如果还需要补搜，再回退到 `path_globs + grep_keywords_any + grep_keywords_all_groups` 手动拼查询
5. 再把候选文件 / 测试函数交给 `subpatterns/` 里的 subpattern JSON 做严格判定

## 当前落地状态

现在 `retrieval_signals.json` 已经不只是“字段建议”，而是已经落到 `v3`，并补了可直接执行的 `rg_templates`：

- `broad_recall`
  - 做更快的当前版本第一跳召回
  - 仍然优先利用当前版本的目录结构
- `fallback_no_path`
  - 当版本重构、目录迁移、历史路径差异导致 `path_globs` 失效时，做全仓兜底召回
  - 如果 scan root 是仓库根，就按全仓范围执行，不再把 `path_globs` 当限制条件
- `group_intersection`
  - 做按组交集收窄

这一步的目标不是降低误报，而是先让新 agent 在全仓里更稳定地“找得到”。误报控制暂时仍然主要留在 verdict layer。

另外，17 个正式 subpattern 当前更完整的正例 / 边界 case 盘点，已经并回：

- `第二轮聚类草案.md` 里的“17 个正式 subpattern 的当前案例清单”

所以如果要回答“这个 subpattern 目前到底落了哪些 case”，应优先看草案；如果要回答“agent 该怎么检索”，优先看本文和 `retrieval_signals.json`。

## 17 个 subpattern 的检索信号建议

下面这些信号，都是**检索层**，不是 verdict 层。

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

## 最后结论

如果问题是：

- “这 17 个能不能直接给 agent 看？”

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
  - 现有 `17` 个 JSON 继续保留做 verdict layer
  - `retrieval_signals.json` 单独承载 retrieval layer
