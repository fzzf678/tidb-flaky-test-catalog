# watchlist 候选 subpattern 草案（不落 JSON）

这份文档是对 `async_wait_without_backoff` family 的 `watchlist` 里 **最有潜力成簇** 的方向做一次“跨 case 对齐”：

- 目标：把 **共享失稳机制 / 共享修法机制** 抽成可复查的候选簇，并明确边界与下一步证据需求。
- 非目标：立刻落盘 `subpatterns/*.json`（这些方向目前仍偏 singleton / 边界未稳）。
- 备注：这里记录的 `rg_template`/signals 仅用于 **coarse retrieval**（召回候选），不是 subpattern 成立证据。

当前对齐的 5 个方向：

1. delta-based wait：**基线采样时序**（baseline capture）
2. async publish（etcd/config/infoschema）：**读后不保证立刻可见**（visibility lag）
3. `require.Eventually` 内直接用 `assert.*`：**poisoned retries**（瞬时失败永久污染测试结果）
4. 外部服务 readiness 探测（MinIO/S3）：用可观测信号替代“curl 成功/盲等”
5. 异步 completion barrier/join：不要立刻断言（或固定 sleep），用 Eventually / channel / WaitGroup 等到异步收敛

---

## 候选簇 A：delta-based wait 的 baseline capture（TOCTOU / missed-event）

### 机制（失稳）

典型形态是“等待 records/sqlMeta 等计数增量”：

- wait 函数按 **delta** 判断（`len(x)-old >= cnt`）
- 但 `old`（基线）是在 wait 调用内部 **现取** 的
- 当“异步上报/发送”在 wait 调用前已经完成（或部分完成）时：
  - 基线被采样得太晚，导致 wait 逻辑要求 **额外增量**，而测试实际只会发生一次上报
  - 结果：等待超时/卡死式失败（不是 backoff 问题，而是 **missed event**）

把它理解成：等待逻辑用“自举的相对增量”来避免绝对值耦合，但基线采样点与触发点之间没有屏障，产生 TOCTOU。

同型也会出现在 **版本号/epoch-based wait**（例如 `SchemaMetaVersion()`）里：如果 baseline 在 DDL 已经推进后才采样，就可能“永远等下一次 version bump”，从而把本来是短抖动的可见性延迟，放大成超时/卡死。

### 典型形态（伪代码）

```go
// anti-pattern：Wait 内部现取 baseline，且调用点在 trigger 之后
triggerAsyncSend()
WaitDelta(/*baseline is captured inside*/, /*delta*/ 1, timeout) // baseline 可能已经包含了本次 send

// fix：baseline 必须在 trigger 之前采样，并显式传入 wait
base := getCountBaseline()
triggerAsyncSend()
WaitDelta(base, /*delta*/ 1, timeout)
```

### 共享修法机制（patch 上的共性）

把“基线采样”从 wait 内部移到触发前，或让 wait 明确接收基线参数：

- 先读取 baseline（如 `RecordsCnt()/SQLMetaCnt()`）
- 再触发发送（`TrySend` / 上报动作）
- 再等待 `len(x) - baseline >= expected_delta`

也常见把一个 wait 拆成多个：records / sqlMetas 各自等待（避免只等 records 但 meta 尚未到达）。

### 对齐样本（source smell = async_wait_without_backoff）

| case_id | 样本位置 | 触发点 | 原因归纳 | 修法归纳 |
|---|---|---|---|---|
| `pr-32464` | `util/topsql/reporter/single_target_test.go` + `util/topsql/topsql_test.go` | `TrySend` 后再 `WaitCollectCnt` | 异步上报可能先于 wait，导致 `old=len(records)` 采样太晚，永远等不到 “+1” | 抽出 `RecordsCnt/SQLMetaCnt` 基线，并把 `WaitCollectCnt` 改成 `(old,cnt)`；新增 `WaitCollectCntOfSQLMeta` |

### 近邻样本（跨 source smell，但机制同型）

