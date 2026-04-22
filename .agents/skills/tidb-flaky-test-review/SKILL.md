---
name: tidb-flaky-test-review
description: Help an AI agent review TiDB (Go) PRs/diffs for flaky-test risk using the tidb-flaky-test-catalog taxonomy and review-smells checklist. Use when asked to identify likely flaky-test patterns during code review, write review questions/comments, or suggest stabilizing fixes for unit/integration/realtikv tests.
---

# TiDB Flaky Test Review

## Quick Start

Audience: **AI agents**. Use this skill to generate actionable review comments.

Before reviewing, **you must read the full dictionaries from repo root** so you are aware of the complete set of keys and definitions. Do not rely solely on the examples in this document:
- `review_smells.json`
- `taxonomy.json`

1. Get the review input: PR link, changed files, or a diff/patch.
2. Identify flaky-test risks in the diff using the checklist below.
3. Map each risk to stable keys in repo root `review_smells.json` and `taxonomy.json`.
4. Write review feedback using **Review Comment Template**.

This skill is based on the current conclusions in `tidb-flaky-test-catalog` (repo root):
- `review_smells.json`: review checklist primitives (stable keys)
- `taxonomy.json`: root-cause taxonomy (stable keys)

## Workflow (Code Review)

### 0) Set the review focus (avoid noise)

Agent goal is to catch **new flaky risks introduced by this PR** with minimal false positives.

- If the PR **adds/changes tests**: focus on those impacted tests first.
- If the PR claims to **fix a flaky test**: check whether the fix addresses root cause vs a band-aid (e.g. adding sleep/increasing timeout). Avoid re-reporting old smells that are unrelated to the change.
- If the PR changes **infra/CI/timeouts/sharding**: treat it as a first-class flaky surface and capture exact targets/timeouts being changed.

### 1) Identify the test surface

Bucket the changes first; flaky patterns differ by test type:
- **Unit tests**: Go `*_test.go` files (especially `pkg/**/_test.go` in TiDB).
- **Integration tests**: `tests/integrationtest/t/**` (test cases) and `tests/integrationtest/r/**` (golden results).
- **Real TiKV tests**: `tests/realtikvtest/**` (often external dependency / timing sensitive).
- **Test infra / build**: `BUILD.bazel`, CI scripts, timeouts, sharding, `flaky = True` flags.

Also extract the **impacted test case(s)** (required for accuracy and communication):
- **Unit tests**: identify `func TestXxx...` / suite subtests being modified; if unclear, at least name the `*_test.go` file.
- **Integration tests**: name the `.test` file under `tests/integrationtest/t/` (and corresponding `.result` under `r/` if present).
- **Real TiKV tests**: name the test file under `tests/realtikvtest/` and the `TestXxx` if visible.
- **Bazel / CI**: record the target or shard/timeout being changed when it is the source of flakiness.

### 1.5) Expand context when needed (look beyond the diff)

If you flag a smell, **read enough surrounding code** to avoid false positives:
- In Go tests, look for `t.Cleanup(...)`, `defer ...` cleanup, suite `TearDown*`, helper wrappers, and whether the test already uses `require.Eventually` / retry / backoff utilities.
- If a suspicious line lives inside a helper, locate the helper definition and confirm actual behavior.
- If the PR modifies only a few lines, but the risk depends on setup/teardown, read the file-level setup to confirm isolation.

### 2) Structural Smell Scan (Thorough)

**IMPORTANT: This skill requires deep LLM reasoning, NOT keyword/pattern matching.** You must carefully read and understand the full PR diff, trace the control flow, understand the intent of the code changes, and reason about potential flaky risks based on semantic understanding. Do not simply scan for keywords like `time.Sleep` or `go func` and mechanically map them to smell keys. A keyword is only a starting point — you must understand the surrounding context (is the sleep inside a retry loop? is the goroutine properly synchronized?) before making any judgment.

