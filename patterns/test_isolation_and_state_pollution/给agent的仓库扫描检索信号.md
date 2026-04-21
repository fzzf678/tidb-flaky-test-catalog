# `test_isolation_and_state_pollution` 给 agent 的仓库扫描检索信号

这份文档记录的是：

- 当前这条 family 已 formalize 的 `retrieval_signals.json`
- 以及第六条 sibling 的一轮检索校准结果

它不是：

- verdict / classification 规则
- 也不是用现成字段给 `234` 个 case 重新归桶

这里仍然只服务：

- **coarse retrieval / candidate retrieval**

也就是说：

- `rg_template` 只负责先把可疑候选粗筛出来
- 最终是不是命中哪个 sibling，仍然必须回到 `subpatterns/*.json`

## 当前分工

- [retrieval_signals.json](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/test_isolation_and_state_pollution/retrieval_signals.json)
  - 当前最权威的结构化检索层
  - 负责告诉 agent 先怎么召回 candidate
- `subpatterns/*.json`
  - verdict layer
  - 负责最终判断是否真的命中对应机制
- [test_isolation_and_state_pollution_234_case_人工review工作板.md](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/test_isolation_and_state_pollution_234_case_人工review工作板.md)
  - `234` 个 patch 的 patch-first 人工复读记录
  - 以及 sibling/backlog/boundary 的 canonical 说明
- 本文档
  - 解释 retrieval layer 怎么用
  - 补第六条 sibling 的检索校准结果
- [第六条_实仓候选采样台账.md](/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/test_isolation_and_state_pollution/%E7%AC%AC%E5%85%AD%E6%9D%A1_%E5%AE%9E%E4%BB%93%E5%80%99%E9%80%89%E9%87%87%E6%A0%B7%E5%8F%B0%E8%B4%A6.md)
  - 第六条 `broad / harness / package` 三档命中的 file-level triage 台账

## Hard Rules

1. `rg_template` 只能做粗筛，允许 false positive。
2. 不能因为某条 regex 能 hit 到 patch，就反过来把它当成 sibling 定义。
3. 不能拿 `root_cause_categories`、`fix_pattern`、`analysis`、`root_cause_explanation` 来替代 patch review。
4. 当前这里写的 hit rate，默认都是：
   - **patch-text proxy 命中率**
   - 或 **真实仓库文件数炸量**
5. 这不是 repo-scan precision，也不是 verdict 准确率。

## 使用方式

先记一条总原则：

- `retrieval_signals.json` 的职责是 **candidate retrieval**
- 默认目标是 **recall 优先，不是 precision 优先**
- 真正严格的地方仍然是：
  - patch review
  - `subpatterns/*.json`

建议顺序：

1. 先跑 `broad_recall`
2. 如果结果太多，再跑 `group_intersection`
3. 如果 `broad_recall` 明显过 sparse，或你本来就在追某个弱分支，再显式跑对应 `weak_recall`
4. 打开代码/patch，回到 verdict layer 做人工判断

## 2026-04-18 第六条 sibling 检索校准

这里校准的是：

- `server / harness / package sandbox 级 test-global 状态必须重建或清理`

这轮没有用已有字段做分类，只做了两件事：

1. 用该 JSON 当前列出的 `10` 个 representative positive examples 做 patch-text proxy 回放。
2. 在本地 TiDB HEAD 仓库 `/Users/fanzhou/workspace/github/tidb` 上直接跑当前模板，看大概会炸出多少文件。

需要强调：

- 这里的 `10` 条是**代表性正例**，不是这条 sibling 的 full positive inventory。
- 所以下面的 patch-proxy hit rate 只能理解成：
  - 当前模板有没有明显形态盲区
  - 不能理解成 canonical recall

### representative positive set

当前回放用的是 JSON 里列出的这 `10` 条 representative positive：

- `pr-15665`
- `pr-17667`
- `pr-19484`
- `pr-31896`
- `pr-36506`
- `pr-36578`
- `pr-36722`
- `pr-38808`
- `pr-65735`
- `pr-65736`

同时额外看了当前 JSON 里列出的 `5` 条 boundary 代表：

- `pr-65229`
- `pr-37908`
- `pr-50008`
- `pr-17964`
- `pr-29053`

### patch-proxy 结果

| template | 命中 representative positives | 说明 |
|---|---:|---|
| `broad_recall` | `5 / 10 = 50%` | 只抓最硬的 harness-global anchors，本来就刻意偏窄 |
| `group_intersection` | `4 / 10 = 40%` | 只是轻量 shrinker，不承担 recall 主入口 |
| `package_sandbox_weak_recall` | `5 / 10 = 50%` | 主要补 `main_test.go` / `TestMain` / package sandbox 分支 |
| `harness_teardown_weak_recall` | `5 / 10 = 50%` | 主要补旧一批 `testleak + close 链`、real-TiKV clear/reset、helper 内绑 cleanup 的分支 |
| `broad + 两条 weak_recall` 的并集 | `10 / 10 = 100%` | 当前这条 sibling 需要分层召回，不能只靠默认第一跳 |

