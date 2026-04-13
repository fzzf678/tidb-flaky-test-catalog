#!/usr/bin/env python3
"""
Evaluate scripts/suggest_tags.py predictions against labels in cases/**/*.json.

Why this exists
---------------
We want a stable, repeatable baseline for improving the flaky-test review skill:
- When we change heuristics (patterns/thresholds), we should be able to measure
  whether the suggestions got better or worse.
- "Fallback / uncertain" labels (e.g. insufficient_evidence / needs_more_evidence)
  should not dominate determinism-focused metrics. By default, this script treats
  them as *fallback* and reports determinism metrics on the remaining (determinate)
  labels; fallback-only cases are reported separately.

Outputs
-------
Writes a Markdown report (default: reports/suggest_tags_eval.md).
"""

import argparse
import datetime as _dt
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


DEFAULT_FALLBACK_CAUSE_KEYS = {"insufficient_evidence", "unclassified"}
DEFAULT_FALLBACK_SMELL_KEYS = {"needs_more_evidence", "unclassified"}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_year(iso_dt: Any) -> Optional[int]:
    if not isinstance(iso_dt, str) or not iso_dt:
        return None
    s = iso_dt.strip()
    # Python 3.8 datetime.fromisoformat does not accept "Z".
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return _dt.datetime.fromisoformat(s).year
    except Exception:
        # Best-effort fallback: YYYY-...
        try:
            return int(s[:4])
        except Exception:
            return None


def _stable_random_bucket(seed: int, case_id: str) -> float:
    h = hashlib.sha1(f"{seed}:{case_id}".encode("utf-8")).hexdigest()
    # Use 32 bits to get a stable float in [0, 1).
    x = int(h[:8], 16)
    return x / float(2**32)


def _parse_csv_ints(s: Optional[str]) -> Set[int]:
    if not s:
        return set()
    out: Set[int] = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        out.add(int(part))
    return out


def _load_key_statuses(path: Path, *, list_field: str) -> Dict[str, str]:
    data = _read_json(path)
    items = data.get(list_field, []) if isinstance(data, dict) else []
    out: Dict[str, str] = {}
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not isinstance(key, str) or not key:
            continue
        status = item.get("status", "active")
        if not isinstance(status, str) or not status:
            status = "active"
        out[key] = status
    return out


def _import_suggest_tags(root: Path):
    scripts_dir = root / "scripts"
    sys.path.insert(0, str(scripts_dir))
    import suggest_tags  # type: ignore

    return suggest_tags


