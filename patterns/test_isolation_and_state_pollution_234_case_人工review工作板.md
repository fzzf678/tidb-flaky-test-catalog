# `test_isolation_and_state_pollution` 234 case 人工 review 工作板

这个文件只记录一件事：

- 对 `234` 个 patch 做 `patch-first` 的全量人工复读

这里先把 `global_variable_mutation` 和 `insufficient_cleanup_between_tests` 合成一个临时方向来做人工聚类。

原因不是要把这两个 smell 直接 formalize 成一个 family，而是它们在 patch 层经常是同一个机制的两面：

- 前者更像“改了共享状态”
- 后者更像“没把它 restore / stop / close 干净”

在人工 review 完成之前，这里不接受：

- field-based 归桶
- 直接套用现有 `subpatterns/*.json`
- 根据 case JSON 里的解释字段先做初筛
- 看到 `global_variable_mutation` 或 `insufficient_cleanup_between_tests` 其中之一就先入为主下结论

## Hard Rules

1. source set 只由 `global_variable_mutation`、`insufficient_cleanup_between_tests` 两个 smell 的并集定义，共 `234` 个 case。
2. 进入人工 review 后，只看：
   - patch subject
   - 改动到的测试文件 / helper / runtime 路径
   - 实际 diff 行
3. 下面这些字段不能用来决定 case 属于哪个 sibling：
   - `root_cause_categories`
   - `fix_pattern`
   - `analysis`
   - `root_cause_explanation`
   - `module`
   - `source_smells`
4. `source_smells` 只能定义 source set 入口，不能决定 sibling。
5. 现有 `race_condition_in_async_code/subpatterns/*.json` 只能当边界参考，不能当分类器。
6. 这轮的目标是先重建机制簇，再决定先 formalize 哪几条；不要提前写 `rg_template`。

## 当前 source set 快照

- source set union：`234`
- 仅 `global_variable_mutation`：`139`
- 仅 `insufficient_cleanup_between_tests`：`79`
- 两个 smell 同时出现：`16`

相邻 smell 重叠提醒：

- 同时带相邻 smell 的 case：`45`
- 同时带 `race_condition_in_async_code`：`25`
- 同时带 `t_parallel_with_shared_state`：`18`
- 同时带 `shared_table_without_isolation`：`2`

这说明这条线里会有不少 boundary case。第一轮人工 review 时要先把边界切干净，不要急着追求 family purity。

模块分布只作为排队导航，不作为归桶依据：

- `executor`: `60`
- `test_infra`: `23`
- `ddl`: `23`
- `server`: `19`
- `planner`: `18`
- `domain`: `18`
- `session`: `18`
- `kv`: `13`
- `statistics`: `13`

## 已知 boundary 提醒

下面这些机制如果在 patch 中是主导信号，优先标成 boundary / migrate-out，不要并入当前主体：

1. 测试改 `lease / TTL / global knob` 前要先停后台 loop
2. 共享 `SessionVars / StmtCtx` 字段 save-and-restore，实质是共享字段竞态
3. process-global logger 替换导致并发 logger race
4. `GetGlobalConfig()` 原地改写，修成 `UpdateGlobal / StoreGlobalConfig / RestoreFunc`
5. cleanup / reuse / reset 路径清共享 map 时漏锁
6. 明显是 `t.Parallel()` 或并行 suite 下 shared-state test 混跑
7. 明显是共享 table / db / fixture namespace 没隔离

换句话说：如果 patch 的核心是“修并发竞态本身”，它通常更接近 `race_condition_in_async_code`；这里只有在 patch 的核心是“测试隔离 / 生命周期 / 污染收口”时才保留。

## 人工 review 记录轴

每条 patch 固定记录下面 4 个轴：

1. 污染对象是什么
   - process-global config / flag / env / timezone / sysvar / failpoint
   - runtime singleton
   - domain / store / session / server / cluster / worker
   - goroutine / watcher / iterator / listener / temp resource
   - schema / data fixture / table / db / file / port / path
2. 污染是怎么发生的
   - 直接改全局值
   - save-and-restore
   - shallow copy / alias
   - create 了资源但没 stop / close / wait
   - cleanup 不完整
   - 共享名字空间复用
3. patch 的稳定化动作是什么
   - restore
   - clone-then-publish
   - `t.Cleanup()` / `defer`
   - `Close / Stop / Shutdown / Wait`
   - unique namespace
   - 串行隔离
4. 它更像哪条边界
   - `race_condition_in_async_code`
   - `t_parallel_with_shared_state`
   - `shared_table_without_isolation`
   - 还是当前方向内的纯 test-isolation case

## 当前候选 sibling 假设

下面这些只是人工 review 假设，不是分类器：

1. 测试临时改 process-global 标量 / 配置 / 环境，但没有完整 restore
2. restore 看似存在，但 restore 不完整 / 不对称 / 时序不对
3. test 创建 domain / store / session / server / background component，但结束时没关干净
4. goroutine / watcher / listener / iterator / temp resource 生命周期没收口
5. 共享 fixture / db / table / file / port 命名空间没有隔离
6. 必须接管 process-global singleton 的测试，本质上应该串行隔离

第一轮人工 review 的目标，不是证明这 6 条一定都成立，而是看它们里哪些能长成真正稳定的 sibling。

## 建议的 review 输出格式

每条 case 暂时按下面的最小模板记：

```text
case_id:
patch_backed:
  - yes / no / boundary
polluted_object:
pollution_shape:
stabilization_action:
boundary_if_any:
notes:
```

不要在第一轮就写 verdict-layer 语言。先把机制记清楚。

## 完成状态

- 已人工 review：`234 / 234`
- patch-backed 支持当前方向：`93 / 234`
- 人工排除 / 边界迁出：`141 / 234`
- 待 review：`0 / 234`

## 第一批已读记录（`1-15`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-1301` | `boundary -> race_condition_in_async_code` | 全局 plan ID counter | 共享全局计数器被并发 builder 读写 | 改成 builder-local `allocID` | 核心是生产代码共享全局状态竞态，不是测试隔离 |
| `pr-2921` | `yes` | `copIterator` worker goroutine / task channel | `Close()` 后后台 worker 仍可能悬挂 | `finished` 感知 + 退出 worker；测试显式检查 goroutine 消失 | 强烈支持“iterator/resultset 早关后不能泄漏后台 goroutine”这条 |
| `pr-2968` | `boundary -> race_condition_in_async_code` | 全局 `TxnEntryCountLimit` | 测试改全局 limit，生产路径裸读写 | 改成 `atomic.Load/Store` | 更像全局标量开关竞态 |
| `pr-3098` | `no` | store / session helper | 主要是 feature patch，引入 `UnionScan` 测试 | 无明确 cleanup 稳定化主线 | patch 主体不支持当前方向，先排除 |
| `pr-3414` | `yes` | test store / domain goroutine / leaktest harness | 测试未 `Close()` store，且 leak detector 本身在 package parallel 下不稳 | 补 `defer store.Close()`；调整 `testleak` 使用方式 | 支持“test 创建 store/domain 后必须显式 teardown”与 test infra cleanup |
| `pr-3435` | `boundary -> race_condition_in_async_code` | 全局 `statsLease` | 测试通过全局 lease knob 影响后台 stats loop | suite setup 里 `SetStatsLease(0)` | 更接近“改 lease/global knob 前先停后台 loop” |
| `pr-3706` | `boundary -> race_condition_in_async_code` | process-global logger level | suite setup 改 logger level 导致 race | 直接删掉 `SetLevelByString` | 更接近 process-global logger 子模式 |
| `pr-4076` | `boundary -> race_condition_in_async_code` | 全局 `TurnOnNewExprEval` flag | 多个 test suite 并发读写全局布尔开关 | 改 `int32` + `atomic.Load/Store` | 典型全局标量开关竞态 |
| `pr-4532` | `boundary -> race_condition_in_async_code` | process-global logger init | 各 suite / init 重复初始化 logger | 把 `InitLogger` 移到 `TestT`，只做一次 | 仍是 process-global logger 竞态，不先并入当前方向 |
| `pr-4591` | `yes` | `domain` / store / bootstrap 后台 goroutine | 测试 bootstrap 后只关 store，不关 domain | `newStoreWithBootstrap` 返回 `dom`，测试里 `defer dom.Close()` | 很强地支持“domain/store/session/background component 没关干净” |
| `pr-4733` | `boundary -> race_condition_in_async_code` | 全局 schema retry knobs | 测试临时改 `SchemaOutOfDateRetry*` 全局变量 | 改成 `atomic` 访问 | 更像全局 scalar knob 竞态 |
| `pr-5020` | `boundary -> race_condition_in_async_code` | `RecordSet` / testkit result lifecycle | `MustExec` 对返回结果不 `Close()`，并与同 session 后续执行交叉 | `MustExec` 自动 `Close()` result；相关测试改 `MustQuery()` | 与“同一 session 上一个 `RecordSet` 未关闭就继续执行”高度重合 |
| `pr-5654` | `yes` | `copIterator` / caller goroutine / response channel | `Close()` 后再 `Next()` 可能永远等 `taskCh` | `finished` 感知的 recv，关闭后 `Next()` 立即退出 | 与 `pr-2921` 同簇，都是 iterator early-close 生命周期问题 |
| `pr-6140` | `yes` | `copIterator.Close()` / worker response channel | `Close()` 等待 worker 退出，但 worker 发 response 时无人接收，导致 hang / leak | `sendToRespCh` 与 `recvFromRespCh` 同时监听 `finished` | 与 `pr-5654` 同簇，都是 close-path 资源收口不完整 |
| `pr-6548` | `boundary -> race_condition_in_async_code` | 全局 binlog ignore-error flag / config | 测试与运行期共享 ignore-error 状态 | 改成独立 `atomic` 标志 | 更像全局 config / flag 竞态，不是测试隔离主簇 |

## 第一批初步聚类线索

从前 `15` 条 patch 看，当前方向至少已经出现了两条可继续追的主线：

1. `domain / store / test harness` teardown 不完整
   - 当前正例：`pr-3414`, `pr-4591`
   - 共同点：
     - 测试会创建 store / domain / bootstrap 后台 goroutine
     - 原先 teardown 只关一部分，或 leak detector 使用方式不对
     - 修法是显式 `Close()` / 调整 suite 级 cleanup
2. `iterator / resultset / worker` 早关或 close-path 收口不完整
   - 当前正例：`pr-2921`, `pr-5654`, `pr-6140`
   - 共同点：
     - 调用方提前 `Close()` 或关闭后仍有后台 worker / channel path 在跑
     - 泄漏形态是 goroutine 不退出、`Close()` hang、`Next()` hang
     - 修法是让 close-path 也监听 `finished` / stop signal，保证后台路径及时退出

同时，前 `15` 条里还有一个非常明显的 migrate-out 簇：

3. process-global scalar / logger / lease knob 竞态
   - 当前 boundary：`pr-1301`, `pr-2968`, `pr-3435`, `pr-3706`, `pr-4076`, `pr-4532`, `pr-4733`, `pr-6548`
   - 这些 patch 的主导修法都是：
     - `atomic`
     - builder-local / local state
     - `TestT` 单次初始化
     - 全局 knob 改写
   - 这组目前更适合迁到 `race_condition_in_async_code` 或其相邻 global-state 子簇，不作为当前方向主体

## 第二批已读记录（`16-20`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-6554` | `boundary -> race_condition_in_async_code` | 全局 binlog ignore-error flag | 测试开启 ignore-error 后需要显式复位 | `SetIgnoreError(true/false)` 配对调用 | 仍是 process-global flag 竞态 / restore 问题，先迁边界 |
| `pr-6950` | `boundary` | stats handle / DDL event visibility | 测试依赖 stats lease 与 DDL event 刷新时序 | `SetStatsLease(0)` + 手动消费 `DDLEventCh()` | 更像 async propagation / global knob，不先并到当前方向 |
| `pr-7232` | `boundary -> race_condition_in_async_code` | 全局 `PreparedPlanCacheEnabled` | 测试与运行期共享 prepared-plan-cache 开关 | `SetPreparedPlanCache()` + `atomic` accessor | 典型全局 scalar config 竞态 |
| `pr-7937` | `yes` | 共享 database / table fixture 名字 | 同一测试里频繁 `drop table` 后复用相同名字，清理窗口与后续断言交叉 | 改成独立 database / table 名字，减少复用并集中 cleanup | 强烈支持“共享 fixture / namespace 没隔离”这条 |
| `pr-8585` | `yes` | 共享 database / table fixture 名字 | 多处 `drop table if exists` + 同名复用，使测试依赖前一步 cleanup 完成 | 改成唯一表名 / 数据库级 cleanup | 与 `pr-7937` 同簇，都是 namespace 隔离优先于反复 drop/recreate |

## 第二批增量线索

在 `16-20` 这批里，当前方向又出现了第三条可继续追的主线：

4. 共享 fixture / database / table namespace 没隔离
   - 当前正例：`pr-7937`, `pr-8585`
   - 共同点：
     - 测试反复 `drop table if exists` 后复用相同对象名
     - 测试正确性隐含依赖前一步 cleanup 已完全生效
     - 修法不是补 sleep，而是改成唯一对象名，或把 cleanup 提升到 database 级别一次性收口

同时，这批又确认了一点：

5. `stats lease` / `DDL event` / visibility 这类 case 目前不要急着并到当前方向
   - `pr-6950` 看起来更像 async propagation / global knob
   - 先保持 boundary，避免把“测试隔离”与“异步可见性”混成一桶

## 第三批已读记录（`21-30`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-8719` | `boundary -> race_condition_in_async_code` | 全局 `EnableSplitTableRegion` | 测试打开 split-table 全局开关，同时 DDL / server 路径读同一标志 | `bool` 改 `uint32`，读写改 `atomic.Load/Store` | 标准 process-global split knob 竞态，不并入当前主体 |
| `pr-8724` | `boundary -> race_condition_in_async_code` | 全局 `TableColumnCountLimit` | 测试临时改列数上限，DDL 校验路径并发读取同一全局值 | `uint32` + `atomic.Load/Store` | 典型全局 scalar limit knob 竞态 |
| `pr-8807` | `boundary -> race_condition_in_async_code` | process-global `ExpensiveThreshold` / `AllowCartesianProduct` | 测试修改全局阈值与 planner 开关，和包级并发测试混跑会互相污染 | 把相关测试移到 `seqtest` 串行执行 | 很像“必须串行接管 process-global singleton”；先按边界保留，后续可再判断要不要单列 sibling |
| `pr-9119` | `boundary -> race_condition_in_async_code` | 全局 `CommitMaxBackoff` | 测试会改 backoff 全局值，而异步 commit goroutine 迟后读取这个 knob | 在 goroutine 外先构造 `secondaryBo`，避免后台路径再碰全局值 | 非 cleanup 问题，核心是“global knob + background goroutine” |
| `pr-9412` | `boundary -> race_condition_in_async_code` | 包级 mock retry 标志 `hasMockAutoIDRetry` | gofail/mock 路径对 package-global retry flag 无同步读写 | 改 `int64` + `atomic` 包装读写 | 本质是 package-global failpoint/mock 状态竞态 |
| `pr-9483` | `boundary -> race_condition_in_async_code` | 全局 `ddl.ReorgWaitTimeout` | cancel-drop 类测试通过 save-and-restore 临时改全局 timeout | 直接删掉测试里的 timeout 改写 | 还是全局 timeout knob，边界簇继续扩大 |
| `pr-9534` | `boundary -> race_condition_in_async_code` | process-global logger / hook | 统计测试需要抓日志，旧 hook / global logger 路径会与其他 suite 共享全局 logger | 改成 suite 级 zap core capturer + 新 logger 接口 | 落在 process-global logger 子簇，不是 teardown / cleanup 主体 |
| `pr-9960` | `boundary -> race_condition_in_async_code` | 全局 config `TreatOldVersionUTF8AsUTF8MB4` | 测试会切换全局 charset knob，builder 路径读这个配置 | 改短路顺序，优先按 table version 返回，减少不必要的全局读取 | 仍是 global config knob 竞态 |
| `pr-10003` | `boundary -> race_condition_in_async_code` | process-global logger | 新增 OOM 测试通过 `log.ReplaceGlobals` 捕获日志，最终被认定会引入 data race | 最终直接 `c.Skip(...)` 避免 suite 混跑 | patch 主体是功能开发；flaky 相关部分再次证明 global logger 簇应迁出 |
| `pr-10295` | `boundary -> race_condition_in_async_code` | process-global config / hot-reload globals | 热加载 + 测试同时覆盖 `globalConf`、prepared-plan-cache、feedback、backoff 等多个全局 knob | 大量尝试 `atomic` / pointer-swap / `Store()` 化读写 | 是“全局热更新配置竞态”的大型 umbrella case，不适合留在当前方向 |

## 第三批增量线索

这 `10` 条几乎没有给当前方向新增主体正例，反而把一个 boundary 簇彻底压实了：

6. process-global config / logger / timeout / hot-reload knob
   - 当前增量 boundary：`pr-8719`, `pr-8724`, `pr-8807`, `pr-9119`, `pr-9412`, `pr-9483`, `pr-9534`, `pr-9960`, `pr-10003`, `pr-10295`
   - 共同点：
     - 测试会临时改 process-global scalar / config / logger / timeout
     - 生产或后台 goroutine 仍会在别处读取这些值
     - 修法通常是 `atomic`、提前 capture、删除测试改写、或强制串行执行
   - 这组已经足够大，后续应单独沉淀为 global-state / async 边界簇，而不是继续混在当前方向里

7. “串行隔离接管 process-global singleton”的 patch 先继续当 boundary 看
   - 代表：`pr-8807`
   - 它和纯 `atomic` 修法不同，因为稳定化动作是搬去 `seqtest`
   - 但它的污染对象仍然是 process-global singleton；在当前阶段先不急着把它吸进当前主体

