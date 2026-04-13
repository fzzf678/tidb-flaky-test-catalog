#!/usr/bin/env python3

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Tuple


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def _iter_case_files(root: Path) -> Iterable[Path]:
    cases_dir = root / "cases"
    if not cases_dir.exists():
        return []
    return sorted(p for p in cases_dir.rglob("*.json") if p.is_file())


def _count_case_labels(case_files: Iterable[Path]) -> Tuple[int, Counter, Counter]:
    total_cases = 0
    root_cause_counts: Counter = Counter()
    smell_counts: Counter = Counter()

    for path in case_files:
        total_cases += 1
        case = _read_json(path)
        if not isinstance(case, dict):
            continue

        root_causes = {
            x
            for x in (case.get("root_cause_categories") or [])
            if isinstance(x, str) and x.strip()
        }
        smells = {
            x
            for x in (case.get("review_smells") or [])
            if isinstance(x, str) and x.strip()
        }

        root_cause_counts.update(root_causes)
        smell_counts.update(smells)

    return total_cases, root_cause_counts, smell_counts


def _pct(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total * 100.0, 2)

def _sort_items_by_observed_case_count(items: list) -> None:
    # Stable sort: for ties, preserve existing order.
    def sort_key(item: Any) -> Tuple[int, int]:
        if not isinstance(item, dict):
            return (1, 0)
        count = item.get("observed_case_count", 0)
        try:
            count = int(count)
        except Exception:
            count = 0
        return (0, -count)

    items.sort(key=sort_key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh observed case counts/pct in taxonomy.json and review_smells.json")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="repo root path")
    args = parser.parse_args()

    root: Path = args.repo.resolve()
    taxonomy_path = root / "taxonomy.json"
    smells_path = root / "review_smells.json"

    taxonomy = _read_json(taxonomy_path)
    smells = _read_json(smells_path)

    total_cases, root_cause_counts, smell_counts = _count_case_labels(_iter_case_files(root))

    if isinstance(taxonomy, dict):
        taxonomy["observed_total_cases"] = total_cases
        categories = taxonomy.get("categories")
        if isinstance(categories, list):
            for item in categories:
                if not isinstance(item, dict):
                    continue
                key = item.get("key")
                if not isinstance(key, str) or not key:
                    continue
                c = int(root_cause_counts.get(key, 0))
                item["observed_case_count"] = c
                item["observed_case_pct"] = _pct(c, total_cases)
            _sort_items_by_observed_case_count(categories)

    if isinstance(smells, dict):
        smells["observed_total_cases"] = total_cases
        smell_items = smells.get("smells")
        if isinstance(smell_items, list):
            for item in smell_items:
                if not isinstance(item, dict):
                    continue
                key = item.get("key")
                if not isinstance(key, str) or not key:
                    continue
                c = int(smell_counts.get(key, 0))
                item["observed_case_count"] = c
                item["observed_case_pct"] = _pct(c, total_cases)
            _sort_items_by_observed_case_count(smell_items)

    _write_json(taxonomy_path, taxonomy)
    _write_json(smells_path, smells)

    print(f"Updated observed stats: total_cases={total_cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