Analyze the control flow, concurrency models, and resource lifecycles:
- Timing: `time.Sleep(...)`, small timeouts, polling without backoff
- Concurrency: `t.Parallel()`, goroutines, shared/global state without cleanup
- Determinism: missing `ORDER BY`, map iteration order, order-sensitive assertions
- Planner/stats sensitivity: asserting exact plans/costs, plan cache dependencies, statistics-sensitive assertions
- DDL/schema propagation: DDL without wait, schema version races, async propagation
- External deps: real TiKV/env deps, hardcoded ports, network calls without retry/timeout

If nothing is immediately obvious, you must systematically trace the test's setup, execution, and teardown for ordering/timing/shared-state risks.

#### Go/TiDB Deep Analysis Patterns (Optional but recommended)

When you have the repo locally, systematically analyze these tokens to trace execution flows and identify flaky-relevant contexts:

- Concurrency: `t.Parallel`, `go func`, `WaitGroup`, `errgroup`, `chan`, `select`, `atomic.`, `sync.Mutex`, `Lock(`, `Unlock(`, `WithCancel`, `WithTimeout`
- Ordering/determinism: `MustQuery(`, `.Check(`, `testkit.Rows`, `ORDER BY`, `Sort`
- Global/shared state: package-level `var`, `init()`, `TestMain`, `failpoint.`, global `config.` / `variable.` setters
- Cleanup: `defer`, `t.Cleanup`, `Close()`, `Stop()`, `Disable`, `Drop`, `Remove`
- Plan/stats: `EXPLAIN`, `ANALYZE`, `GetTableStats`, `statsHandle`, `plan_cache`, `SetVariable`, `tidb_opt_`

### 3) Comprehensive Dictionary Mapping (Strict)

You must exhaustively map your structural findings to the **full set of keys** defined in the repository dictionaries. Do not limit yourself to the common examples listed in this document.

For each issue you find:
1. **Search the full `review_smells.json` (repo root)**: Read through the complete dictionary. Do not just pick the first one that sounds related. Choose the most precise `review_smell` key(s) that match your structural findings.
2. **Search the full `taxonomy.json` (repo root)**: Evaluate the comprehensive list of root cause categories and assign the appropriate `taxonomy` key(s).
3. Prefer actionable, deterministic fixes (not “make it pass” band-aids).
4. Never invent keys. If nothing matches well, use `unclassified` and explain the symptom.

**Primary vs Supporting smell selection (required when multiple smells are found):**

When you identify multiple smells in a single PR, you must designate exactly **1 primary_smell** and 0–3 **supporting_smells**:
- **primary_smell**: the single smell most likely to be the **root cause** of flaky test failure. Selection rules:
  1. Prefer the risk that this PR **newly introduces**, not pre-existing issues in the codebase.
  2. When smells have a causal relationship (e.g., a goroutine race condition leads to adding `time.Sleep` as a workaround), choose the **cause** (`race_condition_in_async_code`) over the **symptom** (`time_sleep_for_sync`).
  3. When no clear causal order exists, choose the smell whose `related_root_causes` in `review_smells.json` is at a higher/more fundamental level.
  4. **HARD**: `time_sleep_for_sync` is usually a symptom. If you can reasonably map the change to an underlying async/concurrency/schema/timeout smell (e.g., `race_condition_in_async_code`, `ddl_without_wait`, `async_schema_propagation`, `schema_version_race`, `insufficient_timeout`), that underlying smell MUST be `primary_smell` and `time_sleep_for_sync` MUST be supporting. Only choose `time_sleep_for_sync` as primary when the only newly introduced risk is adding a fixed sleep barrier in **test code** and no deeper cause is visible.
  5. **HARD**: For order-sensitive assertions on query results, prioritize ordering smells. If a test asserts a fixed row order (e.g., `testkit.Rows(...)` / `require.Equal` on a row slice) and the query has no `ORDER BY` (and no explicit sort), `primary_smell` MUST be `missing_order_by`. Use `unsorted_result_assertion` as supporting (or as primary when ordering is assumed from non-query sources like Go map/slice iteration).
  6. **HARD**: If the PR introduces/modifies concurrency structure (`go func`, channels, worker pools, `t.Parallel`) in or around tests, `primary_smell` SHOULD be `race_condition_in_async_code` (or `t_parallel_with_shared_state`) unless a clearer external-dependency smell dominates (e.g., `real_tikv_dependency`, `hardcoded_port_or_resource`).
  7. **Guardrail**: `global_variable_mutation` is only for true global/package-level state (config/sysvars/failpoints/gofail/singletons). Do not use it for ordinary struct fields or local variables. If the main risk is cross-test pollution/cleanup, prefer `insufficient_cleanup_between_tests` as primary and keep `global_variable_mutation` as supporting.