## 第四批已读记录（`31-40`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-10848` | `boundary -> race_condition_in_async_code` | process-global `EnableTableLock` | DDL 测试在普通 suite 里 save-and-restore 全局 table-lock 配置，和其他测试混跑会互相污染 | 把 config-mutating 测试移到 `serial_test`，其余 suite 只保留固定值 | 又一个“串行接管 process-global singleton”的边界样本 |
| `pr-10855` | `boundary -> race_condition_in_async_code` | process-global config knobs | 仍会改全局配置的测试在 `-race` 下不稳定 | 直接在 race build 下 `c.Skip(...)` | 这是 band-aid，不是主体方向的 cleanup / lifecycle 修法 |
| `pr-10900` | `boundary -> race_condition_in_async_code` | table-lock enable 全局检查逻辑 | 测试通过共享全局 config 影响 table-lock 行为 | 用 test-local `tableLockEnabled` + `atomic`，并覆盖 `config.TableLockEnabled` | 本质仍是 global config / function override 竞态 |
| `pr-10949` | `yes` | bindinfo 背景 lease loop | suite bootstrap 前没有先停 bindinfo 背景组件，默认 lease 会把异步路径带起来 | 在 `BootstrapSession` 前先设 `bindinfo.Lease = 0` | 很像“先停后台 loop，再进测试 harness”的早期样本 |
| `pr-10953` | `yes` | stats background worker / stats lease | 大量测试只写 `SetStatsLease(0)`，但 domain 仍会拉起 stats worker，测试环境并不真正静默 | 增加 `DisableStats4Test()`，并在 `UpdateTableStatsLoop` 里对负 lease 直接不启动 `loadStatsWorker` | 这是当前方向很强的新簇：测试 harness 需要显式禁用背景组件 |
| `pr-11121` | `boundary -> race_condition_in_async_code` | process-global `EnableTableLock` config | 针对 `#10900` 的改进版，仍是在测试里接管共享全局配置 | clone config 后 `StoreGlobalConfig(&newCfg)`，并在 defer 中恢复旧 config | 比 `atomic` 本地影子变量更干净，但仍属于 global config boundary |
| `pr-11204` | `boundary -> race_condition_in_async_code` | process-global `Security.SkipGrantTable` | 测试临时改 security 全局配置后 bootstrap / flush privilege 路径会看到共享值 | 保存旧 config，发布新 config，测试后恢复 | feature patch 里夹带的 global config race 修补，不并入主体 |
| `pr-12796` | `boundary -> race_condition_in_async_code` | process-global `CheckMb4ValueInUTF8` | `statement_context_test` 临时改 UTF8 检查开关 | 取当前 config，改字段后 `StoreGlobalConfig`，结束再恢复 | 大 feature PR 里的 late race fix，仍是标准 global config singleton 问题 |
| `pr-12910` | `boundary -> race_condition_in_async_code` | 全局 `schemaLease` / `statsLease` | 测试调 `SetSchemaLease/SetStatsLease` 时，domain bootstrap 另一边也在读同一对全局 lease | 把 lease 改成 `atomic` int64，统一 `Load/Store` | 它反向证明：如果只是同步 lease knob，本质仍是 global-state race，不如直接别把后台 loop 拉起来 |
| `pr-13112` | `boundary -> race_condition_in_async_code` | 全局 `PessimisticLockTTL` | 测试在 `SetUpTest` 里每次重写 TTL，全局 knob 与其他路径共享 | 把 TTL 设置提升到 `OneByOneSuite` 的 `SetUpSuite` | 又一个“串行隔离 process-global TTL”的边界样本 |

## 第四批增量线索

这批里当前方向第一次出现了比较清晰的新主线：

8. bootstrap 前就禁用背景 lease/worker，而不是只把 lease knob 改成一个“看起来安全”的值
   - 当前正例：`pr-10949`, `pr-10953`
   - 共同点：
     - 测试会 `BootstrapSession` / 拉起 domain
     - 但 bindinfo / stats 这类背景组件如果没有在 bootstrap 前禁掉，仍会异步运行
     - 修法是：在 harness setup 阶段就把 lease 设成“不会启动 worker”的值，或在 domain 初始化里直接不启动 loop
   - 这条很值得后续单独长成 sibling；它比“atomic 掉 lease 变量”更接近 deterministic-first 的测试隔离修法

9. 对照组也更清晰了：table-lock / charset / grant / ttl / lease 这些 process-global singleton patch 继续堆到 boundary
   - 当前增量 boundary：`pr-10848`, `pr-10855`, `pr-10900`, `pr-11121`, `pr-11204`, `pr-12796`, `pr-12910`, `pr-13112`
   - 共同点：
     - 核心动作仍然是改 process-global config / TTL / lease
     - 稳定化手段是串行化、`StoreGlobalConfig`、`atomic`
   - 这一组和 `pr-10949` / `pr-10953` 的区别非常关键：前者是在共享 singleton 上修同步，后者是在 test harness 层直接不让后台组件起来

## 第五批已读记录（`41-50`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-13169` | `boundary -> race_condition_in_async_code` | process-global `CheckMb4ValueInUTF8` config | 测试临时改全局 UTF8/MB4 检查开关，statement context 路径并发读取共享 config | clone 当前 config 后 `StoreGlobalConfig(&conf)`，结束再恢复 | 还是标准 global config singleton 竞态，不是 test lifecycle 主体 |
| `pr-13553` | `boundary -> race_condition_in_async_code` | process-global `tikv.PrewriteMaxBackoff` knob | pessimistic 测试改全局 backoff，异步事务路径会看到共享值 | 提前设置并在 suite close 后恢复 | 核心仍是 process-global knob，而不是 cleanup 主线 |
| `pr-13580` | `boundary -> t_parallel_with_shared_state` | session / planner suite 共享 bootstrap 状态与公共 harness | patch 主体是“修 parallel test”：拆 suite、把部分用例移到 serial、给 `storeBootstrapped` map 补锁、并修一处 domain/store close 顺序 | suite 拆分、串行隔离、锁住共享 bootstrap map、调整 defer 顺序 | 虽有一点 teardown 味道，但主导机制还是 parallel mixing 下的共享 harness 污染 |
| `pr-13859` | `boundary -> race_condition_in_async_code` | 包级 `SchemaChangedWithoutRetry` 标志 | schema checker 测试与运行路径共享布尔标志，产生 data race | `bool` 改 `uint32` + `atomic` | 典型共享标志竞态，不保留在当前主体 |
| `pr-14179` | `boundary -> race_condition_in_async_code` | process-global logger / OOM action / OOM test harness | `log.ReplaceGlobals`、OOM 全局动作、suite 级 store/domain 混在 feature patch 里一起调整；问题核心是共享 logger / config 与异步路径交叉 | 把 OOM suite 搬到 `seqtest`，补 `TearDownSuite` 关闭 `do/store`，并调整 OOM 配置测试 | 有 cleanup hunk，但主要风险仍是 global logger / global OOM config 的共享状态竞态 |
| `pr-14296` | `yes` | server/status 端口、HTTP test client、history jobs registry、并行 suite 级 runtime | 启用并行单测后，大量 server/http/statistics 测试共用固定端口、共享 status endpoint、共享 analyze history jobs，测试间还会混跑一批需要串行的 suite | 生成唯一 port/statusPort、把状态访问封装到 per-suite client、`ClearHistoryJobs()`、并将共享 runtime / 全局配置测试移到 `SerialSuites` | 这是当前方向的重要正例：不是修全局值同步，而是给测试 runtime 做 namespace isolation + lifecycle 隔离 |
| `pr-14592` | `yes` | mock store / RPC client / MVCC store / leak-check harness | 测试或 client 关闭链不完整，导致底层 store 资源与 goroutine 泄漏到后续测试 | 补 `mvccStore.Close()`，让 `RPCClient.Close()` 级联关闭资源，把 region-split 资源局部化并在测试里 `defer` 回收 | 明确强化“domain/store/test harness teardown 不完整”这条主簇 |
| `pr-14615` | `boundary -> race_condition_in_async_code` | process-global `IsolationRead.Engines` config | 集成测试改全局 isolation-read 配置，靠 suite 串行避免互相污染 | 把相关 suite 改成 `SerialSuites`，去掉原来的 defer-restore 舞步 | 仍是 process-global config singleton 的串行隔离样本 |
| `pr-14681` | `boundary -> race_condition_in_async_code` | process-global OOM / tmp-storage 相关配置 | `TestFlushPrivilegesPanic`、`TestSortSpillDisk` 这类测试会碰共享全局配置，和其他用例并行时互相污染 | 把对应 suite / 用例挪到 `SerialSuites` | 机制主轴还是共享全局 config，而不是 cleanup / resource lifecycle |
| `pr-14732` | `boundary -> race_condition_in_async_code` | process-global `wordBufLen` | decimal 测试会改共享全局缓冲长度，其他测试并发读写同一值 | 新建 `testMyDecimalSerialSuite`，让会碰全局值的用例串行执行 | 又一个“串行接管 process-global singleton”的边界样本 |

## 第五批增量线索

10. `domain / store / test harness` teardown 不完整这条主簇被继续强化
   - 新增正例：`pr-14592`
   - 共同点：
     - patch 不是去改共享全局值，而是去补底层资源的 close 链
     - 泄漏对象包括 mock store、RPC client、MVCC store、region split 相关局部资源
     - 修法都是让测试或 client 生命周期在退出时真正收口
   - 这说明当前方向里“资源没关干净”不只发生在 domain/store bootstrap，也会落在更底层的 test infra / mock runtime

11. 并行执行下的 server / status / history runtime namespace 隔离值得单独盯
   - 当前强正例：`pr-14296`
   - 共同点：
     - 一旦把单测切到 parallel，固定端口、固定 status 端口、共享 history registry 立刻暴露为测试间污染面
     - 修法不是补等待，而是给每个 suite 分配独立 port / status client，外加在共享 registry 上做显式清理
   - 这条目前和 `共享 fixture / namespace 没隔离` 很接近，但对象从 table/db 名字扩展到了 server runtime / HTTP endpoint / registry 级别

12. parallel test mixing 这条边界也被进一步压实
   - 当前增量 boundary：`pr-13580`
   - 共同点：
     - patch 主体是拆 suite、把部分 case 改为 serial、或给共享 bootstrap map 补锁
   - 这类 patch 虽然会顺带碰到 cleanup 顺序，但主导问题还是并行混跑下的 shared harness
   - 后续这类 case 优先迁到 `t_parallel_with_shared_state`，不要因为里面带一两处 `Close()` / `defer` 改动就误吸进当前主体

## 第六批已读记录（`51-60`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-14746` | `yes` | 未回滚的事务状态 + 共享 KV key namespace | 一处 optimistic conflict 测试在失败 commit 后未显式 rollback；另一处 snapshot 测试复用过于通用的 key 名，和并行测试容易互相干扰 | 失败路径补 `rollback`；把 key 改成 test-specific 唯一名字 | 一个 patch 里同时出现了“事务 dirty state 要显式清掉”和“共享 key namespace 要隔离”两种当前方向信号 |
| `pr-14756` | `boundary -> race_condition_in_async_code` | process-global prepared-plan-cache config | 多个测试通过改全局 prepared-plan-cache 开关/容量/内存上限来驱动行为，和其他测试共享同一套 singleton | 改成 session-local cache（`CreateSession4TestWithOpt` + `SimpleLRUCache`） | 主导机制是 global config / cache singleton 竞态 |
| `pr-14825` | `boundary -> race_condition_in_async_code` | process-global `TxnLocalLatches.Enabled` | 测试直接切换全局 local-latches 开关，其他路径会看到共享 config | clone config 后 `StoreGlobalConfig()`，结束再恢复 | 标准 process-global config singleton 样本 |
| `pr-14839` | `yes` | cluster log retriever goroutine / stream channel / cancel path | 检索日志时后台 goroutine 在 cancel 之后仍可能阻塞向结果 channel 发送，留下 goroutine 泄漏 | 增加 `exit` 信号，send 侧 select `exit`，统一 cancel 路径；suite teardown 继续显式 `dom.Close()/store.Close()` | 明确落在“worker / goroutine close-path 生命周期没收口”这条主簇 |
| `pr-14868` | `boundary -> race_condition_in_async_code` | process-global `variable.MaxOfMaxAllowedPacket` | `TestParseSlowLogFile` 会改共享全局包长上限，和其他测试并行会互相污染 | 把会改全局值的 token-too-long 检查拆到 `SerialSuite` | 又一个“串行接管 process-global scalar”的边界样本 |
| `pr-15119` | `yes` | mock pump payload buffer / binlog test fixture 状态 | sequence binlog 测试会读共享 mock pump 里的 payload；若前序测试残留 payload，不清空就可能读到旧 binlog | 在测试开头显式清空 `s.pump.mu.payloads`，再做轮询校验 | 这条很有代表性：共享 test fixture 自身需要 reset，不能只靠 sleep/重试 |
| `pr-15201` | `boundary -> race_condition_in_async_code` | process-global prepared-plan-cache config | point-get / prepare 测试仍在切全局 prepared-plan-cache 容量与内存保护参数 | 改成每个 session 自带独立 plan cache | 与 `pr-14756` 同簇，都是把 global cache config 下推到 test-local session |
| `pr-15245` | `boundary -> race_condition_in_async_code` | 全局 `TableStatsCacheExpiry` | 两个 infoschema 统计测试通过改同一个全局 expiry 变量来驱动行为，互相需要串行化 | 先用 mutex 串行保护这两个测试 | 本质还是共享全局 knob，不先并入当前主体 |
| `pr-15260` | `boundary -> race_condition_in_async_code` | 全局 `TableStatsCacheExpiry` / `OOMAction` + stats cache shared state | 延续 `#15245`：一边把统计 cache 改成 `RWMutex` 保护，一边把会改 `TableStatsCacheExpiry` / `OOMAction` 的测试移到 `SerialSuites` | 生产侧加锁 + 测试侧 serial suite + save/restore 全局配置 | 主轴仍是 global cache/config singleton 竞态，而不是 test cleanup 主簇 |
| `pr-15665` | `yes` | server/domain/store teardown 链 | `TestDumpStatsAPI` 只 `defer ds.server.Close()`，没有沿用 suite 的完整 stop 流程，domain/store/status server 都可能残留到后续测试 | 改成 `defer ds.stopServer(c)` | 明确强化“server/domain/store test harness 必须走完整 teardown 链” |

## 第六批增量线索

13. session / txn / mock fixture 的“脏状态没清掉”开始出现独立信号
   - 当前正例：`pr-14746`, `pr-15119`
   - 共同点：
     - 一个是失败事务没有 rollback，后续步骤继续跑在脏 session state 上
     - 另一个是 mock pump payload 缓冲区不清空，后续断言会读到前序测试残留
   - 修法都不是“再等一会儿”，而是显式 reset：`rollback` 或清空 fixture buffer

14. `iterator / resultset / worker` close-path 主簇继续扩大到了日志检索类后台 goroutine
   - 新增正例：`pr-14839`
   - 共同点：
     - cancel / close 之后后台 worker 仍可能卡在 channel send 或 stream recv
     - 修法是在 send/recv 路径都监听退出信号，保证 close-path 可收口
   - 这说明当前这条主簇不只限于 cop iterator，也包括任何 test 里会拉起的异步检索 worker

15. `domain / store / server` teardown 必须走完整 stop 链，而不是只关最外层对象
   - 新增正例：`pr-15665`
   - 共同点：
     - 单独 `server.Close()` 这类“看起来关了”的动作不一定会把 domain/store/status server 一起收掉
     - patch 倾向于复用统一的 `stopServer()` / suite teardown helper，而不是自己手写半套 cleanup
   - 这进一步强化了当前方向的一个判断：完整 teardown helper 比零散 `Close()` 更可信

16. prepared plan cache / table stats expiry 继续把 global-singleton 边界压实
   - 当前增量 boundary：`pr-14756`, `pr-14825`, `pr-14868`, `pr-15201`, `pr-15245`, `pr-15260`
   - 共同点：
     - patch 主体仍然是在共享全局 cache/config/scalar 上做隔离、加锁或串行化
   - 真正的稳定化动作要么是 session-local 化，要么是 serial suite / global config restore
   - 这些 case 后续继续迁到 `race_condition_in_async_code` 的 global-state 边界，不并入当前主体

## 第七批已读记录（`61-70`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-16722` | `boundary -> race_condition_in_async_code` | process-global logger / OOM config | OOM 测试通过替换全局 logger、改全局 OOMAction 来捕获行为；共享 singleton 和其他测试/异步路径会互相干扰 | 把整组 OOM 测试搬到独立 `oomtest` package，并用 `SerialSuites` 执行 | 尽管有 store/domain teardown，但主导问题仍是 global logger / global config |
| `pr-17206` | `boundary -> race_condition_in_async_code` | 全局 `tidb_scatter_region` + split-region 开关 | 测试依赖 ambient global scatter/split 配置，直接在测试里改全局值来固定行为 | 显式 `set global tidb_scatter_region = 1` | 本质仍是共享全局 knob；不是 cleanup/lifecycle 主体 |
| `pr-17437` | `boundary -> race_condition_in_async_code` | process-global failpoint state | analyze 测试因 failpoint 作用域与同 suite 其他用例混跑产生干扰 | 把 `TestFailedAnalyzeRequest` 挪到另一组 suite receiver | patch 太薄，主导信号仍是 failpoint/global state 隔离，而非当前主体 |
| `pr-17667` | `yes` | domain/store/testleak harness | `TestIntegration` 缺少 testleak 包装，也没有完整关闭 bootstrap 后拉起的 store/domain | 补 `testleak.Before/AfterTest`，并 `defer store.Close()` / `defer domain.Close()` | 很标准的“test harness teardown 不完整”正例 |
| `pr-17964` | `boundary -> race_condition_in_async_code` | process-global config | 大量测试直接原地改 `GetGlobalConfig()`，彼此共享同一 config 指针 | 新增 `config.UpdateGlobal()` / `RestoreFunc()`，全仓改成 clone-then-publish + restore | 这是 global config boundary 的集中治理，不并入当前主体 |
| `pr-18051` | `yes` | owner campaign goroutine lifecycle | `CampaignOwner()` 拉起后台 campaign loop 后，`Cancel()` 只发 cancel 不等 goroutine 真退出，测试容易留下泄漏 | 给 manager 加 `WaitGroup`，`Cancel()` 等 `campaignLoop` 退出 | 明确落在“后台 worker / goroutine 生命周期没收口”主簇 |
| `pr-18230` | `boundary -> race_condition_in_async_code` | 全局 `SchemaChangedWithoutRetry` 标志 | DDL 测试直接改包级全局标志来制造 schema-change 分支，和其他测试共享同一 flag | 删除一部分不稳定改写，把测试挪到另一 suite，并用 `defer` 恢复全局 flag | 仍是共享全局标志/并发干扰，不吸进当前主体 |
| `pr-18414` | `yes` | server test runtime：固定端口 + 未关闭 server | `TestDispatchClientProtocol41` 用固定端口，且未 `Close()` server，容易和其他 server test 相互影响 | 改用 `genPort()`，并 `defer server.Close()` | 是 `pr-14296` 之后又一个很干净的 server runtime namespace + teardown 正例 |
| `pr-18424` | `yes` | spill 测试的异步 row-container 行为 + serial suite 下的对象清理 | sort / merge-join in-disk 测试依赖 spill 异步动作完成，且 serial 测试创建的 table/view/sequence 若不统一清理会污染后续 case | 用 failpoint 等待 spill 行为完成，新增 `testSerialSuite1`，并在 `TearDownTest` 里统一 drop table/view/sequence | 这条同时覆盖了“异步 worker 要等结束”和“共享 fixture 名字空间要收口”两种主体信号 |
| `pr-18497` | `boundary -> race_condition_in_async_code` | process-global slow-query config | `TestSlowQuerySensitiveQuery` 会改全局 slow-query 相关配置，和别的测试混跑会互相污染 | 把它挪到独立 `SerialSuites` | 典型串行接管 process-global config 的边界样本 |

