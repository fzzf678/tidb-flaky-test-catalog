# TiDB Flaky Test Review Checklist v0.1

This checklist helps reviewers identify potential flaky test patterns during code review.
Each item includes: what to look for → why it is risky → what questions to ask → how to fix.

## Quick Reference by Category

### async_timing_issue
- [ ] **Insufficient timeout value** (`insufficient_timeout`)
- [ ] **time.Sleep() for synchronization** (`time_sleep_for_sync`)
- [ ] **Async wait without backoff/retry** (`async_wait_without_backoff`)
- [ ] **Clock skew dependency** (`clock_skew_dependency`)
- [ ] **Relying on GC/finalizer timing** (`finalizer_timing_dependency`)

### concurrency_data_race
- [ ] **Race condition in async code** (`race_condition_in_async_code`)
- [ ] **Global variable mutation without cleanup** (`global_variable_mutation`)
- [ ] **t.Parallel() with shared state** (`t_parallel_with_shared_state`)

### external_dependency
- [ ] **Hardcoded port or resource** (`hardcoded_port_or_resource`)
- [ ] **Real TiKV dependency** (`real_tikv_dependency`)
- [ ] **Network operations without retry** (`network_without_retry`)

### nondeterministic_plan_selection
- [ ] **Asserting on exact plan or cost** (`assert_exact_plan_or_cost`)
- [ ] **Statistics-sensitive test** (`statistics_sensitive_test`)
- [ ] **Plan cache dependency** (`plan_cache_dependency`)
- [ ] **Asserting on exact error message/constraint** (`assert_exact_error_message`)
- [ ] **Unsupported pushdown (virtual/generated columns or unsupported expressions)** (`unsupported_pushdown`)

### nondeterministic_result_order
- [ ] **Unsorted result assertion** (`unsorted_result_assertion`)
- [ ] **Missing ORDER BY in SELECT queries** (`missing_order_by`)
- [ ] **Relying on Go map iteration order** (`relying_on_map_iteration_order`)

### nondeterministic_test_input
- [ ] **Randomized test input / probabilistic assertion** (`randomized_test_input`)

### schema_change_race
- [ ] **Async schema propagation issue** (`async_schema_propagation`)
- [ ] **DDL without wait for completion** (`ddl_without_wait`)
- [ ] **Schema version race** (`schema_version_race`)

### shared_state_pollution
- [ ] **Global variable mutation without cleanup** (`global_variable_mutation`)
- [ ] **Insufficient cleanup between tests** (`insufficient_cleanup_between_tests`)
- [ ] **t.Parallel() with shared state** (`t_parallel_with_shared_state`)
- [ ] **Shared table without isolation** (`shared_table_without_isolation`)
- [ ] **Unsafe zero-copy aliasing (mutable backing buffer)** (`unsafe_zero_copy_alias`)

### test_infra_migration
- [ ] **Deprecated test framework usage** (`deprecated_test_framework_usage`)
- [ ] **Test suite setup issue** (`test_suite_setup_issue`)
- [ ] **Incomplete testify migration** (`incomplete_testify_migration`)

## Detailed Checklist

### Race condition in async code

**Key:** `race_condition_in_async_code`

**Related Root Causes:** concurrency_data_race

**Description:** Code with goroutines or background operations that access shared state without proper synchronization.

**Why Risky:** Concurrent access without synchronization leads to data races and unpredictable behavior.

**Review Questions:**
- Are there goroutines accessing shared variables?
- Is there proper synchronization (channels, mutexes)?
- Could the race detector find issues here?

**Suggested Fixes:**
- Use sync.Mutex or atomic operations
- Use channels for goroutine communication
- Add race detector to CI
- Refactor to avoid shared mutable state

### Global variable mutation without cleanup

**Key:** `global_variable_mutation`

**Related Root Causes:** shared_state_pollution, concurrency_data_race

**Description:** Tests that modify global variables, configuration, or package-level state without properly restoring original values.

**Why Risky:** Mutated global state affects subsequent tests, causing order-dependent failures that are hard to debug.

**Review Questions:**
- Is any global variable or configuration modified?
- Is there a defer or t.Cleanup() to restore state?
- Could this affect other tests in the suite?

**Suggested Fixes:**
- Save original value and defer restore
- Use t.Cleanup() for guaranteed restoration
- Encapsulate state in test-specific structures
- Avoid global state when possible

### Unsorted result assertion

**Key:** `unsorted_result_assertion`

