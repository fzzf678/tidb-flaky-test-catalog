# `network_without_retry`

这个目录承接 **“Network operations without retry”** 这条 smell（`network_without_retry`）的机制细化工作。

需要强调：这里不是把 smell 直接镜像成目录；`network_without_retry` 在本 repo 里只作为 **patch-first 人工复读的 source set**。
进入人工 review 后，唯一允许的聚类依据是：

- 共享的不稳定机制
- 或共享的修法机制

不能按关键词、模块名、测试名、报错文案的表面相似度归桶。

## Source set

- source smell：`network_without_retry`
- source case set：`8`（即当前所有带该 smell 的 case）
- patch-first 已人工复读：`8 / 8`

本轮 source set 全量清单：

`pr-22449`, `pr-23078`, `pr-30673`, `pr-33115`, `pr-33610`, `pr-39834`, `pr-51506`, `pr-65549`

## 本轮 patch-first 结论（必须每条有去向）

- retain：`3`
- watchlist：`2`
- migrate：`2`
- exclude：`1`

详细逐例台账见：

- [全量人工review台账.md](./全量人工review台账.md)

## 当前已 formalize 的 subpatterns（稳定高纯）

> 只把边界清楚、可复用、且有足够硬正例支撑的机制簇落 `subpatterns/*.json`。

### 1) `TiKV/TiFlash RPC 遇到 leader/region/engine 不可用类错误时，不能直接失败；要 backoff 并换 peer 或 fallback`

- status：已 formalize
- 当前正例：`3`
  - `pr-22449`（NoLeader → 明确换 peer 再试）
  - `pr-39834`（region error / missing resp body → Backoff + continue retry）
  - `pr-23078`（TiFlash IO/recv error → 归一为 `ErrTiFlashServerTimeout` 触发 fallback 到 TiKV）

边界要点：

- 这条 subpattern 的核心不是“多加几次 retry”，而是：
  - **把错误分类到“可重试”层**（例如 region/leader/engine-unavailable）
  - **用 backoffer/backoff 把重试节奏收敛**
  - **并且重试必须伴随换 target**（换 peer / 触发 fallback），而不是原地死磕同一个 endpoint

## Watchlist（先不落正式 JSON）

这几条 patch-first 看起来仍然属于 “网络不稳定需要 retry” 的大方向，但目前在 `network_without_retry` source set 内都还是 singleton / 边界摇摆，先放观察池，不强行 formalize：

- `pr-30673`
  - 机制：SQL/DB 操作遇到短暂断链/可重试错误时，需要 `WithRetry` + 必要时重建连接；且每次 retry 必须 reset per-attempt accumulator，避免部分结果/重复结果污染。
  - 暂不 formalize 原因：source set 内同机制只有 1 条。
  - 建议升格门槛：`>= 3` 条 patch-backed 正例，且不止集中在同一处调用点；不要把“只加 retry wrapper（无重建连接/无 per-attempt reset）”的 patch 并进来稀释纯度。
  - 扩样记录（patch-first）：[`扩样_SQL_retry_patch_first_notes.md`](./扩样_SQL_retry_patch_first_notes.md)（当前 `cases/` 数据集内仍未扩到 `>=3` 高纯正例）

- `pr-51506`
  - 机制：远端对象存储的 streaming `Read` 可能中途失败；正确的 retry 形态是**在同一次 Read 内**重新打开 reader 并从 offset 续读，而不是直接把错误抛给上层。
  - 暂不 formalize 原因：source set 内同机制只有 1 条。
  - 建议升格门槛：优先 `>= 3` 条 patch-backed 正例，且至少 `2` 条来自不同 backend 或不同 reader 层（例如 object reader vs range reader；S3 vs 非 S3）；若扩样困难，可接受 “`>= 2` 正例 + 强负例边界（negative guards）已验证” 的折中门槛。
  - 扩样记录（patch-first）：[`扩样_object_storage_read_retry_patch_first_notes.md`](./扩样_object_storage_read_retry_patch_first_notes.md)（当前 `cases/` 数据集内仍未扩到 `>=3` 高纯正例）
  - 上游补充正例（patch-first）：`pr-59694`（fix read position on retry when reading a file range using s3）

## Migrate / Exclude

- migrate：`pr-65549`
  - patch-first 机制更像 **共享端口/endpoint namespace 冲突**，主要修法是 `Port=0` / `net.Listen("127.0.0.1:0")` 真正占住空闲端口 + EADDRINUSE 重试。
  - 迁移去向：`test_isolation_and_state_pollution / 共享 namespace 资源必须 per-test 唯一化`