@dataclass
class TopKSummary:
    total: int = 0
    top1_hit: int = 0
    top3_hit: int = 0
    top1_is_fallback: int = 0

    def top1_pct(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(self.top1_hit / self.total * 100.0, 2)

    def top3_pct(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(self.top3_hit / self.total * 100.0, 2)

    def fallback_top1_pct(self) -> float:
        if self.total <= 0:
            return 0.0
        return round(self.top1_is_fallback / self.total * 100.0, 2)


def _eval_multi_label_topk(
    *,
    rows: Iterable[Tuple[str, Path, Set[str], List[str]]],
    active_keys: Set[str],
    fallback_keys: Set[str],
    top_k: int,
) -> Tuple[TopKSummary, Dict[str, Dict[str, int]], List[Tuple[str, int, float, float, float]], List[Tuple[Tuple[str, str], int, List[str]]]]:
    """
    rows: (case_id, rel_path, true_keys, predicted_keys)

    Returns:
    - summary: TopKSummary (on determinate-only rows)
    - counts: per-label counters (support/pred_top1/tp_top1/hit_topk)
    - table: list of (key, support, top1_precision, top1_recall, topk_recall)
    - confusions: top confusion pairs with sample case_ids
    """
    summary = TopKSummary()

    support = Counter()       # label -> #cases where label in truth (determinate only)
    pred_top1 = Counter()     # label -> #cases where top1 predicted == label (determinate only)
    tp_top1 = Counter()       # label -> #cases where top1 predicted == label and label in truth (determinate only)
    hit_topk = Counter()      # label -> #cases where label in truth and label in preds[:k] (determinate only)

    confusion = Counter()     # (true_label, pred_top1_label) -> count (only when pred_top1 not in truth)
    confusion_samples: Dict[Tuple[str, str], List[str]] = {}

    for case_id, rel_path, true_keys, pred_keys in rows:
        true_det = set(true_keys) & set(active_keys)
        if not true_det:
            continue

        summary.total += 1

        pred_list = [p for p in pred_keys if isinstance(p, str) and p]
        top1 = pred_list[0] if pred_list else ""
        topk = pred_list[:top_k]

        if top1 in fallback_keys:
            summary.top1_is_fallback += 1

        if top1 and top1 in true_det:
            summary.top1_hit += 1
        if any(p in true_det for p in topk):
            summary.top3_hit += 1

        for label in true_det:
            support[label] += 1
            if label in topk:
                hit_topk[label] += 1
            if top1 == label:
                tp_top1[label] += 1

        if top1:
            pred_top1[top1] += 1

        if top1 and top1 not in true_det:
            for label in true_det:
                k = (label, top1)
                confusion[k] += 1
                samples = confusion_samples.get(k)
                if samples is None:
                    samples = []
                    confusion_samples[k] = samples
                if len(samples) < 5:
                    samples.append(case_id)

    # Build table for active (determinate) labels only.
    table: List[Tuple[str, int, float, float, float]] = []
    for key in sorted(active_keys, key=lambda k: (-support.get(k, 0), k)):
        sup = int(support.get(key, 0))
        if sup <= 0:
            continue
        tp = int(tp_top1.get(key, 0))
        pred = int(pred_top1.get(key, 0))
        topk_hits = int(hit_topk.get(key, 0))

        precision = round(tp / pred * 100.0, 2) if pred > 0 else 0.0
        recall_top1 = round(tp / sup * 100.0, 2) if sup > 0 else 0.0
        recall_topk = round(topk_hits / sup * 100.0, 2) if sup > 0 else 0.0
        table.append((key, sup, precision, recall_top1, recall_topk))

    # Prepare top confusion pairs.
    confusions: List[Tuple[Tuple[str, str], int, List[str]]] = []
    for pair, cnt in confusion.most_common(30):
        confusions.append((pair, int(cnt), confusion_samples.get(pair, [])[:]))

    counts = {
        "support": dict(support),
        "pred_top1": dict(pred_top1),
        "tp_top1": dict(tp_top1),
        "hit_topk": dict(hit_topk),
    }
    return summary, counts, table, confusions


def _render_md_table(headers: List[str], rows: List[List[str]]) -> List[str]:
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        lines.append("| " + " | ".join(r) + " |")
    return lines


def _git_head(root: Path) -> str:
    try:
        import subprocess

        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root))
        return out.decode("utf-8").strip()
    except Exception:
        return ""


