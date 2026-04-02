# Milestone 3: Guardrails MVP (AI-only)

This milestone turns the **Taxonomy v0.1** + **Checklist v0.1** into a practical, always-on review guardrail.

## Goal

Catch common flaky-test risk patterns **during code review**, especially in test changes, by having a review bot:

- detect high-risk patterns (*review smells*)
- ask actionable questions
- suggest deterministic fixes
- avoid “hard guessing” when evidence is insufficient

## Scope (v0.1)

- **AI-only** guardrails (fast to iterate)
- No mandatory lint/CI rules yet (avoid premature strictness)
- Stable machine-readable keys:
  - root causes: `taxonomy.json`
  - smells/checklist: `review_smells.json` + generated `docs/review_checklist.md`

## Recommended rollout plan

### Step 1 — Enable a review bot (example: CodeRabbit)

Install the GitHub App on the target repo (e.g. TiDB repo) and start in “comment-only” mode.

### Step 2 — Add repo-level instructions

Use a config file and/or guideline file so the bot can:

- focus on test changes (`**/*_test.go`, `tests/**`, etc.)
- reference smell keys (e.g. `missing_order_by`, `race_condition_in_async_code`)
- use semantic fallback for low-evidence cases:
  - root cause: `insufficient_evidence`
  - smell: `needs_more_evidence`

This repo includes a ready-to-use configuration example:

- `.coderabbit.yaml` (path-based guardrails instructions + default ignores for bulk data)
- `.github/copilot-instructions.md` (high-level review instructions)

### Step 3 — Iterate weekly

Collect feedback and iterate on:

- taxonomy boundaries (merge/split categories)
- smell definitions/questions/fixes
- reducing noise (path filters, severity, applies_to)

## Acceptance checklist

- [ ] Bot comments include smell keys in backticks (e.g. `missing_order_by`)
- [ ] Bot asks **actionable** questions, not generic advice
- [ ] For ambiguous cases, bot uses `needs_more_evidence` instead of guessing
- [ ] No CI failures introduced (guardrails are advisory)