| case_id | source smell | 样本位置 | 触发点 | 修法归纳 |
|---|---|---|---|---|
| `pr-66642` | `insufficient_cleanup_between_tests` | `pkg/util/topsql/reporter/single_target_test.go` | `TrySend` 前先读 `records/sqlMeta/ruRecords` baseline | 先采样 `RecordsCnt/SQLMetaCnt/RURecordsCnt`，再触发发送，再等待 `> baseline`，避免异步发送已发生导致的 missed-event 等待超时 |
| `pr-65784` | `shared_table_without_isolation` | `pkg/server/handler/tests/http_handler_serial_test.go` | `doTrigger()` 前先读 job-history baseline | 先采样 `baseJobCnt`，再触发 TTL job，再 `Eventually` 等到 `jobCnt==base+1`，避免“采样太晚 → 等待额外 +1” |
| `pr-54447` | `async_schema_propagation` | `pkg/ddl/tests/partition/db_partition_test.go` | 触发 `truncate partition` 前先读 `SchemaMetaVersion()` baseline | 先采样 `v1 := dom.InfoSchema().SchemaMetaVersion()`，再触发 DDL；在等待 DDL job state 变更时同步要求 `v2>v1`，避免“DDL state 已推进但 infoschema 仍旧” |
| `pr-54695` | `async_schema_propagation` | `pkg/ddl/schema_test.go` | 触发 `rename table` 前先读 `SchemaMetaVersion()` baseline | 先采样 `v1`，再触发 rename；用 `require.Eventually(v2>v1)` 显式等待 infoschema reload 完成，避免 stale infoschema |

### 边界（不要混入）

- **不等价于** `race_condition_in_async_code` 的 TopSQL mock sink “共享 map/slice 并发读写”：
  - 那类本质是数据竞争/同步原语缺失；这里本质是 wait 的 **基线采样时序** 导致 missed event。
- **不等价于** `time_sleep_for_sync`：
  - 如果 patch 只是把 sleep 调大/轮询次数调大，没有引入“基线提前采样/显式 barrier”，不要算进来。
- **不等价于** “用 baseline/delta 规避共享状态污染（pre-existing rows）”：
  - 那类 baseline 的意义是把断言从“绝对值”改成“相对变化”，但不一定有严格的“触发点→异步 side-effect→等待可见”的时序链路（例如 `pr-48050` 的系统表计数 delta 更像 `shared_state_pollution`）。

### retrieval draft（coarse，非证据）

优先加 path hint 降噪：

- path hints：
  - `util/topsql/reporter/mock/server.go`
  - `util/topsql/reporter/*_test.go`
  - `util/topsql/*_test.go`
- anchors（交集检索）：
  - `WaitCollectCnt(` + `RecordsCnt(` / `SQLMetaCnt(` / `len(svr.records)` / `len(svr.sqlMetas)`
  - `TrySend(&ReportData{` 与上述 anchors 的局部共现
- 同型变体（schema meta version）：
  - path hints：`pkg/ddl/schema_test.go`、`pkg/ddl/tests/partition/*_test.go`
  - anchors：`SchemaMetaVersion()` + `require.Eventually(` + `> v1`/`v2 > v1`

### 证据缺口 / 下一步

在本 smell source set 内仍偏 singleton（仅 `pr-32464`），但跨 catalog 已出现多条同型样本（`pr-66642`、`pr-65784`、`pr-54447`、`pr-54695`），覆盖 “计数增量（records/job-history）” 与 “版本号增量（SchemaMetaVersion）” 两类可见性信号，说明“baseline capture → wait delta”很可能是跨模块通用的补稳修法机制。

建议下一步：

1. 在 TiDB 仓库做一次小范围 scan：优先 `util/topsql/**`、`pkg/util/topsql/**`，找 “`TrySend` 之后再 wait 计数增量” 的用法。
2. 如果补到 ≥2 条同型 patch（不同 PR / 不同测试），再考虑把该簇升格为正式 JSON（可能是跨模块的通用簇，不必绑定 TopSQL 目录）。

