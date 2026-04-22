# 给 agent 的仓库扫描检索信号（`async_schema_propagation`）

本文件只记录 **coarse retrieval** 的草案信号与回放结果，用于后续 repo-scan / 人工复核提效：

- ✅ 目标：尽量把“可能属于该 family 的候选 patch”召回出来，供 agent 再做 patch-first 判定
- ❌ 非目标：把检索信号当成 subpattern 成立依据（subpattern 是否成立只看 patch-backed 机制簇）

> 备注：下文的 “patch-proxy 回放” 指用 `.patch` 文本当作 proxy 来测 **正例召回**；它不代表真实仓库扫描 precision。

---

## Family-level broad retrieval（先召回，再人工判）

### rg_template（broad）

建议优先在 `*_test.go` 范围内扫描（避免被生产代码大量淹没）：

```bash
rg -n --glob '*_test.go' -S \
  'SchemaMetaVersion\\(|GetSnapshotInfoSchema\\(|GetAndResetRecentInfoSchemaTS\\(|SchemaOutOfDateRetryTimes|tidb_max_delta_schema_count'
```

> 备注：该 broad 入口主要覆盖 `s1/s2/s3`；`s4`（显式 `dom.Reload()` 作为同步屏障）单独见下文 `s4` 的检索模板，避免把 `Reload()` 直接塞进 broad 入口导致候选爆炸。

### patch-proxy 回放（retain-only 正例）

- pattern：`SchemaMetaVersion|GetSnapshotInfoSchema(|GetAndResetRecentInfoSchemaTS(|SchemaOutOfDateRetryTimes|tidb_max_delta_schema_count`
- 正例集：`{pr-14305, pr-14976, pr-54447, pr-54695, pr-59974, pr-65786, pr-66732}`
- 命中：`7 / 7`

---

## `s1`：DDL 完成不等于 infoschema loaded（等 `SchemaMetaVersion` 推进）

### 为什么这样设计

这条机制的“硬证据”是：patch 里出现 `dom.InfoSchema().SchemaMetaVersion()` 的显式等待（`> v1`），而不是单纯 sleep。

### rg_template（可按炸量逐步收紧）

**1) broad：只用关键 API 锚点**

```bash
rg -n --glob '*_test.go' -S 'SchemaMetaVersion\\('
```

**2) narrow：加 domain/infoschema 上下文**

```bash
rg -n --glob '*_test.go' -S 'InfoSchema\\(\\)\\.SchemaMetaVersion\\('
```

**3) further narrow：同时出现 DDL job 观测/等待**

```bash
rg -n --glob '*_test.go' -S 'SchemaMetaVersion\\(|admin show ddl jobs|ddl finish does not mean|infoschema loaded'
```

### patch-proxy 回放（s1 正例）

- pattern：`SchemaMetaVersion`
- 正例：`{pr-54447, pr-54695, pr-59974}`
- 命中：`3 / 3`

### 可能会炸的信号

- `SchemaMetaVersion()` 在生产代码、诊断日志里也可能出现；务必先限定 `*_test.go`，必要时再加路径（如 `pkg/ddl/**`、`ddl/**`、`pkg/infoschema/test/**`）。

---

## `s2`：internal cache/TS 不要断言 sentinel（用 snapshot 推导/只断言不变量）

### 为什么这样设计

这条机制的 patch-backed 修法高度集中在两类 API：

- `GetSnapshotInfoSchema(ts)`：用 snapshot 推导期望 infoschema（稳定）
- `GetAndResetRecentInfoSchemaTS(...)`：reset 后只断言不变量（稳定）

### rg_template

```bash
rg -n --glob '*_test.go' -S 'GetSnapshotInfoSchema\\(|GetAndResetRecentInfoSchemaTS\\('
```

可选收窄（stale read / snapshot 场景常伴随）：