- migrate：`pr-33610`
  - patch-first 机制是 **external service readiness wait**：外部服务（MinIO）启动/ready 是异步收敛的，测试脚本需要显式 predicate + bounded polling 来等它就绪，而不是一次性探测或弱 predicate。
  - 迁移去向：未来的 `async_wait_without_backoff` unified direction（证据见 [`扩样_readiness_wait_and_migration.md`](./扩样_readiness_wait_and_migration.md)）

- exclude：`pr-33115`
  - patch-first 形态是 mixed patch（revert gRPC resolver + 多处测试脚本/错误处理调整），很难抽出稳定的“共享失稳机制/共享修法机制”来代表 `network_without_retry` 方向。
  - 处理策略：先从本 family 排除，后续若能在更大集合里形成 “gRPC dial / resolver / store address 解析” 的稳定簇，再单独建 family/subpattern。

## Retrieval 交付策略

本轮交付两层 retrieval 工件，但仍保持 **retrieval（候选召回）** 与 **subpattern（verdict 定义）** 严格分离：

- `给agent的仓库扫描检索信号.md`
  - 记录 coarse `rg_template`、patch-proxy 回放、以及 watchlist 的候选召回思路（注意：watchlist 仍未 formalize）
- `retrieval_signals.json`
  - 结构化候选召回信号 **只覆盖当前已 formalize 的 sibling**
  - 不把 watchlist 的方向写进 `entries`，避免把“仍摇摆的想法”混成正式结构化信号

注意：当前 family 仍只有 `1` 条稳定 sibling；`retrieval_signals.json` 的覆盖面也仅限于这 `1` 条 sibling，并不代表能召回/覆盖整个 `network_without_retry` smell 的历史全量。

## 当前未决问题（边界与证据）

1. **两条 watchlist 是否要升格为稳定 sibling？**
   - SQL retry（`pr-30673`）：目前是高纯 singleton；下一步要证明它不是“组件私货”，需要更多独立调用点的同机制 patch-backed 正例（且必须保留“重建连接 + per-attempt reset”的强边界）。
   - object-store Read retry/resume（`pr-51506`）：上游已补到 `pr-59694` 作为第 2 个正例，但仍集中在 S3/range reader 生态；下一步需要第 3 个更“独立”的正例（最好跨 backend 或跨 reader 层）来证明它是可复用机制簇而非单实现演进史。

2. **是否需要把上游补充正例回填为 catalog case？**
   - 例如 `pr-59694` 目前只作为 patch-first 扩样证据记录在 notes/README 中；若后续决定 formalize object-store 分支，回填为 case（即便它不是原始 smell source set）能让机制簇更可复查、更易持续迭代。

3. **“泛化 SQL retry wrapper”要不要单独成簇？**
   - 目前不建议直接 sibling 化，因为它更像通用控制流工具而非稳定共享机制；除非后续 patch-first 读出一批“同一类 SQL 行为 + 同一类 transient 错误 + bounded retry taxonomy 足够”的高纯簇，否则只作为候选召回方向存在。

## 下一步建议

1. **继续稳定边界（优先级高于“凑数量”）**：目前两条 watchlist 都不建议放宽边界来换命中量；下一步应以“补独立正例 + 补强负例边界”为主，先把机制簇的纯度守住。
2. **SQL retry 扩样（沿实现演进线，而不是全仓关键词）**：
   - 优先沿 `dumpling/export/` 里 `BaseConn` / `retry.go` / `reset()` / `backOffer.Reset()` 等符号与文件历史追后续 PR，再逐条 patch-first 复读确认是否同机制。
   - 扩样时同时收集“必要性证据”：证明 *重建连接* 与 *per-attempt reset* 不是可有可无（例如缺失会导致 partial/duplicate 污染的对照 patch/UT）。
3. **object-store Read retry/resume 扩样（优先找跨 backend/跨 reader 层的正例）**：
   - 优先在 `br/pkg/storage/` 的其它 backend 与其它 reader 层（object reader vs range reader/prefetch reader）里追 `Read/Open` 的历史改动，找 “Read 内 retry + reopen + offset resume” 的同构修补。
   - 优先寻找带 UT/failpoint 的补丁（例如 `Test.*Retry.*Read` / `RetryRead` / `ResetRetry` 相关），因为它能把“失败后续读语义”落成可回归证据。
4. readiness-wait 分支已决定迁到未来的 `async_wait_without_backoff` unified direction；后续应在该方向里把“显式 predicate + bounded polling / barrier”这类机制簇 formalize。
5. 当至少有 `2–3` 条稳定 sibling 且边界收敛后，再补 `retrieval_signals.json`（否则会把 coarse retrieval 与机制定义层混在一起）。