> 注：A 与 B（visibility lag）会有交叠——很多“可见性滞后”的修法，会自然采用“基线采样 + 等 delta”作为实现手段；A 更偏“patch 机制”，B 更偏“系统语义上读后不一定可见”的失稳机制。

---

## 候选簇 B：async publish 的 read-after-write 可见性滞后（visibility lag）

### 机制（失稳）

测试做了“写入/触发状态变更 → 立刻读 back 并断言可见/值相等”的强一致假设（典型场景：etcd/global-config；同型也常见于 infoschema/schema meta version、config reload 等异步 publish 路径）：

- 真实系统里写入/同步到 etcd 是异步的（存在传播延迟）
- 读 back 可能短时间返回 `len(resp.Kvs)==0`
- 因此“立刻断言 kv 存在”会在 CI 下概率失败

### 共享修法机制（patch 上的共性）

把“读 back 断言”改成 **bounded retry**：

- 循环 Get + 判空 + sleep（或 Eventually）
- 达到条件后再做 key/value 断言
- 超时则 fail（必须有上限）

### 典型形态（伪代码）

```go
writeConfigAsync()

// fix：读后立刻断言 → Eventually / bounded retry
require.Eventually(t, func() bool {
	resp := etcdGet(key)
	return len(resp.Kvs) > 0
}, timeout, interval)
```

同型变体（schema / cache 可见性）：用 “版本号/epoch” 做可见性信号：

```go
baseVer := dom.InfoSchema().SchemaMetaVersion()
triggerDDL()
require.Eventually(t, func() bool {
	return dom.InfoSchema().SchemaMetaVersion() > baseVer
}, timeout, interval)
```

### 对齐样本（source smell = async_wait_without_backoff）

| case_id | 样本位置 | 触发点 | 原因归纳 | 修法归纳 |
|---|---|---|---|---|
| `pr-29900` | `domain/globalconfigsync/globalconfig_test.go` | `set @@global...` 后立刻 `etcd.Get` | etcd 写入/同步异步，读 back 可能暂时为空 | 加 `for i<20 { Get; if empty sleep; else assert; return }`，超时 fail |

### 近邻样本（跨 source smell，但机制同型）

| case_id | source smell | 样本位置 | 触发点 | 修法归纳 |
|---|---|---|---|---|
| `pr-65732` | `time_sleep_for_sync` | `br/pkg/utils/register_test.go` | etcd lease grant/keepalive/reput 是异步的，TTL/列表查询可能短暂报 `requested lease not found` | 用 `require.Eventually` 替换固定 sleep，并在 Eventually 中容忍 transient lease-not-found；同时把 retry interval 变成可控（failpoint） |
| `pr-15604` | `race_condition_in_async_code` | `config/config_handler_test.go` | reload callback 结束（`reloadWg.Done()`）早于全局 config `Store()`，`reloadWg.Wait()` 后立刻读 `ch.GetConfig()` 可能读到 stale | 追加一次 reload tick（`reloadWg2`）作为 “state committed” 屏障，确保 store 已发生后再断言 |
| `pr-15332` | `race_condition_in_async_code` | `config/config_handler_test.go` | 原 test 依赖真实 `interval/time.After` 调度来触发 reload，调度抖动下容易 race | 注入可控 `timeAfter` channel + `registerWg/reloadWg` 等待 register/reload；并把 suite 改 `SerialSuites` |
| `pr-54447` | `async_schema_propagation` | `pkg/ddl/tests/partition/db_partition_test.go` | `truncate partition` 的 DDL job state 达标后，infoschema 仍可能未完成 reload | 引入 domain，并用 `SchemaMetaVersion()` 作为“新 infoschema 已加载”的可见性信号，避免仅靠 sleep/DDL job state |
| `pr-54695` | `async_schema_propagation` | `pkg/ddl/schema_test.go` | `rename table` 完成后立刻跑后续语句，可能读到 stale infoschema | 记录 `v1` 并 `Eventually(v2>v1)` 等待 infoschema meta version 推进 |
| `pr-59974` | `schema_version_race` | `pkg/ddl/tests/partition/db_partition_test.go` | wait loop 里只比较 `v2>v1` 但不更新 baseline，可能无法稳定覆盖 “job state 达标 → infoschema reload” 的二阶段 | 当检测到 `v2>v1` 时把 `v1=v2` 作为新 baseline，确保后续“再等一次 infoschema loading”不会用旧 baseline 误判 |