## 第七批增量线索

17. `domain / store / testleak` 这条 harness cleanup 主簇继续被强化
   - 新增正例：`pr-17667`
   - 共同点：
     - 不只是要 `Close()` runtime 资源，还要把 leak detector 按标准时机包起来
     - 缺任何一环，都可能把后台 goroutine/资源残留带到后续测试

18. `worker / goroutine` close-path 主簇继续扩展到了 owner campaign loop
   - 新增正例：`pr-18051`
   - 共同点：
     - 单纯发 cancel 不够，测试需要等后台 loop 真正退出
     - 修法从 channel/select 扩展到了 `WaitGroup` 式的显式 wait

19. server runtime 的端口隔离 + 关闭动作仍然是高价值正例
   - 新增正例：`pr-18414`
   - 共同点：
     - 一边是固定端口导致的 namespace 冲突
     - 另一边是 server 对象不关闭导致的 runtime 残留
   - 和 `pr-14296` 一起看，server 类测试的稳定化基本都要同时覆盖“唯一端口 + 完整 stop/close”

20. spill / tmp-storage 这类测试开始暴露“异步行为必须等完成 + fixture 要统一清理”的复合机制
   - 新增正例：`pr-18424`
   - 共同点：
     - 测试不光依赖全局 OOM/tmp-storage 配置，更依赖 spill 动作实际完成
     - 修法不是单靠串行，而是给异步行为加 test-only wait 点，并给 serial suite 加统一 `TearDownTest`
   - 这条后续值得继续观察，看它最终更接近 `worker lifecycle` 还是 `shared fixture namespace`

21. global logger / failpoint / config 这组边界继续变厚
   - 当前增量 boundary：`pr-16722`, `pr-17206`, `pr-17437`, `pr-17964`, `pr-18230`, `pr-18497`
   - 共同点：
     - patch 主轴都是在共享全局 logger / failpoint / config / sysvar 上做隔离
   - 修法是独立 package、serial suite、clone-then-publish、defer restore
   - 继续迁到 `race_condition_in_async_code` 的 global-state 边界，不并入当前主体

## 第八批已读记录（`71-80`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-18751` | `boundary -> race_condition_in_async_code` | 全局 `ManagedLockTTL` / `CommitMaxBackoff` | async commit 测试依赖共享 TTL / backoff，全局值在 test setup 阶段会影响其他路径 | 新增 test-only `noFallBack` knob，并把 `CommitMaxBackoff` 提到 suite 级初始化 | 主导问题仍是共享全局锁等待参数，不并入当前主体 |
| `pr-18963` | `yes` | goroutine lifecycle in pessimistic-lock test | 测试只校验阻塞顺序，不等待后台 goroutine 完整退出，导致 case 结束时仍有 goroutine 在跑 | 在 channel 协议里补最后一个退出信号，并显式 `<-ch` 等 goroutine 收尾 | 很干净的“spawn 了 goroutine 就要等它退出”正例 |
| `pr-19058` | `yes` | row container reset path / spill action state | `RowContainer.Reset()` 后没有把 spill action 状态一起 reset，后续再用时不能正确 spill | 在 `Reset()` 里重置 `actionSpill` 状态，并加回归测试验证 reset 后还能再次 spill | 属于典型 reset/cleanup 不完整，正好落在当前主体 |
| `pr-19434` | `yes` | mock TiKV server port、server lifecycle、test-local client config | 测试原先要扫固定端口区间、手动改全局 `GrpcConnectionCount`，而 mock server 也没有统一 stop | 改成端口 `0` 自动分配、`defer server.Stop()`，并把 grpc connection count 作为 test-local opt 传入 client | 这是 server/runtime namespace isolation 的又一个强正例，同时避免了全局 config 污染 |
| `pr-19484` | `yes` | validator test 的 store/domain teardown 时机 | `TearDownTest` 统一 close store/domain 的方式与具体测试的 leak-check 包装顺序不匹配，导致不稳定 | 把 `dom/store` 的关闭移到具体测试函数里，用局部 `defer` 和 `testleak.AfterTest` 对齐 | 再次说明资源关闭时机要跟测试本体绑定，不能只靠公共 TearDown |
| `pr-19526` | `no` | leak detector ignore list | patch 只是把若干后台 goroutine 加进 leaktest 白名单，减少 false positive | 扩 ignore list | 这是“放宽检测器”的样本，不是 cleanup/隔离机制本身，不计入当前主体 |
| `pr-19561` | `boundary -> race_condition_in_async_code` | failpoint/global-state heavy tests | 一批 failpoint / kill / split-region / repeatable-read 测试互相干扰，被整体挪到 `SerialSuites` | 扩大 serial suite 覆盖面，并微调部分时序断言 | 主轴仍是 failpoint/global-state 并行混跑，不并入当前主体 |
| `pr-19710` | `boundary -> race_condition_in_async_code` | 全局 `tikv.ManagedLockTTL` | pessimistic test 直接改全局 lock TTL，并在 case 结束时恢复 | `atomic.StoreUint64` + `defer` restore | 仍是共享全局 TTL knob 的边界样本 |
| `pr-19762` | `yes` | temp dir lifecycle / disk test runtime | 测试删除 temp dir 后，再初始化路径的 helper 不够稳，路径状态与测试预期脱节 | 改用 `CheckAndInitTempDir()` 重新检查并初始化 temp dir | 属于典型 temp resource lifecycle / namespace cleanup 正例 |
| `pr-19863` | `boundary -> race_condition_in_async_code` | process-global memory tracker maxConsumed | 测试依赖全局 memory tracker 的 `MaxConsumed` 副作用，并通过 test-only setter 改全局状态 | 直接删掉对 `SetMaxConsumed/MaxConsumed` 的断言与测试接口 | 核心是共享 global tracker 状态不可靠，仍属边界 |

## 第八批增量线索

22. “起 goroutine 就要等它退”继续从 worker/owner 扩展到锁冲突测试
   - 新增正例：`pr-18963`
   - 共同点：
     - 测试只验证中间顺序还不够，最后还要显式等待 goroutine 退出
     - 否则 case 表面通过，但后台执行尾巴会泄到后续测试

23. reset / reuse 路径如果不把内部 action 状态一起清掉，也属于当前主体
   - 新增正例：`pr-19058`
   - 共同点：
     - 外层容器已经 reset，但内部 spill action / state machine 还停在旧状态
     - 修法是让 reset 真正成为“全量复位”，而不是只清表面数据

24. test-local runtime 配置 + 唯一端口 + 完整 stop 的组合还在持续出现
   - 新增正例：`pr-19434`, `pr-19762`
   - 共同点：
     - 一类是网络/server runtime 要用局部配置和唯一端口
     - 另一类是 temp dir 这种磁盘 runtime 要在每次测试里重新检查/初始化
   - 它们本质上都属于“测试 runtime 名字空间和生命周期必须局部化”

25. 资源关闭时机必须贴着具体测试逻辑，而不是盲信公共 TearDown
   - 新增正例：`pr-19484`
   - 共同点：
     - 公共 `TearDownTest` 未必能和 testleak / 子测试内部时序对齐
     - 更稳的修法是把 close 动作用局部 `defer` 绑定到具体测试函数

26. boundary 里开始出现一类“只是放宽检测器/去掉断言”的排除样本
   - 当前排除：`pr-19526`
   - 共同点：
     - patch 没有真正让资源更干净，只是让 leak detector 少报
     - 这类样本后续不要误算成当前主体正例

27. global TTL / failpoint / memory tracker 这条边界继续扩张
   - 当前增量 boundary：`pr-18751`, `pr-19561`, `pr-19710`, `pr-19863`
   - 共同点：
     - 都是在共享的 test knob / failpoint / global tracker 上做串行化、restore 或直接删断言
   - 仍然优先迁到 `race_condition_in_async_code` 的 global-state 边界

## 第九批已读记录（`81-90`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-20142` | `boundary -> race_condition_in_async_code` | process-global `OOMAction` config | 测试直接改全局 OOMAction，和其他测试共享同一个 global config 指针 | 改成 `config.UpdateGlobal()`，并在结束时显式恢复 | 典型 global config singleton 边界 |
| `pr-21117` | `no` | session txn init path | patch 只是把 `NewTxn()` 后的 lazy txn 显式 materialize 一次 | 增加 `ts.se.Txn(true)` 断言 | 改动太薄，没形成明确的 cleanup / 污染 / 隔离机制，不纳入当前主体 |
| `pr-21415` | `boundary -> race_condition_in_async_code` | process-global `EnableCollectExecutionInfo` config | `SetSystemVar` 直接原地改全局 config 字段，产生共享 config race | clone config 后 `StoreGlobalConfig()` 发布 | 生产侧 global config race 修补，不并入当前主体 |
| `pr-21493` | `boundary -> race_condition_in_async_code` | process-global collation test knob | `collate.SetNewCollationEnabledForTest` 这类 test knob 会影响同进程其他测试 | 把对应 case 移到 `SerialSuites` | 又一个串行接管 process-global test knob 的边界样本 |
| `pr-21643` | `boundary -> race_condition_in_async_code` | 全局 `tikv.ManagedLockTTL` | pessimistic conflict 测试通过调大共享 TTL 来稳定锁行为 | `atomic.StoreUint64` + `defer` restore | 标准 global TTL knob 边界 |
| `pr-21664` | `boundary` | table-lock 全局配置 + DDL 后的 schema cache visibility | 测试依赖 `EnableTableLock` 全局配置，还要在 `lock/unlock tables` 后等 schema cache 真刷新 | 用 `SerialSuite` 隔离，`RestoreFunc()` 恢复配置，并把 DDL 包到 `mustExecDDL()+domain.Reload()` | 更像 global config + async propagation 边界，而不是当前主体 cleanup 机制 |
| `pr-21668` | `boundary -> race_condition_in_async_code` | process-global `MemoryUsageAlarmRatio` + tmp-storage spill test knob | sort/spill 测试临时改全局 memory alarm ratio，并补错误 trace | 保存旧值后恢复；增加错误 trace | 主体还是共享全局 knob，不并入当前主体 |
| `pr-22009` | `yes` | temp storage path namespace | disk 包测试默认共用一条 temp storage 路径，容易继承上次残留目录状态 | 在 `TestT` 里为整个包生成独立 temp dir，清空并重新创建 | 这是很干净的 temp resource namespace 隔离正例 |
| `pr-22276` | `boundary -> race_condition_in_async_code` | 全局 `ManagedLockTTL` + goroutine error reporting | 锁等待测试一方面依赖共享 TTL，另一方面原来在 goroutine 中直接做断言 | 提高 TTL 并恢复；改成错误通过 channel 回主 goroutine 断言 | 虽然同步方式更稳，但主导问题仍是 global TTL knob / async race |
| `pr-22916` | `yes` | snapshot fail tests 的 KV state cleanup | 多个 snapshot fail 用例会往同一个 mock store 留数据和 failpoint 状态，如果不清理会串扰后续测试 | 抽出 `cleanup(c)`，每个测试后遍历删 key；调整 failpoint disable 顺序 | 明确属于“测试数据/状态要在每个 case 后收口”的当前主体正例 |

## 第九批增量线索

28. temp resource / package-level runtime namespace 隔离继续被强化
   - 新增正例：`pr-22009`
   - 共同点：
     - 不只是单个 case 的 temp dir，连包级 `TestT` 入口也需要用独立 temp storage path
     - 修法是每轮测试启动时重新分配、清空、初始化专属路径

29. mock store / failpoint 类测试的数据清理需要下沉到“每个 case 后”
   - 新增正例：`pr-22916`
   - 共同点：
     - 同一个 suite 里多个 case 共用底层 store，只清 suite 级别不够
     - 更稳的做法是每个 test 自己 `defer cleanup()`，把写入的数据和状态全部抹掉

30. `global config / test knob / TTL` 这条边界持续扩张
   - 当前增量 boundary：`pr-20142`, `pr-21415`, `pr-21493`, `pr-21643`, `pr-21664`, `pr-21668`, `pr-22276`
   - 共同点：
     - patch 主轴仍是恢复、串行化或 clone-then-publish 全局配置 / test knob / TTL
     - 即便顺带补了 reload、channel 汇报错误等动作，主导机制依然不是当前主体的 cleanup/隔离簇

31. `async propagation / reload` 这类 case 先继续放在 boundary
   - 当前代表：`pr-21664`
   - 共同点：
     - DDL 执行后还要显式 `domain.Reload()` 才能让后续断言看到稳定状态
     - 它和当前方向有接壤，但更像“异步可见性/刷新时序”问题，不急着吸入当前主体

## 第十批已读记录（`91-100`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-22977` | `boundary -> race_condition_in_async_code` | process-global `config.Labels` / txn-scope 注入路径 | 多个测试直接改共享 `Labels["zone"]`，后续又改成 test failpoint 注入 txn scope，主轴都是绕 process-global config / test knob | 从原地改 `GetGlobalConfig()` 过渡到 `UpdateGlobal/RestoreFunc`，最终改成 failpoint 注入 | 虽然 patch 来回演化，但主导问题始终是共享全局 config / 注入点，不并入当前主体 |
| `pr-23122` | `boundary -> race_condition_in_async_code` | process-global `EnableTableLock` config | 点查测试直接改共享 table-lock 开关 | `UpdateGlobal` + `RestoreFunc` | 标准 process-global config singleton 边界样本 |
| `pr-23244` | `boundary -> race_condition_in_async_code` | region cache forwarding test knob / liveness 注入 | patch 早期用 package-global forwarding flag 与 failpoint 驱动测试，后期改成 `RegionCache.enableForwarding` 和 instance-local testing knob | 把共享全局 flag / failpoint 下沉到 cache 实例与 test-local mock | 核心是把共享 test knob 局部化，不是 cleanup/lifecycle 主体 |
| `pr-23502` | `yes` | `TestDropPartitionStats` 的共享 table / partition stats fixture | 同名表 `t` 直接复用，case 启动时没有先清旧表，且需要与其他统计测试隔离 | 挪到 `testSerialSuite`，并在测试开头显式 `drop table if exists t` | 是很干净的“共享 fixture 名字与残留表状态要先收口”样本 |
| `pr-23610` | `yes` | unix socket 路径 `new_session:0` | 上次运行残留的 socket 文件会污染下一次 `Listen("unix", ...)` | 测试前先 `os.Remove("new_session:0")` | 这是当前方向里很典型的 temp resource / path cleanup 正例 |
| `pr-24235` | `boundary -> race_condition_in_async_code` | process-global timezone / global failpoint init | 不同测试文件在 `init()` 里改 `timeutil.SetSystemTZ()`、启全局 failpoint，受 suite 启动顺序影响 | 把全局初始化收敛到 `TestT`，统一 enable/disable failpoint | 主导机制是 package/global init 次序与全局注入点，不并入主体 |
| `pr-24779` | `boundary -> race_condition_in_async_code` | process-global async-commit safe-window knob | 测试原先通过改全局 `SafeWindow` 来制造提交模式 | 改用 failpoint `invalidMaxCommitTS`，避免碰共享全局 knob | 明显是“不要改 process-global txn knob，用 test-local fault injection”边界样本 |
| `pr-24807` | `boundary -> race_condition_in_async_code` | process-global sysvar / HTTP settings config | `TestPostSettings` 通过接口改共享 config，测试尾部若不恢复会污染其他 case；后续还把该 case 挪到 serial suite | 恢复原值，并改成 `HTTPHandlerTestSerialSuite` | 虽然带 restore，但污染对象仍是 process-global config，优先放边界 |
| `pr-25035` | `yes` | CTE spill / row-container 异步 action + tmp-storage 测试状态 | `TestSpillToDisk` 只等了部分 spill action，`iterOutTbl` 的 spill 尾巴可能没收口；同时测试还会改 tmp-storage 相关配置与 mem quota | 在生产路径补 `iterOutAction.WaitForTest()`，测试移到 serial suite，并恢复 `OOMUseTmpStorage` / `tidb_mem_quota_query` | 和 `pr-18424` 很接近，属于“spill/tmp-storage 异步动作必须等完成”的当前主体正例 |
| `pr-26233` | `yes` | session-local `OptimizerUseInvisibleIndexes` 标志 | `admin check table` helper 把 session flag 打开后没恢复，后续同一测试里的查询还会沿用这个脏状态 | `defer` 把 `OptimizerUseInvisibleIndexes` 恢复为 `false` | 很标准的 reset/reuse 路径 cleanup 不完整正例 |

## 第十批增量线索

32. process-global config / test knob / init-order 边界继续明显扩张
   - 当前增量 boundary：`pr-22977`, `pr-23122`, `pr-23244`, `pr-24235`, `pr-24779`, `pr-24807`
   - 共同点：
     - patch 主轴都是避免直接改 process-global config、全局 failpoint、或 package-global test knob
     - 修法要么是 `RestoreFunc/UpdateGlobal`，要么直接换成 instance-local testing knob / failpoint 注入
   - 这组继续优先迁到 `race_condition_in_async_code` 的 global-state 边界

