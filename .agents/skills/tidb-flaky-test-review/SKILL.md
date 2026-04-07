---
name: tidb-flaky-test-review
description: Help an AI agent review TiDB (Go) PRs/diffs for flaky-test risk using the tidb-flaky-test-catalog taxonomy and review-smells checklist. Use when asked to identify likely flaky-test patterns during code review, write review questions/comments, or suggest stabilizing fixes for unit/integration/realtikv tests.
---

# TiDB Flaky Test Review

## Quick Start

Audience: **AI agents**. Use this skill to generate actionable review comments.

Before reviewing, **read the dictionaries from repo root** so you use the latest keys/definitions:
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

### 2) Do a fast smell scan (manual)

This skill is intentionally **script-free**. Do a fast manual scan for high-signal patterns:
- Timing: `time.Sleep(...)`, small timeouts, polling without backoff
- Concurrency: `t.Parallel()`, goroutines, shared/global state without cleanup
- Determinism: missing `ORDER BY`, map iteration order, order-sensitive assertions
- Planner/stats sensitivity: asserting exact plans/costs, plan cache dependencies, statistics-sensitive assertions
- DDL/schema propagation: DDL without wait, schema version races, async propagation
- External deps: real TiKV/env deps, hardcoded ports, network calls without retry/timeout

If nothing is flagged, still do a quick manual pass for ordering/timing/shared-state risks.

### 3) Map findings to stable keys

For each issue you find:
1. Choose **review smell key(s)** from `review_smells.json` (repo root).
2. Choose **root-cause category key(s)** from `taxonomy.json` (repo root).
3. Prefer actionable, deterministic fixes (not “make it pass” band-aids).
4. Never invent keys. If nothing matches well, use `unclassified` and explain the symptom.

When evidence is weak, use:
- `root_cause_categories: ["insufficient_evidence"]`
- `review_smells: ["needs_more_evidence"]`
…and ask for failure signature / CI links / repro hints.

### 4) Write review feedback

Use the smell definitions’ review questions and suggested fixes to write crisp comments.

## Review Comment Template

Use this structure (keep it short; link to evidence):

- **Finding**: `<smell_key>` — `<smell_title>`
- **Impacted test(s)**: `<test identifier(s)>`
- **Evidence**: `path:line` + short snippet
- **Confidence**: `high` | `medium` | `low`
- **Why risky**: 1 sentence
- **Questions**:
  - Q1
  - Q2
- **Suggested fix**:
  - Fix 1
  - Fix 2
- **(Optional) Root cause tags**: `<taxonomy_key1>, <taxonomy_key2>`

Tone guidance (agent):
- Prefer objective + collaborative wording (e.g. “It looks like…”, “This may be timing-sensitive because…”, “Could we…?”).
- Avoid overconfident claims when evidence is weak; ask for CI links / failure signature / repro hints.

Confidence guidance (agent):
- **high**: direct, unambiguous signal in diff (e.g. `time.Sleep` used for sync, `t.Parallel()` in tests with shared/global state, hardcoded port/resource, order-sensitive assertion without sort/order-by).
- **medium**: plausible smell but needs context to confirm (e.g. missing `ORDER BY` but assertion might sort elsewhere; timeout might be fine; async wait might already have backoff).
- **low**: weak or indirect evidence; use `needs_more_evidence` / `insufficient_evidence` and ask for CI logs / failure signature / repro hints.

## Common High-Signal Smells (start here)

These catch a large portion of flaky test regressions. Use `review_smells.json` to get: description → why risky → review questions → suggested fixes → related root causes.

- Determinism / ordering:
  - `missing_order_by`, `unsorted_result_assertion`, `relying_on_map_iteration_order`
- Concurrency / shared state:
  - `t_parallel_with_shared_state`, `global_variable_mutation`, `insufficient_cleanup_between_tests`
- Async / timing:
  - `time_sleep_for_sync`, `insufficient_timeout`, `async_wait_without_backoff`, `clock_skew_dependency`
- Plan / stats sensitivity:
  - `assert_exact_plan_or_cost`, `statistics_sensitive_test`, `plan_cache_dependency`
- DDL / schema propagation:
  - `ddl_without_wait`, `schema_version_race`, `async_schema_propagation`
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
- `hardcoded_port_or_resource`:
  - If the code uses ephemeral ports (`:0`) or a port allocator / unique temp dir per test, it may not be the smell.

## Output Prioritization (Agent)

- Prefer **fewer, higher-confidence** findings over a long list.
- Group findings by **impacted test(s)**; each test should have at most a few actionable comments.
