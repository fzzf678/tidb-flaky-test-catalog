# Suggest Tags Evaluation (Baseline)

- Generated at: 2026-04-13T15:46:59
- Repo HEAD: `dfd8024225a3d5a6675b1cc06fb1acdd3b9fb6ca`

## Config

- split: `year`
- test_from_year: `2024`
- top_k: `3`
- thresholds: cause `0.3`, smell `0.3`
- fallback cause keys: `['insufficient_evidence', 'unclassified']`
- fallback smell keys: `['needs_more_evidence', 'unclassified']`

## Dataset

| split | cases | det_cause | fallback_only_cause | det_smell | fallback_only_smell |
|---|---|---|---|---|---|
| train | 2418 | 1122 | 1296 | 1120 | 1298 |
| test | 526 | 339 | 187 | 339 | 187 |

## Results (train)

### Summary

| task | det_cases | top1_hit | top1_% | top3_hit | top3_% | top1_fallback_% |
|---|---|---|---|---|---|---|
| root_cause | 1122 | 736 | 65.60 | 962 | 85.74 | 3.39 |
| review_smells | 1120 | 582 | 51.96 | 835 | 74.55 | 3.30 |

### Root Causes (per-label)

| key | support | top1_precision_% | top1_recall_% | top3_recall_% |
|---|---|---|---|---|
| concurrency_data_race | 485 | 85.34 | 81.65 | 97.32 |
| async_timing_issue | 182 | 80.00 | 26.37 | 70.33 |
| shared_state_pollution | 171 | 68.00 | 19.88 | 55.56 |
| nondeterministic_result_order | 146 | 65.52 | 78.08 | 94.52 |
| nondeterministic_plan_selection | 67 | 54.13 | 88.06 | 95.52 |
| test_infra_migration | 63 | 87.76 | 68.25 | 92.06 |
| external_dependency | 36 | 19.48 | 41.67 | 63.89 |
| schema_change_race | 32 | 26.73 | 84.38 | 100.00 |
| nondeterministic_test_input | 7 | 0.00 | 0.00 | 0.00 |

### Review Smells (per-label)

| key | support | top1_precision_% | top1_recall_% | top3_recall_% |
|---|---|---|---|---|
| race_condition_in_async_code | 440 | 77.53 | 80.00 | 93.41 |
| global_variable_mutation | 130 | 74.47 | 26.92 | 69.23 |
| unsorted_result_assertion | 86 | 6.98 | 3.49 | 63.95 |
| insufficient_cleanup_between_tests | 76 | 75.00 | 7.89 | 23.68 |
| insufficient_timeout | 73 | 65.00 | 17.81 | 46.58 |
| time_sleep_for_sync | 66 | 100.00 | 30.30 | 56.06 |
| missing_order_by | 61 | 33.52 | 96.72 | 100.00 |
| deprecated_test_framework_usage | 58 | 0.00 | 0.00 | 39.66 |
| assert_exact_plan_or_cost | 45 | 57.78 | 57.78 | 95.56 |
| t_parallel_with_shared_state | 40 | 23.53 | 20.00 | 72.50 |
| async_wait_without_backoff | 23 | 30.00 | 26.09 | 47.83 |
| clock_skew_dependency | 23 | 33.33 | 26.09 | 43.48 |
| plan_cache_dependency | 20 | 58.82 | 50.00 | 95.00 |
| statistics_sensitive_test | 20 | 37.93 | 55.00 | 95.00 |
| relying_on_map_iteration_order | 18 | 12.50 | 5.56 | 50.00 |
| async_schema_propagation | 17 | 25.00 | 17.65 | 76.47 |
| hardcoded_port_or_resource | 16 | 36.36 | 25.00 | 43.75 |
| shared_table_without_isolation | 15 | 11.54 | 40.00 | 80.00 |
| ddl_without_wait | 13 | 23.53 | 61.54 | 92.31 |
| real_tikv_dependency | 9 | 18.18 | 22.22 | 77.78 |
| unsafe_zero_copy_alias | 9 | 0.00 | 0.00 | 0.00 |
| test_suite_setup_issue | 8 | 5.88 | 12.50 | 37.50 |
| randomized_test_input | 7 | 0.00 | 0.00 | 0.00 |
| schema_version_race | 7 | 0.00 | 0.00 | 14.29 |
| network_without_retry | 6 | 40.00 | 33.33 | 50.00 |
| assert_exact_error_message | 4 | 0.00 | 0.00 | 0.00 |
| finalizer_timing_dependency | 3 | 0.00 | 0.00 | 0.00 |
| unsupported_pushdown | 3 | 0.00 | 0.00 | 0.00 |

### Common Misses (top-1 confusion samples)

