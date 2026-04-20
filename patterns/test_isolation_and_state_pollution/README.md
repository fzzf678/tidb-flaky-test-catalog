# `test_isolation_and_state_pollution`

这个目录承接“test isolation / state pollution”这条 family 的正式化工作。

它不是单个 smell 的镜像目录，而是从下面两个 smell 的并集出发，经过 `patch-first` 的全量人工复读后，重新抽出来的机制簇：

- `global_variable_mutation`
- `insufficient_cleanup_between_tests`

## 当前状态

- source set 仍然是这两个 smell 并集下的 `234` 个历史 case。
- 但这 `234` 只能作为人工 review 的输入全集，不能直接当成 family inventory。
- 当前唯一接受的方法是：
  - 逐条重读 `234` 个 patch
  - 只根据 patch / test diff 本体归类
  - 再反过来 formalize family / sibling / subpattern

## 这轮人工 review 的当前结论

- 已人工重读：`234 / 234`
- patch-backed 支持当前 unified direction：`93`
- 当前人工排除 / 迁边界：`141`
- patch-first 口径下的 family purity：`39.7%`

这说明：

- 这条 family 不能继续用 smell 字段直接分桶
- retained case 的主体，必须真的落在 test isolation / lifecycle / namespace pollution
- 只要 retained 主体更像 process-global knob race / async ordering / `t.Parallel()` shared-state，就要迁边界

## 当前已 formalize 的 sibling

目前已经正式落盘 `6` 条：

- `共享 namespace 资源必须 per-test 唯一化`
- `后台 component 必须显式 Stop/Close/Wait，不能靠 ignore / 自然退出`
- `临时句柄 / backend / engine / iterator 必须在所有退出路径上收口`
- `test 注入的 hook / filter / matcher 必须缩作用域并在 cancel/切阶段时解绑`
- `可复用 fixture / executor / stateful helper 在再次使用前必须 reset / restore / clone`
- `server / harness / package sandbox 级 test-global 状态必须重建或清理`

它之所以先做，是因为：

- patch-backed 集中度最高
- 修法非常稳定
- retrieval signal 最容易先长成可用的粗筛

这条 sibling 当前覆盖的对象，不急着再拆细：

- table / db / file namespace
- temp dir / temp storage / spill dir / storage path
- slow-log / dump / export file path
- unix socket / server listen endpoint / status port
- package/test sandbox 级的 runtime namespace

共同修法也很稳定：

- `t.TempDir()`
- `config.TempDir` / `TempStoragePath` 指到 case-local 路径
- 唯一 db / table / key / policy 名字
- 唯一 slow-log / socket / dump / storage 路径
- `cfg.Port = 0` / `StatusPort = 0` / 真正占住空闲端口

当前这条 sibling 的 `v1` retrieval 会先偏向：

- path / socket / port / temp-storage / slow-log / plan-replayer 这类显式 namespace 锚点

原因很简单：

- 这组检索信号最稳定
- object-name-only（纯 table / db / policy 名字唯一化）在 repo-scan 上更容易被泛化噪声淹没

所以这部分 case 目前仍然要保留较多人工 patch review，不用强行把 `rg_template` 写成“看起来全能、实际噪声爆炸”的版本。

第二条 sibling 当前覆盖的对象则更偏 lifecycle：

- domain / store / server / cluster harness
- worker / waiter / queue / manager / background loop
- metrics / opencensus view worker
- TTL manager / stats worker / auto-analyze queue

这条的共同修法也很稳定：

- 显式 `Stop()` / `Close()` / `Wait()` / `WaitStopped(...)`
- `Cancel()` 之后真的等 goroutine / campaign loop 退出
- 走完整 stopServer / clean / teardown 链，而不是只关最外层对象
- 删除 `goleak.IgnoreTopFunction(...)`，把后台 worker 真的停掉

这条 sibling 的 `v1` retrieval 会先偏向：

- `view.Stop()` / `WaitStopped(...)` / `TTLJobManager().Stop()` / `DisableStats4Test()` / `stopServer(...)`
- `dom.Close()` / `store.Close()` / `server.Close()` / `testleak.AfterTest()` / `WaitGroupWrapper`

也就是优先抓“显式 lifecycle 收口动作”本身，而不是先去追所有可能启动后台 loop 的功能关键词。

第三条 sibling 当前覆盖的对象则更偏 close-path 资源：

- `RecordSet` / `sql.Rows` / `stmt` / `Session().Execute(...)` 返回句柄
- `resp.Body`
- iterator / channel / worker handle
- chunk / temporary buffer / `StorageRC`
- backend / engine / ingest resource

这条的共同修法同样很稳定：

- 所有返回路径统一 `Close()` / `recycle` / `rollback` / `Unregister`
- `panic` / `reopen` / `rollback` / `cancel` / `open failure` 路径也走同一套 defer 或 close-path
- helper 分流成“自动收口”和“返回句柄给调用者自己负责”两条