### 边界（不要混入）

- 与 “process-global config 的数据竞争/污染” 不同：
  - 后者关注 `GetGlobalConfig()` 返回的对象被原地改写、或并发读写 map；应迁到 `test_isolation_and_state_pollution` / `race_condition_in_async_code` 侧的簇。
- 与 `time_sleep_for_sync` 的关系：
  - 该修法确实包含 sleep，但本质是补齐“外部一致性延迟”的等待语义；如果后续出现更硬的 barrier（比如显式 flush/sync API），应优先归入“completion barrier”簇而非仅 sleep。

### retrieval draft（coarse，非证据）

- path hints：
  - `domain/globalconfigsync/*_test.go`
  - `config/config_handler_test.go`
  - `pkg/ddl/**/schema*_test.go`
  - `pkg/ddl/tests/partition/*_test.go`
  - `pkg/util/etcd/*`（若有）
- anchors：
  - `RandClient().Get(` / `Client().Get(` + `"/global/config/` / `globalconfig`
  - `len(resp.Kvs) == 0` + `time.Sleep(` / `Eventually(`
  - `SchemaMetaVersion()` + `require.Eventually(`（同函数/相邻窗口）

### 证据缺口 / 下一步

在本 smell source set 内仍是单点（仅 `pr-29900`），但跨 catalog 已出现多条同型机制：

- etcd/lease 侧：`pr-65732`
- config reload/state publish 侧：`pr-15604`、`pr-15332`
- infoschema/schema meta version 侧：`pr-54447`、`pr-54695`、`pr-59974`

因此该簇更像一个“外部/异步状态的 read-after-write 可见性滞后”的通用方向；后续升格时需要明确 scope（etcd-only vs 更泛化的 visibility lag）和与相邻 family（`async_schema_propagation`/`schema_version_race`）的边界。

建议下一步：

- 扩展观察范围到 “外部 KV/etcd/PD 写后读验证” 的测试（可能分散在 domain/owner/ddl 等处）。
- 若后续出现多条同型 patch，再决定该簇应落在：
  - `async_wait_without_backoff`（若修法仍主要是 retry/backoff/Eventually）
  - 或拆出更贴切的 family（如 external state visibility / eventually-consistent read-after-write）。

---

## 候选簇 C：`require.Eventually` 的 poisoned retries（EventuallyWithT）

### 机制（失稳）

在 `require.Eventually(t, func() bool { ... })` 的谓词里直接调用 `assert.*(t, ...)`（使用外层 `*testing.T`）：

- `assert.*` 失败会调用 `t.Errorf()`（非 fatal，但会把测试标记为 failed）
- `Eventually` 的语义是“允许谓词在若干次尝试中失败，只要最终在 timeout 内满足即可”
- 但一旦某次尝试里触发 `t.Errorf()`，即使后续尝试成功，测试仍可能因为之前的失败记录而整体失败

因此，在调度抖动（`-race`/并行 shard/锁竞争）下，第一次/前几次尝试的瞬时失败会 **永久污染** 测试结果，这就是“poisoned retries”。

### 共享修法机制（patch 上的共性）

两类等价修法：

1. 用 `require.EventuallyWithT`：
   - `require.EventuallyWithT(t, func(c *assert.CollectT) { assert.NoError(c, ...) }, ...)`
   - 每次尝试使用 `CollectT` 收集失败，不会把失败写到外层 `t`
2. 把谓词改成纯布尔表达式（无副作用）：
   - `return adv.OnTick(ctx) == nil` / `return err == nil`

### 典型形态（伪代码）