def _main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Evaluate suggest_tags.py against case labels")
    parser.add_argument("--output", type=Path, default=Path("reports/suggest_tags_eval.md"))
    parser.add_argument("--split", choices=["none", "year", "random"], default="year")
    parser.add_argument("--test-from-year", type=int, default=2024, help="For split=year: years >= this are test")
    parser.add_argument("--test-years", type=str, default="", help="For split=year: explicit CSV years (overrides from-year if provided)")
    parser.add_argument("--test-size", type=float, default=0.2, help="For split=random: fraction in test")
    parser.add_argument("--seed", type=int, default=42, help="For split=random: stable seed")
    parser.add_argument("--top-k", type=int, default=3, help="Top-K used for hit-rate and recall")
    parser.add_argument("--cause-threshold", type=float, default=0.3, help="Pass-through to suggest_tags thresholds")
    parser.add_argument("--smell-threshold", type=float, default=0.3, help="Pass-through to suggest_tags thresholds")
    parser.add_argument(
        "--fallback-cause-keys",
        type=str,
        default=",".join(sorted(DEFAULT_FALLBACK_CAUSE_KEYS)),
        help="CSV list of cause keys treated as fallback (excluded from determinate metrics)",
    )
    parser.add_argument(
        "--fallback-smell-keys",
        type=str,
        default=",".join(sorted(DEFAULT_FALLBACK_SMELL_KEYS)),
        help="CSV list of smell keys treated as fallback (excluded from determinate metrics)",
    )
    args = parser.parse_args(list(argv))

    root = Path(__file__).resolve().parents[1]
    suggest_tags = _import_suggest_tags(root)

    taxonomy_status = _load_key_statuses(root / "taxonomy.json", list_field="categories")
    smells_status = _load_key_statuses(root / "review_smells.json", list_field="smells")

    fallback_causes = set(k for k in (args.fallback_cause_keys or "").split(",") if k.strip())
    fallback_smells = set(k for k in (args.fallback_smell_keys or "").split(",") if k.strip())

    # Treat deprecated keys as fallback by default (even if not listed explicitly).
    fallback_causes |= {k for k, st in taxonomy_status.items() if st == "deprecated"}
    fallback_smells |= {k for k, st in smells_status.items() if st == "deprecated"}

    all_cause_keys = set(taxonomy_status.keys())
    all_smell_keys = set(smells_status.keys())
    active_cause_keys = set(all_cause_keys) - set(fallback_causes)
    active_smell_keys = set(all_smell_keys) - set(fallback_smells)

    cases = suggest_tags._collect_cases(root)
    if not cases:
        print("No cases found in cases/.", file=sys.stderr)
        return 2

    explicit_test_years = _parse_csv_ints(args.test_years)

    # Precompute predictions.
    rows_causes: List[Tuple[str, Path, Set[str], List[str]]] = []
    rows_smells: List[Tuple[str, Path, Set[str], List[str]]] = []

    split_counts = Counter()
    split_det_cause = Counter()
    split_det_smell = Counter()
    split_fallback_only_cause = Counter()
    split_fallback_only_smell = Counter()

    for path, case in cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("id") if isinstance(case.get("id"), str) else path.stem
        rel = path.relative_to(root)
        year = _safe_year(case.get("pr_merged_at"))

        if args.split == "none":
            split = "all"
        elif args.split == "year":
            is_test = False
            if explicit_test_years:
                is_test = year in explicit_test_years if year is not None else False
            else:
                is_test = (year is not None and year >= args.test_from_year)
            split = "test" if is_test else "train"
        else:
            # random (stable by case_id)
            p = _stable_random_bucket(args.seed, str(case_id))
            split = "test" if p < args.test_size else "train"

        split_counts[split] += 1

        suggestion = suggest_tags._suggest_tags_with_thresholds(
            case,
            cause_threshold=args.cause_threshold,
            smell_threshold=args.smell_threshold,
            top_n_causes=max(args.top_k, 3),
            top_n_smells=max(args.top_k, 3),
        )

        pred_causes = [c[0] for c in (suggestion.suggested_causes or []) if isinstance(c, tuple) and c]
        pred_smells = [s[0] for s in (suggestion.suggested_smells or []) if isinstance(s, tuple) and s]

        true_causes = {x for x in (case.get("root_cause_categories") or []) if isinstance(x, str) and x}
        true_smells = {x for x in (case.get("review_smells") or []) if isinstance(x, str) and x}

        true_det_causes = set(true_causes) & set(active_cause_keys)
        true_det_smells = set(true_smells) & set(active_smell_keys)

        if true_det_causes:
            split_det_cause[split] += 1
        else:
            split_fallback_only_cause[split] += 1
        if true_det_smells:
            split_det_smell[split] += 1
        else:
            split_fallback_only_smell[split] += 1

        # Keep split in case_id prefix for later filtering.
        tagged_id = f"{split}:{case_id}"
        rows_causes.append((tagged_id, rel, true_causes, pred_causes))
        rows_smells.append((tagged_id, rel, true_smells, pred_smells))

    def pick_split(rows, want: str):
        if args.split == "none":
            return rows
        prefix = want + ":"
        return [r for r in rows if r[0].startswith(prefix)]

    splits_to_report = ["all"] if args.split == "none" else ["train", "test"]

    report_lines: List[str] = []
    report_lines.append("# Suggest Tags Evaluation (Baseline)")
    report_lines.append("")
    report_lines.append(f"- Generated at: {_dt.datetime.now().isoformat(timespec='seconds')}")
    head = _git_head(root)
    if head:
        report_lines.append(f"- Repo HEAD: `{head}`")
    report_lines.append("")
    report_lines.append("## Config")
    report_lines.append("")
    report_lines.append(f"- split: `{args.split}`")
    if args.split == "year":
        if explicit_test_years:
            report_lines.append(f"- test_years: `{sorted(explicit_test_years)}`")
        else:
            report_lines.append(f"- test_from_year: `{args.test_from_year}`")
    if args.split == "random":
        report_lines.append(f"- test_size: `{args.test_size}`")
        report_lines.append(f"- seed: `{args.seed}`")
    report_lines.append(f"- top_k: `{args.top_k}`")
    report_lines.append(f"- thresholds: cause `{args.cause_threshold}`, smell `{args.smell_threshold}`")
    report_lines.append(f"- fallback cause keys: `{sorted(fallback_causes)}`")
    report_lines.append(f"- fallback smell keys: `{sorted(fallback_smells)}`")
    report_lines.append("")

    report_lines.append("## Dataset")
    report_lines.append("")
    ds_rows: List[List[str]] = []
    for split in splits_to_report:
        ds_rows.append([
            split,
            str(int(split_counts.get(split, 0))),
            str(int(split_det_cause.get(split, 0))),
            str(int(split_fallback_only_cause.get(split, 0))),
            str(int(split_det_smell.get(split, 0))),
            str(int(split_fallback_only_smell.get(split, 0))),
        ])
    report_lines.extend(
        _render_md_table(
            ["split", "cases", "det_cause", "fallback_only_cause", "det_smell", "fallback_only_smell"],
            ds_rows,
        )
    )
    report_lines.append("")

    def section_for(split: str) -> None:
        report_lines.append(f"## Results ({split})")
        report_lines.append("")

        cause_rows = pick_split(rows_causes, split)
        smell_rows = pick_split(rows_smells, split)

        cause_summary, _, cause_table, cause_conf = _eval_multi_label_topk(
            rows=cause_rows,
            active_keys=active_cause_keys,
            fallback_keys=fallback_causes,
            top_k=args.top_k,
        )
        smell_summary, _, smell_table, smell_conf = _eval_multi_label_topk(
            rows=smell_rows,
            active_keys=active_smell_keys,
            fallback_keys=fallback_smells,
            top_k=args.top_k,
        )

        report_lines.append("### Summary")
        report_lines.append("")
        report_lines.extend(
            _render_md_table(
                ["task", "det_cases", "top1_hit", "top1_%", f"top{args.top_k}_hit", f"top{args.top_k}_%", "top1_fallback_%"],
                [
                    [
                        "root_cause",
                        str(cause_summary.total),
                        str(cause_summary.top1_hit),
                        f"{cause_summary.top1_pct():.2f}",
                        str(cause_summary.top3_hit),
                        f"{cause_summary.top3_pct():.2f}",
                        f"{cause_summary.fallback_top1_pct():.2f}",
                    ],
                    [
                        "review_smells",
                        str(smell_summary.total),
                        str(smell_summary.top1_hit),
                        f"{smell_summary.top1_pct():.2f}",
                        str(smell_summary.top3_hit),
                        f"{smell_summary.top3_pct():.2f}",
                        f"{smell_summary.fallback_top1_pct():.2f}",
                    ],
                ],
            )
        )
        report_lines.append("")

        report_lines.append("### Root Causes (per-label)")
        report_lines.append("")
        report_lines.extend(
            _render_md_table(
                ["key", "support", "top1_precision_%", "top1_recall_%", f"top{args.top_k}_recall_%"],
                [
                    [k, str(sup), f"{prec:.2f}", f"{r1:.2f}", f"{rk:.2f}"]
                    for (k, sup, prec, r1, rk) in cause_table[:30]
                ],
            )
        )
        report_lines.append("")

        report_lines.append("### Review Smells (per-label)")
        report_lines.append("")
        report_lines.extend(
            _render_md_table(
                ["key", "support", "top1_precision_%", "top1_recall_%", f"top{args.top_k}_recall_%"],
                [
                    [k, str(sup), f"{prec:.2f}", f"{r1:.2f}", f"{rk:.2f}"]
                    for (k, sup, prec, r1, rk) in smell_table[:30]
                ],
            )
        )
        report_lines.append("")

        report_lines.append("### Common Misses (top-1 confusion samples)")
        report_lines.append("")
        report_lines.append("- Root causes (when top1 prediction is not in truth):")
        for (true_k, pred_k), cnt, samples in cause_conf[:10]:
            report_lines.append(f"  - `{true_k}` → `{pred_k}`: {cnt} (e.g. {', '.join(samples[:3])})")
        report_lines.append("- Smells (when top1 prediction is not in truth):")
        for (true_k, pred_k), cnt, samples in smell_conf[:10]:
            report_lines.append(f"  - `{true_k}` → `{pred_k}`: {cnt} (e.g. {', '.join(samples[:3])})")
        report_lines.append("")

    for split in splits_to_report:
        section_for(split)

    out_path: Path = (root / args.output).resolve() if not args.output.is_absolute() else args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Wrote report: {out_path}")

    # Also print a tiny console summary for quick iteration.
    if args.split != "none":
        print(f"Splits: train={split_counts.get('train', 0)}, test={split_counts.get('test', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
