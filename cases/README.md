# Cases

One flaky case per JSON file.

## Naming

- One case per PR: `cases/<YYYY>/<MM>/pr-<PR>.json` (e.g. `cases/2026/03/pr-1234.json`)
- Multiple cases per PR: `cases/<YYYY>/<MM>/pr-<PR>-<idx>.json` where `idx` starts from 0

## Required fields (v0.1)

At minimum, each case should contain:

- `id`
- `source_pr.number`, `source_pr.url`
- `pr_merged_at` (ISO 8601 / RFC 3339 date-time, with timezone)
- `test.type`, `test.path`, `test.name`
- `symptoms[]`
- `failure_signature`
- `root_cause_categories[]` (keys from `taxonomy.json`)
- `review_smells[]` (keys from `review_smells.json`)
- `fix_pattern`