```go
// anti-pattern：谓词里调用 assert.*(t, ...) 产生 t.Errorf() 副作用
require.Eventually(t, func() bool {
	assert.NoError(t, doSomething()) // 一次 transient 失败就“污染”整个测试
	return true
}, timeout, interval)

// fix 1：EventuallyWithT + CollectT
require.EventuallyWithT(t, func(c *assert.CollectT) {
	assert.NoError(c, doSomething())
}, timeout, interval)

// fix 2：纯布尔表达式（无副作用）
require.Eventually(t, func() bool {
	return doSomething() == nil
}, timeout, interval)
```

### 对齐样本

**本 smell source set 内：**

| case_id | 样本位置 | 触发点 | 原因归纳 | 修法归纳 |
|---|---|---|---|---|
| `pr-66870-3` | `br/pkg/streamhelper/advancer_test.go` | `Eventually` 中 `assert.NoError(t, adv.OnTick(ctx))` | 瞬时错误会触发 `t.Errorf()`，导致 “Eventually 后续成功也救不回” | 改用 `EventuallyWithT` + `CollectT`；并补 `Eventually(!adv.HasTask())` 等待 state transition |

**跨 family 的相邻证据（不属于本 smell source set，但机制同型）：**

| case_id | source smell | 样本位置 | 修法归纳 |
|---|---|---|---|
| `pr-66907` | `race_condition_in_async_code` | `br/pkg/streamhelper/advancer_test.go` | 同样把 `Eventually`+`assert.NoError(t, ...)` 改成 `EventuallyWithT`+`CollectT` |

### 边界（不要混入）

- 与 “Eventually 条件过弱导致过早放行” 不同（例如只检查 `len==0` 但未确保 job truly picked）：
  - 后者属于 predicate strength / completion condition 问题（见 `pr-66870-4` 的同 PR 系列 patch）。
- 与 “Eventually 失败后继续执行导致后续竞态扩大” 不同（fail-fast）：
  - 后者更像测试控制流/fixture teardown 的问题（见本 family watchlist：`pr-45657`）。
- 与 “需要等待某个异步状态机收敛（缺 barrier）” 不同：
  - `EventuallyWithT` 解决的是 **断言副作用**，不是等待条件本身；两者可叠加但要分开描述。

### retrieval draft（coarse，非证据）

建议做局部窗口共现，减少误报：

- anchors：
  - `require.Eventually(` + `assert.`（同一函数/同一 closure 内）
  - 或 `assert.NoError(t,` / `assert.ErrorContains(t,` 与 `Eventually(` 共现
- shrinker：
  - 优先限定 `*_test.go`
  - 若命中 `EventuallyWithT(`，再反向找原本是否有 `Eventually(` + `assert.*(t,` 的替换历史（需要 patch/proxy 辅助）
  - repo-scan 时可直接用 multiline（高召回但要人工复核）：
    - `rg -n -U "require\\.Eventually\\(t, func\\(\\) bool \\{[\\s\\S]{0,300}?assert\\.[A-Za-z0-9_]+\\(t," --glob '*_test.go'`

### 证据缺口 / 下一步

该机制在 catalog 内至少已有两条明确正例（`pr-66870-3`、`pr-66907`），但在 `async_wait_without_backoff` 的 source set 内仍只有 1 条；且从 TiDB 主仓历史快速扫（`git log -G EventuallyWithT -- '*_test.go'`）看，这类修法出现频率并不高，倾向是“低频但高纯”的机制。

建议下一步：

1. 先在更大的全仓 patch/PR 集里收集更多 “`Eventually` + `assert.*(t, ...)` → `EventuallyWithT`” 的样本。
2. 若形成稳定簇，优先考虑把它 formalize 成 **跨 family 的通用 subpattern**（更像“test assertion semantics”类机制，而非某个模块专属）。

补充观察（不等价但相邻）：

- “`require.*`/`Must*` 这类 **fatal** 断言/助手函数放在 `Eventually` 谓词里”会直接打断重试循环，属于另一种“retries 被断言语义破坏”的风险；是否需要独立成簇，取决于后续能否补到足够多 patch-backed 正例。

