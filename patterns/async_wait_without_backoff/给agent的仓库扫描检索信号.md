# 给 agent 的仓库扫描检索信号（coarse retrieval，不是 subpattern 证据）

这份文档只负责 **检索层**：帮 agent 在全仓里快速召回候选点，减少漏看。

强调三点：

1. 这里的 `rg_template` 只做 **coarse retrieval**，不能当作 subpattern 成立证据。
2. 命中 grep ≠ 命中 subpattern；命中后仍要回到 patch-first/代码语义按 JSON 的 `signals_required` 复核。
3. 下面的 “patch-proxy 回放” 只是验证这些信号能召回正例 patch 的典型改动片段，不代表全仓 scan precision。

## 本轮已 formalize 的 subpatterns

- `disttask cleanup 完成前不要做清理断言（等 task 消失 / 双 cleanup 信号）`
- `DDL delete-range 清理由异步 GC 驱动：用 mysql.gc_delete_range(_done) 取代扫 KV/盲等`
- `GC/MemoryLimit 触发型等待：Eventually 谓词内主动 runtime.GC()（并等待 tuner 退出）`
- `验证 retry 的测试不要“碰运气”：用 failpoint 强制触发，或 Eventually 重试直到触发`
- `等待/重试循环必须可中断：检查 ctx/killed，避免不可取消的 Sleep 等待`

## 1) disttask cleanup：等 task 消失 / 双 cleanup 信号

### Broad signals

- 关键词锚点：
  - `WaitCleanUpFinished`
  - `doCleanupTask`
  - `GetTaskManager(`
  - `GetTaskByID(`
  - `ErrTaskNotFound`
  - `DefaultCleanUpInterval`
  - `ReduceCheckInterval`
  - `TestLastTaskID`
- 目录 hint（不是硬门槛）：
  - `pkg/disttask/`
  - `tests/realtikvtest/importintotest*/`
  - `tests/realtikvtest/addindextest*/`

### `rg_template`

```bash
rg -n "WaitCleanUpFinished|doCleanupTask|ErrTaskNotFound|GetTaskManager\\(|DefaultCleanUpInterval|TestLastTaskID" -S .
```

如果炸量大，先加路径收敛：

```bash
rg -n "ErrTaskNotFound|GetTaskManager\\(|WaitCleanUpFinished|doCleanupTask" -S pkg/disttask tests/realtikvtest
```

### patch-proxy 回放（正例）

- `pr-61207`：命中 `doCleanupTask` + `WaitCleanUpFinished`
- `pr-64478` / `pr-66701`：命中 `GetTaskManager` + `ErrTaskNotFound` + `TestLastTaskID`

### 会炸的信号

- 只搜 `cleanup`/`CleanUp` 会非常泛；必须和 disttask/task manager 关键词一起用。

## 2) DDL gc_delete_range(_done)：不要扫 KV/盲等

### Broad signals

- 关键词锚点：
  - `mysql.gc_delete_range_done`
  - `mysql.gc_delete_range`
  - `gc_delete_range_done`
  - `waitGCDeleteRangeDone`
  - `setDeleteRangeChecker`
  - `OnJobUpdated` / `SetHook`（用于捕获 jobID）
- 目录 hint：
  - `pkg/ddl/`
  - `ddl/`
  - `pkg/ddl/tests/`

### `rg_template`

```bash
rg -n "gc_delete_range_done|gc_delete_range\\b|waitGCDeleteRangeDone|setDeleteRangeChecker" -S .
```

收敛版：

```bash
rg -n "gc_delete_range_done|gc_delete_range\\b" -S pkg/ddl ddl
```

### patch-proxy 回放（正例）

- `pr-29499`：命中 `mysql.gc_delete_range_done`
- `pr-29651`：命中 `gc_delete_range_done` + `gc_delete_range` + `SetHook`

### 会炸的信号

- 只搜 `delete range` 可能会把很多不相关日志/注释召回；建议用系统表名做锚点。

## 3) GC/MemoryLimit：Eventually 谓词内 runtime.GC()

### Broad signals

- 关键词锚点：
  - `runtime.GC()`
  - `require.Eventually(`
  - `adjustPercentageInProgress`
  - `nextGCTriggeredByMemoryLimit`
  - `WaitMemoryLimitTunerExitInTest`
  - `TestIssue48741`
- 目录 hint：
  - `pkg/util/gctuner/`
  - `util/gctuner/`

### `rg_template`

```bash
rg -n "TestIssue48741|WaitMemoryLimitTunerExitInTest|adjustPercentageInProgress|nextGCTriggeredByMemoryLimit" -S pkg/util/gctuner util/gctuner
```

第二跳再找 predicate 内的 `runtime.GC()`：

```bash
rg -n "require\\.Eventually\\(|runtime\\.GC\\(\\)" -S pkg/util/gctuner util/gctuner
```

### patch-proxy 回放（正例）

- `pr-66870-1`：Eventually predicate 内插入 `runtime.GC()`
- `pr-67377`：多处 Eventually predicate 内插入 `runtime.GC()` + teardown 等待 exit

### 会炸的信号

- 全仓直接搜 `runtime.GC()` 会非常泛；必须加 path hint（`gctuner`）或加状态变量锚点。

## 4) Retry 观测测试：不要碰运气

### Broad signals

- 关键词锚点：
  - `TestAuditPluginRetrying`
  - `mockCommitError`（failpoint）
  - `IsRetryingCtxKey`
  - `retrying`
  - `require.Eventually`（用于重复触发）
- 目录 hint：
  - `pkg/server/tests/`
  - `pkg/session/`

### `rg_template`

```bash
rg -n "TestAuditPluginRetrying|mockCommitError|IsRetryingCtxKey|retrying" -S pkg/server pkg/session
```

### patch-proxy 回放（正例）

- `pr-65114`：`require.Eventually` 包裹 workload，重复直到 `len(testResults) > concurrency`
- `pr-67308`：`failpoint.Enable(\"...mockCommitError...\")` 强制触发 retry

### 会炸的信号

- 只搜 `retry` 会召回大量网络重试/DDL 重试；必须绑定到具体测试名或 failpoint key。

## 5) 可中断等待：ctx/killed/ExecWithContext/WithTimeout

### Broad signals

- 关键词锚点：
  - `ExecWithContext(`
  - `SessionVars().Killed` / `Killed`
  - `ErrQueryInterrupted`
  - `ctx.Err() == nil`
  - `context.WithTimeout(`
  - `ctx.Done()`
- 目录 hint：
  - `pkg/executor/`
  - `store/tikv/`
  - `pkg/ttl/`

### `rg_template`

```bash
rg -n "ExecWithContext\\(|ErrQueryInterrupted|SessionVars\\(\\)\\.Killed|ctx\\.Err\\(\\) == nil|context\\.WithTimeout\\(" -S .
```

收敛版（更少炸量）：

```bash
rg -n "ErrQueryInterrupted|ExecWithContext\\(|SessionVars\\(\\)\\.Killed" -S pkg store
```

### patch-proxy 回放（正例）

- `pr-12852`：命中 `Killed` + `ErrQueryInterrupted` + sleep-wait 内检查 killed
- `pr-57140`：命中 `ExecWithContext`
- `pr-57703`：命中 `ctx.Err() == nil` + `context.WithTimeout`

### 会炸的信号

- `context.WithTimeout` 全仓很常见；需要结合 “循环/worker stop/drain/killed/interrupt” 语境做人审。