这条 sibling 的 `v1` retrieval 会先偏向：

- `rows.Close()` / `stmt.Close()` / `resp.Body.Close()`
- `mustExecToRecodeSet`
- `recycleChunk(...)`
- `DerefAndClose`
- `Unregister(job.ID)`

也就是优先抓那些已经显式暴露出“谁拿到句柄，谁负责收口”的 close-path anchors，而不是把所有 `RecordSet` / `engine` / `rollback` 相关代码都一口气扫进来。

第四条 sibling 当前覆盖的对象则更偏 test-local observer state：

- request-level hook / checker / observer
- matcher / wait item / matchFn
- message filter / OOM filter
- 任何只应该在当前请求、当前阶段、当前场景生效的 test-local interceptor

这条的共同修法也很稳定：

- 给目标请求打 `context` 标记，只观察被标记的请求
- 对 internal session / background request 加 guard，不把无关流量算进断言
- 在 `ctx.Done()` / cancel / phase switch 上显式 `clearMatchFn()` / `ClearMessageFilter()`
- 同一测试里重新注册 filter 前，先把上一轮残留 filter 清空

这条 sibling 的 `v1` retrieval 会先偏向：

- `MustQueryWithContext` / `MustExecWithContext`
- `clearMatchFn` / `matchFn`
- `AddMessageFilter` / `ClearMessageFilter`
- `isInternal()`

也就是优先抓那些已经显式暴露出“观察器范围”和“解绑/清空时机”的 anchor，而不是把所有 `hook` / `filter` / `callback` 这种泛词直接扫进来。

第五条 sibling 当前覆盖的对象则更偏 reusable local state：

- 会在同一测试里被再次复用的 task / fixture / helper 对象
- 可重复 `Open()` / `Reopen()` / `Reset()` 的 executor / stateful helper
- 带内部子状态机的 resettable container / spill action / payload buffer
- 会被下游原地 mutate 的共享 expression constant / alias / template object
- 只在当前步骤临时翻转、但下一步还会继续共用同一 session / helper 的 test-local flag

这条的共同修法也很稳定：

- 下一次复用前显式把关键字段改回初始态，或者直接新建 fresh object
- 让 `Reset()` / `Open()` / `Reopen()` 真正递归清掉内部状态，而不是只清表层容器
- 对共享模板/常量先 `Clone()` 再传给会原地 mutate 的逻辑
- 对 session-local / helper-local 临时开关紧贴修改点做 `defer` restore
- 对会被下一阶段继续读的 fixture buffer，在切阶段前显式清空

这条 sibling 的 `v1` retrieval 会先偏向：

- `actionSpill.Reset()`
- `payloads = payloads[:0]`
- `OptimizerUseInvisibleIndexes`
- `task.State` / `task.Step` 回写
- `Open()` / `Reopen()` 附近成组出现的字段归零锚点
- `clone-before-mutate` 则留在带 `collation` / alias 语义的弱召回里

原因也很直接：

- 显式 reset/restore anchors 比 generic `Open()` / `Close()` / `Clone()` / session var 赋值更稳
- 默认第一跳先不把所有 helper restore、所有 `Close()`、或者所有 server harness recreate 裸扫进来，避免和 close-path / global-knob / harness-state 边界混在一起

第六条 sibling 当前覆盖的对象则更偏 test-binary / package-level harness state：

- package sandbox、`main_test.go`、`TestMain`
- store / domain / server / bootstrap harness
- server test one-shot channel / global binding / service readiness state
- real-TiKV / etcd / session-store 这类外部测试环境
- 返回 `clean func()` 的 helper factory，以及应当直接绑到测试生命周期的 cleanup

这条的共同修法也很稳定：

- 把测试拆到独立 package / `main_test.go` / `TestMain`
- 走完整 `stopServer(...)` / store-domain-server teardown 链，而不是只关最外层对象
- 在创建 harness 的同一层立即 `t.Cleanup(...)` / `defer`，不把 cleanup 散落在外围
- 对会跨多次启动复用的 harness-global 状态显式重建，例如 `RunInGoTestChan`
- 对 real-TiKV / etcd / store 这类外部环境显式清空/reset，而不是让下一条 case 接着吃旧环境

这条 sibling 的 `v1` retrieval 会先偏向：

- `RunInGoTestChan`
- `stopServer(...)`
- `clearTiKVStorage(...)`
- `clearEtcdStorage(...)`
- `ResetStoreForWithTiKVTest(...)`
- package sandbox / `TestMain` 则留在弱召回里补
- `testleak.AfterTest` + `CreateMockStoreAndDomain/newStoreWithBootstrap` + close 链这类旧一批 harness teardown 正例，则用额外的弱召回去补

原因也很直接：