- Root causes (when top1 prediction is not in truth):
  - `async_timing_issue` → `concurrency_data_race`: 38 (e.g. train:pr-648, train:pr-1866, train:pr-3258)
  - `concurrency_data_race` → `schema_change_race`: 35 (e.g. train:pr-1656, train:pr-1669, train:pr-1759)
  - `async_timing_issue` → `external_dependency`: 28 (e.g. train:pr-8186, train:pr-10949, train:pr-13824)
  - `shared_state_pollution` → `concurrency_data_race`: 25 (e.g. train:pr-4591, train:pr-5020, train:pr-6554)
  - `shared_state_pollution` → `external_dependency`: 22 (e.g. train:pr-10949, train:pr-14839, train:pr-15332)
  - `shared_state_pollution` → `nondeterministic_result_order`: 21 (e.g. train:pr-2921, train:pr-5455, train:pr-5654)
  - `shared_state_pollution` → `nondeterministic_plan_selection`: 19 (e.g. train:pr-3098, train:pr-3435, train:pr-5158)
  - `async_timing_issue` → `nondeterministic_result_order`: 16 (e.g. train:pr-15094, train:pr-15604, train:pr-20238)
  - `shared_state_pollution` → `schema_change_race`: 13 (e.g. train:pr-6950, train:pr-9483, train:pr-9960)
  - `concurrency_data_race` → `nondeterministic_result_order`: 13 (e.g. train:pr-12349, train:pr-13451, train:pr-24935)
- Smells (when top1 prediction is not in truth):
  - `unsorted_result_assertion` → `missing_order_by`: 47 (e.g. train:pr-1612, train:pr-2423, train:pr-2557)
  - `global_variable_mutation` → `race_condition_in_async_code`: 38 (e.g. train:pr-1301, train:pr-3706, train:pr-4076)
  - `deprecated_test_framework_usage` → `unsorted_result_assertion`: 21 (e.g. train:pr-26322, train:pr-29535, train:pr-30548)
  - `insufficient_timeout` → `race_condition_in_async_code`: 19 (e.g. train:pr-648, train:pr-1866, train:pr-3258)
  - `deprecated_test_framework_usage` → `race_condition_in_async_code`: 17 (e.g. train:pr-28161, train:pr-29861, train:pr-30260)
  - `race_condition_in_async_code` → `t_parallel_with_shared_state`: 16 (e.g. train:pr-9387, train:pr-11380, train:pr-12414)
  - `race_condition_in_async_code` → `missing_order_by`: 15 (e.g. train:pr-6658, train:pr-8295, train:pr-12349)
  - `insufficient_cleanup_between_tests` → `race_condition_in_async_code`: 14 (e.g. train:pr-4591, train:pr-5020, train:pr-6554)
  - `relying_on_map_iteration_order` → `missing_order_by`: 13 (e.g. train:pr-1652, train:pr-5256, train:pr-11095)
  - `insufficient_cleanup_between_tests` → `shared_table_without_isolation`: 12 (e.g. train:pr-18424, train:pr-23244, train:pr-26875)

## Results (test)

### Summary

| task | det_cases | top1_hit | top1_% | top3_hit | top3_% | top1_fallback_% |
|---|---|---|---|---|---|---|
| root_cause | 339 | 200 | 59.00 | 263 | 77.58 | 4.13 |
| review_smells | 339 | 126 | 37.17 | 221 | 65.19 | 4.13 |

### Root Causes (per-label)

| key | support | top1_precision_% | top1_recall_% | top3_recall_% |
|---|---|---|---|---|
| async_timing_issue | 97 | 87.10 | 27.84 | 62.89 |
| nondeterministic_plan_selection | 66 | 81.43 | 86.36 | 93.94 |
| nondeterministic_result_order | 66 | 72.46 | 75.76 | 100.00 |
| shared_state_pollution | 50 | 83.33 | 40.00 | 68.00 |
| concurrency_data_race | 35 | 34.69 | 48.57 | 77.14 |
| schema_change_race | 24 | 40.00 | 83.33 | 95.83 |
| external_dependency | 21 | 28.12 | 42.86 | 52.38 |
| test_infra_migration | 5 | 0.00 | 0.00 | 0.00 |

### Review Smells (per-label)

