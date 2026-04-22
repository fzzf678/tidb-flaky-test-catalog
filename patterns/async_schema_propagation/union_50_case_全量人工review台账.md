# `async_schema_propagation` × (`ddl_without_wait` + `schema_version_race`) union 全量人工 review 台账（patch-first）

> 说明：
>
> 1. 本台账是为了解决 `async_schema_propagation` smell 下 watchlist singleton 难以成簇的问题，因此把相邻方向的 smell（`ddl_without_wait`、`schema_version_race`）并入 union source set，再 **patch-first** 全量复读后反向抽“共享失稳机制 / 共享修法机制”的簇。
> 2. 本台账的归因与去向判定 **只基于 patch 本体**；`cases/*.json` 的 `analysis / fix_pattern / root_cause_explanation` 只作为索引，不作为聚类或归因证据。
> 3. `retain / exclude / migrate / watchlist` 的含义仍以本目录的 family 目标为准：只保留能稳定复用、边界清楚的“schema 异步传播/版本传播”相关机制；其余要么迁移到更匹配的 family，要么排除或先观察。

## Union source set

- smells：`async_schema_propagation` + `ddl_without_wait` + `schema_version_race`
- union 总数：`50`（去重后）
- patch-first 人工复读：`50 / 50`
- union case 索引：[`union_case_list.tsv`](./union_case_list.tsv)

## 全量台账（必须覆盖 union 全部 case）