### boundary spillover

弱召回模板确实会吸到一部分相邻边界：

- `pr-37908`
  - 当前是“后台 component 必须显式 Stop/Close/Wait”边界
  - 但会命中：
    - `package_sandbox_weak_recall`
    - `harness_teardown_weak_recall`
- `pr-17964`
  - 当前是 process-global config / global-state 边界
  - 会命中：
    - `harness_teardown_weak_recall`

这说明：

1. 第六条的 weak recall 不能拿来直接判 verdict。
2. 它们的职责只应该是补 recall。
3. 真正的 sibling 切分仍然要靠：
   - `signals_required`
   - `negative_guards`

### TiDB HEAD 炸量

在本地 TiDB HEAD `/Users/fanzhou/workspace/github/tidb` 上，当前模板的量级大致是：

| template | 当前文件数 | 结论 |
|---|---:|---|
| `broad_recall` | `20` | 量级可控，适合默认第一跳 |
| `group_intersection` | `17` | 只是轻度 shrink，不是 hard gate |
| `package_sandbox_weak_recall` | `98` | 明显过宽，只适合定向补召回 |
| `harness_teardown_weak_recall` | `23` | 量级还能接受，适合在追旧 harness teardown 分支时显式跑 |

这也解释了为什么第六条当前不把 `package sandbox / TestMain` 单拆出来做默认第一跳：

- patch-proxy 上它确实能补正例
- 但 repo-scan 炸量明显偏大

### 实仓主要噪声模式

这轮把三档命中实际抽样打开后，当前主要噪声已经比较清楚：

#### 1. `broad_recall` 的主命中其实很集中，不算“大炸”

`broad_recall` 当前 `20` 个文件里：

- `18` 个在 `pkg/server/**`
- `1` 个在 `cmd/ddltest/ddl_test.go`
- `1` 个在 `pkg/domain/main_test.go`

也就是说，这一跳现在主要抓到的是：

- `RunInGoTestChan` 重建
- server restart / `stopServer(...)`
- server harness 生命周期收口

这条主轴和第六条 sibling 本体是对齐的，所以当前**不建议为了少量噪声继续收 regex**。

再往下看 anchor 结构，这 `20` 个文件基本也不是散的：

- `RunInGoTestChan`：`17 / 20`
- `stopServer(...)`：`3 / 20`
- `ResetStoreForWithTiKVTest(...)`：`1 / 20`

这进一步说明：

- 当前 `broad_recall` 的默认第一跳，本质上就是在抓
  - server restart / `RunInGoTestChan`
  - server harness teardown
  - 少量 real-TiKV reset
- 这和第六条 sibling 的主轴是对齐的

#### 2. `harness_teardown_weak_recall` 的主噪声不是 server，而是普通 bootstrap scaffolding

这条当前 `23` 个文件里，最主要的非目标噪声是：

- 普通 `BootstrapSession(store) + defer dom.Close()/store.Close()` bootstrap smoke tests
- 带 `SetSchemaLease(...)` 的 domain/schema lease 场景
- 少量 `config.UpdateGlobal(...)` / global-config 相关 case

这类命中说明：

- 这条 weak recall 确实能补到老一批真实 harness teardown 正例
- 但它天然也会吸进：
  - bootstrap scaffolding
  - global-knob boundary

所以当前更合理的动作不是收 regex，而是：

- 继续把它当 **weak recall**
- 通过 `negative_guards` 和 soft down-rank 去切边界

它的结构统计也能直接说明问题：

- `BootstrapSession(...)`：`19 / 23`
- `RunInGoTestChan`：`4 / 23`
- `CreateMockStoreAndDomain(...)`：`3 / 23`
- `config.UpdateGlobal(...)`：`3 / 23`
- `SetSchemaLease(...)`：`6 / 23`

也就是说，这一桶现在主要是两类东西混在一起：

1. 真正的 harness teardown / restart 分支
2. 普通 bootstrap scaffolding + global-knob boundary

所以把 `SetSchemaLease(...)` 加成 soft down-rank 是合理的，但再继续靠 regex 去硬切这两类，并不划算。

进一步把这 `11` 个 `likely_boundary` 文件拆开后，当前稳定看到的是 `2 + 1` 个 boundary subtype：

| boundary subtype | count | dominant anchors | should-check-first |
|---|---:|---|---|
| `bootstrap_global_knob_boundary` | `6` | `SetSchemaLease(...)`、`config.UpdateGlobal(...)`、`InitializeSQLFile`、`CPUProfileInterval` | 先看 process-global knob / bootstrap-mode boundary，而不是直接判第六条 sibling |
| `stats_background_boundary` | `4` | `DisableStats4Test()`、`view.Stop()`、`dom.SetStatsUpdating(true)` | 先看第二条 sibling：`后台 component 必须显式 Stop/Close/Wait` |
| `server_namespace_or_endpoint_boundary` | `1` | `conf.Socket`、`conf.Port`、`server.NewServer(...)` | 先看第一条 sibling：`共享 namespace 资源必须 per-test 唯一化` |

