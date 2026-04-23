# 扩样：对象存储 streaming `Read` 中途失败 → reopen reader + offset 续读

目标：为 `network_without_retry` 里的 watchlist `pr-51506` 寻找更多 **同机制**正例（patch-first 证据），以判断是否能升格为稳定 sibling subpattern（原则：至少 `>= 3` 个高纯正例，再落正式 `subpatterns/*.json`）。

> 注意：检索/召回只用于找候选；最终结论一律以 **patch-first 复读 diff** 为证据。

## 本次扩样中“同机制”的判定标准（high-purity）

仅把同时满足下面特征的 case 视为同机制正例：

1. **触发面**：对远端对象存储（S3/KS3/…）进行 streaming `Read` 时，底层 reader 可能因为网络抖动/远端异常在中途失败。
2. **修法核心**：不能把错误直接抛给上层；需要在 **同一次 `Read(p)` 调用内**做 bounded retry（例如最多 3 次），通过 **重新打开对象 reader** 并从“已读 offset”继续读取来完成本次 `Read`。
3. **硬边界**：retry 必须是 *resume*（从 offset 续读），而不是“从头再读”或“让上层重新开始整个读流程”；并且需要 reset per-call retry state，避免跨 Read 调用污染。

上面 (2)(3) 是把该簇与“泛化网络重试”“上层重试”“并发读取/预取优化”等改动区分开的关键边界。

## 粗召回策略（仅用于找候选）

本轮扩样使用的候选召回入口（仅用于找候选）：

- `cases/**/pr-*.json` 的 `changed_files` 命中 `br/pkg/storage/s3.go` 的 case
- 以及少量补充：`changed_files` 同时命中 `br/pkg/storage/ks3.go`（因为 `pr-51506` 同时修改了 ks3/s3 reader）

候选清单（patch-first 全部复读）：

`pr-34409`, `pr-46633`, `pr-48142`, `pr-48873`, `pr-57591`, `pr-64358`, `pr-64402`

上游补充扩样（非 `cases/` 数据集，仍按 patch-first 复读）：

- `pr-59694`：objstore: fix read position on retry when reading a file range using s3

## patch-first 复读台账（候选 → 结论）

| case_id | patch_url | 结论 | 一句机制说明（patch-first） |
|---|---|---|---|
| `pr-51506` | https://github.com/pingcap/tidb/pull/51506.patch | **positive（source set 基准）** | `s3ObjectReader/ks3ObjectReader.Read` 内做 bounded retry：Read 失败时 reopen reader，并从 offset 续读；并测试 `ResetRetry` 行为保证 per-Read state 不跨调用污染。 |
| `pr-59694` | https://github.com/pingcap/tidb/pull/59694.patch | **positive（上游补充正例，未入库 case）** | 修复 range reader 在 retry reopen 时的读位置：`Open` 时把 `pos` 初始化为 `range.Start`；并用 `TestS3RangeReaderRetryRead` 验证“Read 中途失败后 retry 仍能从正确 offset 继续读”。 |
| `pr-34409` | https://github.com/pingcap/tidb/pull/34409.patch | negative | `s3.go` 相关改动是 `WalkDir` prefix/ObjPrefix 行为与测试覆盖，非 streaming Read retry/resume。 |
| `pr-46633` | https://github.com/pingcap/tidb/pull/46633.patch | negative | 方向是“并发 range 读取/并发读优化”（external byte reader + `ReadDataInRange` 等），不涉及“Read 中途失败 → reopen + offset 续读”的 retry 机制。 |
| `pr-48142` | https://github.com/pingcap/tidb/pull/48142.patch | negative | `s3.go` 改动集中在 writer/upload（例如 pipe close / PartSize 可配置），非 reader 的 retry/resume。 |
| `pr-48873` | https://github.com/pingcap/tidb/pull/48873.patch | negative | 引入/调整 prefetch reader，并在 `s3ObjectReader.Read` 增加 `maxCnt==0 -> io.EOF`；不涉及 Read 失败后的 reopen/resume。 |
| `pr-57591` | https://github.com/pingcap/tidb/pull/57591.patch | negative | `s3.go` 改动是“强一致性 marker / WalkDir tombstone 语义”等，非 reader retry/resume。 |
| `pr-64358` | https://github.com/pingcap/tidb/pull/64358.patch | negative | `s3.go` 仅注释/计数逻辑相关小改，非 reader retry/resume。 |
| `pr-64402` | https://github.com/pingcap/tidb/pull/64402.patch | negative | `s3/ks3` 增加 request 计数拦截（Send handlers）并移除 OnUpload 回调，属于 metering/observability；非 reader retry/resume。 |

## 当前结论

- 在当前 `cases/` 数据集内，基于 patch-first 证据，“streaming Read 内 reopen + offset 续读”的高纯同机制正例仍是 `1` 条（`pr-51506`）。
- 但在上游 patch-first 扩样中发现 `pr-59694` 是高纯同机制补充正例：说明该机制不是偶然的“一次性补丁”，而是持续演进/被验证过的 retry-resume 语义问题。
- 目前该簇的 patch-backed 正例仍 **未达到 `>= 3`** 的 formalize 门槛，因此 `pr-51506` 继续维持 watchlist（先不落正式 `subpatterns/*.json`）。

## 下一步建议（若要继续扩样）

1. 继续坚持“Read 内 retry + reopen + offset resume”硬边界，否则会把“并发读取/预取优化/写入参数调整/请求计数”等无关 patch 混入，纯度会迅速下降。
2. **建议升格门槛（避免把单实现演进史误当机制簇）**：
   - 优先门槛：`>= 3` 条 patch-first 正例，且至少 `2` 条来自不同 backend 或不同 reader 层（例如 object reader vs range reader；S3 vs 非 S3）。
   - 折中门槛（扩样困难时）：`>= 2` 条正例 + 至少 1 组强负例边界（negative guards）被明确验证能排掉常见“假相似 patch”（如并发 range 读取/预取优化/writer/WalkDir/metering）。
3. 若要拿到更多正例，优先走“演进线 + 测试意图”两条路（召回只用于找候选，最终仍以 patch-first 复读确认）：
   - **按实现位点追历史**：`br/pkg/storage/s3.go`、`br/pkg/storage/ks3.go`，以及同目录下其它 backend（例如 gcs/azblob/hdfs 等实际存在者）里 `Read`/`Open` 的演进；重点盯 `pos/offset/start`、reopen、retry loop 的引入/修正。
   - **按测试意图召回**：优先搜 `Test.*Retry.*Read` / `RetryRead` / `RangeReader.*Retry` / `ResetRetry` 这类“失败后续读语义”的 UT 名字与断言形态。
   - **按 failpoint 注入召回**：优先找 `failpoint.Inject` 注入“对象存储读失败/中断”的补丁；新增 failpoint + UT 的 PR 往往对应同机制修补。
4. 如果仍然补不到第 3 个正例：
   - 可考虑引入**非 flaky case**（当前 `cases/` 只覆盖 flaky 相关 PR，样本天然稀疏），或
   - 把上游补充正例回填进 catalog（例如将 `pr-59694` 写成 case），以便后续 formalize 时机制簇更可复查、更易继续扩样。