```bash
rg -n --glob '*_test.go' -S 'GetSnapshotInfoSchema\\(|tidb_snapshot|tidb_read_staleness'
```

### patch-proxy 回放（s2 正例）

- pattern：`GetSnapshotInfoSchema(|GetAndResetRecentInfoSchemaTS(`
- 正例：`{pr-65786, pr-66732}`
- 命中：`2 / 2`

### 可能会炸的信号

- `tidb_snapshot` / `tidb_read_staleness` 会召回很多与本子模式无关的 stale-read 测试；建议以 `GetSnapshotInfoSchema` / `GetAndResetRecentInfoSchemaTS` 为主锚点。

---

## `s3`：调大 out-of-date/infoschema 容错旋钮（RetryTimes / max_delta_schema_count）

### 为什么这样设计

这条机制在 patch 里几乎都是“在测试 setup/init 里直接改旋钮”，因此可用 identifier 直接粗召回。

### rg_template

```bash
rg -n --glob '*_test.go' -S 'SchemaOutOfDateRetryTimes|SchemaOutOfDateRetryInterval|tidb_max_delta_schema_count'
```

如果想只抓 SQL 形态的设置：

```bash
rg -n --glob '*_test.go' -S 'set\\s+@@global\\.tidb_max_delta_schema_count'
```

### patch-proxy 回放（s3 正例）

- pattern：`SchemaOutOfDateRetryTimes|tidb_max_delta_schema_count`
- 正例：`{pr-14305, pr-14976}`
- 命中：`2 / 2`

### 可能会炸的信号

- `tidb_max_delta_schema_count` 可能在文档/注释中出现；建议先限定 `*_test.go`，必要时再限定 `ddl/**` 相关目录。

---

## `s4`：`Domain.Reload()` 作为 schema/cache 同步屏障（DDL/lock 状态变更后断言前必须 reload）

### 为什么这样设计

这条机制的 patch-backed 证据高度集中在：测试在关键断言/执行前显式调用 `dom.Reload()`（或 `domain.GetDomain(sess).Reload()`），并把它当作“释放/刷新 cache + 推进 infoschema 可见性”的同步屏障。

### rg_template（分两跳，先召回再收束）

**1) broad：先按 `Reload()` 锚点粗召回**

```bash
rg -n --glob '*_test.go' -S 'GetDomain\\(.*\\)\\.Reload\\(|\\.Reload\\(\\)'
```

**2) shrink：在候选文件里再做 DDL/lock/状态机上下文交集（只是 shrinker，不是 absence proof）**

```bash
rg -l --glob '*_test.go' -S 'GetDomain\\(.*\\)\\.Reload\\(|\\.Reload\\(\\)' <repo_root> | \
  xargs rg -n --glob '*_test.go' -S 'lock tables|unlock tables|admin show ddl jobs|SchemaState|OnJob|ddl jobs|schema state'
```

### patch-proxy 回放（s4 正例）

- pattern：`Reload(`
- 正例：`{pr-19580, pr-21491, pr-21624, pr-21664}`
- 命中：`4 / 4`

### 可能会炸的信号

- `Reload()` 在很多测试中会被用于通用 setup/多 domain 协调；仅凭命中无法直接判定属于 `s4`，必须回到 patch-first 复核其作为“同步屏障”的因果角色。
- 若召回量过大，优先用 “lock/unlock / DDL job state 观测 / SchemaState” 做文件级交集收束，再人工读 patch 判定。

---

## 额外提醒（本轮 watchlist 里最像会成簇的信号）

这些还没落正式 JSON，但如果后续要扩展 source set，可以优先用下面的锚点粗召回候选：

- `ErrInfoSchemaChanged`（尤其出现在 test 对 commit/txn 的容忍逻辑里）
- `SetSchemaLease(` / `schema lease`（测试调 lease 稳定化）
- `OwnerCheckAllVersions` / `waitSchemaChanged`（schema sync 语义边界）