33. temp path / socket / 表对象这类共享 fixture 仍然是当前方向的稳定正例来源
   - 新增正例：`pr-23502`, `pr-23610`
   - 共同点：
     - 测试复用通用名字或路径时，会继承上一轮遗留状态
     - 修法不是加等待，而是 case 启动前先删旧表 / 旧 socket 文件，必要时再配合 serial suite

34. spill / tmp-storage 这条“异步 action 要等完成”主线被继续强化
   - 新增正例：`pr-25035`
   - 共同点：
     - 测试只验证查询结果还不够，spill 相关后台动作也要真正收尾
     - 修法是把 test-only wait 点补到所有参与 spill 的 action 上，而不是只在外层做断言

35. session helper / utility path 临时改内部 flag 后必须恢复原状态
   - 新增正例：`pr-26233`
   - 共同点：
     - 不是 process-global config，而是同一个 session / helper 在一次调用里偷偷打开某个内部标志
     - 如果不 restore，后续断言会在被污染的 session 状态上继续运行

## 第十一批已读记录（`101-110`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-26460` | `boundary -> race_condition_in_async_code` | process-global `MinLogScanCount` / `MinLogErrorRate` | 统计反馈相关测试直接改共享最小阈值，其他路径会读同一组 global threshold | 把全局阈值改成 `atomic`，测试侧统一 `Load/Store` | 是很典型的 global singleton threshold 边界样本 |
| `pr-26463` | `yes` | `TableInfo` shared meta pointer | 测试直接拿 `tb.Meta()` 并继续改，实际是在 alias 共享 schema meta 对象 | 改成 `tb.Meta().Clone()` 后再用 | 这是当前方向里第一条很干净的“shared meta alias / clone-before-mutate”正例 |
| `pr-26586` | `no` | sysvar validation test logic | patch 主体是补 coverage / helper test，并顺手删掉一段不稳定断言 | 增删断言与 helper case | 没看到稳定的 cleanup / 生命周期 / 共享状态收口机制，先排除 |
| `pr-26728` | `boundary -> race_condition_in_async_code` | global auto-analyze window / `AutoAnalyzeMinCnt` | `TestOutdatedStatsCheck` 会改全局 auto-analyze 时间窗与阈值，还需要 serial suite 才稳 | 挪到 serial integration suite，测试后恢复全局时间窗与阈值 | 主导问题仍是 process-global stats knob，不并入主体 |
| `pr-26848` | `no` | analyze-version expectation | patch 只是调整测试期望与 warning 检查，不再走原先那条 analyze-version 路径 | 改断言 / 改输入参数 | 更像逻辑期望修正，不形成当前方向的稳定机制 |
| `pr-26875` | `boundary -> race_condition_in_async_code` | global `statistics.FeedbackProbability` / analyze-history singleton | 一组 analyze 相关测试会碰共享反馈概率与 analyze history，patch 主体是把这些测试整体挪到 serial suite；虽然顺手清了 `mysql.stats_histograms` / `ClearHistoryJobs()`，但主导信号仍是共享 stats singleton | 挪到 `testSerialSuite2`，并在个别 case 前清 history / histograms | 这是 mixed case，但先按 global-state 边界保守处理 |
| `pr-27477` | `boundary -> race_condition_in_async_code` | process-global charset feature flag | `TestCharsetFeature` 通过 `collate.SetCharsetFeatEnabledForTest(true/false)` 接管共享 test knob | 抽成独立 serial suite，并把 enable/disable 放到 suite setup/teardown | 又一个“串行接管 process-global test knob”的边界样本 |
| `pr-27482` | `boundary -> race_condition_in_async_code` | process-global local timezone | parquet test 依赖本地时区；早期修法把它搬到 serial suite 并改 `time.Local`，后续又去掉这条共享全局状态改写 | 最终不再直接改 `time.Local` | 主轴仍是 process-global timezone 依赖，不吸进主体 |
| `pr-27894` | `yes` | placement policy fixture namespace | 测试一开始反复复用极短 policy 名 `x` / `y`，和其他 placement 用例共享命名空间 | 改成更局部的 `alter_x` / `alter_y`，并在尾部显式 drop | 虽然这是大 feature PR，但测试侧稳定化动作很明显是“共享 fixture 名字空间隔离” |
| `pr-28693` | `boundary -> race_condition_in_async_code` | global auto-analyze window / `AutoAnalyzeMinCnt` + stats harness | `TestOutdatedStatsCheck` 被迁到独立 serial file，专门建 store/domain，并显式说明要这样做来避 data race；但测试里仍直接改全局 auto-analyze 窗口和最小阈值 | 独立 serial suite + 独立 harness + restore 全局 knob | 虽然带 harness 隔离，但主导问题还是共享 global stats knob |

## 第十一批增量线索

36. shared meta / schema object 的 alias 污染开始出现明确正例
   - 新增正例：`pr-26463`
   - 共同点：
     - 测试拿到的是共享对象指针，不是副本
     - 后续任何“只是想在测试里改一下”的动作，都会回写到共享 meta 上
   - 后续如果再看到 `Meta()`、`Clone()`、copy-on-write 这类 patch，要优先留意这条支线

37. stats / auto-analyze 这条 global-state 边界已经形成一个很厚的子簇
   - 当前增量 boundary：`pr-26460`, `pr-26728`, `pr-26875`, `pr-28693`
   - 共同点：
     - 共享对象包括 `FeedbackProbability`、`MinLogScanCount`、`MinLogErrorRate`、`AutoAnalyzeMinCnt`、global auto-analyze 时间窗、analyze history
     - 稳定化动作主要是 `atomic`、serial suite、独立 harness、显式 restore
   - 这组即便偶尔带一点 cleanup hunk，主导机制仍是 process-global stats singleton

38. “纯断言修正 / 输入调整”的 patch 先继续排除，不要硬吸进当前方向
   - 当前新增排除：`pr-26586`, `pr-26848`
   - 共同点：
     - patch 没有新增明确的 cleanup / restore / close / namespace 隔离动作
     - 更像把原来的不稳期望换掉，或把测试输入改成另一条逻辑路径

## 第十二批已读记录（`111-120`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-28898` | `yes` | attributes test 的 infosync runtime singleton + 表名 namespace | 每个测试自己 bootstrap/store，但 attributes 相关运行时上下文没有做到“每测一份”，同时还复用 `t1/t2` 这类通用表名 | 每个 case 都单独 `GlobalInfoSyncerInit(...)`，并把表名改成 `alter_t` / `truncate_t` / `recover_t` 这类更局部的名字 | 这是 mixed case，但 patch 主轴明显是“runtime singleton 按 case 隔离”加“fixture namespace 去共用化” |
| `pr-29053` | `boundary -> race_condition_in_async_code` | global `bindinfo.Lease` | 测试原先在 `CreateMockStoreAndDomain` 之后才改 lease，而且 defer 顺序让 cleanup 先看到恢复后的全局 lease | 把 lease 改写前移到 bootstrap 之前，并让 restore 晚于 cleanup | 是很典型的 async global knob / defer LIFO 时序边界 |
| `pr-30045` | `boundary -> race_condition_in_async_code` | emulator GC 全局开关 + GC failpoint | placement GC 测试直接依赖 ambient 的 emulator GC 状态，并启用共享 failpoint | 先记录原始 GC 状态，测试内统一 `EmulatorGCDisable()`，结束时配对 restore + disable failpoint | 主导对象仍是 process-global knob / failpoint，不并入主体 |
| `pr-30287` | `boundary -> t_parallel_with_shared_state` | auth plugin failpoint 状态 + server socket runtime endpoint | authplugin 测试在并行运行时共用 failpoint；server 侧多个测试又反复改 `cfg.Socket` | 去掉 `t.Parallel()`，并把 `newTestConfig()` 的默认 socket 设成空串 | 虽然带一点 endpoint 隔离，但主导信号还是“parallel 下共享 failpoint / runtime endpoint” |
| `pr-30299` | `boundary -> race_condition_in_async_code` | process-global logger singleton | `ddltest` 每个 suite 创建时都重新 `InitLogger()`，会碰共享 logger 全局状态 | 把 logger 初始化收敛到 `TestMain`，只做一次并配 `goleak.VerifyTestMain` | 标准 process-global logger 边界样本 |
| `pr-30306` | `yes` | `sql.Rows` / prepared statement / server-side query result 生命周期 | 大量 server 测试在继续发 query / exec 前没有把前一个 `rows` / `stmt` 显式关掉，资源尾巴可能拖到后续断言里 | 系统性补 `rows.Close()` / `stmt.Close()` 并断言无错 | 很强的“resultset / rows close-path 收口不完整”正例 |
| `pr-30323` | `boundary -> race_condition_in_async_code` | process-global collation / prepared-plan-cache / clustered-index test knobs | 一批 expression 集成测试都要接管共享 collation / cache / clustered-index 相关 test knob，原地混跑容易互相污染 | 整体迁到 `integration_serial_test.go`，保持每个 test 内 enable/restore 成对出现 | 核心稳定化动作是“串行接管 process-global test knob”，先继续放边界 |
| `pr-30346` | `boundary -> race_condition_in_async_code` | global slow-log config | 测试与 session/sysvar 路径共享 `EnableSlowLog` / `SlowThreshold` 等全局配置 | 把 `EnableSlowLog` 改成 atomic bool，访问统一 `Load/Store` | 很标准的 global config atomicization 边界 |
| `pr-30490` | `yes` | package-level `Constant` test fixture / `collationInfo` | 测试把共享的 `varcharCon` / `int8Con` 直接传给函数构造，内部会 mutate collation 相关元信息，形成 alias 污染 | 用 `Clone()` 生成局部 expression 常量再传入 | 这条把“shared meta alias / clone-before-mutate”支线又压实了一次 |
| `pr-30503` | `boundary -> t_parallel_with_shared_state` | vectorized builtin test helper 的共享执行状态 | helper 级 `t.Parallel()` 让生成式 vectorized 用例并行撞上共享状态 | 删掉 helper 中的 `t.Parallel()` | 非 cleanup 主线，属于显式 parallel/shared-state 边界 |

## 第十二批增量线索

39. per-test runtime singleton bootstrap + fixture namespace 去共用，开始出现更完整的正例
   - 新增正例：`pr-28898`
   - 共同点：
     - 测试虽然各自建 store / domain，但仍然默认复用某个 runtime singleton 语义或通用对象名
     - 更稳的修法不是补等待，而是把 singleton 初始化也做成 per-test，并把表/对象名改成 case-local

40. `rows / stmt / resultset` 显式 close 纪律继续强化当前主体
   - 新增正例：`pr-30306`
   - 共同点：
     - query 已经跑完，不代表底层 `rows` / `stmt` 生命周期已经收口
     - 如果后续还要继续发 statement、查 warning、或复用连接，前一个 `rows` 必须先关干净

41. process-global knob / failpoint / logger 的 boundary 继续增厚
   - 当前增量 boundary：`pr-29053`, `pr-30045`, `pr-30299`, `pr-30323`, `pr-30346`
   - 共同点：
     - 主导污染对象仍是共享 lease、GC 开关、logger、collation/test knob、slow-log config
     - 稳定化动作主要是“前移/后移 restore 时序”“atomic 化”“挪到 serial file”“收敛到 TestMain”

42. 显式 `t.Parallel()` 退场的 case 先继续放在 parallel/shared-state 边界
   - 当前新增 boundary：`pr-30287`, `pr-30503`
   - 共同点：
     - patch 的一阶动作就是删 `t.Parallel()`
     - 即便顺带补了 socket 默认值或别的小收口，主导机制仍不是当前主体的 cleanup/lifecycle 簇

43. `shared meta alias / clone-before-mutate` 这条支线继续变厚
   - 新增正例：`pr-30490`
   - 共同点：
     - 共享 fixture 不一定是 table / path / runtime，也可能是 package-level test helper object
     - 一旦 helper object 会在函数里被原地写回，就要优先考虑 `Clone()` / copy-on-write，而不是继续共用指针

## 第十三批已读记录（`121-130`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-30692` | `boundary -> t_parallel_with_shared_state` | 大量 package test 的共享 test infra / runtime state | patch 几乎纯粹是在很多测试里删 `t.Parallel()`，说明主导问题是并行混跑撞共享状态 | 大范围移除 `t.Parallel()` | 这是非常纯的 parallel/shared-state 边界，不并入当前主体 |
| `pr-30891` | `boundary -> race_condition_in_async_code` | global CPU profiler / TopSQL profiler singleton / profiling loop | patch 主体是在拆 profiler 与 TopSQL 的并发冲突；测试侧顺带补 `Stop/Close`、HTTP server close、goleak ignore | 引入独立 profiler consumer/handler，测试里补 `defer Stop/Close()` | 虽然有 cleanup hunk，但主导机制仍是全局 profiler singleton 的并发边界 |
| `pr-31032` | `boundary -> race_condition_in_async_code` | global `tidb_enable_historical_stats` + shared `mysql.stats_history` | 历史统计测试会切全局特性开关，而且早期断言直接看全局 history 表，容易吃到别的 case 残留 | `defer` 恢复 global flag，查询按 `table_id/create_time` 缩窄，session 内显式设 analyze version | mixed case，但第一主轴仍是 process-global feature knob |
| `pr-31167` | `yes` | mock cluster 的 TCP port / runtime endpoint | 旧实现先分配端口再释放，后面再 `NewServer`/重 listen，中间有明显的端口抢占窗口 | 用真实 `net.Listen(\"127.0.0.1:\")` 选端口，并把 mock cluster 的 start/stop 更稳地放进 setup/teardown | 很干净的 temp resource / runtime endpoint isolation 正例 |
| `pr-31317` | `yes` | BR restore test 的 mock cluster harness lifecycle | 每个 test 自己起停 cluster 的路径不够稳，反复 start/stop 会把 harness 生命周期拖成噪声 | 把 cluster 提到 `TestMain` 做 package 级初始化/收尾，case 内直接复用 | 虽然牺牲了一点 case 级隔离，但 patch 主轴确实是 harness lifecycle 不能安全重复收口 |
| `pr-31371` | `yes` | stats test 的 session-local analyze mode | 多个统计测试默认吃环境里的 analyze-version 语义，没有把本 case 需要的 session 模式钉死 | 在 case 开头显式 `set @@session.tidb_analyze_version = 0/1`，并避开重名测试入口 | 这条更像“case-local session state 要显式 pin 住”，属于当前方向主体 |
| `pr-31781` | `boundary -> race_condition_in_async_code` | global `CheckMb4ValueInUTF8` config | 测试、HTTP settings、sysvar 路径都在共享读写同一个全局布尔开关 | 改成 atomic bool，访问统一 `Load/Store` | 标准 process-global config atomic 边界 |
| `pr-31815` | `boundary -> race_condition_in_async_code` | global `SchemaOutOfDateRetryTimes/Interval` | DDL / domain / session 测试和 schema checker 共享一组 retry 全局变量 | 把 int / duration 都改成 atomic 包装，并成对 `Load/Store` restore | 典型 global retry knob 边界样本 |
| `pr-31896` | `yes` | DDL test harness 的 failpoint / unistore / pd / rpc / store / ddl 资源 | 测试里有全局 failpoint init，也有 `unistore.New()` / store / ddl / client 等资源没关干净，伴随 data race 与 goroutine leak | failpoint 初始化收敛到 `TestMain`，并给 unistore/pd/rpc/store/ddl/client 全部补 `Close()` + goleak VerifyTestMain | 很强的“test harness / runtime resource teardown 不完整”正例 |
| `pr-31950` | `yes` | helper goroutine 持有的事务 / 行锁 | 阻塞查询测试在 helper goroutine 里拿到锁后就退出，没有释放事务，导致锁尾巴拖到 CI timeout | 在 goroutine 里显式 `rollback` | 这是当前方向里很干净的 case-level cleanup 缺失正例 |

## 第十三批增量线索

44. `mock cluster / port / runtime endpoint` 这条资源隔离主线继续变强
   - 新增正例：`pr-31167`, `pr-31317`, `pr-31896`
   - 共同点：
     - 测试会自己启动一套 server / cluster / unistore / pd / rpc harness
     - 不稳点常常不在断言，而在“端口选择窗口”“cluster start/stop 重复收口”“底层 client/store 没关完”

45. case-local session mode 要显式 pin 住，不要吃环境默认值
   - 新增正例：`pr-31371`
   - 共同点：
     - 测试真正依赖的是某个 session mode（这里是 analyze version），但以前默认从环境/全局继承
     - 更稳的做法是在 case 开头就把 session mode 明确设死，而不是赌外部默认值没变

46. helper goroutine 里打开的事务/锁，也必须自己收口
   - 新增正例：`pr-31950`
   - 共同点：
     - 主 goroutine 看到“行为验证成功”后，helper goroutine 的事务尾巴还在
     - 如果不显式 `rollback/commit`，锁和事务会拖到 suite 末尾才暴露

47. profiler / feature knob / retry knob 这组 process-global 边界继续增厚
   - 当前增量 boundary：`pr-30891`, `pr-31032`, `pr-31781`, `pr-31815`
   - 共同点：
     - 主导对象仍是全局 profiler singleton、全局 feature flag、全局 retry knob
     - patch 的核心动作仍是 `atomic`、拆 singleton 冲突、或 restore 全局配置

48. 大范围删除 `t.Parallel()` 的 patch 仍然不要吸进当前主体
   - 当前新增 boundary：`pr-30692`
   - 共同点：
     - 一阶稳定化动作就是“整片测试改串行”
     - 这类 patch 更适合进入 `t_parallel_with_shared_state` 的边界簇，而不是当前 cleanup/lifecycle 主体