---

## 候选簇 D：外部服务 readiness 探测（MinIO/S3）不要只看 “curl 成功”

### 机制（失稳）

外部服务（典型：MinIO）启动后短时间内可能出现：

- 端口已监听但 HTTP 返回 `5xx`
- `curl` 退出码不稳定（连接失败 / 超时 / TLS/HTTP 细节）

如果 readiness 探测只写成：

- `while ! curl ...; do sleep; done`

就可能出现两类 flake：

1. **误判 ready**：`curl` 成功但服务实际上返回 `5xx` 或未进入可用态，后续请求才失败。
2. **误判不 ready**：`curl` 命令本身在错误分支/退出码上不稳定（例如 pipeline/`set -e` 行为），导致 readiness loop 逻辑被提前打断或永远卡住。

### 共享修法机制（patch 上的共性）

把 readiness 条件改成“更可复核的外部信号”，并确保 shell 条件表达式正确：

- 用 `curl -f`（把 HTTP >=400 当失败）或显式读取 `http_code`
- 对 `curl` 失败显式 `|| true`，避免脚本被错误退出码中断
- readiness loop 用 **bounded retry**（最大次数/超时）+ `sleep`
- 对 shell 的 boolean expression 用 `{ ...; }` 或正确的 `&&/||` 组合，避免 `!` 的优先级/短路导致逻辑反转

### 对齐样本

| case_id | source smell | 样本位置 | 原因归纳 | 修法归纳 |
|---|---|---|---|---|
| `pr-33666` | `async_wait_without_backoff` | `br/tests/br_s3/run.sh` | MinIO readiness 探测对异常/HTTP 状态不稳，导致启动检测偶发误判 | 用 `http_code` + `|| true` 做有界循环探测；最后修正 shell 条件表达式 `{ [ code>0 ] && [ code<500 ]; }` |
| `pr-33610` | `network_without_retry` | `br/tests/br_s3/run.sh` | 同型（早期版本），readiness loop 条件仍可能被 shell 表达式坑到 | 引入 `http_code` 探测与 `|| true`，但 boolean expression 版本仍偏脆弱（后续由 `pr-33666` 修正） |

### 边界（不要混入）

- 只调大 `sleep`/重试次数而不改 readiness 判据 → 更像 `time_sleep_for_sync`
- 外部服务“outage 注入/kill/restart 协调”属于相邻机制（可能需要等信号文件/事件），不要硬塞进 readiness 探测簇

### retrieval draft（coarse，非证据）

- path hints：
  - `br/tests/br_s3/run.sh`
  - 其它 `tests/**/run.sh`（尤其含 `minio`/`S3_ENDPOINT` 的）
- anchors：
  - `start_s3()` / `S3_ENDPOINT`
  - `curl -w '%{http_code}'` / `curl -f`
  - `|| true` 与 `http_code` 同窗出现

### 证据缺口 / 下一步

当前正例主要集中在同一个脚本（`br_s3/run.sh`）。若要升格为更通用的 subpattern：

- 需要在其它外部服务（如 PD mock / HTTP servers / object storage）测试里补到同型 patch；
- 或明确把该 subpattern scope 限制为 “br integration shell harness 的 readiness 探测”。

---

## 候选簇 E：异步 goroutine/worker 完成屏障（join）：不要立刻断言/固定 sleep

### 机制（失稳）

测试在以下场景中，**隐含假设** “异步 goroutine/后台 worker 的状态变化/退出已经发生”：

- `Close()` / cancel 后立刻断言 goroutine 已退出
- 依赖后台 rollback/commit/cancel 的结果，但未等异步路径真正完成
- 用 `atomic` 计数 + `time.Sleep` 轮询来做并发屏障（容易卡在某个分支上永远等不到）

而现实中这些状态变化都依赖调度/锁/异步收尾路径，属于典型的 timing window：

- 立刻断言会偶发失败（慢机/CI 抖动）
- 或 sleep/poll 的屏障条件在某些 interleaving 下永远等不到 → hang/timeout

