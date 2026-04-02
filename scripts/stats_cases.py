#!/usr/bin/env python3

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class CasePathMeta:
    year: str
    month: str
    filename: str


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _iter_case_files(root: Path) -> Iterable[Path]:
    cases_dir = root / "cases"
    if not cases_dir.exists():
        return []
    return sorted(p for p in cases_dir.rglob("*.json") if p.is_file())


def _case_meta_from_path(path: Path) -> Optional[CasePathMeta]:
    # cases/<YYYY>/<MM>/pr-<PR>.json
    try:
        month_dir = path.parent
        year_dir = month_dir.parent
        if year_dir.parent.name != "cases":
            return None
        year = year_dir.name
        month = month_dir.name
        return CasePathMeta(year=year, month=month, filename=path.name)
    except Exception:
        return None


def _path_prefix(path_str: str, *, depth: int) -> str:
    parts = [p for p in path_str.split("/") if p]
    if not parts:
        return path_str
    return "/".join(parts[: max(1, depth)])


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


def _joined_text(case: Dict[str, Any]) -> str:
    chunks: List[str] = []
    chunks.append(_safe_str(case.get("fix_pattern")))
    chunks.extend(_safe_str(s) for s in (case.get("symptoms") or []) if isinstance(s, str))
    chunks.append(_safe_str(case.get("failure_signature")))
    test = case.get("test") if isinstance(case.get("test"), dict) else {}
    chunks.append(_safe_str(test.get("path")))
    chunks.extend(_safe_str(p) for p in (case.get("changed_files") or []) if isinstance(p, str))
    return "\n".join(c for c in chunks if c)


def _count_keyword_hits(case_files: Sequence[Path]) -> List[Tuple[str, int]]:
    # Counts are "number of cases that match the keyword regex at least once".
    patterns: Dict[str, re.Pattern[str]] = {
        "order": re.compile(r"\b(order|ordering|sort|order\s+by|stable\s+result|ordered\s+result)\b", re.I),
        "race": re.compile(r"\brace\b|data race", re.I),
        "nondetermin": re.compile(r"nondetermin", re.I),
        "unstable": re.compile(r"unstable", re.I),
        "plan": re.compile(r"\bplan\b|explain|optimizer|cost model", re.I),
        "ddl": re.compile(r"\bddl\b|schema", re.I),
        "flaky": re.compile(r"\bflaky\b", re.I),
        "skip": re.compile(r"\bskip\b|t\.Skip\(|c\.Skip\(", re.I),
        "timeout": re.compile(r"timeout|deadline|takes too long|slow", re.I),
        "rand": re.compile(r"\brand\b|rand\.|seed|uuid|UnixNano", re.I),
        "sleep": re.compile(r"time\.Sleep\(|\bsleep\b", re.I),
        "eventually": re.compile(r"Eventually|polling|wait", re.I),
        "bazel_race_attr": re.compile(r"race\s*=\s*\"(on|off)\"", re.I),
        "bazel_flaky_attr": re.compile(r"flaky\s*=\s*True", re.I),
    }

    hits: Counter[str] = Counter()
    for path in case_files:
        case = _read_json(path)
        if not isinstance(case, dict):
            continue
        blob = _joined_text(case)
        for name, pat in patterns.items():
            if pat.search(blob):
                hits[name] += 1
    return hits.most_common()


def _print_table_kv(items: Sequence[Tuple[str, int]], *, limit: int) -> List[str]:
    lines: List[str] = []
    for k, v in items[:limit]:
        lines.append(f"- `{k}`: {v}")
    return lines


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Compute quick stats for cases/ (Milestone 2 groundwork).")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="repo root path")
    parser.add_argument("--top", type=int, default=15, help="top N entries for list-style sections")
    parser.add_argument("--path-prefix-depth", type=int, default=2, help="how many path components to group by")
    parser.add_argument("--output", type=Path, default=None, help="write markdown report to this path")
    args = parser.parse_args(list(argv))

    root: Path = args.repo
    case_files = list(_iter_case_files(root))
    if not case_files:
        print(f"No case files found under: {root / 'cases'}", file=sys.stderr)
        return 2

    # Core counts
    by_year: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    by_test_type: Counter[str] = Counter()
    by_test_path_prefix: Counter[str] = Counter()
    by_root_cause: Counter[str] = Counter()
    by_smell: Counter[str] = Counter()
    by_fix_pattern: Counter[str] = Counter()

    for path in case_files:
        meta = _case_meta_from_path(path)
        if meta:
            by_year[meta.year] += 1
            by_month[f"{meta.year}/{meta.month}"] += 1

        case = _read_json(path)
        if not isinstance(case, dict):
            continue

        test = case.get("test")
        if isinstance(test, dict):
            ttype = test.get("type")
            tpath = test.get("path")
            if isinstance(ttype, str) and ttype:
                by_test_type[ttype] += 1
            if isinstance(tpath, str) and tpath:
                by_test_path_prefix[_path_prefix(tpath, depth=args.path_prefix_depth)] += 1

        for k in case.get("root_cause_categories") or []:
            if isinstance(k, str) and k:
                by_root_cause[k] += 1

        for k in case.get("review_smells") or []:
            if isinstance(k, str) and k:
                by_smell[k] += 1

        fp = case.get("fix_pattern")
        if isinstance(fp, str) and fp.strip():
            by_fix_pattern[fp.strip()] += 1

    # Build markdown
    lines: List[str] = []
    lines.append("# Flaky Case Stats (quick)\n")
    lines.append(f"- Repo: `{root}`")
    lines.append(f"- Total cases: **{len(case_files)}**")

    lines.append("\n## By test.type\n")
    for k, v in by_test_type.most_common():
        lines.append(f"- `{k}`: {v}")

    lines.append("\n## Top test.path prefixes\n")
    lines.extend(_print_table_kv(by_test_path_prefix.most_common(), limit=args.top))

    lines.append("\n## root_cause_categories distribution (current)\n")
    lines.extend(_print_table_kv(by_root_cause.most_common(), limit=max(args.top, 30)))

    lines.append("\n## review_smells distribution (current)\n")
    lines.extend(_print_table_kv(by_smell.most_common(), limit=max(args.top, 30)))

    lines.append("\n## Top fix_pattern strings (verbatim)\n")
    for fp, v in by_fix_pattern.most_common(args.top):
        # keep it readable (avoid giant inline strings)
        fp_one_line = " ".join(fp.split())
        if len(fp_one_line) > 140:
            fp_one_line = fp_one_line[:137] + "..."
        lines.append(f"- {v}: {fp_one_line}")

    lines.append("\n## Keyword hits (case-level)\n")
    for name, v in _count_keyword_hits(case_files):
        lines.append(f"- `{name}`: {v}")

    out = "\n".join(lines).rstrip() + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