**Related Root Causes:** nondeterministic_result_order

**Description:** Using MustQuery().Check() without Sort() when query results may come in any order.

**Why Risky:** Test assertions that expect specific row order without sorting will fail when database returns rows in different order.

**Review Questions:**
- Does the assertion use .Sort() before .Check()?
- Is the expected row order explicitly defined?
- Could the storage layer return rows in different order?

**Suggested Fixes:**
- Add .Sort() before .Check() in the assertion chain
- Use testkit.Rows() and ensure expected order matches
- Consider if ORDER BY in query is more appropriate

### Insufficient timeout value

**Key:** `insufficient_timeout`

**Related Root Causes:** async_timing_issue

**Description:** Timeout values that are too short for the operation under normal or load conditions.

**Why Risky:** Short timeouts cause intermittent failures under load or on slower hardware.

**Review Questions:**
- Is the timeout sufficient for the operation?
- Could this fail under CI load?
- Is the timeout hardcoded or configurable?

**Suggested Fixes:**
- Increase timeout to accommodate load
- Use context with appropriate deadline
- Make timeout configurable via environment

### Insufficient cleanup between tests

**Key:** `insufficient_cleanup_between_tests`

**Related Root Causes:** shared_state_pollution

**Description:** Tests that create resources (tables, files, goroutines) without proper cleanup, leaving state for subsequent tests.

**Why Risky:** Leftover state from previous tests can cause unexpected behavior, making failures dependent on test execution order.

**Review Questions:**
- Are all created tables cleaned up after the test?
- Are goroutines properly terminated?
- Is there a tearDown or cleanup function?

**Suggested Fixes:**
- Use defer to drop tables after creation
- Use t.Cleanup() for test resource management
- Ensure goroutines exit properly
- Use unique resource names per test

### Asserting on exact plan or cost

**Key:** `assert_exact_plan_or_cost`

**Related Root Causes:** nondeterministic_plan_selection

**Description:** Tests that check for specific plan IDs, operator costs, or exact plan structure which may vary.

**Why Risky:** Optimizer plan selection depends on statistics, configuration, and algorithm changes. Exact plan assertions are fragile.

**Review Questions:**
- Is the test asserting on specific plan IDs?
- Are cost values hardcoded in assertions?
- Could statistics changes affect the plan?

**Suggested Fixes:**
- Assert on plan properties instead of exact IDs
- Use hints to stabilize plan when needed
- Update statistics before asserting on plans
- Make cost assertions approximate/range-based

### time.Sleep() for synchronization

**Key:** `time_sleep_for_sync`

**Related Root Causes:** async_timing_issue

**Description:** Using fixed time.Sleep() calls to wait for async operations instead of proper synchronization.

**Why Risky:** Fixed sleeps are fragile - too short causes races, too long slows tests. Load-dependent failures.

**Review Questions:**
- Is time.Sleep() used for synchronization?
- Could the sleep be too short under load?
- Is there a better synchronization mechanism?

**Suggested Fixes:**
- Replace sleep with channel/condition variable
- Use wait loop with backoff
- Add proper event notification

### Missing ORDER BY in SELECT queries

**Key:** `missing_order_by`

**Related Root Causes:** nondeterministic_result_order

**Description:** SELECT queries without explicit ORDER BY may return results in non-deterministic order, causing assertions to fail intermittently.

**Why Risky:** SQL standard does not guarantee result order without ORDER BY. Parallel execution, chunk processing, and storage layer variations can all affect observed order.

**Review Questions:**
- Does this query need ordered results for the test assertion?
- Is the test asserting on row order without ORDER BY?
- Could parallel execution affect the observed order?

**Suggested Fixes:**
- Add explicit ORDER BY clause to the query
- Use .Sort() before .Check() in test assertions
- Use testkit.Rows() with explicit ordering expectations

### Deprecated test framework usage

**Key:** `deprecated_test_framework_usage`

**Related Root Causes:** test_infra_migration

**Description:** Tests still using deprecated frameworks (check.C, gocheck) that have known issues.

**Why Risky:** Deprecated frameworks have known limitations and are not actively maintained.

**Review Questions:**
- Is this test using a deprecated framework?
- Should it be migrated to testify?
- Are there framework-specific issues?

**Suggested Fixes:**
- Migrate to testify
- Update to modern Go testing patterns
- Remove deprecated framework dependencies

### Statistics-sensitive test

**Key:** `statistics_sensitive_test`

**Related Root Causes:** nondeterministic_plan_selection

