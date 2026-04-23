# `time_sleep_for_sync` - retrieval 真实仓库校准记录（TiDB repo）

目的：对 `patterns/time_sleep_for_sync/retrieval_signals.json` 的 `rg_templates` 做一次真实仓库炸量/噪声校准，明确哪条模板会炸、哪里需要 path narrowing / 交集 shrinker。

重要声明：

- 本文件只服务 **candidate retrieval**，不代表 subpattern 成立证据。
- 最终 verdict 必须回到 `subpatterns/*.json` 的 shared mechanism + 人工复核。

## 校准环境

- 仓库：`/Users/fanzhou/Documents/GitHub/tidb`
- 当前 HEAD：`9ff0b83a58`（2026-04-23 本机状态）
- 工具：`rg`（ripgrep）

下面统计主要用两类量级：

- **files**：`rg -l ... | wc -l`
- **lines**：`rg -n ... | wc -l`

## 结果摘要（按 retrieval_signals.json 的 3 条 entry）

### A：`固定 sleep 当同步屏障必须改成确定性同步原语`

#### broad_recall（当前 v1 模板）

```bash
cd /Users/fanzhou/Documents/GitHub/tidb
rg -l -F -g '**/*_test.go' -g '**/*.go' -e 'time.Sleep(' -e 'time.After(' -e 'time.NewTimer(' . | wc -l
rg -n -F -g '**/*_test.go' -g '**/*.go' -e 'time.Sleep(' -e 'time.After(' -e 'time.NewTimer(' . | wc -l
```

- files：`417`
- lines：`1097`

噪声观察（机制层面的噪声，而非关键词噪声）：

- `time.Sleep`/timer 在真实仓库里大量用于：
  - backoff/节流/超时（生产语义）
  - integration harness 等待外部组件
  - “让并发更容易发生”的测试编排
- 因此 A 的第一跳本质上是“大召回入口”，不可避免偏大。

#### group_intersection（当前 v1 模板）

```bash
cd /Users/fanzhou/Documents/GitHub/tidb
rg -l -F -g '**/*_test.go' -g '**/*.go' -e 'time.Sleep(' -e 'time.After(' -e 'time.NewTimer(' . \
  | xargs rg -n -U -P '(?i)(sync\\.WaitGroup|WaitGroup|wg\\.Wait\\(|chan\\s+struct\\{}|close\\(|\\bready\\b|\\bbootstrap\\b|createSession|LoadNeededHistograms|WaitReady|waitUntilReady)' \
  | wc -l
```

- lines：`3527`（文件级交集并没有有效 shrink，反而把“使用 WaitGroup/close/ready 的常见测试”都捞进来）

结论：

- A 的 group_intersection 对“降炸量”帮助有限（锚点仍太通用）。
- 建议把 **A 的默认 broad_recall 限制到 `*_test.go`**，并把 `**/*.go` 放到 fallback（仅在需要追 helper 时使用）。

补充：如果只扫描 `_test.go`（不含 `**/*.go`），量级会明显下降：

```bash
rg -l -F -g '**/*_test.go' -e 'time.Sleep(' -e 'time.After(' -e 'time.NewTimer(' . | wc -l
rg -n -F -g '**/*_test.go' -e 'time.Sleep(' -e 'time.After(' -e 'time.NewTimer(' . | wc -l
```

- files：`256`
- lines：`823`

这仍然不小，但更像“可人工复核”的候选规模。

### B：`sleep 等异步状态传播必须改成 Eventually/条件轮询`

#### broad_recall（当前 v1 模板）

```bash
cd /Users/fanzhou/Documents/GitHub/tidb
rg -l -U -P -g '**/*_test.go' -g '**/*.go' '(require\\.Eventually|assert\\.Eventually|EventuallyMust(QueryAndCheck)?|\\bwaitUntil\\b|\\bwaitFor\\b)' . | wc -l
rg -n -U -P -g '**/*_test.go' -g '**/*.go' '(require\\.Eventually|assert\\.Eventually|EventuallyMust(QueryAndCheck)?|\\bwaitUntil\\b|\\bwaitFor\\b)' . | wc -l
```

- files：`93`
- lines：`347`

这个量级整体可接受，但要注意：

- `Eventually`/waitUntil 也会跨 family 命中（并发 race、资源 teardown、plan/cache 等都可能用 Eventually）。
- 所以 B 的 broad_recall 更像 “优先候选池”，不适合作为高精召回。

#### group_intersection（当前 v1 模板）

```bash
cd /Users/fanzhou/Documents/GitHub/tidb
rg -l -U -P -g '**/*_test.go' -g '**/*.go' '(require\\.Eventually|assert\\.Eventually|EventuallyMust(QueryAndCheck)?|\\bwaitUntil\\b|\\bwaitFor\\b)' . \
  | xargs rg -n -F -e 'time.Sleep(' -e 'time.After(' -e 'time.NewTimer(' \
  | wc -l
```

- lines：`222`
-（文件数口径）交集后大约 `42` 个文件（可作为第二跳 shrinker）

结论：

- B 的 `Eventually` → `sleep/timer` 交集对“抓到从 sleep 迁移到条件轮询”的候选很有用。
- 建议保留该交集模板；但仍需回到 verdict layer 逐例判定“是否真在等异步传播”。

### C：`stale read / as-of timestamp 测试必须显式控制 TSO/now，而不是短 sleep`

#### broad_recall（当前 v1 模板）

```bash
cd /Users/fanzhou/Documents/GitHub/tidb
rg -l -U -P -g '**/*_test.go' -g '**/*.go' '(?i)(as\\s+of\\s+timestamp|stale\\s*read)' . | wc -l
rg -n -U -P -g '**/*_test.go' -g '**/*.go' '(?i)(as\\s+of\\s+timestamp|stale\\s*read)' . | wc -l
```

- files：`58`
- lines：`452`

#### group_intersection（当前 v1 模板）

```bash
cd /Users/fanzhou/Documents/GitHub/tidb
rg -l -U -P -g '**/*_test.go' -g '**/*.go' '(?i)(as\\s+of\\s+timestamp|stale\\s*read)' . \
  | xargs rg -n -U -P '(?i)(@@tidb_current_ts|tidb_parse_tso|oracle\\.ComposeTS|ExtractPhysical|injectNow|assertStaleTSO)' \
  | wc -l
```

- lines：`40`
-（文件数口径）交集后 `9` 个文件

结论：

- C 的交集模板非常有效：stale-read 场景 × TSO/now 控制锚点 → 候选集合明显更小、更可复核。
- 建议 agent 扫仓时优先用 C 的交集作为第二跳 shrinker。

## 建议调整（不等于立刻改，先给出方向）

1. A 的 broad_recall 建议默认只扫 `*_test.go`，把 `**/*.go` 放到 fallback（需要追 helper 时再用）。
2. A 的 group_intersection 当前锚点过通用（`WaitGroup/close/ready`），对降炸量帮助有限；可以考虑移除过通用锚点或改用更具体的“屏障语义”锚点（例如 wait-ready helper 名称、明确的 ready channel 模式等），否则建议只把它当“排序/优先级提示”，不要当 shrinker。
3. B/C 的交集模板表现良好，建议保留；C 的交集尤其适合 aggressive shrink。

