# TiDB Flaky Guardrails (Milestone 3) — Review Instructions

This repo maintains a flaky-test catalog plus two authoritative dictionaries:

- `taxonomy.json`: root cause taxonomy (**stable keys** used by cases)
- `review_smells.json`: review smells + checklist items (**stable keys** used by cases)

When reviewing PRs that touch tests, prioritize catching patterns that may introduce flakiness.

## What to do in reviews

1) **Detect review smells (prefer key-based comments)**
- If you spot a known pattern, mention the smell `key` in backticks (e.g. `missing_order_by`).
- Ask the associated `review_questions`.
- Suggest concrete fixes aligned with `suggested_fixes`.

2) **Prefer deterministic fixes**
- Prefer ordering (`ORDER BY` / `.Sort()`), synchronization, isolation, and proper cleanup.
- Avoid masking issues with pure timeouts/sleeps/retries unless absolutely necessary.

3) **Use semantic fallback for low-evidence cases**
- If there is not enough evidence to confidently determine root cause, use:
  - root cause: `insufficient_evidence`
  - smell: `needs_more_evidence`
- Ask for missing failure signature / CI logs / repro hints so the case can be re-triaged later.

## Output format suggestion (for bot comments)

- **Findings**: bullet list with smell keys
- **Why risky**: 1–2 lines
- **Questions**: 2–5 concrete questions
- **Suggested fixes**: 1–3 actionable changes