- **supporting_smells**: additional real risks found in the same PR that are secondary or consequential. These provide useful context but are not the primary driver of flakiness.

Examples:
- Example A: `go func(){...}; time.Sleep(...)` → primary=`race_condition_in_async_code`, supporting=`time_sleep_for_sync`
- Example B: `tk.MustQuery("select ...").Check(testkit.Rows(...))` with no `ORDER BY` → primary=`missing_order_by`, supporting=`unsorted_result_assertion`

When evidence is weak, use:
- `root_cause_categories: ["insufficient_evidence"]`
- `review_smells: ["needs_more_evidence"]`
…and ask for failure signature / CI links / repro hints.

### 4) Write review feedback

Use the smell definitions’ review questions and suggested fixes to write crisp comments.

## Review Comment Template (Interceptor Output)

Use this structure (keep it short; anchor to evidence; optimized so test authors can fix quickly):

- **Primary Finding**: `<smell_key>` — `<smell_title>`
- **Impacted test(s)**: `<test identifier(s)>`
- **Flaky mechanism**: 1–2 sentences describing the causal chain (root cause → nondeterministic behavior).
- **Evidence**: `path:line` + short snippet (from this diff)
- **Fix sketch (deterministic-first)**:
  - 2–3 concrete steps. MUST include at least **1** item from the smell’s `suggested_fixes` in repo root `review_smells.json`, rewritten to match this PR.
  - If `confidence != high`, label the fix as **likely options** and state what evidence would confirm.
- **How to verify**:
  - 1 concrete rerun recipe (e.g. `go test ./... -run TestXxx -count=50 -race`)
- **Supporting Findings** (if any): `<smell_key_2>`, `<smell_key_3>` (0–3). Keep each supporting to 1 sentence mechanism + 1 fix.
- **Confidence**: `high` | `medium` | `low`
- **Recommended action**: `blocker` | `non_blocker` | `needs_more_evidence`
- **Questions (from `review_smells.json`)**:
  - MUST include at least **1** item from the smell’s `review_questions`, rewritten to be PR-specific.
- **(Optional) Root cause tags**: `<taxonomy_key1>, <taxonomy_key2>`

Tone guidance (agent):
- Prefer objective + collaborative wording (e.g. “It looks like…”, “This may be timing-sensitive because…”, “Could we…?”).
- Avoid overconfident claims when evidence is weak; ask for CI links / failure signature / repro hints.

Recommended action guidance (agent):
- `blocker`: only when `confidence=high` and you provided a specific **mechanism + deterministic fix** (not just “increase timeout/add sleep”).
- `needs_more_evidence`: when `confidence=medium/low` or key context is missing. List exactly what you need (CI failure signature/log, whether tests run in parallel, teardown/cleanup behavior, external deps).
- `non_blocker`: when risk is real but already mitigated in this PR (still provide mechanism + fix sketch + verify).

Confidence guidance (agent):
- **high**: direct, unambiguous signal in diff (e.g. fixed `time.Sleep` used for sync, goroutine lifecycle not deterministically bounded, `t.Parallel()` with shared/global state, hardcoded port/resource, order-sensitive assertion without sort/order-by). Your fix sketch should be specific and deterministic-first.
- **medium**: plausible smell but needs context to confirm (e.g. missing `ORDER BY` but assertion might sort elsewhere). Still provide a fix sketch as **likely options** and ask for the missing context.
- **low**: weak or indirect evidence. Still provide a minimal safe fix option, but prefer `needs_more_evidence` and explicitly ask for CI logs / failure signature / repro hints before blocking.

