# `time_sleep_for_sync` - 给 agent 的仓库扫描检索信号（retrieval draft）

本文件只记录 **coarse candidate retrieval** 的检索想法与 patch-proxy 回放，不作为 subpattern 成立证据。  
判定层（verdict）以 `subpatterns/*.json` 的共享机制为准（尤其是 `signals_required / negative_guards`）。

## 设计原则

- 目标是“召回候选集合”，不是直接判定 flaky root cause。
- 先召回，再用 **subpattern verdict layer**（JSON + 人工复核）做精判。
- `time.Sleep`/`sleep(...)` 只是症状入口：要看它在同步什么（屏障/收敛/TSO 时间语义）。
- 单个 `time.Sleep` 会炸；优先加 **路径 hint**（`*_test.go`、测试脚本目录）和 **关键词组交集** 做粗收束。

## 推荐使用方式（两层）

1. **检索层**：按下文 `rg_templates` 先召回候选文件/片段（允许 false positive）。
2. **判定层**：对候选逐个对照 `subpatterns/*.json` 的 shared mechanism 下 verdict：
   - A：`固定 sleep 当同步屏障必须改成确定性同步原语`
   - B：`sleep 等异步状态传播必须改成 Eventually/条件轮询`
   - C：`stale read / as-of timestamp 测试必须显式控制 TSO/now，而不是短 sleep`

## Broad retrieval drafts（可执行 `rg_templates`）

### Template 0：Go 测试中的固定 sleep（默认第一跳）

```bash
rg -n -F -g '**/*_test.go' \
  -e 'time.Sleep(' \
  -e 'time.After(' \
  -e 'time.NewTimer(' \
  <repo_root>
```

意图：
- 覆盖 A/B/C 三条已 formalize subpattern 的主入口（它们大多从 `time.Sleep` 作为同步手段出发）。

会炸的点：
- `time.Sleep` 也会出现在 backoff/节流/超时/benchmark/生产代码里；所以强烈建议先限制到 `*_test.go`。

### Template 1：补充召回（failpoint / sqlmock delay / SQL SLEEP 等）

```bash
rg -n -U -P \
  -e 'time\\.Sleep\\(' \
  -e '\\bsleep\\(' \
  -e 'WillDelayFor\\(' \
  -e '(?i)\\bSLEEP\\(' \
  <repo_root>
```

意图：
- 覆盖 source set 里 “不直接出现 `time.Sleep(`” 的边界形态：failpoint `sleep(1000)`、sqlmock `WillDelayFor(...)`、SQL `SLEEP()`。

会炸的点：
- `\\bsleep\\(` 在大仓里噪声很大（failpoint / 文本 / shell），建议结合路径：
  - Go：`-g '**/*_test.go' -g '**/*.go'`
  - shell/integration：`-g 'tests/**' -g '**/*.sh'`

## Subpattern-oriented 粗收束（可选第二跳 shrinker）

> 这些是“检索层”的粗下钻，不是 verdict 规则；最终仍需用 `subpatterns/*.json` 判定。

### C（TSO/now 语义）优先下钻

```bash
rg -l -U -P -g '**/*_test.go' '(?i)(as\\s+of\\s+timestamp|stale\\s*read)' <repo_root> \\
  | xargs rg -n -U -P '(?i)(@@tidb_current_ts|tidb_parse_tso|oracle\\.ComposeTS|ExtractPhysical|injectNow|assertStaleTSO)'
```

说明：
- 这条交集在本 family 内的 precision 明显更高（先抓 stale-read 场景，再抓“显式 TSO/now 控制”锚点）。

### B（异步传播收敛）粗下钻

```bash
rg -n -U -P -g '**/*_test.go' '(require\\.Eventually|assert\\.Eventually|EventuallyMust|EventuallyMustQueryAndCheck)' <repo_root>
```

说明：
- `Eventually` 也会出现在其他 family；这里只是帮助把 “已经在用 Eventually” 的候选先捞出来做人工复核。

### A（同步屏障/握手）粗下钻

```bash
rg -l -F -g '**/*_test.go' 'time.Sleep(' <repo_root> \\
  | xargs rg -n -U -P '(sync\\.WaitGroup|wg\\.Wait\\(|chan\\s+struct\\{}|<-\\w+|close\\(|\\bready\\b|\\bbootstrap\\b)'
```

说明：
- 这条只是帮你从 sleep candidate 里优先挑出“像在做屏障/握手”的文件；不是硬条件（很多 A 的稳定修法也可能是显式阻塞式 API，而不一定包含 WaitGroup/channel 关键词）。

## Patch-proxy 回放（基于本次 source set 的 patch 文本）

> 注意：patch-proxy 是“在 patch 文本上跑 grep”做近似回放；它只能反映**正例召回倾向**，不代表真实仓库扫描 precision。并且 patch 可能不包含未修改的上下文行，因此会出现“假 miss”。

数据源：`/tmp/tidb_flaky_time_sleep_for_sync_patches/*.patch`（`85` 个 case 的 patch 缓存）。

### Template 0 回放

- 命中 patch 数：`82 / 85`
- 在 retained `37` 条里命中：`36 / 37`
  - 唯一 miss：`pr-39294`
    - 原因：patch 没改到 `time.Sleep(...)` 那一行（sleep 存在于文件上下文，但 diff 未包含），属于 patch-proxy 的典型低估。
- 另外 2 个 miss（在 source set 内）：
  - `pr-32667`：sqlmock `WillDelayFor(time.Second)`，不含 `time.Sleep(`
  - `pr-53225`：failpoint `sleep(1000)`，不含 `time.Sleep(`

### Template 1 回放（扩展召回）

- 命中 patch 数：`84 / 85`
- 仍然 miss：`pr-39294`（同上：diff 未包含 sleep 上下文）
- 说明：
  - 扩展模板主要用于兜住 watchlist/exclude 里的边界形态（failpoint sleep、sqlmock delay、SQL SLEEP），不保证与 A/B/C 的 verdict 边界一致。

### C 交集回放

- 对 retained 的 C 子簇（`3` 条）：
  - `as of timestamp / stale read` × `TSO/now 控制锚点` 的交集：`3 / 3`
- 这说明：C 的检索层可以更 aggressively 地做交集，而不会明显漏掉正例（至少在本次 patch 集合上）。

## 已知会炸的信号 & 建议的降噪策略

- `time.Sleep(`（全仓）：
  - 必炸；务必先加 `-g '**/*_test.go'`，并在人审阶段排除生产 backoff/节流语义。
- `\\bsleep\\(`：
  - 会把 failpoint 文本、shell、日志样例等都捞进来；建议按目录分两次扫（Go tests vs integration scripts）。
- `(?i)\\bSLEEP\\(`：
  - 会抓到 SQL builtin `SLEEP()` 的产品语义用例；在本 family 里多为 `exclude`，建议低优先级处理或结合上下文关键词再看。

## 真实仓库校准（已完成）

已在真实 TiDB 仓库上对 `retrieval_signals.json`（v1）做过炸量/噪声校准，记录见：

- `retrieval_真实仓库校准记录.md`

结论要点：

- A 的 `time.Sleep` 第一跳天然偏大，默认应优先扫描 `*_test.go`；`**/*.go` 只在追 helper 时再用（否则会把生产 backoff/节流大量捞进来）。
- B/C 的“场景 × 交集锚点” shrinker 更有效；尤其 C（stale read/as-of × TSO 控制锚点）能把候选集压到更可复核的规模。