**Description:** Tests that fail when statistics change or are not updated, leading to plan or cost differences.

**Why Risky:** Statistics affect optimizer decisions. Tests sensitive to stats will fail when data distribution changes.

**Review Questions:**
- Does the test require specific statistics?
- Is ANALYZE TABLE called before assertions?
- Could data volume affect test results?

**Suggested Fixes:**
- Call ANALYZE TABLE to ensure stats are current
- Use hints to control plan selection
- Make assertions less sensitive to exact plans

### Async wait without backoff/retry

**Key:** `async_wait_without_backoff`

**Related Root Causes:** async_timing_issue

**Description:** Waiting for async operations without proper backoff strategy or retry logic.

**Why Risky:** Without backoff, tests may poll too aggressively or give up too quickly.

**Review Questions:**
- Is there proper backoff for async waits?
- Could polling be too aggressive?
- Is retry logic adequate?

**Suggested Fixes:**
- Implement exponential backoff
- Use library utilities for wait/retry
- Add jitter to prevent thundering herd

### t.Parallel() with shared state

**Key:** `t_parallel_with_shared_state`

**Related Root Causes:** concurrency_data_race, shared_state_pollution

**Description:** Tests marked with t.Parallel() that access shared variables, global state, or common fixtures without proper synchronization.

**Why Risky:** Parallel tests run concurrently and race on shared state, causing data races and non-deterministic failures.

**Review Questions:**
- Does this parallel test access any shared variables?
- Are global settings modified by this test?
- Could other parallel tests interfere with this one?

**Suggested Fixes:**
- Remove t.Parallel() if shared state cannot be avoided
- Use sync.Mutex to protect shared state
- Convert shared state to per-test local state
- Use t.Run() with sequential execution instead

### Relying on Go map iteration order

**Key:** `relying_on_map_iteration_order`

**Related Root Causes:** nondeterministic_result_order

**Description:** Go maps have randomized iteration order. Code that assumes map iteration is deterministic will be flaky.

**Why Risky:** Go intentionally randomizes map iteration order to prevent dependence on implementation details. Tests assuming stable order will fail randomly.

**Review Questions:**
- Is the code iterating over a map and assuming order?
- Are map keys being used in a way that affects test output?
- Is there a slice that should be sorted before comparison?

**Suggested Fixes:**
- Sort slices before comparison
- Use ordered data structures when order matters
- Use maps only when order is irrelevant to the test

### Clock skew dependency

**Key:** `clock_skew_dependency`

**Related Root Causes:** async_timing_issue

**Description:** Tests that fail due to clock skew or depend on precise timing between operations.

**Why Risky:** Clock skew in distributed systems or CI environments can cause timing-dependent tests to fail.

**Review Questions:**
- Does the test depend on system clock?
- Could clock skew affect results?
- Is time comparison used?

**Suggested Fixes:**
- Use monotonic clock where possible
- Allow tolerance in time comparisons
- Mock time for deterministic tests

### Async schema propagation issue

**Key:** `async_schema_propagation`

**Related Root Causes:** schema_change_race

**Description:** Tests affected by the asynchronous nature of schema propagation in TiDB cluster.

**Why Risky:** Schema changes are propagated asynchronously. Tests assuming immediate visibility will be flaky.

**Review Questions:**
- Is the test running against a cluster (not mock store)?
- Does it query immediately after DDL?
- Are there multiple TiDB nodes involved?

**Suggested Fixes:**
- Add waits for schema propagation
- Use local/mock store for DDL-sensitive tests
- Implement retry logic for schema errors

### Hardcoded port or resource

**Key:** `hardcoded_port_or_resource`

**Related Root Causes:** external_dependency

**Description:** Tests using hardcoded ports, file paths, or other resources that may conflict.

**Why Risky:** Hardcoded resources cause conflicts when tests run in parallel or on shared infrastructure.

**Review Questions:**
- Are ports hardcoded?
- Could file paths conflict?
- Are resources properly isolated?

**Suggested Fixes:**
- Use ephemeral ports (port 0)
- Use temporary directories
- Generate unique resource names

### Plan cache dependency

**Key:** `plan_cache_dependency`

**Related Root Causes:** nondeterministic_plan_selection

**Description:** Tests that depend on plan cache behavior without clearing or accounting for cached plans.

**Why Risky:** Plan cache state from previous tests or operations can cause unexpected plan selection.

