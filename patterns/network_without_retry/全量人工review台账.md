# `network_without_retry` 全量 patch-first 人工 review 台账

这个文件只记录一件事：

- 对 `network_without_retry` smell 下的 **全部 `8` 个 case** 做 `patch-first` 全量人工复读

这里不接受：

- 先用 case JSON 的解释字段（`root_cause_explanation` / `fix_pattern` / `analysis`）做初筛
- 先跑 regex / 脚本命中结果再回头读 patch
- 按关键词/模块名/测试名/报错文案表面相似度归桶

## 完成状态

- source set：`8`
- 已人工复读：`8 / 8`
- retain：`3`
- watchlist：`2`
- migrate：`2`
- exclude：`1`

## 逐例台账（必须每条有去向）

> 说明：`归属 subpattern` 只填写已经落盘的 `subpatterns/*.json`；singleton / 边界摇摆簇先放 `watchlist`，并在该列写明“未 formalize 原因”。

| case_id | pr_id | pr_title | patch_url | source smell | 最终去向 | 归属 subpattern | 一句机制说明（按共享机制/修法口径） | 迁移目标 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| `pr-22449` | `22449` | store/tikv: always switch to a different peer when meets no-leader | https://github.com/pingcap/tidb/pull/22449.patch | `network_without_retry` | retain | `TiKV/TiFlash RPC 遇到 leader/region/engine 不可用类错误时，不能直接失败；要 backoff 并换 peer 或 fallback` | 遇到 `NotLeader/NoLeader` 这类 region/leader 拓扑抖动时，不能反复打同一个 peer；需要带 backoff 的 retry，并在 retry 时换 peer |  | patch 主体是 region cache / region request error handling；修法是“换 target + backoff”，而不是单纯加次数 |
| `pr-23078` | `23078` | store/copr: polish the tiflash-tikv fallback function. | https://github.com/pingcap/tidb/pull/23078.patch | `network_without_retry` | retain | `TiKV/TiFlash RPC 遇到 leader/region/engine 不可用类错误时，不能直接失败；要 backoff 并换 peer 或 fallback` | TiFlash/Mpp RPC 遇到 IO/recv/dispatch 类错误时，需要把错误归一到 fallback 识别的 sentinel（如 `ErrTiFlashServerTimeout`），让请求能 fallback 到 TiKV 而不是直接失败 |  | 这条体现的是“错误分类 + 触发 fallback”，属于换 target 的一种 |
| `pr-39834` | `39834` | ddl: retry prepare RPC when meets region error | https://github.com/pingcap/tidb/pull/39834.patch | `network_without_retry` | retain | `TiKV/TiFlash RPC 遇到 leader/region/engine 不可用类错误时，不能直接失败；要 backoff 并换 peer 或 fallback` | DDL prepare RPC 遇到 `region error / missing resp body / resp error` 时，不能直接 return error；要 `bo.Backoff(...)` 后继续 retry，等待 region 恢复可用 |  | patch 用 failpoint 注入 epoch-not-match 来回归“可重试 region error”路径 |
| `pr-30673` | `30673` | dumpling: support sql retry mechanism for meta conn | https://github.com/pingcap/tidb/pull/30673.patch | `network_without_retry` | watchlist | （未 formalize：singleton） | SQL/DB 操作遇到可重试错误时，需要 `WithRetry` + 必要时 rebuild conn；并且每次 retry 必须 reset per-attempt accumulator，避免 partial/duplicate results 污染输出 |  | 当前 source set 内同机制只有 1 条；扩样记录见 `扩样_SQL_retry_patch_first_notes.md` |
| `pr-51506` | `51506` | s3: retry 3 times inside one `Read` | https://github.com/pingcap/tidb/pull/51506.patch | `network_without_retry` | watchlist | （未 formalize：singleton） | 对象存储 streaming `Read` 中途失败时，正确修法是在同一次 `Read` 内 reopen reader 并从 offset 续读，而不是把 transient error 直接抛给上层 |  | 当前 source set 内同机制只有 1 条；扩样记录见 `扩样_object_storage_read_retry_patch_first_notes.md` |
| `pr-33610` | `33610` | br: fix unstable s3 test | https://github.com/pingcap/tidb/pull/33610.patch | `network_without_retry` | migrate |  | external service readiness wait：服务 ready 异步收敛，脚本需要显式 predicate + bounded polling 等就绪后再继续 | `async_wait_without_backoff`（未来 unified direction） | 迁移证据见 `扩样_readiness_wait_and_migration.md`；同族对照含 `pr-33666`（同一路径更完整的 predicate/循环括号修正） |
| `pr-65549` | `65549` | test: refine network port assignment in test | https://github.com/pingcap/tidb/pull/65549.patch | `network_without_retry` | migrate |  | 本质是端口/endpoint namespace 冲突（EADDRINUSE）与缺少 deadline 导致 hang；修法是 `Port=0`/占住空闲端口 + addr-in-use 重试 + `PingContext` 加超时 | `test_isolation_and_state_pollution / 共享 namespace 资源必须 per-test 唯一化` | 不属于“网络瞬断重试”主机制簇，迁到 namespace 隔离方向更纯 |
| `pr-33115` | `33115` | lightning: revert custom gRPC resolver | https://github.com/pingcap/tidb/pull/33115.patch | `network_without_retry` | exclude |  | patch 是 mixed 形态（resolver/dial 行为变化 + 测试脚本/错误处理改动），难以抽出稳定的共享失稳机制簇代表本 family |  | 先排除，后续若形成 “gRPC dial/resolver/address 解析” 独立簇再处理 |