## Example Review Comments (Copy/Paste Style)

### Example 1 — `missing_order_by` (+ `unsorted_result_assertion`)

- **Primary Finding**: `missing_order_by` — Missing ORDER BY in SELECT queries
- **Impacted test(s)**: `executor/diagnostics_test.go:TestInspectionResult` (PR 14114)
- **Flaky mechanism**: The test asserts an exact row order for results from `SELECT * ...` queries, but the SQL has no `ORDER BY`. Without an explicit order, result ordering may vary with execution details (parallelism/chunk processing/storage scan order), making `result.Check(testkit.Rows(...))` intermittently fail.
- **Evidence**:
  - `executor/diagnostics_test.go`: `sql: "select * from information_schema.inspection_result ..."` (no `ORDER BY`) + `result.Check(testkit.Rows(cs.rows...))`
- **Fix sketch (deterministic-first)**:
  - Add an explicit `ORDER BY` clause on stable columns (e.g. `ORDER BY rule, item, type`) for each query under assertion. If keys can tie, add a tie-breaker to make ordering unique. (from `review_smells.json`: “Add explicit ORDER BY clause to the query”)
  - If order is not part of the contract, make the assertion order-insensitive (e.g. `.Sort().Check(...)` or sort returned rows before checking). (from `review_smells.json`: “Use .Sort() before .Check() in test assertions”)
- **How to verify**:
  - `go test ./executor -check.f TestInspectionResult -count=50`
- **Supporting Findings**: `unsorted_result_assertion`
- **Confidence**: high
- **Recommended action**: blocker
- **Questions (from `review_smells.json`)**:
  - Does this query need ordered results for the test assertion? If yes, can we add a stable `ORDER BY` here?

### Example 2 — `race_condition_in_async_code` (+ `time_sleep_for_sync`)

- **Primary Finding**: `race_condition_in_async_code` — Race condition in async code
- **Impacted test(s)**: `util/topsql/reporter/pubsub_test.go:TestPubSubDataSink` (PR 31340)
- **Flaky mechanism**: The test starts `ds.run()` in a background goroutine, then uses a fixed `time.Sleep(1 * time.Second)` as a synchronization barrier before asserting `mockStream.*` lengths. Under slow/loaded CI or different scheduling, the async goroutine may not have processed the data yet, causing assertions to race and fail intermittently.
- **Evidence**:
  - `util/topsql/reporter/pubsub_test.go`: `go func() { _ = ds.run() }()` + `time.Sleep(1 * time.Second)` + `assert.Len(t, mockStream.records, 1)` (etc.)
- **Fix sketch (deterministic-first)**:
  - Replace the fixed sleep with deterministic synchronization (e.g. a `sentCh`/callback in the mock stream to signal when `Send()` happens, then `select` with a bounded timeout). (from `review_smells.json`: “Use channels for goroutine communication” / “Replace sleep with channel/condition variable”)
  - If a direct signal is hard, use a bounded wait loop / `require.Eventually` (reasonable interval + max timeout) rather than a single sleep. (from `review_smells.json`: “Use wait loop with backoff”)
- **How to verify**:
  - `go test ./util/topsql/reporter -run TestPubSubDataSink -count=50 -race`
- **Supporting Findings**: `time_sleep_for_sync`
- **Confidence**: high
- **Recommended action**: blocker
- **Questions (from `review_smells.json`)**:
  - Is there a better synchronization mechanism than `time.Sleep()` here (channels/mutex/condition/event notification)?

## Evaluation Notes (Optional)

If you use this skill as a merge **interceptor**, success is not just “smell exact match”. Keep tracking:
- **Recall**: do we consistently flag truly risky PRs as `risk`?
- **Actionability**: can the test author fix the issue from the review comment alone?

Suggested lightweight rubric (sample a small set of PRs, e.g. N=10; score each 0–2):
- **Evidence specificity**: does the comment point to the exact changed test/statement (file/test/line) that causes risk?
- **Mechanism clarity**: is the causal chain explained (cause vs symptom), without hand-waving?
- **Fix executability**: are there deterministic-first steps that are directly implementable (not only “increase timeout/add sleep”)?

