# TiDB Flaky Test Catalog

This repository catalogs historical flaky-test fixes in TiDB as structured JSON cases, and maintains two dictionaries:

- `taxonomy.json`: root-cause taxonomy (stable keys) for classification and statistics
- `review_smells.json`: reviewer-facing “review smells” (stable keys) for PR review checklists

For a human-readable checklist generated from `review_smells.json`, see `docs/review_checklist.md`.

## Key Concepts

- **Taxonomy (root causes)**: `root_cause_categories` represents “what likely caused the flake”. It is used for catalog-wide classification and statistics.
- **Checklist (review smells)**: `review_smells` represents “what risk signals a reviewer can spot in code review”. It is reviewer-facing and is not necessarily a final root-cause conclusion.
- **Multi-select**: a single case may have multiple root causes and multiple smells. As a result, per-category counts can exceed the total number of cases.
- **Insufficient evidence**: when available evidence is not enough to confidently determine the root cause, use the semantic fallback `insufficient_evidence` instead of guessing.

## References

- Review checklist (Markdown): `docs/review_checklist.md`
- Dictionaries: `taxonomy.json`, `review_smells.json`
- Schemas: `schemas/`

## Repository Layout

- `cases/`: one flaky case per JSON file (suggested: `cases/<YYYY>/<MM>/pr-<PR>.json`)
- `docs/`: generated and hand-written reference docs (see `docs/review_checklist.md`)
- `reports/`: generated reports and stats outputs
- `taxonomy.json`: root-cause taxonomy dictionary
- `review_smells.json`: review-smells dictionary
- `schemas/`: JSON Schemas for the above files
- `scripts/validate.py`: repository validator (schema + cross-reference checks)

## Validation

### Local

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python scripts/validate.py
```

### Makefile

```bash
make check
```

## Scripts

These scripts do not modify `cases/**` unless explicitly stated.

- Generate a quick stats report:

```bash
./.venv/bin/python3 scripts/stats_cases.py --output reports/milestone2_stats.md
```

- Generate the review checklist markdown from `review_smells.json`:

```bash
./.venv/bin/python3 scripts/gen_checklist.py
```
