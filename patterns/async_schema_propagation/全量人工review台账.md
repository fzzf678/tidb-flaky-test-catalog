# `async_schema_propagation` 全量人工 review 台账（patch-first）

> 说明：本台账只基于 **patch 本体** 做归因与去向判定；`cases/*.json` 里的 `analysis / fix_pattern / root_cause_explanation` 仅作为索引信息，不作为聚类或归因证据。

| case_id | pr_id | source smell | 最终去向 | 归属 subpattern | 一句机制说明 | 迁移目标（如有） |
|---|---:|---|---|---|---|---|
| pr-6950 | 6950 | async_schema_propagation | migrate | - | `information_schema.tables` 的 `table_rows` 断言依赖 stats handle 消费 DDL event；测试需显式 `HandleDDLEvent(<-DDLEventCh())` 把异步事件 drain 掉。 | `patterns/plan_stability_and_stats_dependency/subpatterns/统计信息真正_load_materialize_apply_之前不应断言依赖它的计划或统计输出.json` |
| pr-14305 | 14305 | async_schema_propagation | retain | `s3` | DDL 测试在高 schema churn 下触发 transient `InfoSchemaChanged` 类错误；通过调大 `@@global.tidb_max_delta_schema_count` 增强 schema diff 容量来“消化”异步传播抖动。 | - |
| pr-14976 | 14976 | async_schema_propagation | retain | `s3` | DDL 测试在 schema out-of-date 路径上偶发失败；通过调大 `domain.SchemaOutOfDateRetryTimes` 让重试窗口更大。 | - |
| pr-16511 | 16511 | async_schema_propagation | watchlist | -（singleton：只看到了 lease 旋钮） | 通过把 `schema lease` 从 `100ms` 提高到 `600ms` 增大 DDL/schema sync 的时间窗口以减轻抖动；但机制可复用边界尚不清晰。 | - |
| pr-18205 | 18205 | async_schema_propagation | watchlist | -（singleton：hook 顺序与 waitSchemaChanged） | DDL job state 迁移时回调（`OnJobUpdated`）若在 `waitSchemaChanged` 之前触发，会让测试观察到“状态已变但 schema 未同步”的窗口；修法是把回调移动到等待之后。 | - |
| pr-18468 | 18468 | async_schema_propagation | watchlist | -（singleton：schema version leap） | 等待 schema version 同步时用 `==` 会在版本跳跃（ver 直接变大）场景下卡死；修法是把条件改成 `>= latestVer`。 | - |
| pr-22307 | 22307 | async_schema_propagation | exclude | - | 主要是 DDL 中间态语义/可见性 bugfix：`UPDATE ... WHERE/ORDER BY` 不应显式使用 non-public 列；通过 name resolution 标记 `NotExplicitUsable` 让行为确定化，不是“异步传播等待/同步”类测试机制簇。 | - |
| pr-24082 | 24082 | async_schema_propagation | migrate | - | 用 failpoint `pause` + channel 显式同步替代固定 `sleep` 来编排 “DDL 与 txn commit 并发” 的时序；属于通用异步等待/同步 smell，而非 schema propagation 机制簇。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` / `async_wait_without_backoff` 方向） |
| pr-25184 | 25184 | async_schema_propagation | exclude | - | 以 “modify column type / OriginDefaultValue” 的产品语义与测试构造为主（DDL hook 下的 DML/断言改写），不落在 schema propagation/同步机制簇。 | - |
| pr-25384 | 25384 | async_schema_propagation | exclude | - | 以 “modify column type” 的产品语义（default value cast）与新增测试为主，不是传播等待/同步类机制簇。 | - |
| pr-37447 | 37447 | async_schema_propagation | watchlist | -（schema validator test 稳定化，但缺少 sibling） | `schema_validator_test` 去随机化：移除 `rand + sleep + ticker`，改为按需发放 lease/version，使 test 不再依赖真实时间推进。 | - |
| pr-37985 | 37985 | async_schema_propagation | watchlist | -（patch 只做 assert，未形成可复用修法） | 在 multi-schema change cancel hook 中加入 `assertMultiSchema` 校验 job/type/subjob 长度，提示“回调观察对象不稳定”；但 patch 未形成稳定可复用的过滤/once 修法簇。 | - |
| pr-43832 | 43832 | async_schema_propagation | migrate | - | DDL callback 误触发：仅按 `SchemaState==Public` 会命中非目标 job；修法是额外检查 `job.Type==ActionRenameTable`（并配套期望 err 非空）。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-46855 | 46855 | async_schema_propagation | watchlist | -（multi-mechanism，大 patch） | ingest 分区恢复测试大幅重构（抽 testutil、拆分 package、dist ctx + owner 切换）；仍遗留 “owner change 后等待上一个 owner loop 退出” TODO，难以提炼高纯 sibling。 | - |
| pr-46899 | 46899 | async_schema_propagation | migrate | - | DDL callback 需要对“非目标 job / MultiSchemaInfo 为空”的更新事件做过滤；修法是 `if job.MultiSchemaInfo == nil { return }`。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-46908 | 46908 | async_schema_propagation | exclude | - | 主要是分区 DDL 的产品 bugfix + 新增 unit test，不是“测试因异步传播假设导致不稳 → 加同步/等待/降断言”的机制簇。 | - |
| pr-46932 | 46932 | async_schema_propagation | migrate | - | disttask GC 测试从 `sleep` 改成 `Eventually` + channel 同步后台 loop，属于通用异步等待/轮询稳定化，不是 schema propagation 家族。 | `patterns/其他_smell_细化_backlog.md`（`time_sleep_for_sync` / `async_wait_without_backoff` 方向） |
| pr-53688 | 53688 | async_schema_propagation | watchlist | -（singleton：repair list 清理时序） | repair mode 下 “DDL 已 public 但 repair list 尚未清理” 会导致 InfoSchema 把表隐藏掉；修法是仅在 `tbl.State!=Public` 时 skip repaired table。 | - |
| pr-54367 | 54367 | async_schema_propagation | watchlist | -（候选：v1/v2 switch + full reload 触发 ErrInfoSchemaChanged） | infoschema v1↔v2 切换可能触发 full reload，schema validator delta 可能被 `Reset()`；测试在 `commit` 上接受 `ErrInfoSchemaChanged`，并把 `RefreshSession` 的 RNG seed 落日志以便复现。 | - |
| pr-54447 | 54447 | async_schema_propagation | retain | `s1` | 仅等 DDL job state（如 `delete only`）不足以保证当前 domain 已加载新 infoschema；修法是额外等待 `dom.InfoSchema().SchemaMetaVersion()` 推进。 | - |
| pr-54695 | 54695 | async_schema_propagation | retain | `s1` | DDL `public`/结束不代表 infoschema 已加载（尤其 v1→v2 full load）；修法是 `Eventually(dom.InfoSchema().SchemaMetaVersion() > v1)` 后再做后续断言/DML。 | - |
| pr-54958 | 54958 | async_schema_propagation | watchlist | -（singleton：lease 旋钮用于控制 schema syncer 时序） | `TestFailSchemaSyncer` 通过把 schema lease 拉长到 `10s` 来稳定 “syncer done 后禁止 DML 直到 loadSchemaInLoop 重启” 的时序观察。 | - |
| pr-55314 | 55314 | async_schema_propagation | exclude | - | 主要是产品 bugfix：避免在多 index 路径中污染 `opt.IgnoreAssertion`，与 schema propagation 机制无关。 | - |
| pr-56382 | 56382 | async_schema_propagation | exclude | - | 大型 feature/行为改动（Global Index + DDL 下 PointGet 等），包含多机制与多模块变更，不是可复用的“测试同步/等待”修法簇。 | - |
| pr-55831 | 55831 | async_schema_propagation | watchlist | -（multi-mechanism，大 patch） | TRUNCATE PARTITION + Global Index 改动巨大（多 domain、多 state、多访问路径）；包含测试调整但机制簇边界不清晰，先保留观察。 | - |
| pr-56786 | 56786 | async_schema_propagation | exclude | - | 分区 DDL rollback 的产品语义/索引状态管理为主（multi-domain tests 伴随），不属于可复用的测试同步机制簇。 | - |
| pr-57114 | 57114 | async_schema_propagation | exclude | - | 分区 reorg/并发 DML 的产品语义修复为主（patch 体量大），不属于测试同步机制簇。 | - |
| pr-62549 | 62549 | async_schema_propagation | exclude | - | modifying column 的产品状态机增强（removing/changing state 等）为主，多机制大 patch，不属于测试同步机制簇。 | - |
| pr-64397 | 64397 | async_schema_propagation | migrate | - | DDL callback 的稳定化：过滤 `JobStateSynced` 的回调、避免依赖 `dom.InfoSchema().TableByID`（可能与 schema 刷新时序耦合），改为按名称取表并用 history job 信息做校验。 | `patterns/race_condition_in_async_code/subpatterns/DDL_callback_目标_job_过滤_once_控制.json` |
| pr-65786 | 65786 | async_schema_propagation | retain | `s2` | stale read 的 infoschema 版本不应断言为固定 sentinel（如 `0`）；修法是按 `expectedTS` 调 `GetSnapshotInfoSchema(ts)` 推导期望版本再比较。 | - |
| pr-66732 | 66732 | async_schema_propagation | retain | `s2` | `dom.Reload()` 可能触发内部 infoschema 访问，导致 `recentMinTS` 非稳定；修法是先 reset，再只断言“不为 sentinel / 有序关系”等不变量。 | - |

## subpattern 索引

- `s1`：DDL 完成不等于 domain infoschema 已加载；断言前必须等 `SchemaMetaVersion` 推进
- `s2`：InfoSchema internal cache/TS 不能断言 sentinel；断言应基于 snapshot 或只校验不变量
- `s3`：SchemaOutOfDate/InfoSchemaChanged 的容错旋钮被测试调大（RetryTimes / max_delta_schema_count）