### 共享修法机制（patch 上的共性）

把隐式假设改成 **显式 completion barrier**（且必须有上限）：

- 用 `require.Eventually` 等到谓词成立（例如 goroutine 不存在、某个状态已完成）
- 或引入更硬的同步信号（channel/WaitGroup），等待异步 goroutine 把“完成/退出”显式通知回来
- 把“固定 sleep/原子轮询”替换为“可复查的屏障 + bounded timeout”

### 对齐样本

| case_id | source smell | 样本位置 | 原因归纳 | 修法归纳 |
|---|---|---|---|---|
| `pr-33809` | `async_wait_without_backoff` | `ddl/db_integration_test.go` | 后台 query rollback 是异步的，测试结束前未等 rollback 完成 | `select { case <-ch: ... case <-time.After(...): fail }` 等到后台完成信号 |
| `pr-43273` | `async_wait_without_backoff` | `executor/seqtest/seq_executor_test.go` | close/cancel 后 goroutine 退出非即时，立刻 `checkGoroutineExists` 会吃调度窗口 | 对多个 goroutine keyword 分别用 `require.Eventually` 等到不存在 |
| `pr-45244` | `time_sleep_for_sync` | `executor/test/seqtest/seq_executor_test.go` | 固定 sleep 太短导致 `checkGoroutineExists` 偶发仍为真 | 用 `require.Eventually` 替换 `time.Sleep(10ms)`，等待 goroutine 消失 |
| `pr-18963` | `race_condition_in_async_code` | `session/session_test.go` | goroutine 里的 `COMMIT` 可能发生在主线程 teardown（DROP TABLE）之后 | 在 goroutine 结束前额外 `ch <- 0`，主线程 `<-ch` 等 goroutine 退出 |
| `pr-32009` | `time_sleep_for_sync` | `dumpling/export/dump_test.go` | writer goroutine 延迟 cancel ctx，主线程先断言 `dumpDatabases` 返回 canceled error 会抢跑 | 先 `wg.Wait()` 等 writer/cancel 完成，再断言 canceled error |
| `pr-37873` | `time_sleep_for_sync` | `ddl/db_change_test.go` | 用 atomic+sleep 轮询来等“两 session 同时进入屏障”可能卡住 | 用 `WaitGroup` + channel 显式建屏障：两 session 先对齐，再放行执行顺序 |

### 边界（不要混入）

- “goroutine 数量增长/减少”类断言（用 `runtime.NumGoroutine()` 证明行为）是另一类机制（更像调度敏感断言）
- 如果根因是 data race（共享变量/容器缺锁）或 WaitGroup Add/Done 顺序竞态，则应迁到 `race_condition_in_async_code`
- 如果修法只是“把 sleep 调大/把 timeout 调大”，且没有引入更硬的 completion barrier，则更像 `time_sleep_for_sync`

### retrieval draft（coarse，非证据）

- anchors：
  - `require.Eventually(` 与 `checkGoroutineExists(` 同窗
  - `WaitGroup` / `Add(` / `Done()` / `Wait()` 与 `go func()` 同窗
  - `time.After(` 与 `select { case <-ch: ... }` 同窗（用于找 “channel+timeout 的 completion barrier”）
- path hints：
  - `*_test.go`（优先）
  - `executor/**/seq*_test.go` / `ddl/**` / `session/**` / `dumpling/**`（按爆炸量再收敛）

### 证据缺口 / 下一步

该簇在 catalog 内已有多条不同 PR 的正例，且修法机制高度一致（Eventually 或显式 join 屏障）；下一步可以：

- 继续补 “Close/cancel 后立刻断言 vs join barrier” 的同型 patch（尤其是非 `checkGoroutineExists` 的场景），确认边界是否能收敛成稳定子簇；
- 若要 formalize，倾向做成跨 family 的通用 subpattern（更像“async completion barrier”），避免被 `time_sleep_for_sync` / `async_wait_without_backoff` / `race_condition_in_async_code` 重复吸收。