**Review Questions:**
- Does the test assume a cold plan cache?
- Is plan cache cleared between relevant operations?
- Could previous tests affect plan selection?

**Suggested Fixes:**
- Clear plan cache at test start when needed
- Account for cached plans in assertions
- Use ADMIN EVOLVE to manage plan bindings

### DDL without wait for completion

**Key:** `ddl_without_wait`

**Related Root Causes:** schema_change_race

**Description:** DDL operations (CREATE, ALTER, DROP) executed without waiting for completion before subsequent queries.

**Why Risky:** DDL is asynchronous. Queries executed immediately after DDL may see old schema or fail.

**Review Questions:**
- Is there a wait after DDL operations?
- Does the test query the table immediately after creation?
- Is schema version synchronization handled?

**Suggested Fixes:**
- Use tk.MustExec() and ensure DDL completes
- Add explicit waits for schema propagation
- Query information_schema to verify DDL completion

### Shared table without isolation

**Key:** `shared_table_without_isolation`

**Related Root Causes:** shared_state_pollution

**Description:** Multiple tests using the same table names without proper isolation or cleanup.

**Why Risky:** Shared tables cause data pollution between tests, leading to order-dependent failures.

**Review Questions:**
- Are table names unique per test?
- Is there proper table cleanup?
- Could data from one test affect another?

**Suggested Fixes:**
- Use unique table names per test
- Drop tables in defer/t.Cleanup()
- Use transactions and rollback

### Real TiKV dependency

**Key:** `real_tikv_dependency`

**Related Root Causes:** external_dependency

**Description:** Tests that require a real TiKV cluster instead of using mock storage.

**Why Risky:** Real TiKV tests are slower and can fail due to cluster issues, not code bugs.

**Review Questions:**
- Does this test need real TiKV?
- Could it use mock store instead?
- Are cluster issues causing flakiness?

**Suggested Fixes:**
- Use mock store when possible
- Add proper retry for cluster operations
- Isolate TiKV-specific tests

### Test suite setup issue

**Key:** `test_suite_setup_issue`

**Related Root Causes:** test_infra_migration

**Description:** Issues with test suite initialization, shared fixtures, or suite-level setup/teardown.

**Why Risky:** Suite-level issues affect multiple tests and can cause cascading failures that are hard to diagnose.

**Review Questions:**
- Is the test suite setup correct?
- Are shared fixtures properly initialized?
- Does teardown clean up properly?

**Suggested Fixes:**
- Review and fix suite setup/teardown
- Ensure fixtures are properly managed
- Consider migrating to testify suite

### Schema version race

**Key:** `schema_version_race`

**Related Root Causes:** schema_change_race

**Description:** Tests that encounter schema version mismatches due to propagation delays in distributed systems.

**Why Risky:** In distributed TiDB, schema changes propagate asynchronously. Nodes may have different schema versions.

**Review Questions:**
- Does the test involve multiple sessions/connections?
- Could schema cache be stale?
- Is there schema version synchronization?

**Suggested Fixes:**
- Ensure DDL completion before cross-session queries
- Handle schema error with retry
- Use single session when possible

### Unsafe zero-copy aliasing (mutable backing buffer)

**Key:** `unsafe_zero_copy_alias`

**Related Root Causes:** shared_state_pollution

**Description:** Errors/warnings capture string/byte arguments that alias mutable buffers (e.g., chunk-backed strings), so later buffer reuse/mutation can change the message.

**Why Risky:** Delayed formatting may read mutated data, producing nondeterministic error texts and flaky assertions.

**Review Questions:**
- Are strings built from mutable byte slices (e.g., hack.String) stored and formatted later?
- Could a buffer (chunk/byte slice) be reused before the message is formatted or asserted?
- Is there an explicit copy/freeze of string arguments before storing them in warnings/errors?

**Suggested Fixes:**
- Copy or freeze string/byte arguments before storing them in errors/warnings
- Avoid zero-copy conversions for values that outlive the backing buffer
- Format messages eagerly while inputs are still valid

### Network operations without retry

**Key:** `network_without_retry`

**Related Root Causes:** external_dependency

**Description:** Network-dependent operations that don't implement retry logic for transient failures.

**Why Risky:** Network is inherently unreliable. Without retry, transient errors cause test failures.

**Review Questions:**
- Does this involve network operations?
- Is there retry logic for failures?
- Are transient errors handled?

**Suggested Fixes:**
- Add retry with exponential backoff
- Handle transient errors gracefully
- Use idempotent operations when possible

