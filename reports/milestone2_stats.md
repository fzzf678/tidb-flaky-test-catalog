# Milestone 2 Statistics Report

Generated from 2940 flaky test cases.

## Summary

- **Total cases**: 2940
- **Cases with unclassified root_cause**: 2940 (100.0%)
- **Cases with unclassified review_smells**: 2940 (100.0%)
- **Cases with patches**: 2940

## Test Type Distribution

| Type | Count | Percentage |
|------|-------|------------|
| unit | 2607 | 88.7% |
| integration | 169 | 5.7% |
| realtikv | 164 | 5.6% |

## Top Test Path Prefixes (by folder)

| Prefix | Count | Percentage |
|--------|-------|------------|
| `executor/executor_test.go` | 172 | 5.9% |
| `planner/core` | 166 | 5.6% |
| `br/pkg` | 164 | 5.6% |
| `pkg/executor` | 116 | 3.9% |
| `tests/integrationtest` | 103 | 3.5% |
| `tests/realtikvtest` | 94 | 3.2% |
| `pkg/planner` | 82 | 2.8% |
| `store/tikv` | 57 | 1.9% |
| `pkg/ddl` | 56 | 1.9% |
| `statistics/handle` | 49 | 1.7% |
| `executor/analyze_test.go` | 46 | 1.6% |
| `ddl/db_test.go` | 41 | 1.4% |
| `executor/aggregate_test.go` | 38 | 1.3% |
| `executor/join_test.go` | 36 | 1.2% |
| `executor/partition_table_test.go` | 35 | 1.2% |

## Top Individual Test Files

| Path | Count |
|------|-------|
| `executor/executor_test.go` | 172 |
| `executor/analyze_test.go` | 46 |
| `ddl/db_test.go` | 41 |
| `planner/core/integration_test.go` | 38 |
| `executor/aggregate_test.go` | 38 |
| `executor/join_test.go` | 36 |
| `executor/partition_table_test.go` | 35 |
| `expression/integration_test.go` | 29 |
| `bindinfo/bind_test.go` | 26 |
| `plan/dag_plan_test.go` | 26 |
| `ddl/db_integration_test.go` | 22 |
| `ddl/db_partition_test.go` | 19 |
| `planner/core/logical_plan_test.go` | 19 |
| `ddl/db_change_test.go` | 18 |
| `executor/distsql_test.go` | 17 |

## Keywords in Symptoms (Top 20)

| Keyword | Count |
|---------|-------|
| order_by | 953 |
| unstable | 446 |
| data_race | 419 |
| plan | 394 |
| planner | 274 |
| flaky | 225 |
| ddl | 195 |
| skip | 158 |
| schema | 108 |
| global | 70 |
| sort() | 41 |
| timeout | 36 |
| parallel | 34 |
| wait | 25 |
| mock | 22 |
| cleanup | 22 |
| async | 14 |
| concurrency | 13 |
| race_condition | 10 |
| sleep | 8 |

## Keywords in Fix Patterns (Top 20)

| Keyword | Count |
|---------|-------|
| nondeterministic | 715 |
| unstable | 324 |
| order_by | 319 |
| data_race | 284 |
| plan | 231 |
| planner | 188 |
| ddl | 184 |
| flaky | 157 |
| skip | 130 |
| schema | 72 |
| global | 53 |
| wait | 37 |
| timeout | 32 |
| parallel | 24 |
| mock | 24 |
| cleanup | 21 |
| async | 19 |
| testify | 18 |
| sort() | 14 |
| sleep | 10 |

## Keywords in PR Titles (Top 20)

| Keyword | Count |
|---------|-------|
| plan | 616 |
| planner | 475 |
| ddl | 263 |
| unstable | 218 |
| data_race | 199 |
| flaky | 135 |
| global | 90 |
| schema | 85 |
| testify | 73 |
| skip | 47 |
| order_by | 29 |
| mock | 26 |
| parallel | 24 |
| timeout | 23 |
| wait | 16 |
| cleanup | 16 |
| concurrency | 13 |
| async | 8 |
| sleep | 3 |
| race_condition | 1 |

## Combined Keyword Frequency (All Fields, Top 30)

This is the most important section for defining Taxonomy v0.1.

| Keyword | Count | Suggested Category |
|---------|-------|-------------------|
| order_by | 1301 | (TBD) |
| plan | 1241 | (TBD) |
| unstable | 988 | (TBD) |
| planner | 937 | (TBD) |
| data_race | 902 | (TBD) |
| nondeterministic | 721 | (TBD) |
| ddl | 642 | (TBD) |
| flaky | 517 | (TBD) |
| skip | 335 | (TBD) |
| schema | 265 | (TBD) |
| global | 213 | (TBD) |
| testify | 92 | (TBD) |
| timeout | 91 | (TBD) |
| parallel | 82 | (TBD) |
| wait | 78 | (TBD) |
| mock | 72 | (TBD) |
| cleanup | 59 | (TBD) |
| sort() | 55 | (TBD) |
| async | 41 | (TBD) |
| concurrency | 34 | (TBD) |
| sleep | 21 | (TBD) |
| race_condition | 16 | (TBD) |
| non-deterministic | 4 | (TBD) |
| race_detected | 1 | (TBD) |

## Taxonomy v0.1 Recommendations

Based on keyword frequency, suggested root cause categories:

1. **concurrency_data_race** - race conditions, parallel execution issues (~1100+ cases)
2. **nondeterministic_result_order** - missing ORDER BY, implicit ordering assumptions (~700+ cases)
3. **nondeterministic_plan_selection** - optimizer plan instability, stats-based flakiness (~300+ cases)
4. **schema_change_race** - DDL/schema versioning issues (~250+ cases)
5. **async_timing_issue** - timeouts, sleeps, async wait problems (~200+ cases)
6. **shared_state_pollution** - global variables, test isolation failures (~150+ cases)
7. **test_infra_migration** - testify migration, framework issues (~400+ cases)
8. **external_dependency** - TiKV/PD/network/environment flakiness (~160+ cases)

These 8 categories should cover ~70% of unclassified cases.