## 第十四批已读记录（`131-140`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-31984` | `yes` | executor 测试里手动取出的 `domain` 生命周期 | 测试从 `domain.GetDomain(tk.Session())` 拿到 `dom` 后直接往下跑，没有把 domain 生命周期显式收口，容易把 teardown 责任悬挂在外层 | 补 `defer dom.Close()`，或直接改成 `CreateMockStoreAndDomain()` 让 `clean()` 统一接管 | 很干净的 `domain / harness teardown` 正例 |
| `pr-31989` | `yes` | `Session().Execute(...)` 返回的 `RecordSet` 切片 | 弱一致性测试先走底层 `Execute`，但把返回的 `rs` 全部丢掉，后续 query/assertion 又继续复用同一 session | 捕获 `rss, err := Execute(...)`，并对每个 `rs.Close()` | 很强的 `resultset close-path 收口不完整` 正例 |
| `pr-32005` | `yes` | `clusterTablesSuite` 共享的 store/domain/http/rpc/failpoint harness | 一个大 `TestClusterTables` 里用 `t.Run` 串一整组子测试，大家共用同一套 suite/harness，failpoint 和 runtime endpoint 的边界不清晰 | 把子测试拆成独立顶层 test；每个 test 自己 fresh `CreateMockStoreAndDomain`、起/停 rpc/http server、配对 enable/disable failpoint | 主导机制是“共享 suite sandbox 没拆开”，留在当前方向 |
| `pr-32225` | `yes` | spill / temp storage 共用的临时目录路径 | 原先 `executor/main_test.go` 在包级 `TestMain` 里直接删建同一条 `TempStoragePath`，不同 case / 上次遗留文件都可能撞在共享路径上 | 去掉包级共享目录清理，具体测试里改用 `t.TempDir()` + `config.RestoreFunc()` | 很强的 `temp path / runtime namespace` 隔离正例 |
| `pr-32674` | `boundary -> race_condition_in_async_code` | DDL 测试共享的全局 config / `infosync` singleton / package 级 knob | patch 主轴是把 scattered 的 `GlobalInfoSyncerInit`、table-lock / slow-threshold / async-commit 这类全局设置收拢到 `ddl/main_test.go::TestMain` | 统一在 `TestMain` 初始化 global config 和 `infosync`，测试里顺手把 `store.Close()` 等写严一点 | 虽然带少量 cleanup，但主导对象还是 process-global settings / singleton |
| `pr-33246` | `yes` | server stat test 的 runtime port endpoint | `TestUptime` 之前只清 `Socket`，server / status 端口仍可能沿用默认值，和别的测试实例碰撞 | 显式把 `cfg.Port = 0`、`cfg.Status.StatusPort = 0`，让测试每次拿随机空闲端口 | `privilege` 里的 goleak ignore 只是弱配套；主导稳定化动作是 endpoint 隔离 |
| `pr-33772` | `boundary -> race_condition_in_async_code` | global `EnableCollectExecutionInfo` config | 测试直接 `config.UpdateGlobal(...)` 打开共享执行信息开关，再用 `RestoreFunc()` 收尾 | save-and-restore process-global knob | 这是标准 global config knob 边界，不并入当前主体 |
| `pr-34578` | `yes` | real-TiKV session tests 的 package / runtime sandbox | 真实 TiKV 场景原先混在 `session` 包里，和普通 session suite 共用一套测试命名空间、入口与环境约束，隔离边界很差 | 抽成专门的 `tests/realtikvtest` 包，新增自己的 `TestMain`、storage/etcd 清理和 `domain/store` cleanup helper | 虽然 PR 很大且中途有回退，但最终保留下来的稳定化主轴很清楚：专用 package sandbox |
| `pr-35246` | `yes` | `TestFlushTables` 所在 package sandbox | `TestFlushTables` 原先放在拥挤的 `executor` 包里，与大量别的 executor test 共用包级环境 | 把该测试迁到独立 `executor/simpletest` 包，并给它单独 `TestMain` | 这是很典型的“把不稳 case 拆进 standalone sandbox”正例 |
| `pr-35343` | `no` | feature patch 中一度出现的测试 cleanup / global-config 片段 | 早期 commit 临时往 `executor/simple_test.go` 塞了一批带 `se.Close()` / `rollback` / `SkipGrantTable` / `SetLease` 的测试，但后续 `fix conflicts` 又整块删掉；最终保留下来的是 `show/set session_states` feature 与配套测试 | 无稳定化主轴可追；最终 diff 不是一条“修测试隔离/污染”的 patch | 这类 case 说明第一轮必须以最终 patch 为准，不能被中途 transient hunks 带偏 |

## 第十四批增量线索

49. `domain / resultset` 生命周期收口继续稳定地支持当前方向
   - 新增正例：`pr-31984`, `pr-31989`
   - 共同点：
     - 测试不是没有 teardown，而是把 `dom` / `RecordSet` 这类次级生命周期对象漏在外面
     - 修法不是调大等待，而是把“谁创建，谁关闭”补完整

50. 共享 suite + `t.Run` 也是一种“sandbox 没拆开”的污染形态
   - 新增正例：`pr-32005`
   - 共同点：
     - 表面上看没有共享 table/db 名，但一整组 subtests 共用同一套 store/domain/http/rpc/failpoint harness
     - 更稳的修法是让每个 case 自己拥有 fresh setup/cleanup，而不是继续在大 suite 里串着跑

51. `TempDir` / 随机端口 / 独立 package sandbox，本质上是同一条 runtime namespace 隔离支线
   - 新增正例：`pr-32225`, `pr-33246`, `pr-34578`, `pr-35246`
   - 共同点：
     - 共享的不是业务数据，而是 temp path、监听端口、包级入口、真实集群测试空间
     - 高收益修法往往是给 case/package 一个独占 namespace，而不是在共享 namespace 上反复清残留

52. 把 scattered global setup 收拢到 `TestMain`，如果主导对象是 process-global knob / singleton，仍应先当 boundary
   - 当前新增 boundary：`pr-32674`, `pr-33772`
   - 共同点：
     - patch 虽然也让测试“更整洁”，但主轴仍是全局 `config` / `infosync` / feature knob 的接管方式
     - 这更接近 `race_condition_in_async_code` 那边的 global knob / singleton 子簇

53. final diff 比中途 commit history 更重要；有些 source-set case 会因为 transient hunks 假装像当前方向
   - 当前新增排除：`pr-35343`
   - 共同点：
     - 早期 commit 里确实出现过 `rollback` / `Close` / `RestoreFunc` / `SetLease` 等强信号
     - 但如果这些 hunks 在后续 commit 被整块拿掉，最终 patch 就不该继续算作当前方向正例

## 第十五批已读记录（`141-150`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-35373` | `yes` | `RecordSet` / 同 session 执行链路 | 失败路径或错误断言分支拿到 `RecordSet` 后没有及时 `Close()`，后续语句继续复用同一 session | 改用会自动 close 的 error helper，或显式 `rec.Close()` | 很强的 resultset close-path 正例，和前面 iterator / resultset 生命周期簇连得很紧 |
| `pr-35374` | `boundary -> race_condition_in_async_code` | 全局 `tidb_store_limit` / `TokenLimit` 阈值 | patch 曾尝试改 `CreateMockStoreAndDomain` 的全局 `TokenLimit`，最终保留的是把测试里的 `set global tidb_store_limit = 100` 改成更高值，仍是 process-global knob | 不再把全局 limit 压得过低 | 主导信号仍是全局阈值 / knob，不是 cleanup / teardown |
| `pr-36115` | `no` | 多处 feature / leaktest 零散点 | 巨大功能 patch 中夹杂少量 `goleak.IgnoreTopFunction(...)` 与测试改写，但没有形成清晰、可复用的测试隔离 / 生命周期修法主线 | 局部忽略 leak / 调整测试 | 最终 retained patch 主体是 log-backup 功能，不把这条强行吸进当前机制簇 |
| `pr-36217` | `boundary -> race_condition_in_async_code` | 全局 `config.Security.SpilledFileEncryptionMethod` | 把原来 `t.Run(...)` 下共享的 config-mutating case 拆成多个顶层 test，但每个 test 仍然 save-and-restore 同一个 process-global config | `config.RestoreFunc()` + `config.UpdateGlobal(...)` 配对；取消共享 `t.Run` 结构 | 表层像 test 拆分，核心仍是 process-global config knob |
| `pr-36506` | `yes` | 共享 executor test package / 全局 memory tracker test runtime | 不稳定测试和大量 executor 其他测试共处一个 package / `TestMain` / runtime，隔离不够 | 把测试移到单独 `executor/memtest` package，并给独立 `TestMain` / goleak 设置 | 很强的“独立 package sandbox”正例 |
| `pr-36507` | `yes` | `RecordSet` / insert error path | 多个 `insert_test` 错误分支拿到 `rec` 后没有关闭，影响后续执行和资源回收 | 显式 `rec.Close()` 或替换成自动收口的 helper | 与 `pr-35373` 同簇，继续加固 resultset close-path |
| `pr-36578` | `yes` | real-TiKV 共享存储 / etcd / session-store 测试环境 | real-TiKV helper 曾停掉 `clearTiKVStorage`、`clearEtcdStorage`、`ResetStoreForWithTiKVTest`，导致共享环境残留；同 patch 里也混有 `set global tidb_txn_mode=''` 这类边界信号 | 恢复存储清空、etcd 清空、store reset；补少量 goleak ignore | 虽然混有 global knob 次信号，但 retained 的 helper reset/cleanup 很强，先保留为当前方向正例 |
| `pr-36722` | `yes` | store / domain / rpc/http server / failpoint cleanup closure | 大量测试靠手写 `clean` closure 或 `defer clean()`，生命周期散落，漏调时容易留下 server / failpoint / suite 资源 | 系统性改成 `t.Cleanup(...)`，把 cleanup 绑定到测试生命周期 | 很强的“cleanup 注册到 test lifecycle”正例 |
| `pr-37003` | `yes` | `RecordSet` / 查询返回句柄 | 更多 executor tests 在 query/exec 后遗漏 `RecordSet.Close()` | 系统性补 `Close()` / 使用自动关闭 helper | 继续扩充 resultset close-path 簇 |
| `pr-37014` | `boundary -> race_condition_in_async_code` | planner test-only 全局布尔开关 | `ForceUseOuterBuild4Test` / `ForcedHashLeftJoin4Test` 这类 test knob 被并发读写 | 改成 `atomic.Bool` / `.Store()` | 典型 process-global test knob race，继续迁边界 |

## 第十五批增量线索

54. `RecordSet` / query result 生命周期没收口，这条线还在持续放大
   - 当前增量正例：`pr-35373`, `pr-36507`, `pr-37003`
   - 共同点：
     - 测试在 error path / query path 上拿到了 `RecordSet`
     - 旧写法没有及时 `Close()`，或者 helper 不负责收口
     - 修法是显式 close，或者把错误断言改成自动 close 的 helper

55. 独立 package sandbox / 独立 `TestMain` 是当前方向里的高价值稳定化动作
   - 当前增量正例：`pr-36506`
   - 共同点：
     - 某个不稳定测试和大型包内其他测试共享 runtime / `TestMain`
     - 修法不是微调断言，而是直接拆到单独 package，给独立的初始化和 leak 配置

56. 把 cleanup 绑定到测试生命周期，而不是散落在手写 closure 里
   - 当前增量正例：`pr-36722`
   - 共同点：
     - 旧测试依赖 `clean func()` / `defer clean()` / 手动返回 cleanup
     - 修法是统一收敛到 `t.Cleanup(...)`
     - 这条线和前面的 `domain/store/server teardown` 是天然相邻簇

57. real-TiKV / 共享集群环境 reset 不完整，也应算当前方向主体
   - 当前增量正例：`pr-36578`
   - 共同点：
     - 共享 store / etcd / bootstrap session 状态会跨测试残留
     - 修法是恢复 helper 级别的环境清空与 reset，而不是只在单个 case 上补断言

58. 只要 patch 的主体仍是 process-global knob / config / test-only flag，哪怕表面上也拆了 test 结构，仍先迁边界
   - 当前增量 boundary：`pr-35374`, `pr-36217`, `pr-37014`
   - 这三条都说明：不要因为 patch 里出现 `t.Run` 拆分、helper 变更，就误吸到当前方向；关键仍看污染对象是不是 process-global knob

59. 巨大 feature patch 中零散夹带的 leak ignore，不足以构成当前方向正例
   - 当前代表：`pr-36115`
   - 这类 patch 后面还会继续遇到；标准应保持严格，只认 retained 主体里真正清晰、可复用的隔离 / 生命周期修法

## 第十六批已读记录（`151-160`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-37016` | `yes` | HTTPS client `resp.Body` / 同一测试里的连接复用链路 | 第一段请求读取 body 后没有把 `resp.Body` 用严格 close 语义收口，再继续跑后续 TLS 请求 | 显式 `require.NoError(t, resp.Body.Close())` | 虽然 patch 里也碰了 bazel `shard_count`，但 retained 的核心稳定化动作仍是 request-handle close-path 收口 |
| `pr-37372` | `yes` | statement-scoped memTracker / executor close-path | `insert/update` 执行后内存 tracker 的 bytes used 没在 close-path 归零，导致后续断言看到残留状态 | 在 `InsertExec.Close` / `UpdateExec.Close` 里 `ReplaceBytesUsed(0)`；测试改看 session-local tracker | 本质是 executor 生命周期收口不完整，和“资源/状态未 reset”同向 |
| `pr-37382` | `yes` | 测试注入的 coprocessor priority 检查 hook | 共享 mock client 的检查逻辑会把无关 RPC 也算进来，测试 hook 作用域过大 | 给目标请求打 `context` 标记；新增 `MustQueryWithContext` / `MustExecWithContext`，只校验带标记的请求 | 很像“测试观察器 / hook 没有 scoped namespace”，先保留为当前方向正例 |
| `pr-37705` | `no` | analyze options 测试逻辑 | 早期 commit 里有 `tidb_enable_auto_analyze` save/restore，但最终 retained patch 主体是重做测试数据、切 analyze version / option 组合与期望值 | 调整测试构造与断言 | 最终主体不像 cleanup / teardown / namespace isolation，不并入当前方向 |
| `pr-37908` | `yes` | `go.opencensus` view worker / metrics background worker | 大量测试以前靠 `goleak.IgnoreTopFunction(\"...view.(*worker).start\")` 掩盖残留 worker，没有显式 stop | 在具体测试 / helper / cleanup 里补 `view.Stop()`，并删掉 goleak ignore | 很强的“后台 worker 要显式 stop，而不是靠 ignore 掩盖”正例 |
| `pr-38143` | `no` | race-build / test infra 调整 | patch 主轴是给部分 bazel test 开 `race=on`、升级 goleak 并顺手补一个 cleanup callback | build/race 配置调整 | 虽有少量 cleanup 配套，但 retained 主体仍是 test infra/race enable，不记当前方向正例 |
| `pr-38161` | `no` | coprocessor paging 默认值 / 相关 plan expectation | patch 主轴是打开 paging、修改默认配置与 golden 输出；测试里显式 `set @@tidb_enable_paging = on` 只是把行为钉死 | 调整 session var / golden | 更像功能与预期对齐，不是 cleanup / 隔离修法 |
| `pr-38288` | `yes` | `go.opencensus` view worker / 多个 suite 的 cleanup | 为了打开更多 race test，patch 系统性移除 `goleak` 对 view worker 的忽略，并把 `view.Stop()` 接到各类 helper / `t.Cleanup` / close path 上 | 显式 `view.Stop()` + 清理时机绑定到 helper/test cleanup | 和 `pr-37908` 同簇，进一步坐实“background metrics worker stop-path” |
| `pr-38374` | `boundary -> race_condition_in_async_code` | 全局函数指针 `SetPDClientDynamicOption` | domain 初始化和 sysvar set 路径共享读写同一个全局函数指针 | 改成 `atomic.Pointer[func(...)]` 并原子加载 | 很标准的 process-global function pointer data race，继续迁边界 |
| `pr-38808` | `yes` | autoid 相关测试共用的大 package sandbox / 对象命名空间 | 一大批 autoid 测试散在 `ddl/executor/insert` 等包里，和其他测试共享包级环境；后续 CI 修正还把对象名改唯一 | 抽成独立 `executor/autoidtest` package，补自己的 `main_test.go` / BUILD；个别 case 改唯一表名 | 这是“独立 package sandbox + 唯一 namespace”正例，和 `memtest/simpletest` 支线一致 |

## 第十六批增量线索

60. 不只是 `RecordSet`，HTTP response body / request handle 的 close-path 也属于同一类生命周期收口问题
   - 当前增量正例：`pr-37016`
   - 共同点：
     - 同一测试里的后续操作依赖前一个 handle 已经彻底 close
     - 稳定化动作不是加等待，而是把 handle close 写严

61. “执行后残留状态没 reset” 也能落到当前方向，哪怕残留的是 tracker / runtime state
   - 当前增量正例：`pr-37372`
   - 共同点：
     - 某个 statement/executor 级别的状态在 close-path 后还残留
     - 修法是把 reset / zeroing 放回 close 生命周期

62. 测试注入的 observer / hook 也需要有自己的作用域，不然会误吃到无关请求
   - 当前增量正例：`pr-37382`
   - 共同点：
     - 问题不在业务对象，而在测试检查器本身观察范围过大
     - 修法是给目标请求打标记，缩小 hook 的生效范围

63. `goleak.IgnoreTopFunction(...)` 不该是终点；更强的修法是把后台 worker 真的停掉
   - 当前增量正例：`pr-37908`, `pr-38288`
   - 共同点：
     - 残留对象是 metrics / opencensus 的后台 view worker
     - 旧 patch 只是 ignore；更干净的 patch 会在 helper / cleanup / close path 上显式 `view.Stop()`

64. 独立 package sandbox 这条支线继续扩大，而且会和“唯一对象名”一起出现
   - 当前增量正例：`pr-38808`
   - 共同点：
     - 测试先从拥挤 package 里拆出去，随后再给个别 case 补唯一 table 名
     - 说明 package-level isolation 和 fixture namespace isolation 经常配套出现

65. 如果 retained patch 的主体是“测试逻辑重写 / golden 变更 / race build 开关”，即使中间夹带一点 cleanup 信号，也先不算当前方向正例
   - 当前代表：`pr-37705`, `pr-38143`, `pr-38161`
   - 这类 patch 后面还会继续出现；标准仍然要盯住最终主轴，而不是被配套小改动带偏

66. process-global function pointer / callback 注册竞态，继续稳定落在边界
   - 当前新增 boundary：`pr-38374`
   - 这说明边界簇不只有标量 config / bool flag，也包括“全局 callback 指针”这类可变入口