| key | support | top1_precision_% | top1_recall_% | top3_recall_% |
|---|---|---|---|---|
| race_condition_in_async_code | 62 | 72.41 | 33.87 | 56.45 |
| assert_exact_plan_or_cost | 49 | 72.09 | 63.27 | 95.92 |
| unsorted_result_assertion | 37 | 0.00 | 0.00 | 48.65 |
| insufficient_timeout | 28 | 36.36 | 14.29 | 42.86 |
| statistics_sensitive_test | 27 | 75.00 | 44.44 | 85.19 |
| global_variable_mutation | 25 | 42.86 | 36.00 | 64.00 |
| relying_on_map_iteration_order | 23 | 57.14 | 17.39 | 56.52 |
| async_wait_without_backoff | 22 | 58.33 | 31.82 | 59.09 |
| insufficient_cleanup_between_tests | 19 | 30.00 | 15.79 | 42.11 |
| time_sleep_for_sync | 19 | 100.00 | 36.84 | 68.42 |
| async_schema_propagation | 14 | 31.58 | 42.86 | 71.43 |
| clock_skew_dependency | 10 | 41.67 | 50.00 | 80.00 |
| hardcoded_port_or_resource | 10 | 33.33 | 10.00 | 20.00 |
| ddl_without_wait | 8 | 21.43 | 37.50 | 87.50 |
| real_tikv_dependency | 8 | 20.00 | 12.50 | 25.00 |
| test_suite_setup_issue | 8 | 0.00 | 0.00 | 12.50 |
| missing_order_by | 7 | 7.69 | 85.71 | 100.00 |
| plan_cache_dependency | 5 | 60.00 | 60.00 | 80.00 |
| schema_version_race | 5 | 0.00 | 0.00 | 20.00 |
| t_parallel_with_shared_state | 4 | 20.00 | 75.00 | 100.00 |
| shared_table_without_isolation | 3 | 0.00 | 0.00 | 33.33 |
| network_without_retry | 2 | 0.00 | 0.00 | 50.00 |
| unsafe_zero_copy_alias | 2 | 0.00 | 0.00 | 0.00 |
| assert_exact_error_message | 1 | 0.00 | 0.00 | 0.00 |

### Common Misses (top-1 confusion samples)

- Root causes (when top1 prediction is not in truth):
  - `async_timing_issue` → `concurrency_data_race`: 26 (e.g. test:pr-50446, test:pr-50634, test:pr-51689)
  - `async_timing_issue` → `schema_change_race`: 14 (e.g. test:pr-50144, test:pr-50314, test:pr-51076)
  - `async_timing_issue` → `external_dependency`: 9 (e.g. test:pr-50824, test:pr-51139, test:pr-51480)
  - `shared_state_pollution` → `external_dependency`: 8 (e.g. test:pr-50687, test:pr-53548, test:pr-56002)
  - `shared_state_pollution` → `schema_change_race`: 7 (e.g. test:pr-50156, test:pr-50874, test:pr-53507)
  - `async_timing_issue` → `insufficient_evidence`: 6 (e.g. test:pr-49971, test:pr-46991, test:pr-57140)
  - `async_timing_issue` → `nondeterministic_result_order`: 6 (e.g. test:pr-51400, test:pr-57703, test:pr-65329)
  - `nondeterministic_result_order` → `nondeterministic_plan_selection`: 5 (e.g. test:pr-47496, test:pr-56307, test:pr-56813)
  - `nondeterministic_result_order` → `schema_change_race`: 4 (e.g. test:pr-50779, test:pr-53277, test:pr-54110)
  - `concurrency_data_race` → `schema_change_race`: 4 (e.g. test:pr-54292, test:pr-55233, test:pr-58229)
- Smells (when top1 prediction is not in truth):
  - `unsorted_result_assertion` → `missing_order_by`: 31 (e.g. test:pr-49758, test:pr-50341, test:pr-50762)
  - `relying_on_map_iteration_order` → `missing_order_by`: 16 (e.g. test:pr-50779, test:pr-51152, test:pr-51531)
  - `assert_exact_plan_or_cost` → `missing_order_by`: 7 (e.g. test:pr-51203, test:pr-53362, test:pr-55195)
  - `race_condition_in_async_code` → `missing_order_by`: 7 (e.g. test:pr-51400, test:pr-52890, test:pr-54504)
  - `race_condition_in_async_code` → `shared_table_without_isolation`: 4 (e.g. test:pr-50314, test:pr-51029, test:pr-58229)
  - `race_condition_in_async_code` → `unsorted_result_assertion`: 4 (e.g. test:pr-54292, test:pr-56596, test:pr-64398)
  - `global_variable_mutation` → `async_schema_propagation`: 4 (e.g. test:pr-55362, test:pr-55431, test:pr-58589)
  - `race_condition_in_async_code` → `insufficient_timeout`: 4 (e.g. test:pr-56444, test:pr-63527, test:pr-63535)
  - `global_variable_mutation` → `t_parallel_with_shared_state`: 4 (e.g. test:pr-56798, test:pr-65064, test:pr-65313)
  - `statistics_sensitive_test` → `assert_exact_plan_or_cost`: 4 (e.g. test:pr-58254, test:pr-60333, test:pr-62123)

