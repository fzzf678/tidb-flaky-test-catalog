# `network_without_retry` 给 agent 的仓库扫描检索信号

这份文档记录的是：

- 本轮从 `network_without_retry` smell 的全量 patch-first 复读里，抽出来的 **coarse retrieval draft**
- 以及这些 draft 在 **正例 patch 文本** 上的回放结果（patch-text proxy）

它不是：

- verdict / classification 规则
- subpattern 定义证据（subpattern 的证据仍然只来自 patch-first 聚类）

## Hard Rules

1. `rg_template` 只能做粗筛，允许 false positive。
2. 不能因为某条 regex 能 hit 到 patch，就反过来把它当成 subpattern 成立依据。
3. 最终是否命中机制，必须回到 `subpatterns/*.json` 的 `signals_required / negative_guards`。

## 本轮已 formalize 的 subpattern

当前只有 1 条稳定 sibling：

- `TiKV/TiFlash RPC 遇到 leader/region/engine 不可用类错误时，不能直接失败；要 backoff 并换 peer 或 fallback`
  - 正式定义：[`subpatterns/TiKV_TiFlash_RPC_遇到_leader_region_engine_不可用类错误时_不能直接失败_要_backoff_并换_peer_或_fallback.json`](./subpatterns/TiKV_TiFlash_RPC_遇到_leader_region_engine_不可用类错误时_不能直接失败_要_backoff_并换_peer_或_fallback.json)

## 当前 full positive set（patch-first retained）

该 subpattern 当前的 full positive set（来自本轮 patch-first）是：

- `pr-22449`
- `pr-23078`
- `pr-39834`

总计：`3`。

## draft broad `rg_templates`

这些模板都按 `rg -n -S '<pattern>' <repo_root>` 口径设计。

### Template A：`broad_recall_rpc_reroute_fallback`

```regex
(?i)(InvalidateCachedRegionWithReason|NoLeader|NotLeader|EpochNotMatch|GetRegionError|BoRegionMiss|ErrTiFlashServerTimeout|BoTiFlashRPC)
```

意图：

- 先把“可重试拓扑/region error”与 “TiFlash fallback sentinel” 两类强锚点全部粗召回
- recall 优先，不追求 precision

### Template B：`group_intersection_shrinker`（建议用来降炸量）

> 思路：先各自召回，再对文件路径做交集。

Group 1（错误类型锚点）：

```regex
(?i)(NoLeader|NotLeader|EpochNotMatch|GetRegionError|RegionError|ErrTiFlashServerTimeout)
```

Group 2（重试/节奏控制锚点）：

```regex
(?i)(Backoff\\(|BoRegionMiss|BoTiFlashRPC)
```

意图：

- 把“只提到错误类型但不重试”的代码排掉一部分
- 把“只有 Backoff 但错误类型不明确”的代码也排掉一部分

## patch-proxy 回放结果（仅验证形态盲区）

> 这里验证的是：模板能不能在 patch 文本里重新“看见” retained 机制；不是实仓 precision。

| template | 命中 full positives | 结果 |
|---|---:|---|
| `broad_recall_rpc_reroute_fallback` | `3 / 3` | 3 条都能命中 |
| `group_intersection_shrinker` | `3 / 3` | 3 条都能命中（但在实仓仍可能吸到相邻 RPC backoff 噪声） |

## Watchlist draft `rg_templates`（未 formalize，仅记录粗召回）

> 这些方向目前仍是 singleton watchlist（证据不足以升 `subpatterns/*.json`），这里只记录“怎么粗召回候选”。最终是否同机制仍要回到 patch-first 复读。

### Template C：`watchlist_sql_retry_rebuild_and_reset`（对应 `pr-30673`）

```regex
(?i)(BaseConn|QuerySQL\\(|WithRetry\\(|backOfferResettable|rebuildConnFn|retry-aware|cannot execute query)
```

建议收敛方式：

- **强 path hint**：`dumpling/export/`（否则 `WithRetry` 在全仓会炸）
- 或用“交集”进一步压炸量：`BaseConn` ∩ `WithRetry(` ∩ `rebuildConn`
  - 额外扩样提示（仍只做候选召回）：优先沿 `dumpling/export/conn.go` / `dumpling/export/retry.go` / `dumpling/export/sql.go` 的文件历史追后续 PR，再逐条 patch-first 复读确认是否同机制（比全仓关键词更稳）

patch-proxy 回放（形态检查）：

- 在 `pr-30673.patch` 上可命中（`BaseConn/QuerySQL/WithRetry/rebuildConnFn/backOfferResettable` 均出现）

### Template D：`watchlist_object_store_read_retry_resume`（对应 `pr-51506`）

```regex
(?i)(s3ObjectReader|ks3ObjectReader|read s3 object failed, will retry|maxErrorRetries|retryCnt)
```

建议收敛方式：

- path hint：`br/pkg/storage/(s3|ks3)\\.go`
- 注意：`Read\\(` 本身会炸，避免用“Read”当主锚点
  - 额外扩样提示（仍只做候选召回）：优先搜 `ResetRetry` / `StartOffset` / `range.Start` / `pos`，以及测试名形态 `Test.*Retry.*Read` / `RetryRead` / `RangeReader.*Retry`；这些更贴近“Read 内 retry + reopen + offset resume”机制

patch-proxy 回放（形态检查）：

- 在 `pr-51506.patch` 上可命中（`s3ObjectReader/ks3ObjectReader` + warn log string）
- 在 `pr-59694.patch` 上可命中（range reader retry 的补充正例，含 `StartOffset`/`pos` 初始化与 UT `TestS3RangeReaderRetryRead`）

## 哪些信号会炸、怎么收敛

1. `Backoff(` 本身在 TiDB 内部非常常见
   - 建议搭配 Group 1 的错误类型锚点做交集
2. `BoRegionMiss` 命中面仍然偏大
   - 建议加 path hint：`store/tikv/`, `ddl/`, `kv/`, `txnkv/` 等
3. `ErrTiFlashServerTimeout` 相对更窄
   - 适合追 TiFlash fallback 分支时直接用作第一跳锚点

4. watchlist 方向的 `WithRetry(` / `retryCnt` 也很常见
   - 必须依赖 path hint / 交集（见 Template C / D），否则噪声远大于信号

## 下一步（什么时候补 `retrieval_signals.json`）

当满足以下条件时再补结构化 `retrieval_signals.json`：

- 至少有 2–3 条稳定 sibling（不是 singleton watchlist）
- family 边界收敛（SQL retry / object-store retry / readiness wait 的去向稳定）
- 且每条 sibling 都有可复用的 `signals_required / negative_guards`