## 第十七批已读记录（`161-170`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-39023` | `yes` | hash join worker / waiter goroutine / result channel | hash join close-path 没有等后台 worker/waiter 全部退出，容易留下 goleak | 用 `WaitGroupWrapper` 接管 worker 与 waiter，并在 `Close()` / close-path 上 `Wait()` | 很强的“后台 worker teardown 要等完”正例 |
| `pr-39718` | `yes` | `RecordSet` in `TestBootstrap` | bootstrap test 读取完结果后遗漏 `r.Close()` | 显式补 `require.NoError(t, r.Close())` | 继续扩充 recordset close-path 簇 |
| `pr-39747` | `boundary -> race_condition_in_async_code` | process-global logger init / slow log config | `CreateMockStore` 期间就可能触发共享 logger 路径，测试先建 store 再 `InitLogger` 会打到全局 logger race | 把 `logutil.InitLogger(...)` 提前到 `CreateMockStore(...)` 之前 | 标准的 process-global logger 初始化顺序边界 |
| `pr-39783` | `yes` | `RecordSet` / session query handle | 多个 bootstrap / main / const tests 里把 `mustExec()` 返回的结果句柄直接拿来读或丢掉，没有统一 close | 改 helper 分流：需要结果的走 `mustExecToRecodeSet`，纯执行的走自动收口路径 | 很干净的 recordset helper 收口正例 |
| `pr-39900` | `boundary -> race_condition_in_async_code` | process-global logger / slow log config | 多个 slow-query / binary-plan tests 都是“先建 store/session，再改 slow-log config 和 InitLogger”，与其他路径共享全局 logger | 把配置/`InitLogger` 提前，再创建 store/testkit | 和 `pr-39747` 同簇，还是 logger init ordering |
| `pr-40010` | `yes` | `RecordSet` / error-path `Exec()` 返回值 | 一批 executor tests 还在用裸 `Exec()` 接错误，不自动 close 返回句柄 | 继续替换成 `MustExec` / `ExecToErr` / `MustGetErrMsg` 等自动收口 helper | 和 `pr-35373/#36507/#37003/#39783` 连成同一大簇 |
| `pr-40024` | `boundary -> race_condition_in_async_code` | 全局 `PreparedStmtCount` 计数器 | `TestMaxPreparedStmtCount` 依赖 package/global prepared statement counter 的当前值，和别的测试互相污染 | 测试前保存旧值、原子置零，结束时 restore | 还是 process-global counter / scalar state，继续迁边界 |
| `pr-40199` | `no` | explain golden / cost model expectation | retained patch 只是给一段 explaintest 脚本显式包一层 `set tidb_cost_model_version=2` / `=1`，让 golden 对上 | 调整 test script 的执行环境 | 更像 exact-plan golden fix，不是 cleanup / 生命周期主线 |
| `pr-40542` | `yes` | backfill worker manager / worker context / session pool / backfill ctx pool | 新的 distributed reorg/backfill 路径引入一组 worker/session/context，但 close-path 如果不完整就会把 worker 和 session 留在池外或悬挂 | 新增/强化 `close()`：关闭 exit channel、等待 worker、把 session 放回 pool、把 backfill worker ctx 放回 pool | 虽然 PR 很大且偏功能，但 retained 的 worker/pool teardown 机制很强，保留为当前方向正例 |
| `pr-41321` | `yes` | slow log 文件名 / runtime file namespace | `TestSelectClusterTable` 复用共享 slow log 文件名，和其他路径可能撞到同一个 slow log 产物 | 改成专用 slow log 文件名，并显式更新 `conf.Log.SlowQueryFile` | 属于 runtime file namespace 隔离支线 |

## 第十七批增量线索

67. 后台 worker / worker-pool / session-pool 的 teardown，是当前方向里又一条稳定主线
   - 当前增量正例：`pr-39023`, `pr-40542`
   - 共同点：
     - 问题不是单个句柄没关，而是成组 worker / waiter / session context 没有在 close-path 上等完、回收完
     - 修法会显式 `Wait()`、`close(exitCh)`、把 session/context 放回 pool

68. `RecordSet` close-path 这条线还在持续扩展，而且开始通过 helper 分流来系统化收口
   - 当前增量正例：`pr-39718`, `pr-39783`, `pr-40010`
   - 共同点：
     - 既有直接补 `r.Close()`，也有把 helper 改成“需要结果”和“纯执行”两类，避免再漏关

69. process-global logger 初始化顺序，继续稳定地落在边界而不是当前主体
   - 当前新增 boundary：`pr-39747`, `pr-39900`
   - 共同点：
     - 稳定化动作不是 cleanup，而是“先改 logger / slow-log config，再建 store / session”
     - 这仍然是 logger/global-config ordering 子簇

70. process-global counter / scalar state 的 save-and-restore，继续不要吸进当前主体
   - 当前新增 boundary：`pr-40024`
   - 这和前面的 prepared-plan-cache / knob / callback 指针其实是一类边界：共享全局状态被测试临时接管

71. runtime file namespace 隔离，不只会表现为 `TempDir()`；固定 slow-log 文件名也会撞
   - 当前增量正例：`pr-41321`
   - 这条线和前面的 temp path / port / package sandbox 是同一支系

72. exact-plan / explaintest 脚本里通过显式 session var 把环境钉死，这类 retained patch 仍先记 `no`
   - 当前代表：`pr-40199`
   - 它说明后面要继续分清“让 golden 对上”和“真正修隔离/生命周期问题”

## 第十八批已读记录（`171-180`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-41356` | `boundary -> race_condition_in_async_code` | process-global stmt-summary / binary-plan / slow-log knobs | 多个 binary-plan tests 通过 `set @@global...` 接管共享全局开关，再手动 restore；还靠开关翻转清内存态 | save-and-restore 全局变量，显式清 stmt summary 状态 | 主轴仍是 process-global knob，不并入当前主体 |
| `pr-41547` | `yes` | slow log 文件名 / slow-log config | 多个 infoschema / executor slow-log 相关测试共用默认 `tidb-slow.log` 等文件名，容易互撞 | 改成专用文件名前缀，并配 `config.RestoreFunc()` / `UpdateGlobal()` 指向各自文件 | 很典型的 runtime file namespace 隔离正例 |
| `pr-42009` | `boundary -> race_condition_in_async_code` | 全局 `UnistoreRPCClientSendHook` callback 指针 | 测试直接改写共享 hook callback，和 failpoint 路径并发读写时 data race | 改成 `atomic.Pointer[func(...)]` 并原子 load/store | 和 `pr-38374` 的全局 callback 指针边界完全同型 |
| `pr-42101` | `yes` | failpoint 断言 hook 的观察范围 | `assertTSONotRequest` 会把 internal session 触发的请求也算进来，测试断言范围过大 | 只在 `!s.isInternal()` 时触发断言 | 和 `pr-37382` 一样，是“测试观察器 / 断言 hook 没有缩作用域”的正例 |
| `pr-42133` | `boundary -> race_condition_in_async_code` | 全局 `stmtsummaryv2.GlobalStmtSummary` singleton | 关闭 stmt summary 后还把全局 singleton 直接置 `nil`，和并发读取者形成 race | 保留 `Close()`，不再把全局指针置空 | 还是 global singleton mutation 边界 |
| `pr-42336` | `boundary -> race_condition_in_async_code` | 全局 `TxnTotalSizeLimit` | 多个测试和运行期共享读写这个全局 limit | 改成 `atomic.NewUint64` + `.Load/.Store()` | 标准 process-global scalar limit 子簇 |
| `pr-42454` | `no` | disttask dispatcher feature 主线 | retained patch 主体是并行 dispatcher / spool pool / 任务探测流程重构，测试改动主要是配套功能验证与加速 | feature 重构 | 虽有少量 test-main/MockDispatcher 配套，但不构成当前方向可复用的隔离/cleanup 主轴 |
| `pr-42589` | `boundary -> race_condition_in_async_code` | 全局 DDL dist-task / reorg worker knobs | 为了让结果顺序确定，测试显式关闭 `tidb_enable_dist_task`、固定 `tidb_ddl_reorg_worker_cnt=1` | 接管全局 DDL knob | 这是“global knob + async execution order”边界，不纳入当前主体 |
| `pr-42776` | `boundary -> race_condition_in_async_code` | 全局 memory tuner 后台状态 | 测试原先用固定 `sleep` 等待 tuner 复位；修成 `require.Eventually(...)` 等待后台状态收敛 | eventual wait 替代固定 sleep | 更像 async/background-state 边界，不是 cleanup/namespace 主线 |
| `pr-43067` | `yes` | add-index ingest chunk pool / cop-request chunk 生命周期 | `cop` 读出的 chunk 在错误路径或某些返回路径上没有统一 recycle，导致 chunk pool 状态泄漏 | 把 `recycleChunk(rs.chunk)` 绑到统一 defer / close-path，并增加测试覆盖错误路径 | 很干净的“chunk/temporary buffer 生命周期没收口”正例 |

## 第十八批增量线索

73. slow-log 相关测试继续证明：固定文件名本身就是共享 namespace 污染源
   - 当前增量正例：`pr-41547`
   - 这条线和 `pr-41321` 可以并成一个稳定 sibling：slow-log / runtime file namespace isolation

74. “测试断言 hook 作用域过大”这条线再次被确认
   - 当前增量正例：`pr-42101`
   - 这说明 `pr-37382` 不是偶然个案；后面可以考虑把它单列成 observer/hook scope sibling

75. chunk / buffer / 临时数据块的 recycle-path，也属于当前方向的资源生命周期主线
   - 当前增量正例：`pr-43067`
   - 它和 `RecordSet` / `resp.Body` / `cop chunk` 本质上是同一类：谁拿到临时句柄/数据块，谁负责在所有返回路径上收口

76. process-global callback / singleton / scalar knob 的边界继续扩张
   - 当前新增 boundary：`pr-42009`, `pr-42133`, `pr-42336`, `pr-42589`
   - 这再次说明：当前 unified direction 里必须持续把 global-state 竞态切出去，哪怕这些 patch 也带“让测试稳定”的效果

77. async background state 用 `Eventually` / 关闭 dist-task / 调顺序 来稳住的 patch，先继续记边界
   - 当前代表：`pr-42589`, `pr-42776`
   - 这类更接近 async/ordering family，而不是当前 cleanup/lifecycle 主体

78. 巨大 feature patch 如果 retained 主体是功能/调度重构，就不要因为夹带了少量 test helper 改动而硬吸进来
   - 当前代表：`pr-42454`

## 第十九批已读记录（`181-190`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-43108` | `no` | `load data` / generated column feature 主线 | retained patch 主体是 generated column + `load data` 支持，测试里的临时文件/statement 只是配套功能覆盖 | 功能实现与用例补齐 | 不像 cleanup / teardown / namespace isolation 主轴 |
| `pr-43139` | `no` | 已知不稳定的 `TestDBStmtCount` | patch 没有收口污染源，直接把 case 整体跳过 | `t.Skip("unstable test")` | 没有形成可复用的稳定化机制，不记当前方向 |
| `pr-43399` | `no` | 外部 `poll/runtime_pollWait` 残留 goroutine | patch 用 `goleak.IgnoreTopFunction(...)` 掩盖泄漏，而不是把 worker / fd 生命周期收口 | 扩大 goleak ignore 白名单 | 这是 band-aid，不算当前方向正例 |
| `pr-43758` | `yes` | CTE 临时存储 `StorageRC` / spill 资源 / reopen-close 生命周期 | CTE 在 panic / reopen / deref-close 路径上没有把底层 RC 存储和状态位重置干净，后续复用会挂住 | 统一在 `DerefAndClose` / `Reopen` / panic 返回路径上 close 底层存储并重置状态 | 很典型的“临时资源生命周期没收口”正例 |
| `pr-44206` | `yes` | ingest backend / backend registry | add-index rollback / cancel 路径里 backend 注册项没有在所有返回路径上注销，后续任务会看到残留 backend | 把 `Unregister(job.ID)` 绑定到 rollback / cancel 路径的统一 defer | 属于 domain/backend 级资源 teardown 不完整 |
| `pr-45488` | `no` | import-into range overlap / subtask sizing 主线 | retained patch 主体是调大 subtask size、调整切分策略减少 range overlap | 功能/性能参数调整 | 即使 source set 里带 global-state 味道，主体仍不是 test-isolation 修法 |
| `pr-45563` | `boundary -> race_condition_in_async_code` | config labels / `StoreGlobalConfig` 相关共享全局配置 | 读 labels 与改 labels 并发打到同一份全局 config | clone-then-publish / `StoreGlobalConfig` | 标准 process-global config data race，继续迁边界 |
| `pr-45579` | `boundary -> race_condition_in_async_code` | labels 相关共享全局配置 | `TestSetLabelsConcurrentWithGetLabel` 里显式暴露出全局 config 读写并发 | clone 后再发布全局配置 | 和 `pr-45563` 同簇，仍是 global config 边界 |
| `pr-45969` | `no` | statistics feedback feature 主线 | retained patch 主要是 remove feedback 的功能/代码面清理，测试改动只是随产品重排 | 功能移除 / 测试跟随 | 不构成当前方向可复用的 cleanup / namespace 机制 |
| `pr-46075` | `boundary -> race_condition_in_async_code` | disttask owner-change / scheduler side state | 不稳定来自 owner change 与并发调度/状态更新交织，patch 主体是并发可见性与任务表行为修正 | 改共享状态承载方式，避免并发读写踩踏 | 更像 async scheduling / shared state 边界，不纳入当前主体 |

## 第十九批增量线索

79. backend / temp storage / RC handle 的 close-path 继续扩张成一条明确主线
   - 当前增量正例：`pr-43758`, `pr-44206`
   - 共同点：
     - 不稳定来自临时 backend / 存储句柄在异常或 rollback 路径上没被完整回收
     - 修法不是等一等，而是把 unregister / close / reset 绑定到统一生命周期出口

80. 直接 `Skip` 或继续扩 goleak ignore，不应算当前方向正例
   - 当前代表：`pr-43139`, `pr-43399`
   - 这两条再次提醒：只有真正把污染对象 stop/close/reset 掉，才计入当前机制簇

81. process-global config labels 这类“clone-then-publish”修法，继续稳定落在边界
   - 当前新增 boundary：`pr-45563`, `pr-45579`
   - 这说明边界簇里不只有标量 knob，也包括结构化全局 config 的并发发布

82. 巨大功能 patch 里夹带少量测试味道时，仍然要盯 retained 主体
   - 当前代表：`pr-45488`, `pr-45969`
   - 二者都不是当前 unified direction 的可复用稳定化主轴

## 第二十批已读记录（`191-200`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-48050` | `no` | BR public delete-range / restore feature 主线 | patch 主体是把 delete-range 逻辑对接到 BR restore，测试改动只是跟随功能路径 | 功能实现 | 不是 cleanup / 隔离主线 |
| `pr-48133` | `yes` | executor open/close 生命周期 / `EvalSubqueryFirstRow` goroutine | `Open()` 失败时没有保证 executor 统一 close，可能留下 goroutine / worker 残留 | 把 `defer executor.Close()` 绑到统一 `exec.Open(...)` wrapper 周围 | 很干净的“open 失败也要完整 close”正例 |
| `pr-48184` | `no` | add-index / external engine 效率主线 | retained patch 主体是索引构建效率与实现细节调整 | 功能/性能优化 | 不构成当前方向的隔离或生命周期机制 |
| `pr-48604` | `yes` | benchmark 中的 query handle / 事务上下文 | benchmark 循环里用 `MustExec(select ...)` 丢掉查询结果，且循环结束后事务没显式收口 | 改成 `MustQuery(...)` 并在末尾 `rollback` | 属于“重复执行场景里的句柄/事务 cleanup 不完整”正例 |
| `pr-48653` | `boundary -> race_condition_in_async_code` | process-global RNG seed | `math/rand.Seed` 影响整个进程的随机源，测试彼此会互相污染 | 去掉全局 `Seed`，改局部随机源 | 仍是共享 process-global state 边界 |
| `pr-50008` | `yes` | 被重复复用的 `task` fixture 对象 | 前一次调用会原地改 `task.State` / `task.Step`，下一次复用时继承旧状态 | 在再次调用前显式把字段改回初始值 | 很好的“可复用对象 reused without reset”正例 |
| `pr-50156` | `no` | `TestFlashbackSchema` 运行环境 | retained patch 主体是换用 `EmbedUnistore` 并追加一个 goleak ignore | 环境切换 + ignore | 更像环境带宽/infra 调整，不是当前方向主线 |
| `pr-50687` | `yes` | `TTLJobManager` 背景 job loop | 测试期望自己掌控 TTL job 提交，但后台 manager 仍在运行并会注入额外 job schedule | 显式 `Stop()` 后再跑测试 | 继续坐实“后台 manager 要先停，再改测试条件”这一支 |
| `pr-52060` | `boundary -> race_condition_in_async_code` | planner test 使用的全局 atomic knob | 测试靠改 shared plan knob 控制执行路径，和其他路径共享同一全局开关 | 删除 test-only global knob，改成 query hints | 标准全局 knob 边界 |
| `pr-52968` | `no` | 任务 ID 断言 / 顺序假设 | patch 没有隔离或 reset 状态，只是去掉对精确 task ID 的硬编码断言 | 放宽断言，改用返回值自身的 ID | 更像 brittle assertion 修补，不是当前方向主体 |

## 第二十批增量线索

83. `Open` 失败也必须走完整 `Close`，否则就是资源/worker 泄漏
   - 当前增量正例：`pr-48133`
   - 这条线和前面的 `RecordSet` / `resp.Body` / backend close-path 本质一致：只要拿过 executor/handle，就要保证所有退出路径都收口

84. benchmark / stress loop 也会积累 test-local 污染，事务与查询结果同样要显式收尾
   - 当前增量正例：`pr-48604`
   - 它补充了一个此前较少出现的场景：不是单测 case，而是循环 benchmark 自己留下了事务/句柄残留

85. “复用对象先 reset 再重用”现在可以单列成一条 sibling 候选
   - 当前增量正例：`pr-50008`
   - 共同点：
     - 上一次调用会原地污染输入对象
     - 测试为下一次调用复用同一对象时，必须先把关键字段改回初始态

86. TTL / planner 这类 process-global knob 继续稳定地落边界；真正保留的是“先停后台 manager”
   - 当前方向正例：`pr-50687`
   - 当前新增 boundary：`pr-48653`, `pr-52060`
   - 这组三条把边界和主体切得更清楚了

87. 仅仅放宽 ID / 顺序断言，不等于修好了 test-isolation 问题
   - 当前代表：`pr-52968`

