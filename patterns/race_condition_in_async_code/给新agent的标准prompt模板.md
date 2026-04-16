# 给新 agent 扫描历史记录的 Prompt 模板

这个模板用于让一个**全新的 agent**在当前 worktree 扫描**历史代码 / 存量测试**，判断是否能仅依据当前 subpattern 找出潜在 flaky tests。

这份文件本身就是 Markdown 模板。后续只需要替换必要占位符，然后把下面的模板块整体发给新 agent 即可。

## 使用方法

把下面模板里的占位符替换掉后，直接发给新 agent：

- `<worktree_path>`：目标 worktree / repo 路径

当前 family 目录在模板里已经直接写死为当前绝对路径：

- `/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/race_condition_in_async_code`

## 可直接复制的标准模板

```text
你现在在当前 worktree 的当前分支上工作。

你的目标是扫描这个分支上的存量测试，判断是否能仅依据现有 subpattern 找出潜在 flaky tests。

当前只使用这个 family：
- `/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/race_condition_in_async_code`

你必须把这个 family 下的材料分成两层使用：
- `retrieval_signals.json`：只用于 candidate retrieval
- `subpatterns/` 下的 subpattern JSON：只用于严格判定 / evidence threshold，不是最终 review 文案

工作要求：

1. 先阅读下面文件：
- `/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/race_condition_in_async_code/retrieval_signals.json`
- `/Users/fanzhou/workspace/github/tidb-flaky-pattern-race-async-20260415/patterns/race_condition_in_async_code/subpatterns/*.json`

2. 明确禁止读取这些历史答案/标签文件：
- `cases/*.json`
- `review_smells.json`
- replay truth
- 历史标注
- 评测结论
- 任何通过 case id / PR id 反查已有答案的材料

3. 本次扫描直接覆盖 `<worktree_path>` 下的整个仓库。

4. 在扫描测试时，直接按 `retrieval_signals.json` 里的 `fallback_no_path` 做粗筛。

5. 对粗筛出来的每个 candidate，agent 必须逐个打开代码人工判断；这一步不能交给脚本自动判定，也不能批量凭感觉打标签。
- 对每个 candidate，都要对相关 subpattern 做结构化匹配：
- `signals_required` 命中了哪些
- `signals_optional` 命中了哪些
- `negative_guards` 是否命中
- 这一步可以适当放宽，不要过早压掉候选：
  - 只要主要信号已经比较像，就可以先保留
  - 允许有一定 false positive
  - 宁可多报一些候选，也不要因为阈值过严把潜在 flaky test 提前漏掉
- 如果证据已经比较闭合，可以放到 `high_confidence_findings`
- 如果还不完全闭合，但已经值得人工继续看，也保留到 `needs_more_evidence`

6. 每个结论都必须给出具体代码证据，不能只报结论。

固定输出格式：

对每个命中的测试，输出：
- `file`
- `test_name`
- `matched_subpattern`
- `matched_required_signals`
- `matched_optional_signals`
- `triggered_negative_guards`
- `verdict`
- `confidence`
- `evidence`

最终结果按 2 个部分汇总：

1. `high_confidence_findings`
- 最像真的 flaky tests

2. `needs_more_evidence`
- 有信号，但现有 subpattern 证据还不够闭合

额外要求：
- 不要直接照抄 JSON 原文作为最终结论
- 要把 subpattern 翻译成对当前测试代码的具体判定
```