Automatable checks (cheap regression guardrails):
- Template compliance: comment includes Mechanism/Evidence/Fix/Verify + Recommended action.
- Dictionary grounding: for the primary smell, includes at least 1 PR-specific question and 1 PR-specific fix derived from `review_smells.json`.

## Common High-Signal Smells (Representative Examples)

These catch a large portion of flaky test regressions, but **they are not exhaustive**. You must still consult the full `review_smells.json` for precise mapping. Use `review_smells.json` to get: description → why risky → review questions → suggested fixes → related root causes.

- Determinism / ordering:
  - `missing_order_by`, `unsorted_result_assertion`, `relying_on_map_iteration_order`
  - **Structural patterns to verify (TiDB tests)**:
    - Look for `tk.MustQuery(...).Check(testkit.Rows(...))` / `tk.MustQuery(...).Sort().Check(...)` and confirm ordering is actually stabilized.
    - If a query is asserted as an ordered list but lacks `ORDER BY`, that's often `missing_order_by` / `unsorted_result_assertion`.
    - If `ORDER BY` exists but the ordering key is **not unique**, tie ordering can still be nondeterministic → downgrade to `medium` and ask for a stable tie-breaker if needed.
    - If results come from iterating a `map[...]...` into a slice (or printed output), suspect `relying_on_map_iteration_order`.
    - Integration tests: check `.test` files under `tests/integrationtest/t/` for queries without `ORDER BY` whose `.result` files assume a fixed row order.
- Concurrency / shared state:
  - `t_parallel_with_shared_state`, `race_condition_in_async_code`, `global_variable_mutation`, `insufficient_cleanup_between_tests`
  - **Structural patterns to verify (Go tests)**:
    - `race_condition_in_async_code`: `go func` / background worker + shared variable/struct/map/slice accessed without mutex/atomic/channel handoff; or goroutine started but test doesn't **wait** for it deterministically (no `WaitGroup`, no channel sync, no context cancel). Also watch for callback/hook functions registered with the system that run asynchronously.
    - `t_parallel_with_shared_state`: `t.Parallel()` + shared DB/schema/port/temp dir/global config/failpoint. Confirm isolation is truly per-test.
    - `global_variable_mutation`: package-level `var`, `init()`, `TestMain`, or global setters (`config`/`variable`/failpoint) modified in tests; ensure they're restored via `defer` / `t.Cleanup`. Common TiDB patterns: `config.UpdateGlobal(...)`, `variable.SetSysVar(...)`, `failpoint.Enable(...)` without corresponding disable/restore.
    - `insufficient_cleanup_between_tests`: resources (tables/files/goroutines/failpoints/servers) created but not reliably cleaned up. Watch for `CREATE TABLE` without `DROP`, `failpoint.Enable` without `defer failpoint.Disable`, goroutines started without join.
- Async / timing:
  - `time_sleep_for_sync`, `insufficient_timeout`, `async_wait_without_backoff`, `clock_skew_dependency`
  - **Structural patterns to verify (Go tests)**:
    - `time_sleep_for_sync`: bare `time.Sleep(...)` used as a synchronization barrier (not inside a retry/eventually loop).
    - `insufficient_timeout`: hardcoded short timeouts (`time.Second`, `time.Millisecond * 100`) in tests that wait for async operations; look for `context.WithTimeout`, `time.After`, `time.NewTimer` with tight bounds.
    - `async_wait_without_backoff`: polling loops (`for { ... time.Sleep(...) }`) without exponential backoff or bounded retry count; also `require.Eventually` with very short poll intervals that may not give enough time for the operation.
    - `clock_skew_dependency`: tests using `time.Now()` for ordering/comparison, `time.Since()` for assertions, or `AS OF TIMESTAMP` / stale read features that depend on clock precision.
