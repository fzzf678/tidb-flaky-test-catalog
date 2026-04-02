#!/usr/bin/env python3

import argparse
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


ROOT_CAUSE_SENTENCE: Dict[str, str] = {
    "nondeterministic_result_order": (
        "The test was flaky because it relied on nondeterministic result ordering "
        "(e.g., missing ORDER BY / unsorted assertions)."
    ),
    "concurrency_data_race": "The test was flaky due to concurrency races or unsynchronized shared state.",
    "nondeterministic_plan_selection": (
        "The test was flaky because it asserted an exact plan/EXPLAIN output that can vary between runs."
    ),
    "async_timing_issue": (
        "The test was flaky due to timing-sensitive asynchronous behavior (background tasks/events not fully settled)."
    ),
    "schema_change_race": "The test was flaky around DDL/schema changes where schema propagation is asynchronous.",
    "shared_state_pollution": "The test was flaky due to leaked global/shared state between tests.",
    "external_dependency": (
        "The test was flaky due to environment/external dependencies (resource contention, ports, or real cluster timing)."
    ),
    "time_based_flakiness": "The test was flaky due to time-based assumptions (fixed sleeps, deadlines, or clock/TSO skew).",
    "insufficient_evidence": (
        "Insufficient evidence to determine the underlying root cause from the available case data; "
        "needs CI logs or a reliable repro."
    ),
}


SMELL_HINT: Dict[str, str] = {
    "missing_order_by": "Result ordering is not guaranteed unless explicitly enforced.",
    "unsorted_result_assertion": "Result ordering is not guaranteed unless explicitly enforced.",
    "relying_on_map_iteration_order": "Map/dict iteration order is not stable across runs.",
    "time_sleep_for_sync": "Fixed sleeps are brittle under CI timing jitter.",
    "async_wait_without_backoff": "Fixed waits without polling/backoff are brittle under CI timing jitter.",
    "race_condition_in_async_code": "Asynchronous state transitions need polling/Eventually-style checks.",
    "t_parallel_with_shared_state": "Running in parallel with shared state can introduce races.",
    "global_variable_mutation": "Global state must be reset/restored between tests.",
    "assert_exact_plan_or_cost": "Exact plan/EXPLAIN assertions are brittle when optimizer choices can vary.",
    "plan_cache_dependency": "Plan-cache/lease/background refresh can introduce timing-dependent behavior.",
    "needs_more_evidence": "Insufficient evidence to determine the underlying root cause.",
}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _is_generic_fix_pattern(fp: str) -> bool:
    fp = (fp or "").strip()
    if not fp:
        return True
    if fp.lower().startswith("diff shows determinism stabilization"):
        return True
    if fp.lower() in {"todo", "tbd"}:
        return True
    return False


def _first_sentence(text: str, *, max_len: int = 220) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""

    parts = re.split(r"(?<=[.!?])\s+", text)
    if parts:
        first = parts[0].strip()
        if len(first) <= max_len:
            return first
    return text[:max_len].rstrip() + "…"


def _generate_explanation(case: Dict[str, Any]) -> str:
    root_causes = case.get("root_cause_categories") or ["insufficient_evidence"]
    rc = root_causes[0] if root_causes else "insufficient_evidence"
    smells = case.get("review_smells") or []
    smell = smells[0] if smells else None

    base = ROOT_CAUSE_SENTENCE.get(
        rc,
        "The test was flaky due to nondeterministic behavior that was not fully captured in the extracted evidence.",
    )
    hint = SMELL_HINT.get(smell) if smell else None

    # For insufficient evidence cases, keep it as a short marker for stats.
    if rc == "insufficient_evidence" or smell == "needs_more_evidence":
        return ROOT_CAUSE_SENTENCE["insufficient_evidence"]

    fp = (case.get("fix_pattern") or "").strip()
    title = (case.get("source_pr") or {}).get("title", "").strip()

    if _is_generic_fix_pattern(fp):
        fix = title or "removing the source of nondeterminism in the test/logic"
        s2 = f"This PR stabilizes it by {fix}."
    else:
        s2 = f"This PR stabilizes it by: {_first_sentence(fp)}"
        if not s2.endswith("."):
            s2 += "."

    if hint:
        return f"{base} {hint} {s2}"
    return f"{base} {s2}"


def _inject_after_review_smells(case: Dict[str, Any], *, explanation: str) -> Dict[str, Any]:
    out: "OrderedDict[str, Any]" = OrderedDict()
    inserted = False
    for k, v in case.items():
        if k == "root_cause_explanation":
            continue
        out[k] = v
        if k == "review_smells":
            out["root_cause_explanation"] = explanation
            inserted = True
    if not inserted:
        out["root_cause_explanation"] = explanation
    return out


def _iter_case_files(paths: Sequence[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file() and p.suffix == ".json":
            yield p
            continue
        if p.is_dir():
            yield from sorted(pp for pp in p.rglob("pr-*.json") if pp.is_file())


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Add root_cause_explanation to case JSON files.")
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=None,
        help="Case file(s) or directory(s). Defaults to repo_root/cases.",
    )
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="repo root path")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing root_cause_explanation values (default: only fill missing).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned updates, do not write files.")
    args = parser.parse_args(list(argv))

    repo: Path = args.repo
    targets = args.paths or [repo / "cases"]
    case_files = list(_iter_case_files(targets))
    if not case_files:
        print("No case files found.", file=sys.stderr)
        return 2

    updated = 0
    skipped = 0
    for path in case_files:
        case = _read_json(path)
        if not isinstance(case, dict):
            skipped += 1
            continue

        existing = case.get("root_cause_explanation")
        if existing and not args.overwrite:
            skipped += 1
            continue

        explanation = _generate_explanation(case)
        if not explanation.strip():
            raise RuntimeError(f"Generated empty explanation for: {path}")

        out = _inject_after_review_smells(case, explanation=explanation)
        if args.dry_run:
            print(f"{path}: {explanation}")
        else:
            _write_json(path, out)
        updated += 1

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {updated} file(s); skipped {skipped} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
