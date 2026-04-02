#!/usr/bin/env python3
"""
Tag suggestion script for TiDB Flaky Test Catalog - Milestone 2.

Analyzes all cases and suggests root_cause_categories and review_smells
based on keywords, patterns, and heuristics.

Usage:
    ./.venv/bin/python3 scripts/suggest_tags.py
    ./.venv/bin/python3 scripts/suggest_tags.py --output reports/tag_suggestions.json
    ./.venv/bin/python3 scripts/suggest_tags.py --apply  # Apply suggestions to cases
    ./.venv/bin/python3 scripts/suggest_tags.py --apply-all  # Force-tag every case (no unclassified)
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


FALLBACK_CAUSE = "insufficient_evidence"
FALLBACK_SMELL = "needs_more_evidence"


@dataclass
class Suggestion:
    case_id: str
    case_path: Path
    suggested_causes: List[Tuple[str, float, str]]  # (key, confidence, reason)
    suggested_smells: List[Tuple[str, float, str]]  # (key, confidence, reason)


# Keyword patterns for classification
PATTERNS = {
    # Root cause patterns
    "nondeterministic_result_order": {
        "keywords": [
            "order", "sort", "ordering", "nondeterministic", "order by",
            "rows order", "check", "mustquery", "sort().check",
            "map ranging", "stabilize map",
        ],
        "title_patterns": ["sort", "order", "ordering"],
        "path_patterns": [],
        "fix_patterns": ["sort", "order by", "ordering", "map ranging"],
    },
    "concurrency_data_race": {
        "keywords": [
            "race", "data race", "race detected", "concurrency", "parallel",
            "goroutine", "sync", "mutex", "atomic", "concurrent",
        ],
        "title_patterns": ["race", "data race", "concurrent"],
        "path_patterns": [],
        "fix_patterns": ["race", "parallel", "concurrent", "sync"],
    },
    "nondeterministic_plan_selection": {
        "keywords": [
            "plan", "planner", "explain", "cost", "statistics", "stats",
            "plan cache", "plan_id", "execution plan",
        ],
        "title_patterns": ["plan", "planner"],
        "path_patterns": ["planner/"],
        "fix_patterns": ["plan", "planner"],
    },
    "schema_change_race": {
        "keywords": [
            "ddl", "schema", "partition", "table create", "alter table",
            "schema version", "information schema",
        ],
        "title_patterns": ["ddl", "schema", "partition"],
        "path_patterns": ["ddl/"],
        "fix_patterns": ["ddl", "schema"],
    },
    "test_infra_migration": {
        "keywords": [
            "testify", "migration", "migrate", "test infra", "testinfra",
            "test suite", "serialsuite", "parallelsuite",
            "vendor", "dependencies", "dependency", "go.mod", "godeps",
        ],
        "title_patterns": ["migrate", "testify", "test-infra"],
        "path_patterns": [],
        "fix_patterns": ["migrate", "testify", "vendor", "dependenc", "go.mod"],
    },
    "async_timing_issue": {
        "keywords": [
            "timeout", "sleep", "wait", "async", "timing", "time.",
            "deadline", "context deadline", "eventual", "consistent",
        ],
        "title_patterns": ["timeout", "async", "wait", "timing"],
        "path_patterns": [],
        "fix_patterns": ["timeout", "sleep", "wait", "async"],
    },
    "external_dependency": {
        "keywords": [
            "realtikv", "tikv", "pd", "network", "cluster", "external",
            "environment", "env", "unstable test",
        ],
        "title_patterns": ["realtikv", "tikv", "cluster"],
        "path_patterns": ["realtikvtest/"],
        "fix_patterns": ["tikv", "cluster", "network"],
    },
    "shared_state_pollution": {
        "keywords": [
            "global", "shared", "state", "cleanup", "pollution", "isolation",
            "reset", "restore", "tear down",
        ],
        "title_patterns": ["global", "shared", "cleanup"],
        "path_patterns": [],
        "fix_patterns": ["global", "cleanup", "reset", "restore"],
    },
}

# Smell patterns mapping
SMELL_PATTERNS = {
    "needs_more_evidence": {
        "causes": [FALLBACK_CAUSE],
        "keywords": [],
        "context": [],
    },
    "missing_order_by": {
        "causes": ["nondeterministic_result_order"],
        "keywords": ["order by", "ordering", "sort"],
        "context": ["mustquery", "check", "select"],
    },
    "relying_on_map_iteration_order": {
        "causes": ["nondeterministic_result_order"],
        "keywords": ["map", "iteration", "range"],
        "context": ["order", "sort"],
    },
    "unsorted_result_assertion": {
        "causes": ["nondeterministic_result_order"],
        "keywords": ["check", "mustquery", "rows"],
        "context": ["without sort", "no sort"],
    },
    "t_parallel_with_shared_state": {
        "causes": ["concurrency_data_race", "shared_state_pollution"],
        "keywords": ["parallel", "t.parallel", "shared"],
        "context": ["race", "concurrent"],
    },
    "global_variable_mutation": {
        "causes": ["shared_state_pollution", "concurrency_data_race"],
        "keywords": ["global", "variable", "mutation"],
        "context": ["set", "modify", "change"],
    },
    "insufficient_cleanup_between_tests": {
        "causes": ["shared_state_pollution"],
        "keywords": ["cleanup", "teardown", "defer"],
        "context": ["table", "resource", "state"],
    },
    "race_condition_in_async_code": {
        "causes": ["concurrency_data_race"],
        "keywords": ["race", "goroutine", "async", "concurrent"],
        "context": ["data race", "race detected"],
    },
    "assert_exact_plan_or_cost": {
        "causes": ["nondeterministic_plan_selection"],
        "keywords": ["plan", "cost", "explain"],
        "context": ["assert", "check", "equal"],
    },
    "plan_cache_dependency": {
        "causes": ["nondeterministic_plan_selection"],
        "keywords": ["plan cache", "cache"],
        "context": ["plan", "query"],
    },
    "statistics_sensitive_test": {
        "causes": ["nondeterministic_plan_selection"],
        "keywords": ["statistics", "stats", "analyze"],
        "context": ["plan", "cost"],
    },
    "ddl_without_wait": {
        "causes": ["schema_change_race"],
        "keywords": ["ddl", "create table", "alter"],
        "context": ["wait", "sync", "async"],
    },
    "schema_version_race": {
        "causes": ["schema_change_race"],
        "keywords": ["schema version", "information schema"],
        "context": ["race", "sync", "version"],
    },
    "async_schema_propagation": {
        "causes": ["schema_change_race"],
        "keywords": ["schema", "propagation", "ddl"],
        "context": ["async", "cluster", "distributed"],
    },
    "incomplete_testify_migration": {
        "causes": ["test_infra_migration"],
        "keywords": ["testify", "migration", "migrate"],
        "context": ["incomplete", "partial"],
    },
    "test_suite_setup_issue": {
        "causes": ["test_infra_migration"],
        "keywords": ["suite", "setup", "fixture"],
        "context": ["test", "infra"],
    },
    "deprecated_test_framework_usage": {
        "causes": ["test_infra_migration"],
        "keywords": ["deprecated", "check.C", "gocheck"],
        "context": ["old", "legacy"],
    },
    "time_sleep_for_sync": {
        "causes": ["async_timing_issue"],
        "keywords": ["sleep", "time.sleep"],
        "context": ["sync", "wait", "async"],
    },
    "insufficient_timeout": {
        "causes": ["async_timing_issue"],
        "keywords": ["timeout", "deadline", "context"],
        "context": ["short", "insufficient"],
    },
    "async_wait_without_backoff": {
        "causes": ["async_timing_issue"],
        "keywords": ["wait", "poll", "retry"],
        "context": ["backoff", "loop"],
    },
    "clock_skew_dependency": {
        "causes": ["async_timing_issue"],
        "keywords": ["clock", "time", "now", "timestamp"],
        "context": ["skew", "compare", "diff"],
    },
    "real_tikv_dependency": {
        "causes": ["external_dependency"],
        "keywords": ["realtikv", "tikv", "cluster"],
        "context": ["external", "dependency"],
    },
    "network_without_retry": {
        "causes": ["external_dependency"],
        "keywords": ["network", "connection", "rpc"],
        "context": ["retry", "fail", "error"],
    },
    "hardcoded_port_or_resource": {
        "causes": ["external_dependency"],
        "keywords": ["port", "address", "resource"],
        "context": ["hardcoded", "fixed"],
    },
    "shared_table_without_isolation": {
        "causes": ["shared_state_pollution"],
        "keywords": ["table", "shared", "same table"],
        "context": ["isolation", "cleanup"],
    },
}


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _collect_cases(root: Path) -> List[Tuple[Path, Dict[str, Any]]]:
    """Load all case files from cases/ directory."""
    cases_dir = root / "cases"
    cases = []
    for path in sorted(cases_dir.rglob("*.json")):
        if path.is_file():
            try:
                cases.append((path, _read_json(path)))
            except Exception as e:
                print(f"Warning: failed to read {path}: {e}", file=sys.stderr)
    return cases


def _match_keywords(text: str, keywords: List[str]) -> Tuple[bool, List[str]]:
    """Check if any keywords appear in text. Returns (matched, matched_keywords)."""
    if not text:
        return False, []
    text_lower = text.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in text_lower:
            matched.append(kw)
    return len(matched) > 0, matched


def _score_cause(
    cause_key: str,
    case: Dict[str, Any],
    symptoms_text: str,
    fix_text: str,
    title_text: str,
    path_text: str,
) -> Tuple[float, str]:
    """Score a potential root cause match. Returns (confidence, reason)."""
    patterns = PATTERNS.get(cause_key, {})
    score = 0.0
    reasons = []
    
    # Check symptoms
    matched, kws = _match_keywords(symptoms_text, patterns.get("keywords", []))
    if matched:
        score += 0.4
        reasons.append(f"symptoms keywords: {kws[:3]}")
    
    # Check fix_pattern
    matched, kws = _match_keywords(fix_text, patterns.get("fix_patterns", []))
    if matched:
        score += 0.3
        reasons.append(f"fix_pattern keywords: {kws[:2]}")
    
    # Check title
    matched, kws = _match_keywords(title_text, patterns.get("title_patterns", []))
    if matched:
        score += 0.2
        reasons.append(f"title keywords: {kws[:2]}")
    
    # Check path
    matched, kws = _match_keywords(path_text, patterns.get("path_patterns", []))
    if matched:
        score += 0.1
        reasons.append(f"path match: {kws[:1]}")
    
    return min(score, 1.0), "; ".join(reasons) if reasons else "no match"


def _score_smell(
    smell_key: str,
    case: Dict[str, Any],
    symptoms_text: str,
    fix_text: str,
    title_text: str,
    suggested_causes: List[str],
) -> Tuple[float, str]:
    """Score a potential smell match. Returns (confidence, reason)."""
    patterns = SMELL_PATTERNS.get(smell_key, {})
    score = 0.0
    reasons = []
    
    # Check if related causes are suggested
    related_causes = set(patterns.get("causes", []))
    matched_causes = related_causes & set(suggested_causes)
    if matched_causes:
        score += 0.3
        reasons.append(f"related causes: {list(matched_causes)[:2]}")
    
    # Check keywords
    matched, kws = _match_keywords(symptoms_text, patterns.get("keywords", []))
    if matched:
        score += 0.4
        reasons.append(f"keywords: {kws[:2]}")
    
    matched, kws = _match_keywords(fix_text, patterns.get("keywords", []))
    if matched:
        score += 0.2
        reasons.append(f"fix keywords: {kws[:2]}")
    
    # Check context
    context_text = f"{symptoms_text} {fix_text} {title_text}"
    matched, kws = _match_keywords(context_text, patterns.get("context", []))
    if matched:
        score += 0.1
        reasons.append(f"context: {kws[:1]}")
    
    return min(score, 1.0), "; ".join(reasons) if reasons else "no match"


def _suggest_tags(case: Dict[str, Any]) -> Suggestion:
    """Generate tag suggestions for a case."""
    return _suggest_tags_with_thresholds(case, cause_threshold=0.3, smell_threshold=0.3, top_n_causes=3, top_n_smells=3)


def _suggest_tags_with_thresholds(
    case: Dict[str, Any],
    *,
    cause_threshold: float,
    smell_threshold: float,
    top_n_causes: int,
    top_n_smells: int,
) -> Suggestion:
    """Generate tag suggestions for a case with configurable thresholds.

    - With the default thresholds (0.3/0.3), this is a *conservative* suggester.
    - With thresholds (0.0/0.0), it becomes a *forcing* classifier (useful for 100% coverage).
    """
    case_id = case.get("id", "unknown")
    
    # Extract text fields
    symptoms = case.get("symptoms", [])
    symptoms_text = " ".join(str(s) for s in symptoms) if symptoms else ""
    
    fix_pattern = case.get("fix_pattern", "")
    fix_text = str(fix_pattern) if fix_pattern else ""
    
    pr = case.get("source_pr", {})
    title_text = pr.get("title", "") if isinstance(pr, dict) else ""
    
    test = case.get("test", {})
    path_text = test.get("path", "") if isinstance(test, dict) else ""
    
    # Score each cause
    min_cause_score = cause_threshold if cause_threshold > 0 else 1e-9
    cause_scores = []
    for cause_key in PATTERNS.keys():
        score, reason = _score_cause(
            cause_key, case, symptoms_text, fix_text, title_text, path_text
        )
        if score >= min_cause_score:  # Threshold for suggestion (exclude 0.0 score in forcing mode)
            cause_scores.append((cause_key, score, reason))
    
    # Sort by confidence
    cause_scores.sort(key=lambda x: x[1], reverse=True)

    # If no causes matched, use a semantic fallback (instead of guessing).
    if not cause_scores:
        cause_scores = [(FALLBACK_CAUSE, 1.0, "no strong pattern match")]

    # For fallback cases, keep smells consistent with the fallback as well.
    # Otherwise generic keywords (e.g. "table") may produce misleading smell stats.
    if cause_scores[0][0] == FALLBACK_CAUSE:
        return Suggestion(
            case_id=case_id,
            case_path=Path("unknown"),
            suggested_causes=cause_scores[: max(1, top_n_causes)],
            suggested_smells=[(FALLBACK_SMELL, 1.0, "insufficient evidence")],
        )
    
    # Get top causes for smell scoring
    top_causes = [c[0] for c in cause_scores[:3]]
    
    # Score each smell
    min_smell_score = smell_threshold if smell_threshold > 0 else 1e-9
    smell_scores = []
    for smell_key in SMELL_PATTERNS.keys():
        score, reason = _score_smell(
            smell_key, case, symptoms_text, fix_text, title_text, top_causes
        )
        if score >= min_smell_score:  # Threshold for suggestion (exclude 0.0 score in forcing mode)
            smell_scores.append((smell_key, score, reason))
    
    # Sort by confidence
    smell_scores.sort(key=lambda x: x[1], reverse=True)
    
    # If no smells matched but we have causes, infer smells
    if not smell_scores and cause_scores[0][0] not in ("unclassified", FALLBACK_CAUSE):
        # Find smells related to top cause
        top_cause = cause_scores[0][0]
        for smell_key, patterns in SMELL_PATTERNS.items():
            if top_cause in patterns.get("causes", []):
                smell_scores.append((smell_key, 0.5, f"inferred from {top_cause}"))
                if len(smell_scores) >= 2:
                    break
    
    if not smell_scores:
        smell_scores = [(FALLBACK_SMELL, 1.0, "no strong pattern match")]

    return Suggestion(
        case_id=case_id,
        case_path=Path("unknown"),
        suggested_causes=cause_scores[: max(1, top_n_causes)],
        suggested_smells=smell_scores[: max(1, top_n_smells)],
    )


def _generate_report(suggestions: List[Suggestion]) -> Dict[str, Any]:
    """Generate summary report."""
    total = len(suggestions)
    
    cause_counts: Dict[str, int] = {}
    smell_counts: Dict[str, int] = {}
    unclassified_causes = 0
    unclassified_smells = 0
    
    for s in suggestions:
        # Count top suggestion per case
        if s.suggested_causes:
            top_cause = s.suggested_causes[0][0]
            cause_counts[top_cause] = cause_counts.get(top_cause, 0) + 1
            if top_cause == "unclassified":
                unclassified_causes += 1
        
        if s.suggested_smells:
            top_smell = s.suggested_smells[0][0]
            smell_counts[top_smell] = smell_counts.get(top_smell, 0) + 1
            if top_smell == "unclassified":
                unclassified_smells += 1
    
    return {
        "total_cases": total,
        "coverage": {
            "classified_causes": total - unclassified_causes,
            "classified_causes_pct": round((total - unclassified_causes) / total * 100, 1),
            "classified_smells": total - unclassified_smells,
            "classified_smells_pct": round((total - unclassified_smells) / total * 100, 1),
        },
        "cause_distribution": dict(sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)),
        "smell_distribution": dict(sorted(smell_counts.items(), key=lambda x: x[1], reverse=True)),
    }


def _apply_suggestions(
    cases: List[Tuple[Path, Dict[str, Any]]],
    suggestions: List[Suggestion],
    *,
    min_confidence: float,
    force_all: bool,
) -> None:
    """Apply suggestions to case files."""
    suggestion_map = {s.case_id: s for s in suggestions}
    
    for path, case in cases:
        case_id = case.get("id")
        if case_id not in suggestion_map:
            continue
        
        s = suggestion_map[case_id]
        
        if force_all:
            # Force-tag: always pick at least one non-unclassified root cause.
            top_cause = s.suggested_causes[0][0]
            causes = [c[0] for c in s.suggested_causes if c[1] >= 0.6]
            if not causes:
                causes = [top_cause]
            # Guard: never write unclassified in force mode.
            causes = [c for c in causes if c != "unclassified"] or [top_cause]
            case["root_cause_categories"] = causes[:2]
        else:
            # Conservative: only apply high-confidence non-unclassified tags.
            if s.suggested_causes and s.suggested_causes[0][0] != "unclassified":
                causes = [c[0] for c in s.suggested_causes if c[1] >= min_confidence]
                if causes:
                    case["root_cause_categories"] = causes
        
        if force_all:
            # Force-tag: pick smells related to the chosen root cause first.
            chosen_cause = case["root_cause_categories"][0]
            if chosen_cause == FALLBACK_CAUSE:
                # For semantic fallback cases, keep smells consistent with the fallback,
                # instead of matching generic keywords (e.g. "table") that can be noisy.
                case["review_smells"] = [FALLBACK_SMELL]
                _write_json(path, case)
                continue
            related = []
            for key, conf, _reason in s.suggested_smells:
                if chosen_cause in (SMELL_PATTERNS.get(key, {}).get("causes") or []):
                    related.append((key, conf))
            if related:
                # Prefer high confidence; fall back to top related.
                smells = [k for k, conf in related if conf >= 0.6] or [related[0][0]]
            else:
                smells = [s.suggested_smells[0][0]]
            smells = [k for k in smells if k != "unclassified"] or [s.suggested_smells[0][0]]
            case["review_smells"] = smells[:2]
        else:
            # Conservative: only apply high-confidence non-unclassified smells.
            if s.suggested_smells and s.suggested_smells[0][0] != "unclassified":
                smells = [m[0] for m in s.suggested_smells if m[1] >= min_confidence]
                if smells:
                    case["review_smells"] = smells
        
        # Write back
        _write_json(path, case)


def _main() -> int:
    parser = argparse.ArgumentParser(description="Suggest tags for flaky test cases")
    parser.add_argument("--output", "-o", type=str, help="Output JSON file for suggestions")
    parser.add_argument("--apply", "-a", action="store_true", help="Apply suggestions to case files")
    parser.add_argument(
        "--apply-all",
        action="store_true",
        help=(
            "Force-tag every case (no unclassified) using conservative thresholds and "
            "semantic fallbacks (e.g. insufficient_evidence / needs_more_evidence)."
        ),
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.5,
        help="Min confidence for --apply (default 0.5). Ignored by --apply-all.",
    )
    args = parser.parse_args()
    
    root = Path(__file__).resolve().parents[1]
    
    # Load all cases
    cases = _collect_cases(root)
    if not cases:
        print("No cases found.", file=sys.stderr)
        return 1
    
    print(f"Analyzing {len(cases)} cases...")
    
    # Generate suggestions
    suggestions = []
    # Keep conservative thresholds even in --apply-all and rely on semantic
    # fallback tags (insufficient_evidence / needs_more_evidence) for 100%
    # coverage without hard-guessing.
    cause_threshold = 0.3
    smell_threshold = 0.3
    top_n_smells = 10 if args.apply_all else 3
    for path, case in cases:
        s = _suggest_tags_with_thresholds(
            case,
            cause_threshold=cause_threshold,
            smell_threshold=smell_threshold,
            top_n_causes=3,
            top_n_smells=top_n_smells,
        )
        s.case_path = path
        suggestions.append(s)
    
    # Generate report
    report = _generate_report(suggestions)
    
    print(f"\nCoverage Report:")
    print(f"  Total cases: {report['total_cases']}")
    print(f"  Classified causes: {report['coverage']['classified_causes']} ({report['coverage']['classified_causes_pct']}%)")
    print(f"  Classified smells: {report['coverage']['classified_smells']} ({report['coverage']['classified_smells_pct']}%)")
    
    print(f"\nTop Root Cause Categories:")
    for cause, count in list(report['cause_distribution'].items())[:8]:
        pct = count / report['total_cases'] * 100
        print(f"  {cause}: {count} ({pct:.1f}%)")
    
    print(f"\nTop Review Smells:")
    for smell, count in list(report['smell_distribution'].items())[:8]:
        pct = count / report['total_cases'] * 100
        print(f"  {smell}: {count} ({pct:.1f}%)")
    
    # Output detailed suggestions if requested
    if args.output:
        output_data = {
            "report": report,
            "suggestions": [
                {
                    "case_id": s.case_id,
                    "case_path": str(s.case_path.relative_to(root)),
                    "suggested_causes": [
                        {"key": c[0], "confidence": round(c[1], 2), "reason": c[2]}
                        for c in s.suggested_causes
                    ],
                    "suggested_smells": [
                        {"key": m[0], "confidence": round(m[1], 2), "reason": m[2]}
                        for m in s.suggested_smells
                    ],
                }
                for s in suggestions
            ],
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(output_path, output_data)
        print(f"\nDetailed suggestions written to: {args.output}")
    
    # Apply suggestions if requested
    if args.apply or args.apply_all:
        print("\nApplying suggestions to case files...")
        _apply_suggestions(cases, suggestions, min_confidence=args.min_confidence, force_all=args.apply_all)
        print("Done.")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