- 这几条 anchor 更像“harness 级共享态没有重建或清掉”，纯度高于 generic `TestMain()` / `CreateMockStoreAndDomain()` / `goleak.VerifyTestMain(...)`
- package sandbox / `main_test.go` 这条虽然也很重要，但如果直接塞进默认第一跳，会把大量普通测试包初始化一起扫进来
- `testleak + close 链` 这条如果直接塞进默认第一跳也会把普通 harness 测试一起带进来，所以更适合做弱召回补充；当前 HEAD 上这条补充模板规模约 `23` 个文件

## 当前先不并进来的边界

下面这些即使表面上也带一点 cleanup / restore / config hunk，当前仍优先迁到边界，而不是并入这个 family：

- process-global knob / config / TTL / lease / retry 参数
- process-global logger / callback / singleton
- 只是在共享 namespace 上 save-and-restore 全局值，但没有真的换成独立 namespace
- patch 的一阶动作是删 `t.Parallel()` 或把 case 挪到 serial suite
- 只是 cleanup 旧残留，但没有把资源真正做成 per-test 唯一
- 只是把 lease / TTL / global knob 改成“看起来安全”的值，但没有把后台 component 真正停掉
- 只是 `sleep` / `Eventually` 等后台状态自然收敛，没有明确 stop/close/wait

## 方法论 Hard Rules

1. `234` 个 case 的 source set 只能定义 review 输入全集，不能定义 sibling。
2. 不要用下面这些字段决定 case 归类：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
   - `source_smells`
3. `subpatterns/*.json` 只能承接已经完成的人工归纳，不能反过来拿来套标签。
4. `retrieval_signals.json` 只服务 coarse retrieval。
   - 它允许 false positive
   - 它不能反过来定义 subpattern
5. 一旦某条粗筛信号把大量 global-knob / async-race boundary 拉进来，优先补 `negative_guards`，不要扩大 sibling 定义。

## 当前目录结构

- [test_isolation_and_state_pollution_234_case_人工review工作板.md](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/test_isolation_and_state_pollution_234_case_人工review工作板.md)
  - `234` 个 patch 的 patch-first 人工工作板
- [retrieval_signals.json](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/test_isolation_and_state_pollution/retrieval_signals.json)
  - 当前已 formalize sibling 的 coarse retrieval hints
- [给agent的仓库扫描检索信号.md](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/test_isolation_and_state_pollution/%E7%BB%99agent%E7%9A%84%E4%BB%93%E5%BA%93%E6%89%AB%E6%8F%8F%E6%A3%80%E7%B4%A2%E4%BF%A1%E5%8F%B7.md)
  - 当前 retrieval layer 的使用方式，以及第六条 sibling 的检索校准结果
- `subpatterns/`
  - 当前已 formalize 的 JSON：
    - `共享_namespace_资源必须_per_test_唯一化.json`
    - `后台_component_必须显式_Stop_Close_Wait.json`
    - `临时句柄_backend_engine_iterator_必须在所有退出路径上收口.json`
    - `test_注入的_hook_filter_matcher_必须缩作用域并在_cancel_切阶段时解绑.json`
    - `可复用_fixture_executor_stateful_helper_再次使用前必须_reset_restore_clone.json`
    - `server_harness_package_sandbox_级_test_global_状态必须重建或清理.json`

## 下一步顺序

在当前这 `6` 条 sibling 稳定后，下一步优先继续做第六条的边界校准：

1. 当前判断：package sandbox / `TestMain` 暂不再单拆成第七条 sibling。现有最纯的代表仍主要是 `pr-36506`、`pr-38808` 这类“给共享 harness/runtime 单独开 package sandbox”的修法分支，本体还是第六条里的 test-binary / harness-global state 隔离；而且这条弱召回在 TiDB HEAD 上单跑会膨胀到 `98` 个文件，独立成默认第一跳 sibling 的收益还不够。
2. 更值得继续压实的是第六条和 namespace / background-component / global-singleton 边界，尤其要分清：独立 package 只是为了拿到专属 harness/runtime，还是 patch 主体其实已经转成 path / port / binding / background loop / process-global singleton 这类别的机制。
3. `2026-04-18` 这轮第六条检索校准的当前结论也已经明确：
   - 用当前 `10` 条 representative positive patches 回放时，`broad_recall` 命中 `5 / 10`
   - `package_sandbox_weak_recall` 命中 `5 / 10`
   - `harness_teardown_weak_recall` 命中 `5 / 10`
   - 三者并集能回补到 `10 / 10`
   - 对应 TiDB HEAD 当前炸量大致是：`20 / 98 / 23`
   - 因此当前继续保持“默认第一跳偏窄 + 两条弱召回补齐”的结构，比把 `package sandbox / TestMain` 直接抬进默认 broad 更合理

## 使用方式

如果目标是继续细化这条 family，正确顺序仍然是：

1. 从 `234` 个 patch 的人工工作板出发
2. 逐条看 patch / test diff 本体
3. 先人工归纳共同机制
4. 再补充 / 合并 / 拆分 `subpatterns/*.json`

在这之前，不要把 `retrieval_signals.json` 当成分类器，也不要回退到 smell-level 大桶。
