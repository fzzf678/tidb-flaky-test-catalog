# 扩样：SQL/DB 操作的 retry +（必要时）重建连接 + per-attempt state reset

目标：为 `network_without_retry` 里的 watchlist `pr-30673` 寻找更多 **同机制**正例（patch-first 证据），以判断是否能升格为稳定 sibling subpattern（原则：至少 `>= 3` 个高纯正例，再落正式 `subpatterns/*.json`）。

> 注意：这里的检索/召回只用于找候选；最终结论一律以 **patch-first 复读 diff** 为证据。

## 本次扩样中“同机制”的判定标准（high-purity）

仅把同时满足下面特征的 case 视为同机制正例：

1. **触发面**：SQL/DB 操作会遇到短暂断链/可重试错误（连接抖动、driver bad connection、transient errors 等），一次失败不应直接把错误抛上层。
2. **修法核心**：引入 `WithRetry`/`RunWithRetry`/backoffer/backoff 这类“可控重试层”，并对“哪些错误可重试”做显式分类/收敛（而不是无脑循环）。
3. **必要时重建连接**：若错误可能来自连接本身（例如连接已不可用），重试必须允许 **重建 conn / refresh session**，而不是在坏连接上原地重试。
4. **per-attempt state reset**：每次重试必须 reset 本次 attempt 的局部 accumulator / partial results（避免部分结果 / 重复结果污染后续尝试）。

其中 (3)(4) 是把该簇与“泛化 SQL retry wrapper”区分开的关键边界：很多 patch 只做 (2) 或只做 backoff，不会做到 (3)(4)。

## 粗召回策略（仅用于找候选）

在全库 `cases/` 里做过以下粗召回（仅用于找候选，不能当证据）：

- 关键词：`sql retry`, `WithRetry`, `RunWithRetry`, `RetrySQL`, `rebuild`, `reconnect`, `bad connection`
- changed_files 线索：`dumpling/export/*`, `br/pkg/*/conn.go`, `*/retry.go`, `util/backoff/*`

结论：能稳定命中的候选非常少；目前更像是 **机制稀缺**，而不是我们漏检。

## patch-first 复读台账（候选 → 结论）

| case_id | patch_url | 结论 | 一句机制说明（patch-first） |
|---|---|---|---|
| `pr-30673` | https://github.com/pingcap/tidb/pull/30673.patch | **positive（但仍是 singleton）** | 引入 `BaseConn` 包装：SQL query/exec 统一走 `utils.WithRetry` + backoffer；第二次起可重建连接；并通过 `reset()`/清空结果容器保证 per-attempt state 不污染后续尝试。 |
| `pr-46790` | https://github.com/pingcap/tidb/pull/46790.patch | near-miss | 引入通用 `RunWithRetry` + exponential backoff 来重试“更新 job table”的函数，但不体现“重建连接 + per-attempt accumulator reset”这组强边界。更像“泛化 SQL retry wrapper”。 |
| `pr-44801` | https://github.com/pingcap/tidb/pull/44801.patch | negative | 对 lightning 获取表结构时的错误处理做“忽略某类错误并继续”，不是 retry/rebuild conn 机制簇。 |
| `pr-32667` | https://github.com/pingcap/tidb/pull/32667.patch | negative | sqlmock 稳定性修补（延迟 + 注释 typo），不是 retry/rebuild conn 机制簇。 |
| `pr-32009` | https://github.com/pingcap/tidb/pull/32009.patch | negative | 调整测试 cancel/wait 时序与断言顺序，非 retry/rebuild conn 机制簇。 |

## 当前结论

- 以目前 patch-first 证据，`pr-30673` 仍是 **高纯 singleton**；尚不足以升格为稳定 `subpatterns/*.json`。
- `pr-46790` 等“只做 retry/backoff”的 patch 很可能会形成另一个更宽的 sibling，但它的机制边界与 `pr-30673` 不一致（缺少 conn rebuild + per-attempt reset），如果直接合并会降低纯度。

## 下一步建议（若要继续扩样）

1. **扩大候选来源而不是扩大边界**：继续保持 (3)(4) 这两个强边界，否则 subpattern 会变成过宽的“只要加 retry 都算”。建议优先在 `br/`、`dumpling/`、`lightning/` 的 SQL 访问层里找“重建连接 + reset state”的 patch。
2. **沿实现演进线扩样（比关键词更稳）**：优先沿 `pr-30673` 改动路径追文件历史，再逐条 `.patch` patch-first 复读确认是否同机制。
   - 优先位点：`dumpling/export/conn.go`（`BaseConn`）、`dumpling/export/retry.go`（`rebuildConnFn`/`Reset`/错误分类）、`dumpling/export/sql.go`（`reset()` 调用点）。
   - 关键锚点（仅用于召回候选）：`BaseConn`、`WithRetry(`、`dbutil.IsRetryableError`、`rebuildConnFn`、`backOffer.Reset()`、`reset()`/清空结果容器。
3. **刻意补“必要性证据”（锁住边界，避免 overfit）**：
   - 至少补 1 条能证明“**重建连接是必要条件**”的正例：错误形态是连接不可用（bad connection / ping failed / session invalid），如果不 rebuild 就会原地失败。
   - 至少补 1 条能证明“**per-attempt reset 是必要条件**”的正例或对照：不 reset 会导致 partial/duplicate/混合旧结果污染。
   - 同时保留几条“只做 retry/backoff 但无 rebuild/reset”的负例，用来证明它们不应并入本簇（否则纯度会被拉垮）。
4. **允许跨 smell 扩样**：这类机制可能被标到其他 smell（例如 `async_wait_*`、`resource_cleanup_*`），但 patch-first 仍可能同机制；扩样时可不拘泥于 `network_without_retry` 标签。
5. 如果长时间找不到同机制正例：保留 `pr-30673` 在 watchlist，并把“泛化 SQL retry wrapper（不含 conn rebuild + reset）”留作**候选扩样方向**（除非后续 patch-first 读出一个明确且一致的高纯簇，否则不要急于 sibling 化）。