- Plan / stats sensitivity:
  - `assert_exact_plan_or_cost`, `statistics_sensitive_test`, `plan_cache_dependency`
  - **Structural patterns to verify (TiDB tests)**:
    - `assert_exact_plan_or_cost`: `tk.MustQuery("EXPLAIN ...")` with assertions on exact plan operator names, row counts, or cost values; `tk.MustQuery("EXPLAIN ANALYZE ...")` checking exact execution stats. Any `EXPLAIN` output compared with `Check(testkit.Rows(...))` is suspect unless plan is pinned with hints.
    - `statistics_sensitive_test`: tests that depend on optimizer stats being in a specific state — look for `ANALYZE TABLE` presence/absence, assertions on row estimates, tests that `INSERT` data then immediately assert plans without `ANALYZE`. Also: tests that set `tidb_opt_*` session variables or modify stats-related config.
    - `plan_cache_dependency`: tests exercising prepared statements or `EXECUTE` that assume cold/warm plan cache state. Look for `PREPARE`/`EXECUTE` sequences without explicit `ADMIN FLUSH PLAN_CACHE` or plan cache variable toggles.
- DDL / schema propagation:
  - `ddl_without_wait`, `schema_version_race`, `async_schema_propagation`
  - **Structural patterns to verify (TiDB tests)**:
    - `ddl_without_wait`: DDL statements (`ALTER`, `CREATE INDEX`, `ADD COLUMN`) issued without waiting for completion in async DDL mode.
    - `schema_version_race`: tests that issue DDL then immediately read `information_schema` or use the new schema without ensuring the schema version has propagated. Multi-domain tests or tests with multiple TiDB instances are especially suspect.
    - `async_schema_propagation`: tests that create/modify schema objects across goroutines or in callbacks where propagation timing is uncertain.
- External dependencies / resources:
  - `real_tikv_dependency`, `network_without_retry`, `hardcoded_port_or_resource`

## Accuracy Guardrails (False Positives)

Use these checks to reduce noisy/incorrect flags. If you cannot confirm, keep confidence `medium/low` and ask for context.

- `time_sleep_for_sync`:
  - Confirm it is being used as a **fixed synchronization barrier**.
  - If the sleep is part of a **retry/backoff/eventually** pattern (and bounded), it may be acceptable — don’t automatically flag as flaky.
- `missing_order_by` / `unsorted_result_assertion`:
  - Verify the test doesn’t already sort results (or the query has deterministic ordering for the asserted fields).
  - If ordering is handled elsewhere, downgrade to `medium` and point to the place that needs confirmation.
- `t_parallel_with_shared_state`:
  - If the test uses `t.Parallel()`, check whether resources are actually isolated (unique DB/schema/temp dir) and whether there is package-level/shared state.
  - If isolation is explicit and complete, avoid flagging or downgrade confidence.
- `global_variable_mutation` / `insufficient_cleanup_between_tests`:
  - Look for `t.Cleanup`, `defer` resets, and suite teardown that restores global state.
  - If cleanup exists but is fragile, call that out precisely (what is reset, when).
- `race_condition_in_async_code`:
  - Prefer flagging when you can point to concrete shared-state access across goroutines **without** sync, or a goroutine lifecycle that is not deterministically bounded by the test.
  - If the code clearly uses proper synchronization (`WaitGroup`/channels/mutex/atomic) and the test waits for completion, downgrade or avoid flagging.
- `assert_exact_plan_or_cost` / `statistics_sensitive_test`:
  - If the test uses optimizer hints (`/*+ USE_INDEX(...) */`, `/*+ HASH_JOIN(...) */`) to pin the plan, the plan assertion is likely stable — don't flag.
  - If `ANALYZE TABLE` is called right before the assertion AND the data is deterministic, the stats dependency is controlled — downgrade to `medium` at most.
  - Flag when plan/cost assertions have NO hints AND no explicit `ANALYZE`, especially after data modifications.
- `hardcoded_port_or_resource`:
  - If the code uses ephemeral ports (`:0`) or a port allocator / unique temp dir per test, it may not be the smell.

## Output Prioritization (Agent)

- Prefer **fewer, higher-confidence** findings over a long list.
- Group findings by **impacted test(s)**; each test should have at most a few actionable comments.
