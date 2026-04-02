# TiDB Flaky Test Catalog

This repository catalogs historical flaky tests in TiDB as structured JSON cases and maintains two dictionaries:

- `taxonomy.json`: root-cause taxonomy (stable keys)
- `review_smells.json`: review smells / checklist primitives (stable keys)

## Layout

- `cases/`: one flaky case per JSON file (suggested: `cases/<YYYY>/<MM>/pr-<PR>.json`)
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

## Milestone 2 helpers

These scripts do not modify `cases/**` unless explicitly stated.

- Generate a quick stats report:

```bash
./.venv/bin/python3 scripts/stats_cases.py --output reports/milestone2_stats.md
```

- Generate the review checklist markdown from `review_smells.json`:

```bash
./.venv/bin/python3 scripts/gen_checklist.py
```