这轮细分后的结论也更明确：

1. `harness_teardown_weak_recall` 现在最大的 boundary spillover，不只是泛泛的 “bootstrap scaffolding”。
   具体已经能稳定分成：
   - bootstrap/global knob
   - stats/background
   - 少量 namespace/endpoint
2. 这解释了为什么当前 retrieval layer 仍然只保留：
   - `SetSchemaLease(...)` 这一个 soft down-rank
3. 其他这些词暂时不适合继续下放成 retrieval 层 hard cut：
   - `DisableStats4Test()`
   - `view.Stop()`
   - `config.UpdateGlobal(...)`
   - `InitializeSQLFile`
   - `conf.Socket` / `conf.Port`

原因是：

- 它们虽然能提示“更像 boundary”，但分别又直连 family 的相邻 sibling。
- 这类词更适合作为：
  - 人工 patch review 的优先怀疑方向
  - 或 verdict layer 的 boundary note
- 不适合现在就直接做 regex 级硬排除。

#### 3. `package_sandbox_weak_recall` 的主量来自 generic `main_test.go` scaffolding

`package_sandbox_weak_recall` 当前 `98` 个文件里，主要集中在：

- `pkg/executor/**`，尤其 `pkg/executor/test/**`
- `pkg/session/test/**`
- `pkg/planner/core/casetest/**`
- `pkg/ddl/tests/**`
- `pkg/server/tests/**`

抽样看下来，这批命中里很大一部分只是：

- `TestMain(...)`
- `goleak.VerifyTestMain(...)`
- `config.UpdateGlobal(...)`
- `autoid.SetStep(...)`
- `tikv.EnableFailpoints()`

也就是普通 package-level test harness 初始化，并不天然等于“当前 patch/当前候选在修 package sandbox 污染”。

这条的结构统计也非常稳定：

- `TestMain(...)`：`98 / 98`
- `goleak.VerifyTestMain(...)`：`92 / 98`
- `config.UpdateGlobal(...)`：`85 / 98`
- `testsetup.SetupForCommonTest(...)`：`69 / 98`
- `tikv.EnableFailpoints()`：`63 / 98`
- `autoid.SetStep(...)`：`31 / 98`

换句话说，这一桶的主量不是“真的在修 package sandbox 污染”的 patch 痕迹，而是：

- 大量 package 的通用 `main_test.go`
- 统一的 goleak / failpoint / config 初始化模板

因此它的当前价值更像：

- 帮你定向找“可能和 package sandbox 相关”的候选面
- 不是帮你直接缩到一个很纯的候选集

所以这条当前最合理的定位仍然是：

- **只在明确追 package sandbox 分支时再显式跑**
- 不作为默认第一跳
- 也不支撑把 `package sandbox / TestMain` 单拆成第七条 sibling

## 当前结论

1. 第六条 sibling 当前的分层设计是对的：
   - `broad_recall` 负责默认第一跳
   - `package_sandbox_weak_recall` 和 `harness_teardown_weak_recall` 负责补 recall
2. 当前不应该把 `goleak.VerifyTestMain()` / `TestMain()` / `CreateMockStoreAndDomain()` 直接抬进默认 broad。
3. 当前也不应该为了减少 weak recall false positive，反过来收缩 sibling 定义。
4. 更合理的做法是：
   - 继续保持“弱召回可以有 false positive”
   - 再用 `negative_guards` 去切开：
     - namespace sibling
     - background-component sibling
     - global-state / async-race 边界
5. 当前唯一值得直接补进 retrieval layer 的，是很明确的 soft down-rank：
   - `SetSchemaLease(...)`
   - 它在这轮实仓抽样里稳定更像 global-knob / async boundary，而不是第六条主体
6. 当前还**不值得**补进去的 down-rank 也已经明确：
   - `goleak.VerifyTestMain(...)`
   - `config.UpdateGlobal(...)`
   - `testsetup.SetupForCommonTest(...)`
   - `tikv.EnableFailpoints()`
   - `autoid.SetStep(...)`
   - 原因不是它们没噪声，而是它们既是 generic scaffolding 噪声，也是 package sandbox 分支里真实会出现的修法上下文；现在直接拿来 down-rank，风险是把本来就不多的 package-sandbox 正例一并压掉

## 下一步

1. 如果继续细化这条 family，最值得做的是：
   - 继续压第六条和 namespace / background-component / global-singleton 的边界
2. 如果继续做 retrieval 校准，优先顺序是：
   - 先补第六条真实 repo-scan 下的 candidate 采样
   - 再考虑要不要给 `package_sandbox_weak_recall` 增加额外 down-rank 提示
3. 在那之前：
   - 不要把第六条的 weak recall 当成 verdict
   - 也不要把 `package sandbox / TestMain` 单拆成第七条默认 sibling
4. 如果要继续推进 repo-scan calibration，优先看：
   - `第六条_实仓候选采样台账.md`
   - 先判断某类命中是 `likely_boundary` 还是 `generic_scaffolding`
   - 再决定是否值得补新的 down-rank / boundary 规则