## 第二十一批已读记录（`201-210`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-53017` | `yes` | `TTLJobManager` 后台 loop | 早期修法是直接关全局 TTL knob，但最终 retained patch 改成测试启动 domain 后显式停掉 TTLJobManager，避免它读到测试中被手改的元数据 | `CreateMockStoreAndDomain` 后 `dom.TTLJobManager().Stop()` | 应归到“先停后台 loop，再改测试对象”的当前方向正例 |
| `pr-53507` | `yes` | schema version syncer 中的 matcher / wait item 状态 | `ctx.Done()` 提前返回时，没有清掉本次 wait 注册的 matchFn，后续循环会继承残留匹配器 | 在 `ctx.Done()` 分支也执行 `item.clearMatchFn()` | 这是“hook / matcher 生命周期没收口”的正例 |
| `pr-53548` | `boundary -> race_condition_in_async_code` | DDL scheduler / owner change / async job framework | patch 主体是把 scheduler 与 owner change 解耦并改运行/退出语义 | async scheduling 重构 | 更像 async family，不纳入当前 cleanup/namespace 主体 |
| `pr-54311` | `no` | `TopN` 功能 bug 主线 | retained patch 主体是修复关闭 tmp storage 时 `TopN` 的 production panic，测试只是新增一个覆盖 case | 功能修复 + 新用例 | 不像 test-isolation / teardown 修法 |
| `pr-54709` | `yes` | `PipelinedWindowExec` 可复用执行器实例 | `Open()` 没把上一轮运行留下的字段状态全部清零，重复 open/close 时会吃到旧参数 | 在 `Open()` 开头系统性重置行游标、窗口边界和缓存字段 | 和 `pr-50008` 同簇，属于“reused object must reset” |
| `pr-55362` | `no` | infoschema v2 default/测试期望 主线 | 系列 patch 主要是切默认值、修 infoschema 行为与测试期望；测试对 schema cache/global var 的调整只是功能切换配套 | 功能切换 / 期望对齐 | retained 主体不是 cleanup / teardown / namespace |
| `pr-55431` | `no` | infoschema join 行为 / 测试期望 | 主轴是修具体查询行为与断言，非隔离/清理机制 | 测试逻辑与期望调整 | 不并入当前方向 |
| `pr-56002` | `boundary -> race_condition_in_async_code` | 全局 `autoid` step | 测试靠改 shared autoid 步长制造期望值，和其他路径共享同一全局步长 | 调整全局 step 的接管方式 / restore 顺序 | 标准 global knob 边界 |
| `pr-56737` | `yes` | plan replayer 输出目录 / server socket 文件路径 | 测试把 plan replayer 产物和 socket 放在共享 `/tmp` 路径下，容易和同进程其他 case 撞文件 | 改用 `t.TempDir()` 承载测试专属路径 | runtime file namespace 隔离正例 |
| `pr-56798` | `boundary -> race_condition_in_async_code` | runaway `recordMap` 全局状态 | 测试依赖/修改共享全局记录表，修法是把全局 mutable map 收回局部 | 去全局化 / 局部化记录表 | 仍是 process-global mutable singleton 边界 |

## 第二十一批增量线索

88. “先停后台 loop，再改测试对象”的 TTL 支线再次被坐实
   - 当前增量正例：`pr-53017`
   - 它和前面的 `pr-50687` 已经形成清晰可 formalize 的 sibling

89. matcher / filter / callback 如果只在 happy path 清理，取消路径一样会留下污染
   - 当前增量正例：`pr-53507`
   - 这和前面的 hook-scope 线天然相邻，但这里更偏“注册后没解绑”

90. reused object / executor 实例 reset 这条线继续扩张
   - 当前增量正例：`pr-54709`
   - 这和 `pr-50008` 共同说明：不仅 test fixture，会复用的 runtime executor 也会把旧状态带到下一轮

91. `/tmp` / 默认输出目录依然是共享 namespace 高发点
   - 当前增量正例：`pr-56737`
   - 后面已经能预期还会遇到更多 `TempDir()`/`TempStoragePath` 同簇 case

92. infoschema default switch / exact behavior 对齐，不要因为碰到 global var 就误吸进来
   - 当前代表：`pr-55362`, `pr-55431`

## 第二十二批已读记录（`211-220`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-57201` | `no` | instance plan cache 语义/实现主线 | retained patch 主体是 shallow copy / cache 行为修正，测试只是跟着行为变更 | 功能实现修正 | 不是当前方向的 teardown / namespace 主体 |
| `pr-57823` | `boundary -> race_condition_in_async_code` | dist-task / CPU count 相关全局环境开关 | 测试通过 SQL 全局开关和 failpoint 去钉住导入目标节点数，实质仍是接管共享全局环境 | 关全局开关 / 依赖 eventual 结果 | async/global knob 边界 |
| `pr-58589` | `boundary -> race_condition_in_async_code` | `tidb_schema_cache_size` 全局变量 | 不稳定来自 infoschema 测试对全局 schema-cache knob 的接管与恢复 | reset 全局 schema-cache 相关变量 | 继续归到 process-global knob 边界 |
| `pr-60901` | `yes` | `TTLJobManager` 后台 manager / session pool | TTL integration tests 运行时仍有 manager 在后台调度 session，干扰 fault/session 用例 | `Stop()` + `WaitStopped(...)` 后再跑测试 | 比 `pr-50687` / `pr-53017` 更完整，明确要求等待停止完成 |
| `pr-61400` | `boundary -> race_condition_in_async_code` | `tidb_schema_cache_size` 全局变量 | 测试需要把 schema cache size 钉到特定值才能对齐行为，本质还是 process-global knob | restore 为默认值 / 重新设全局变量 | 仍属边界 |
| `pr-61977` | `yes` | BR parallel restore registry / checkpoint 产物 | parallel restore 中 registry 与 checkpoint 文件/状态没被完整清掉，后续运行会继承残留 | 新增清理工具，在测试/脚本路径上显式删除 registry 与 checkpoints | 很干净的 harness-level cleanup 正例 |
| `pr-63897` | `boundary -> race_condition_in_async_code` | disttask scheduler limit / cancellation 流程 | patch 主体是并发 scheduler 达到上限时如何继续响应 cancel/revert 请求 | async scheduling 路径重排 | 更像 async/task framework 边界 |
| `pr-64105` | `yes` | ingest engine / engine close-path | 引擎清理逻辑没有保证在所有退出路径执行，残留 engine/temp data 会污染后续 case | 把 engine cleanup 收拢到统一 defer / close-path | 属于 backend/engine lifecycle 主线 |
| `pr-64170` | `no` | import-into SEM v2 / external-id 语义主线 | retained patch 主体是功能检查与 external-id 修正 | 功能修复 | 不像当前方向 |
| `pr-64358` | `boundary -> race_condition_in_async_code` | metering singleton / recorder registry / flush loop | patch 虽然补了 `t.Cleanup` 和 loop 退出时 `SetMetering(nil)`，但 retained 主体仍是 process-global metering singleton 与异步 flush 流程重构 | singleton register/unregister + async flush 生命周期重排 | 更接近 global singleton / async 边界，不并入当前主体 |

## 第二十二批增量线索

93. TTL 这条线已经收敛出更强的动作模板：`Stop()` 还不够，最好 `WaitStopped(...)`
   - 当前增量正例：`pr-60901`

94. registry / checkpoint / engine 这类“运行过一次就留下物理痕迹”的资源，也属于当前方向主体
   - 当前增量正例：`pr-61977`, `pr-64105`
   - 这把当前正例从内存态/句柄态扩展到了磁盘与任务框架资产清理

95. process-global schema cache / disttask limit / metering singleton，继续保持边界处理
   - 当前新增 boundary：`pr-57823`, `pr-58589`, `pr-61400`, `pr-63897`, `pr-64358`
   - 尤其 `pr-64358` 再次说明：即便测试里有 `t.Cleanup`，只要 retained 主轴还是 global singleton/async flush，就不要误吸

96. 巨大功能修复里夹带的少量 cleanup 不能自动升格为当前方向正例
   - 当前代表：`pr-57201`, `pr-64170`

## 第二十三批已读记录（`221-230`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-64457` | `yes` | plan replayer 输出目录 / `config.TempDir` | 多个 plan replayer UT 共用全局 temp dir，dump 产物会撞到同一路径 | 保存旧 `TempDir`，测试内改成 `t.TempDir()` 并 restore | 这是当前方向里明确的 temp-path namespace isolation |
| `pr-64817` | `yes` | auto-analyze priority queue / queue DDL handler | auto analyze 关闭后队列仍保持 initialized 状态，后续事件/测试会继承脏队列状态 | 关闭 auto analyze 时显式 `pq.Close()`，允许后续重新 initialize | 属于后台 queue 生命周期收口 |
| `pr-65064` | `yes` | spill 临时目录 / `TempStoragePath` | 多组 spill 测试共享同一个全局 temp storage path，文件残留和并发写入会互相踩踏 | 每个测试先 `config.RestoreFunc()`，再把 `TempStoragePath` 指到各自 `t.TempDir()` | 很强的 temp-storage namespace isolation 正例 |
| `pr-65122` | `yes` | stats handler server socket / 导出文件路径 | stats handler tests 在共享 `/tmp` 下复用 socket 与 stats dump 文件名 | 统一改到 `t.TempDir()` 下的专属 socket / json 路径 | 和 plan replayer 的 temp-dir 支线完全同型 |
| `pr-65229` | `yes` | cluster-table RPC server / advertise address / registry 文件 | 测试自建 RPC server 后没有把地址、配置和 readiness 协调得足够严格，后续请求可能打到未就绪 server 或残留产物 | `t.Cleanup(config.RestoreFunc())`、显式设置 advertise address、等待 server ready、补文件清理 | 很典型的 harness/server teardown 与 namespace 隔离正例 |
| `pr-65313` | `yes` | OOM message filter 全局过滤器 | 同一测试里多段场景连续 `AddMessageFilter(...)`，但没有先清上一次 filter，导致后半段继承旧过滤条件 | 每次重新加 filter 前先 `oom.ClearMessageFilter()` | 属于 test hook/filter 生命周期没收口 |
| `pr-65317` | `boundary -> race_condition_in_async_code` | flight recorder / trace categories 全局 singleton | flaky 来自全局 flight recorder 与 category 状态在同一测试二进制里互相影响 | 改用 recorder-local categories、调整 global recorder 测试组织 | 主轴仍是 process-global singleton / trace state 边界 |
| `pr-65547` | `yes` | plan replayer dump 目录 / log file namespace | dump-single test 默认使用共享日志/plan replayer 目录，容易和其他 case 互撞 | 先造 `t.TempDir()`，再把 log 文件与 plan replayer 目录锚到测试专属路径 | 继续扩充 runtime file namespace 支线 |
| `pr-65644` | `yes` | storage 初始化路径 / `config.Path` | `TestInitStorage` 复用共享 storage path，系统 storage 初始化可能读到别的 case 产物 | 把全局 path 指到 `t.TempDir()` 并在 cleanup 恢复 | 本质仍是 per-test storage namespace 隔离 |
| `pr-65735` | `yes` | plan replayer server harness / `RunInGoTestChan` / global binding | 同一测试二进制里多次起 server 时复用已关闭的全局 test channel，且 dump/load 会留下全局 binding 干扰后续阶段 | 重建 `RunInGoTestChan`、串行化 DB 连接、在 dump 后显式 `drop global binding` | 属于 server harness 状态污染与 cleanup 不完整 |

## 第二十三批增量线索

97. `TempDir` / `TempStoragePath` 已经成为后半段最密集的一条正例簇
   - 当前增量正例：`pr-64457`, `pr-65064`, `pr-65122`, `pr-65547`, `pr-65644`
   - 共同点：
     - 原测试复用共享目录、socket、spill path 或导出文件名
     - 修法是把路径切到 per-test namespace，并且保留 restore

98. server/harness 自带的全局 channel / binding / address 也会跨阶段残留
   - 当前增量正例：`pr-65229`, `pr-65735`
   - 这说明当前方向不能只盯文件和句柄，还要盯“测试搭出来的临时 server harness”

99. filter / matcher / hook state 这条线再次出现了更直白的正例
   - 当前增量正例：`pr-65313`
   - 和 `pr-53507` 一起看，已经足够支撑一个“测试过滤器/匹配器状态未清空”的 sibling

100. flight recorder / trace state 这种 global singleton，继续坚持迁边界
   - 当前新增 boundary：`pr-65317`

## 第二十四批已读记录（`231-234`）

| case_id | 初步结论 | polluted_object | pollution_shape | stabilization_action | notes |
|---|---|---|---|---|---|
| `pr-65736` | `yes` | stats handler server harness / `RunInGoTestChan` | stats tests 多次起 server 时会复用已关闭的全局 go-test channel，后一个 server start 会被前一个测试残留状态影响 | 在各个 server 起点前重新创建 `RunInGoTestChan` | 和 `pr-65735` 同簇，属于 server harness 全局状态 reset |
| `pr-66074` | `yes` | extstore 路径探测环境 / 文件系统可写性判定 | 测试原先依赖真实 OS 目录权限与平台行为，路径/权限环境既共享又不稳定 | 用 `t.TempDir()` + 可注入 `afero.Fs` 替代真实 OS 目录权限，显式控制可写/只读环境 | 属于 runtime environment namespace/sandbox 隔离 |
| `pr-66642` | `no` | TopRU plumbing feature 主线 | retained patch 主体是 TopRU 状态与订阅能力的功能引入，测试里的 `t.Cleanup` / TopRU reset 只是新功能配套 | 功能实现 + 测试配套 cleanup | 不把 feature patch 里夹带的 cleanup 信号误吸进当前方向 |
| `pr-66988` | `yes` | import-into conflict resolution 临时目录 / `TempDir` | 测试依赖全局 `config.TempDir`，冲突处理产物会写到共享路径 | 保存旧值，测试内改为 `t.TempDir()` 后再 restore | 继续巩固 temp-dir namespace isolation 支线 |

## 第二十四批增量线索

101. `RunInGoTestChan` 这类 server test 专用的 process-global channel，也应按“harness 状态污染”处理
   - 当前增量正例：`pr-65736`

102. 测试不一定非要碰真实 OS 权限；给文件系统抽象注入测试 sandbox，本质上也是隔离共享环境
   - 当前增量正例：`pr-66074`

103. feature patch 中附带的 cleanup/t.Cleanup 继续保持严格排除
   - 当前代表：`pr-66642`

104. 到 `234 / 234` 全量 patch-first 复读结束后，除前面已经清晰的 close-path / teardown 主线外，后半段又补齐了 5 条新增 sibling 线索
   - `后台 manager / queue 显式 Stop/Close/WaitStopped`
   - `reused object / executor instance 必须 reset 后再复用`
   - `TempDir / TempStoragePath / config.TempDir` 驱动的 per-test 路径隔离
   - `server harness 全局 channel / binding / readiness / address` 清理与重置
   - `filter / matcher / hook state` 在 cancel/多阶段测试里的解绑与清空

105. 同时，边界也在后半段被进一步坐实成 3 条
   - `process-global knob / schema cache / autoid / RNG / config labels`
   - `process-global singleton / traceevent / metering / recordMap`
   - `disttask / scheduler / owner change` 这类 async framework 路径
   - 这三条后续可以直接作为 migrate-out 规则使用

## 第二轮 formalize backlog

这一节回答的不是“哪些 case 是正例”，而是：

- 在 `93` 个当前方向正例里，哪些 sibling 已经足够值得单独 formalize
- 哪些 sibling 先进入 backlog，但还不该马上写 JSON
- 下一步应该按什么顺序开工，才能避免又退回 smell-level 大桶

### 排序口径

优先级按下面 `5` 个维度综合判断：

1. patch-backed 集中度
   - 相同稳定化动作是否反复出现，而不是只有 `2-3` 个散例
2. 边界清晰度
   - 能不能和 `race_condition_in_async_code` / `t_parallel_with_shared_state` / feature patch 明确切开
3. agent 可操作性
   - 后续能不能自然长成稳定的 review signal / retrieval signal
4. 代表 case 的跨模块重复度
   - 是否跨 `executor / ddl / server / domain / statistics` 等模块重复出现
5. 对后续扫描的直接收益
   - formalize 后，能不能马上反哺仓库扫描 / case 过滤

### 当前建议优先级

| 优先级 | candidate sibling | 为什么现在值得做 | 代表 case | 暂不并入的边界 |
|---|---|---|---|---|
| `P0` | 共享 namespace 资源必须 per-test 唯一化 | patch-backed 集中度最高，修法非常稳定；而且对 retrieval 最友好 | `pr-7937`, `pr-8585`, `pr-41321`, `pr-41547`, `pr-56737`, `pr-64457`, `pr-65064`, `pr-65122`, `pr-65229`, `pr-65547`, `pr-65644`, `pr-66988` | 单纯 save-and-restore 全局 knob、但没有真正换独立 namespace 的 case，继续迁边界 |
| `P0` | 后台 component 必须显式 `Stop/Close/Wait`，不能靠 ignore / 自然退出 | 当前方向最像“test isolation 主轴”的一条；和 TTL / domain / worker / queue / metrics worker 都能对上 | `pr-3414`, `pr-4591`, `pr-37908`, `pr-38288`, `pr-39023`, `pr-40542`, `pr-50687`, `pr-53017`, `pr-60901`, `pr-64817` | 只是等后台状态收敛、或只改 lease/TTL/global knob 的 patch，继续迁到 async/race 边界 |
| `P1` | 临时句柄 / backend / engine / iterator 必须在所有退出路径上收口 | 资源生命周期信号很硬，且跨模块重复出现；很适合 formalize 成 close-path sibling | `pr-2921`, `pr-5654`, `pr-6140`, `pr-37016`, `pr-39718`, `pr-39783`, `pr-40010`, `pr-43067`, `pr-43758`, `pr-44206`, `pr-48133`, `pr-48604`, `pr-64105` | 只是 helper API 迁移但没有清晰 lifecycle 改动的 patch，先不吸进来 |
| `P1` | test 注入的 hook / filter / matcher 必须缩作用域并在 cancel/切阶段时解绑 | case 数没有前三条大，但纯度很高，而且 review signal 很明确 | `pr-37382`, `pr-42101`, `pr-53507`, `pr-65313` | 真正的问题如果是 process-global singleton / binding / trace state，则继续迁边界或并到 harness 子簇 |
| `P2` | reused fixture / executor instance 在再次复用前必须 reset | 机制很清楚，但当前 case 还偏少，适合先 hold 做 backlog | `pr-50008`, `pr-54709`, `pr-37372`, `pr-43758` | 如果 retained 主体是功能 bugfix，而 reset 只是顺手补的，不要硬吸进来 |
| `P2` | server / harness 级 test-global 状态必须重建或清理 | 这条很有价值，但当前还和 namespace / hook / singleton 边界交叉，先放第二批 | `pr-65229`, `pr-65735`, `pr-65736`, `pr-36506`, `pr-38808` | process-global trace/meters/singleton 若主体在生产代码共享态，仍按边界迁出 |