### Randomized test input / probabilistic assertion

**Key:** `randomized_test_input`

**Related Root Causes:** nondeterministic_test_input

**Description:** Tests that generate random inputs (math/rand) or rely on probabilistic properties without controlling the seed or making the assertion deterministic.

**Why Risky:** Random inputs can occasionally hit rare edge cases (e.g., scientific notation, zero shard bits, rounding/overflow), and probabilistic assertions can fail rarely. This makes failures intermittent and hard to reproduce.

**Review Questions:**
- Does the test generate random inputs (math/rand) without a fixed seed or a per-test rand.Source?
- Could random values hit edge cases that break parsing/formatting or assertions?
- Can we replace randomness with deterministic test vectors, or log the seed to make failures reproducible?

**Suggested Fixes:**
- Replace randomness with deterministic test vectors (table-driven inputs)
- Use a fixed seed or per-test rand.Source and log the seed on failure
- Avoid probabilistic assertions; assert deterministic invariants or accept equivalent outcomes

### Asserting on exact error message/constraint

**Key:** `assert_exact_error_message`

**Related Root Causes:** nondeterministic_plan_selection

**Description:** Tests that assert an exact error message or constraint name when multiple equivalent errors can occur depending on plan or execution order.

**Why Risky:** For multi-table statements (e.g. JOIN with foreign keys), which constraint fails first and the exact message can vary across runs, causing intermittent failures even when the error code is correct.

**Review Questions:**
- Does the test match the full error string or a specific constraint name?
- Could a different but equivalent error be returned depending on join/plan order?
- Is it sufficient to assert on the error code (and optionally a stable substring) instead of the full message?

**Suggested Fixes:**
- Assert on stable error code (e.g. 1451) and allow multiple acceptable messages
- Use regex/substring matching for the stable part of the message
- Stabilize execution/plan with hints if the specific error source matters

### Relying on GC/finalizer timing

**Key:** `finalizer_timing_dependency`

**Related Root Causes:** async_timing_issue

**Description:** Tests rely on Go GC/finalizer scheduling to trigger cleanup or callbacks, and assert on behavior that depends on when finalizers run.

**Why Risky:** Finalizers run asynchronously and are not guaranteed to execute at a specific time (or at all before process exit). This makes tests timing-sensitive and flaky under CI load or different runtime behavior.

**Review Questions:**
- Does the test depend on a finalizer callback running within a time window?
- Can the same assertion be done via an explicit Close/Stop API instead of finalizers?
- Is the test asserting inside a finalizer, which may run after teardown?

**Suggested Fixes:**
- Avoid finalizers in tests; use explicit lifecycle management (Close/Stop) and wait for completion
- If finalizers must be used, guard callbacks during teardown and avoid fatal assertions in finalizers
- Use deterministic synchronization (poll/Eventually) rather than relying on GC timing

### Unsupported pushdown (virtual/generated columns or unsupported expressions)

**Key:** `unsupported_pushdown`

**Related Root Causes:** nondeterministic_plan_selection

**Description:** The optimizer pushes down operators (e.g. TopN/Sort) to TiKV/TiFlash when ORDER BY / filter expressions reference virtual/generated columns or expressions not supported for pushdown.

**Why Risky:** Unsupported pushdown can lead to incorrect results or panics, and the behavior may vary across engines (TiKV vs TiFlash) or plan choices, making tests intermittently fail.

**Review Questions:**
- Does the plan push down TopN/Sort/filters to coprocessor while using virtual/generated columns in the expressions?
- Are there engine-specific limitations (TiKV/TiFlash) for the pushed-down expressions/operators?
- Would a different plan choice change whether the operator is pushed down?

**Suggested Fixes:**
- Add capability checks to prevent pushdown when expressions/operators are not supported
- Materialize virtual/generated expressions at the right layer (keep TopN/Sort on root when needed)
- Add regression tests to assert correctness across TiKV/TiFlash paths

### Incomplete testify migration

**Key:** `incomplete_testify_migration`

**Related Root Causes:** test_infra_migration

**Description:** Tests partially migrated to testify that still have issues with setup, assertions, or cleanup.

**Why Risky:** Partial migrations often have subtle issues with test lifecycle, assertion patterns, or fixture management.

**Review Questions:**
- Is the testify migration complete?
- Are there leftover patterns from old framework?
- Does test setup work correctly with testify?

**Suggested Fixes:**
- Complete the testify migration
- Remove old framework dependencies
- Update test setup to testify patterns