| case_id | pr_id | smells_hit（索引） | 最终去向 | 归属 subpattern | 一句机制说明（patch-backed） | 迁移目标（如有） |
|---|---:|---|---|---|---|---|
| pr-6242 | 6242 | schema_version_race | exclude | - | DDL worker 单测移除不稳定的中间态校验（Stop/重建 DDL 后继续拿旧 table meta 做 index create），并补齐 DDL job 队列为空的判定；更像 DDL 内部测试重构，不是 schema 异步传播/等待类机制簇。 | - |
| pr-6950 | 6950 | async_schema_propagation | migrate | - | `information_schema.tables` 的 `table_rows` 断言依赖 stats handle 消费 DDL event；测试需显式 `HandleDDLEvent(<-DDLEventCh())` 把异步事件 drain 掉。 | `patterns/plan_stability_and_stats_dependency/subpatterns/统计信息真正_load_materialize_apply_之前不应断言依赖它的计划或统计输出.json` |
| pr-14305 | 14305 | async_schema_propagation,schema_version_race | retain | `s3` | DDL 测试在高 schema churn 下触发 transient `InfoSchemaChanged` 类错误；通过调大 `@@global.tidb_max_delta_schema_count` 增强 schema diff 容量来“消化”异步传播抖动。 | - |
| pr-14976 | 14976 | async_schema_propagation | retain | `s3` | DDL 测试在 schema out-of-date 路径上偶发失败；通过调大 `domain.SchemaOutOfDateRetryTimes` 让重试窗口更大。 | - |
| pr-16511 | 16511 | async_schema_propagation | watchlist | -（候选：schema lease 旋钮稳定化） | 通过把 `schema lease` 从 `100ms` 提高到 `600ms` 增大 DDL/schema sync 的时间窗口以减轻抖动；但机制可复用边界尚不清晰。 | - |
| pr-18205 | 18205 | async_schema_propagation,ddl_without_wait | watchlist | -（singleton：hook 顺序与 waitSchemaChanged） | DDL job state 迁移时回调（`OnJobUpdated`）若在 `waitSchemaChanged` 之前触发，会让测试观察到“状态已变但 schema 未同步”的窗口；修法是把回调移动到等待之后。 | - |
| pr-18468 | 18468 | async_schema_propagation | watchlist | -（singleton：schema version leap） | 等待 schema version 同步时用 `==` 会在版本跳跃（ver 直接变大）场景下卡死；修法是把条件改成 `>= latestVer`。 | - |
| pr-19580 | 19580 | schema_version_race | retain | `s4` | 在 schema state change/lock 相关测试里，执行 SQL/断言前强制 `domain.GetDomain(sess).Reload()`，把“domain infoschema/caches 已刷新”显式化，避免拿到旧 schema/旧 lock 元信息。 | - |
| pr-21491 | 21491 | schema_version_race | retain | `s4` | `unlock tables` 后追加 `dom.Reload()`，用“强制 reload schema”释放/刷新内部 cache，避免 explain/point-get 行为受旧 infoschema 状态影响。 | - |
| pr-21624 | 21624 | schema_version_race | retain | `s4` | `unlock tables` 后追加 `dom.Reload()` 作为同步屏障，避免后续 lock/point-get 路径仍读取到旧的 schema/lock 视图。 | - |
| pr-21664 | 21664 | schema_version_race | retain | `s4` | 把 DDL/lock/unlock 执行封装为 `MustExec + dom.Reload()` 的组合，保证每次状态切换后 domain infoschema 及时刷新（修复同一类 cache/lock 可见性抖动）。 | - |
| pr-22307 | 22307 | async_schema_propagation | exclude | - | 主要是 DDL 中间态语义/可见性 bugfix：`UPDATE ... WHERE/ORDER BY` 不应显式使用 non-public 列；通过 name resolution 标记 `NotExplicitUsable` 让行为确定化，不是“异步传播等待/同步”类测试机制簇。 | - |
| pr-24082 | 24082 | async_schema_propagation | migrate | - | 用 failpoint `pause` + channel 显式同步替代固定 `sleep` 来编排 “DDL 与 txn commit 并发” 的时序；属于通用异步等待/同步 smell，而非 schema propagation 机制簇。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` / `async_wait_without_backoff` 方向） |
| pr-25184 | 25184 | async_schema_propagation,ddl_without_wait | exclude | - | 以 “modify column type / OriginDefaultValue” 的产品语义与测试构造为主（DDL hook 下的 DML/断言改写），不落在 schema propagation/同步机制簇。 | - |
| pr-25384 | 25384 | async_schema_propagation,ddl_without_wait | exclude | - | 以 “modify column type” 的产品语义（default value cast）与新增测试为主，不是传播等待/同步类机制簇。 | - |
| pr-37447 | 37447 | async_schema_propagation | watchlist | -（schema validator test 稳定化，但缺少 sibling） | `schema_validator_test` 去随机化：移除 `rand + sleep + ticker`，改为按需发放 lease/version，使 test 不再依赖真实时间推进。 | - |
| pr-37985 | 37985 | async_schema_propagation | watchlist | -（patch 只做 assert，未形成可复用修法） | 在 multi-schema change cancel hook 中加入 `assertMultiSchema` 校验 job/type/subjob 长度，提示“回调观察对象不稳定”；但 patch 未形成稳定可复用的过滤/once 修法簇。 | - |
| pr-38906 | 38906 | ddl_without_wait | migrate | - | 为了“确保 DDL job 已写入系统表”直接插入固定 `time.Sleep(2s)`；属于通用 sleep-for-sync 稳定化，不应在 schema propagation family 内 formalize。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` 方向） |
| pr-39247 | 39247 | ddl_without_wait | migrate | - | multi-schema change cancel hook 先过滤 `job.Type`，避免回调对非目标 job 误触发；典型 DDL callback 目标过滤修法。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-40950 | 40950 | schema_version_race | exclude | - | 大体量 flashback cluster/备份链路相关产品 patch，夹带 domain/schema version 细节调整；机制混杂且非测试侧同步/等待修法，不适合并入本 family。 | - |
| pr-42311 | 42311 | ddl_without_wait | exclude | - | 以 Global Index 行为修复 + 新增覆盖测试为主（含 DDL callback 场景），但并非围绕“schema 异步传播导致断言不稳”的同步机制修法簇。 | - |
| pr-43832 | 43832 | async_schema_propagation,ddl_without_wait | migrate | - | DDL callback 误触发：仅按 `SchemaState==Public` 会命中非目标 job；修法是额外检查 `job.Type==ActionRenameTable`（并配套期望 err 非空）。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-46816 | 46816 | ddl_without_wait | migrate | - | 在轮询观察到 DDL job state 后再追加固定 `Sleep(50ms)`“等 infoschema load”；属于 sleep-for-sync workaround，不是可复用 readiness 信号。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` 方向） |
| pr-46855 | 46855 | async_schema_propagation,ddl_without_wait | watchlist | -（multi-mechanism，大 patch） | ingest 分区恢复测试大幅重构（抽 testutil、拆分 package、dist ctx + owner 切换）；仍遗留 “owner change 后等待上一个 owner loop 退出” TODO，难以提炼高纯 sibling。 | - |
| pr-46899 | 46899 | async_schema_propagation,ddl_without_wait | migrate | - | DDL callback 需要对“非目标 job / MultiSchemaInfo 为空”的更新事件做过滤；修法是 `if job.MultiSchemaInfo == nil { return }`。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-46908 | 46908 | async_schema_propagation,ddl_without_wait | exclude | - | 主要是分区 DDL 的产品 bugfix + 新增 unit test，不是“测试因异步传播假设导致不稳 → 加同步/等待/降断言”的机制簇。 | - |
| pr-46932 | 46932 | async_schema_propagation,ddl_without_wait | migrate | - | disttask GC 测试从 `sleep` 改成 `Eventually` + channel 同步后台 loop，属于通用异步等待/轮询稳定化，不是 schema propagation 家族。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` / `async_wait_without_backoff` 方向） |
| pr-48131 | 48131 | ddl_without_wait | migrate | - | DDL 测试在关键断言前插入固定 `time.Sleep(50ms)`（Issue 48123）；属于 sleep-for-sync workaround。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` 方向） |
| pr-50076 | 50076 | ddl_without_wait | exclude | - | 主要是 DDL runningJobs 的产品语义修复（processing/unfinished 语义拆分等）；非测试同步/等待机制簇。 | - |
| pr-51631 | 51631 | ddl_without_wait | exclude | - | 主要是分区 rollback/reorg 中间态的产品状态机修复；虽触及 DDL state，但不是可复用的测试稳定化修法簇。 | - |
| pr-53557 | 53557 | ddl_without_wait | migrate | - | DDL callback 触发条件从 “`StatePublic`” 收紧为 “`StatePublic && job.IsDone()`”，避免在未完成窗口误触发；典型回调过滤修法。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-53688 | 53688 | async_schema_propagation | watchlist | -（singleton：repair list 清理时序） | repair mode 下 “DDL 已 public 但 repair list 尚未清理” 会导致 InfoSchema 把表隐藏掉；修法是仅在 `tbl.State!=Public` 时 skip repaired table。 | - |
| pr-54367 | 54367 | async_schema_propagation | watchlist | -（候选：v1/v2 switch + full reload 触发 ErrInfoSchemaChanged） | infoschema v1↔v2 切换可能触发 full reload，schema validator delta 可能被 `Reset()`；测试在 `commit` 上接受 `ErrInfoSchemaChanged`，并把 `RefreshSession` 的 RNG seed 落日志以便复现。 | - |
| pr-54447 | 54447 | async_schema_propagation | retain | `s1` | 仅等 DDL job state（如 `delete only`）不足以保证当前 domain 已加载新 infoschema；修法是额外等待 `dom.InfoSchema().SchemaMetaVersion()` 推进。 | - |
| pr-54514 | 54514 | schema_version_race | exclude | -（更像“async stats load 的 schema 快照漂移”候选） | stats-lite/async stats 初始化/加载路径若耦合外部 `InfoSchema` 或假设存在性映射完整，会在 schema 视图漂移下出现不一致；patch 倾向通过降低对 `InfoSchema` 的耦合、弱化“必须存在”的强断言来稳定行为。 | - |
| pr-54695 | 54695 | async_schema_propagation | retain | `s1` | DDL `public`/结束不代表 infoschema 已加载（尤其 v1→v2 full load）；修法是 `Eventually(dom.InfoSchema().SchemaMetaVersion() > v1)` 后再做后续断言/DML。 | - |
| pr-54958 | 54958 | async_schema_propagation | watchlist | -（候选：schema lease 旋钮稳定化） | `TestFailSchemaSyncer` 通过把 schema lease 拉长到 `10s` 来稳定 “syncer done 后禁止 DML 直到 loadSchemaInLoop 重启” 的时序观察。 | - |
| pr-55314 | 55314 | async_schema_propagation | exclude | - | 主要是产品 bugfix：避免在多 index 路径中污染 `opt.IgnoreAssertion`，与 schema propagation 机制无关。 | - |
| pr-55730 | 55730 | schema_version_race | exclude | -（更像“async stats load 的 schema 快照漂移”候选） | 异步 stats load 若目标列已不在当前 schema（`InfoSchema` 查不到 ColumnInfo）仍继续合并会污染结果并导致不稳；patch 在 `GetColumnByID` 为空时删除 load item 并直接返回，显式容忍 schema 漂移。 | - |
| pr-55831 | 55831 | async_schema_propagation,ddl_without_wait | watchlist | -（multi-mechanism，大 patch） | TRUNCATE PARTITION + Global Index 改动巨大（多 domain、多 state、多访问路径）；包含测试调整但机制簇边界不清晰，先保留观察。 | - |
| pr-56029 | 56029 | ddl_without_wait | watchlist | -（multi-mechanism：multi-domain/schema version） | 多 domain + schema version 交错的测试/产品 patch 串，包含 `dom.Reload()` 与版本断言；但 patch 体量过大、机制混杂，暂不作为高纯 sibling。 | - |
| pr-56327 | 56327 | schema_version_race | migrate | - | DDL job 轮询等待里每轮新建 `testkit`/session 会引入额外 schema reload/资源抖动；修法是复用同一个 `tk` 进行轮询查询。 | `patterns/其他_smell_细化_backlog.md`（`async_wait_without_backoff` / “轮询副作用” 方向） |
| pr-56382 | 56382 | async_schema_propagation,ddl_without_wait | exclude | - | 大型 feature/行为改动（Global Index + DDL 下 PointGet 等），包含多机制与多模块变更，不是可复用的“测试同步/等待”修法簇。 | - |
| pr-56786 | 56786 | async_schema_propagation | exclude | - | 分区 DDL rollback 的产品语义/索引状态管理为主（multi-domain tests 伴随），不属于可复用的测试同步机制簇。 | - |
| pr-57114 | 57114 | async_schema_propagation,ddl_without_wait | exclude | - | 分区 reorg/并发 DML 的产品语义修复为主（patch 体量大），不属于测试同步机制簇。 | - |
| pr-59974 | 59974 | schema_version_race | retain | `s1`（variant：多阶段等待需更新 baseline） | 通过 `SchemaMetaVersion` 等待“新 infoschema 已加载”作为断言前屏障，并在多阶段 state 之间更新 `v1=v2`，避免后续等待退化为 no-op；同时用额外 txn/MDL 控制 DDL state 观察窗口。 | - |
| pr-62549 | 62549 | async_schema_propagation,ddl_without_wait | exclude | - | modifying column 的产品状态机增强（removing/changing state 等）为主，多机制大 patch，不属于测试同步机制簇。 | - |
| pr-64397 | 64397 | async_schema_propagation,schema_version_race | migrate | - | DDL callback 的稳定化：过滤 `JobStateSynced` 的回调、避免依赖 `dom.InfoSchema().TableByID`（可能与 schema 刷新时序耦合），改为按名称取表并用 history job 信息做校验。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-65786 | 65786 | async_schema_propagation | retain | `s2` | stale read 的 infoschema 版本不应断言为固定 sentinel（如 `0`）；修法是按 `expectedTS` 调 `GetSnapshotInfoSchema(ts)` 推导期望版本再比较。 | - |
| pr-66732 | 66732 | async_schema_propagation | retain | `s2` | `dom.Reload()` 可能触发内部 infoschema 访问，导致 `recentMinTS` 非稳定；修法是先 reset，再只断言“不为 sentinel / 有序关系”等不变量。 | - |