### 第一批建议直接 formalize 的 `3` 条

#### 1. 共享 namespace 资源必须 per-test 唯一化

为什么先做：

- patch-backed 证据最密
- 稳定化动作最一致：
  - `t.TempDir()`
  - 唯一 slow-log / socket / spill path / storage path
  - 唯一 db / table / file namespace
- 很适合后续做 retrieval 校准

建议 scope：

- table / db / file / path / socket / port / spill dir / log file / temp storage path
- 只要 retained patch 主体是在“换成独立 namespace”，都先保留在同一 sibling 里

先不拆的子边界：

- `db/table` 名字唯一化
- `TempDir/TempStoragePath/config.TempDir`
- slow-log / socket / server listen path

这几条先不要过早拆开，先合成一个 namespace sibling 看 purity。

#### 2. 后台 component 必须显式 `Stop/Close/Wait`

为什么先做：

- 这是当前 unified direction 里最像“test isolation and state pollution”主轴的一条
- 它能把大量“不要靠 goleak ignore / 不要靠自然退出”的 patch 收到一起

建议 scope：

- domain / store / server / worker / queue / TTL manager / metrics worker / background loop
- patch 主体必须落在显式 stop/close/wait 上

明确排除：

- 只是在测试里 `sleep` / `Eventually` 等后台状态收敛
- 只是在测试里关全局 knob，而没有先停 loop

#### 3. 临时句柄 / backend / engine / iterator 必须在所有退出路径上收口

为什么先做：

- 这条跨模块重复很多次，而且修法模式非常像
- 很容易形成统一的 review checklist：
  - 正常路径 close 了没
  - error path close 了没
  - early return / panic / open failure path close 了没

建议 scope：

- `RecordSet`
- `resp.Body`
- iterator / channel / worker handle
- chunk / temp storage RC
- backend / engine / ingest resource

### 第二批 backlog（原始 hold 记录；截至 `2026-04-18`，A/B/C 已正式落盘）

#### A. hook / filter / matcher scope + cleanup

先 hold 的原因：

- 纯度高，但 retrieval signal 还需要再想
- 很容易和 “process-global singleton / binding / trace categories” 混到一起

下一步要补的判断：

- 什么算 test-local hook/filter/matcher
- 什么已经变成 process-global singleton 边界

#### B. reused fixture / executor reset

先 hold 的原因：

- 机制很真，但 case 还不够多
- 需要确认它到底应该独立成 sibling，还是并到 broader “lifecycle reset” 线里

#### C. server / harness test-global state recreate/reset

先 hold 的原因：

- 有价值，但现在和 namespace isolation / singleton boundary 交叉太多
- 需要等第一批 formalize 完，再看它是否值得单开

### 当前不建议单独 formalize 的方向

下面这些现在都更适合作为边界规则，而不是当前 family 的 sibling：

1. process-global knob / schema cache / TTL / autoid / RNG / config labels
2. process-global singleton / logger / traceevent / metering / recordMap
3. disttask / scheduler / owner-change / async framework
4. 只靠 `Eventually` / `sleep` / 关功能开关来稳住后台状态

原因很简单：

- 这些 patch 的 retained 主体是共享状态竞态 / async ordering
- 不是 test isolation / teardown / namespace pollution 本体

### 推荐开工顺序

1. 先 formalize：`共享 namespace 资源必须 per-test 唯一化`
2. 再 formalize：`后台 component 必须显式 Stop/Close/Wait`
3. 再 formalize：`临时句柄 / backend / engine / iterator 必须在所有退出路径上收口`
4. 第一批 formalize 完后，已经继续 formalize：
   - `hook/filter/matcher scope + cleanup`
   - `reused fixture / executor reset`
5. 第二批 backlog 已全部落盘；这一轮边界校准先得到一个明确结论：package sandbox / `TestMain` 暂不继续从第六条里单拆。当前最纯的代表仍主要是 `pr-36506` / `pr-38808`，它们更像“给共享 harness/runtime 单独开 sandbox”的修法分支，而不是另一条独立机制。
6. 当前更值得继续压的是 harness recreate 与 namespace / background-component / global-singleton 边界；`package_sandbox_weak_recall` 先继续留在第六条里做弱召回，不升成单独 sibling 的默认第一跳。

### 对后续 JSON / rg_template 的约束

第一批开工时，仍然保持这几条约束：

1. 不要按现有 smell 字段把 `93` 个正例重新自动分桶
2. 不要先写 rg_template 再倒推机制
3. 每条 subpattern 都要先从工作板里拿出完整正例列表
4. `rg_template` 只能服务粗筛，允许 false positive，但不能反过来定义 subpattern
5. 一旦某条 retrieval signal 明显把大量 boundary case 拉进来，优先加 negative guards，而不是扩大 sibling 定义

## formalization 状态更新

`2026-04-18` 已完成前两批落盘：

- family skeleton：`patterns/test_isolation_and_state_pollution/README.md`
- retrieval：`patterns/test_isolation_and_state_pollution/retrieval_signals.json`
- subpattern：`patterns/test_isolation_and_state_pollution/subpatterns/共享_namespace_资源必须_per_test_唯一化.json`
- subpattern：`patterns/test_isolation_and_state_pollution/subpatterns/后台_component_必须显式_Stop_Close_Wait.json`
- subpattern：`patterns/test_isolation_and_state_pollution/subpatterns/临时句柄_backend_engine_iterator_必须在所有退出路径上收口.json`
- subpattern：`patterns/test_isolation_and_state_pollution/subpatterns/test_注入的_hook_filter_matcher_必须缩作用域并在_cancel_切阶段时解绑.json`
- subpattern：`patterns/test_isolation_and_state_pollution/subpatterns/可复用_fixture_executor_stateful_helper_再次使用前必须_reset_restore_clone.json`
- subpattern：`patterns/test_isolation_and_state_pollution/subpatterns/server_harness_package_sandbox_级_test_global_状态必须重建或清理.json`

当前这条 sibling 的 `v1` retrieval 有两个明确取舍：

1. 默认先偏向 path / socket / port / temp-storage / slow-log / plan-replayer 这类显式 namespace anchors。
2. 纯 `db/table/policy` 名字唯一化暂时不强行塞进默认第一跳；这部分继续保留更多人工 patch review，后续再单独校准弱召回模板。

第二条 sibling 的 `v1` retrieval 也有两个明确取舍：

1. 默认 broad recall 先偏向显式 lifecycle anchors，例如 `view.Stop()`、`WaitStopped(...)`、`DisableStats4Test()`、`TTLJobManager().Stop()`、`stopServer(...)`、`WaitGroupWrapper`，并默认排除 `main_test.go` 的通用 teardown 噪声。
2. `CreateMockStoreAndDomain/newStoreWithBootstrap + dom.Close/store.Close/server.Close` 这类 harness teardown 不强行塞进默认第一跳，而是单独保留一个 `harness_teardown_weak_recall` 模板。

第三条 sibling 的 `v1` retrieval 也有两个明确取舍：

1. 默认 broad recall 只抓显式 close-path anchors，例如 `rows.Close()`、`stmt.Close()`、`resp.Body.Close()`、`mustExecToRecodeSet`、`recycleChunk(...)`、`DerefAndClose`、`Unregister(job.ID)`，并默认排除 `main_test.go`。
2. 不把所有 `RecordSet` / `engine` / `rollback` 直接当默认第一跳；这些更泛的资源语义只放到文件级 `group_intersection` 里做第二跳 shrink。

第四条 sibling 的 `v1` retrieval 也有两个明确取舍：

1. 默认 broad recall 只抓显式 observer-scope / matcher-cleanup anchors，例如 `MustQueryWithContext`、`MustExecWithContext`、`clearMatchFn`、`AddMessageFilter`、`ClearMessageFilter`、`isInternal()`、`matchFn`。
2. matcher cleanup 如果主要落在实现文件里，就靠 `fallback_no_path` 去补；默认第一跳不把 generic `hook/filter/callback` 裸扫进来，避免和 process-global singleton / callback pointer 噪声混在一起。

第五条 sibling 的 `v1` retrieval 也有两个明确取舍：

1. 默认 broad recall 先偏向显式 reset/restore anchors，例如 `actionSpill.Reset()`、`payloads = payloads[:0]`、`OptimizerUseInvisibleIndexes`、`task.State/task.Step` 回写，以及可复用 executor 的字段归零锚点；generic `Clone()` 不放默认第一跳，而是留给带 `collation` / alias 语义的弱召回。
2. 默认第一跳不把所有 generic `Open()` / `Close()` / `Reset()`、所有 `Clone()`、或所有 session var 赋值都裸扫进来；那些更宽的 reset/reuse 语义只放到 `group_intersection` / `weak_recall` 里，避免和 close-path 资源回收、global knob restore、server harness recreate 混成一桶。

第六条 sibling 的 `v1` retrieval 也有两个明确取舍：

1. 默认 broad recall 只抓最硬的 harness-state anchors，例如 `RunInGoTestChan`、`stopServer(...)`、`clearTiKVStorage(...)`、`clearEtcdStorage(...)`、`ResetStoreForWithTiKVTest(...)`，而不把 generic `TestMain()` / `CreateMockStoreAndDomain()` / `goleak.VerifyTestMain(...)` 直接当默认第一跳。
2. package sandbox / `main_test.go` / `TestMain` 这条放在弱召回里单独补，因为它在 TiDB HEAD 上过于高频；默认第一跳先保证 server/harness/global-env 状态污染这条主轴纯度。

`2026-04-18` 又补了一轮第六条的检索校准：

- 用当前 subpattern JSON 里列的 `10` 条 representative positive patch 做 patch-proxy 回放：
  - `broad_recall = 5 / 10`
  - `group_intersection = 4 / 10`
  - `package_sandbox_weak_recall = 5 / 10`
  - `harness_teardown_weak_recall = 5 / 10`
  - `broad + 两条 weak_recall` 并集 = `10 / 10`
- 在 TiDB HEAD `/Users/fanzhou/workspace/github/tidb` 上看当前炸量：
  - `broad_recall = 20` 个文件
  - `group_intersection = 17` 个文件
  - `package_sandbox_weak_recall = 98` 个文件
  - `harness_teardown_weak_recall = 23` 个文件
- 当前结论：
  - 第六条继续维持“默认第一跳偏窄 + 两条弱召回补齐”的结构
  - `package sandbox / TestMain` 暂不抬进默认 broad，也不单拆第七条 sibling
  - 弱召回里允许 false positive；像 `pr-37908`、`pr-17964` 这类 background/global-config boundary 继续靠 `negative_guards` 切开
- 再往下看当前 TiDB HEAD 的实仓命中结构，主要有 3 个补充结论：
  - `broad_recall` 的 `20` 个文件里，`18` 个都在 `pkg/server/**`，说明这一跳当前主召回的确是 server restart / `RunInGoTestChan` / `stopServer` 这条 harness 主轴，不值得继续收 regex
  - `harness_teardown_weak_recall` 的 `23` 个文件里，主要噪声是普通 `BootstrapSession + defer dom.Close/store.Close` bootstrap scaffolding，以及 `SetSchemaLease(...)` 这种 global-knob boundary
  - `package_sandbox_weak_recall` 的 `98` 个文件主要集中在 `pkg/executor/test/**`、`pkg/session/test/**`、`pkg/planner/core/casetest/**`、`pkg/ddl/tests/**` 这类 generic `main_test.go` harness 初始化；因此继续只把它当定向弱召回，不抬到默认第一跳
- 这 3 桶再往下拆，当前最有用的结构统计是：
  - `broad_recall`：`RunInGoTestChan = 17 / 20`，`stopServer = 3 / 20`
  - `harness_teardown_weak_recall`：`BootstrapSession = 19 / 23`，`SetSchemaLease = 6 / 23`，`RunInGoTestChan = 4 / 23`
  - `package_sandbox_weak_recall`：`goleak.VerifyTestMain = 92 / 98`，`config.UpdateGlobal = 85 / 98`，`testsetup.SetupForCommonTest = 69 / 98`，`tikv.EnableFailpoints = 63 / 98`，`autoid.SetStep = 31 / 98`
- 这轮因此没有继续改 regex 主体，只补了一个明确的 soft down-rank：
  - `SetSchemaLease(...)`
  - 原因：这类命中在实仓抽样里稳定更像 global-knob / async boundary，而不是第六条主体
- 同时也明确了当前**不宜**直接拿来做 down-rank 的 generic scaffolding 词：
  - `goleak.VerifyTestMain(...)`
  - `config.UpdateGlobal(...)`
  - `testsetup.SetupForCommonTest(...)`
  - `tikv.EnableFailpoints()`
  - `autoid.SetStep(...)`
  - 原因：它们虽然贡献了 package-sandbox 桶的大部分噪声，但同时也是 package sandbox 分支真实会出现的运行时初始化上下文；现在直接压掉，会更容易伤到本来就不多的正例
- 详细说明见：
  - `patterns/test_isolation_and_state_pollution/给agent的仓库扫描检索信号.md`
  - `patterns/test_isolation_and_state_pollution/第六条_实仓候选采样台账.md`


## 导航文件

- source set 入口：`patterns/test_isolation_and_state_pollution_234_case_source_set.tsv`
  - 只用于导航到 patch / case / test path
  - 不是分类器

## Source Set PR IDs

### Block 1

`pr-1301`, `pr-2921`, `pr-2968`, `pr-3098`, `pr-3414`, `pr-3435`, `pr-3706`, `pr-4076`, `pr-4532`, `pr-4591`, `pr-4733`, `pr-5020`, `pr-5654`, `pr-6140`, `pr-6548`, `pr-6554`, `pr-6950`, `pr-7232`, `pr-7937`, `pr-8585`, `pr-8719`, `pr-8724`, `pr-8807`, `pr-9119`, `pr-9412`, `pr-9483`, `pr-9534`, `pr-9960`, `pr-10003`, `pr-10295`, `pr-10848`, `pr-10855`, `pr-10900`, `pr-10949`, `pr-10953`, `pr-11121`, `pr-11204`, `pr-12796`, `pr-12910`, `pr-13112`, `pr-13169`, `pr-13553`, `pr-13580`, `pr-13859`, `pr-14179`, `pr-14296`, `pr-14592`, `pr-14615`, `pr-14681`, `pr-14732`, `pr-14746`, `pr-14756`, `pr-14825`, `pr-14839`, `pr-14868`, `pr-15119`, `pr-15201`, `pr-15245`, `pr-15260`, `pr-15665`, `pr-16722`, `pr-17206`, `pr-17437`, `pr-17667`, `pr-17964`, `pr-18051`, `pr-18230`, `pr-18414`, `pr-18424`, `pr-18497`, `pr-18751`, `pr-18963`, `pr-19058`, `pr-19434`, `pr-19484`, `pr-19526`, `pr-19561`, `pr-19710`, `pr-19762`, `pr-19863`

### Block 2

`pr-20142`, `pr-21117`, `pr-21415`, `pr-21493`, `pr-21643`, `pr-21664`, `pr-21668`, `pr-22009`, `pr-22276`, `pr-22916`, `pr-22977`, `pr-23122`, `pr-23244`, `pr-23502`, `pr-23610`, `pr-24235`, `pr-24779`, `pr-24807`, `pr-25035`, `pr-26233`, `pr-26460`, `pr-26463`, `pr-26586`, `pr-26728`, `pr-26848`, `pr-26875`, `pr-27477`, `pr-27482`, `pr-27894`, `pr-28693`, `pr-28898`, `pr-29053`, `pr-30045`, `pr-30287`, `pr-30299`, `pr-30306`, `pr-30323`, `pr-30346`, `pr-30490`, `pr-30503`, `pr-30692`, `pr-30891`, `pr-31032`, `pr-31167`, `pr-31317`, `pr-31371`, `pr-31781`, `pr-31815`, `pr-31896`, `pr-31950`, `pr-31984`, `pr-31989`, `pr-32005`, `pr-32225`, `pr-32674`, `pr-33246`, `pr-33772`, `pr-34578`, `pr-35246`, `pr-35343`, `pr-35373`, `pr-35374`, `pr-36115`, `pr-36217`, `pr-36506`, `pr-36507`, `pr-36578`, `pr-36722`, `pr-37003`, `pr-37014`, `pr-37016`, `pr-37372`, `pr-37382`, `pr-37705`, `pr-37908`, `pr-38143`, `pr-38161`, `pr-38288`, `pr-38374`, `pr-38808`

### Block 3

`pr-39023`, `pr-39718`, `pr-39747`, `pr-39783`, `pr-39900`, `pr-40010`, `pr-40024`, `pr-40199`, `pr-40542`, `pr-41321`, `pr-41356`, `pr-41547`, `pr-42009`, `pr-42101`, `pr-42133`, `pr-42336`, `pr-42454`, `pr-42589`, `pr-42776`, `pr-43067`, `pr-43108`, `pr-43139`, `pr-43399`, `pr-43758`, `pr-44206`, `pr-45488`, `pr-45563`, `pr-45579`, `pr-45969`, `pr-46075`, `pr-48050`, `pr-48133`, `pr-48184`, `pr-48604`, `pr-48653`, `pr-50008`, `pr-50156`, `pr-50687`, `pr-52060`, `pr-52968`, `pr-53017`, `pr-53507`, `pr-53548`, `pr-54311`, `pr-54709`, `pr-55362`, `pr-55431`, `pr-56002`, `pr-56737`, `pr-56798`, `pr-57201`, `pr-57823`, `pr-58589`, `pr-60901`, `pr-61400`, `pr-61977`, `pr-63897`, `pr-64105`, `pr-64170`, `pr-64358`, `pr-64457`, `pr-64817`, `pr-65064`, `pr-65122`, `pr-65229`, `pr-65313`, `pr-65317`, `pr-65547`, `pr-65644`, `pr-65735`, `pr-65736`, `pr-66074`, `pr-66642`, `pr-66988`
