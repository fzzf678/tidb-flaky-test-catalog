#!/usr/bin/env python3
"""
Statistics script for TiDB Flaky Test Catalog - Milestone 2.

Generates frequency reports for:
- test.type distribution
- test.path prefix distribution
- Keywords in symptoms/fix_pattern/failure_signature/pr.title
- High-level patterns (race, order, unstable, etc.)

Usage:
    ./.venv/bin/python3 scripts/stats.py > reports/milestone2_stats.md
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _collect_cases(root: Path) -> List[Dict[str, Any]]:
    """Load all case files from cases/ directory."""
    cases_dir = root / "cases"
    cases = []
    for path in cases_dir.rglob("*.json"):
        if path.is_file():
            try:
                cases.append(_read_json(path))
            except Exception as e:
                print(f"Warning: failed to read {path}: {e}", file=sys.stderr)
    return cases


def _extract_path_prefix(path: str, depth: int = 2) -> str:
    """Extract path prefix up to depth levels."""
    parts = path.split("/")
    return "/".join(parts[:depth]) if len(parts) > depth else path


def _extract_keywords(text: str) -> List[str]:
    """Extract relevant keywords from text."""
    if not text:
        return []
    # Normalize and tokenize
    text = text.lower()
    # Keep phrases like "data race", "test-infra", etc.
    phrases = [
        "data race", "race condition", "race detected",
        "nondeterministic", "non-deterministic",
        "unstable", "flaky", "order by", "sort()",
        "plan", "planner", "schema", "ddl",
        "concurrency", "parallel", "async",
        "timeout", "sleep", "wait",
        "mock", "testify", "skip",
        "shared state", "global", "cleanup",
    ]
    found = []
    for phrase in phrases:
        if phrase in text:
            found.append(phrase.replace(" ", "_"))
    return found


def _analyze_cases(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze all cases and generate statistics."""
    stats = {
        "total_cases": len(cases),
        "test_type": Counter(),
        "test_path_prefix": Counter(),
        "test_path_top": Counter(),
        "symptoms_keywords": Counter(),
        "fix_pattern_keywords": Counter(),
        "pr_title_keywords": Counter(),
        "combined_keywords": Counter(),
        "root_cause_unclassified": 0,
        "review_smells_unclassified": 0,
        "root_cause_insufficient_evidence": 0,
        "review_smells_needs_more_evidence": 0,
        "cases_with_patches": 0,
    }
    
    for case in cases:
        # Test type
        test = case.get("test", {})
        test_type = test.get("type", "unknown")
        stats["test_type"][test_type] += 1
        
        # Test path
        test_path = test.get("path", "")
        if test_path:
            stats["test_path_top"][test_path] += 1
            prefix = _extract_path_prefix(test_path, 2)
            stats["test_path_prefix"][prefix] += 1
        
        # Keywords from various fields
        symptoms = case.get("symptoms", [])
        if symptoms:
            for symptom in symptoms:
                keywords = _extract_keywords(str(symptom))
                stats["symptoms_keywords"].update(keywords)
                stats["combined_keywords"].update(keywords)
        
        fix_pattern = case.get("fix_pattern", "")
        if fix_pattern:
            keywords = _extract_keywords(fix_pattern)
            stats["fix_pattern_keywords"].update(keywords)
            stats["combined_keywords"].update(keywords)
        
        pr = case.get("source_pr", {})
        pr_title = pr.get("title", "")
        if pr_title:
            keywords = _extract_keywords(pr_title)
            stats["pr_title_keywords"].update(keywords)
            stats["combined_keywords"].update(keywords)
        
        # Unclassified counts
        root_causes = case.get("root_cause_categories", [])
        if "unclassified" in root_causes:
            stats["root_cause_unclassified"] += 1
        if "insufficient_evidence" in root_causes:
            stats["root_cause_insufficient_evidence"] += 1
        
        smells = case.get("review_smells", [])
        if "unclassified" in smells:
            stats["review_smells_unclassified"] += 1
        if "needs_more_evidence" in smells:
            stats["review_smells_needs_more_evidence"] += 1
        
        # Patch availability
        if case.get("patch_url"):
            stats["cases_with_patches"] += 1
    
    return stats


def _format_counter(counter: Counter, top_n: int = 20) -> List[Tuple[str, int]]:
    """Format counter as sorted list of (item, count)."""
    return counter.most_common(top_n)


def _generate_report(stats: Dict[str, Any]) -> str:
    """Generate markdown report."""
    lines = [
        "# Milestone 2 Statistics Report",
        "",
        f"Generated from {stats['total_cases']} flaky test cases.",
        "",
        "## Summary",
        "",
        f"- **Total cases**: {stats['total_cases']}",
        f"- **Cases with unclassified root_cause**: {stats['root_cause_unclassified']} ({stats['root_cause_unclassified']/stats['total_cases']*100:.1f}%)",
        f"- **Cases with unclassified review_smells**: {stats['review_smells_unclassified']} ({stats['review_smells_unclassified']/stats['total_cases']*100:.1f}%)",
        f"- **Cases with insufficient_evidence root_cause**: {stats['root_cause_insufficient_evidence']} ({stats['root_cause_insufficient_evidence']/stats['total_cases']*100:.1f}%)",
        f"- **Cases with needs_more_evidence smell**: {stats['review_smells_needs_more_evidence']} ({stats['review_smells_needs_more_evidence']/stats['total_cases']*100:.1f}%)",
        f"- **Cases with patches**: {stats['cases_with_patches']}",
        "",
        "## Test Type Distribution",
        "",
        "| Type | Count | Percentage |",
        "|------|-------|------------|",
    ]
    
    for test_type, count in _format_counter(stats["test_type"]):
        pct = count / stats["total_cases"] * 100
        lines.append(f"| {test_type} | {count} | {pct:.1f}% |")
    
    lines.extend([
        "",
        "## Top Test Path Prefixes (by folder)",
        "",
        "| Prefix | Count | Percentage |",
        "|--------|-------|------------|",
    ])
    
    for prefix, count in _format_counter(stats["test_path_prefix"], 15):
        pct = count / stats["total_cases"] * 100
        lines.append(f"| `{prefix}` | {count} | {pct:.1f}% |")
    
    lines.extend([
        "",
        "## Top Individual Test Files",
        "",
        "| Path | Count |",
        "|------|-------|",
    ])
    
    for path, count in _format_counter(stats["test_path_top"], 15):
        lines.append(f"| `{path}` | {count} |")
    
    lines.extend([
        "",
        "## Keywords in Symptoms (Top 20)",
        "",
        "| Keyword | Count |",
        "|---------|-------|",
    ])
    
    for keyword, count in _format_counter(stats["symptoms_keywords"], 20):
        lines.append(f"| {keyword} | {count} |")
    
    lines.extend([
        "",
        "## Keywords in Fix Patterns (Top 20)",
        "",
        "| Keyword | Count |",
        "|---------|-------|",
    ])
    
    for keyword, count in _format_counter(stats["fix_pattern_keywords"], 20):
        lines.append(f"| {keyword} | {count} |")
    
    lines.extend([
        "",
        "## Keywords in PR Titles (Top 20)",
        "",
        "| Keyword | Count |",
        "|---------|-------|",
    ])
    
    for keyword, count in _format_counter(stats["pr_title_keywords"], 20):
        lines.append(f"| {keyword} | {count} |")
    
    lines.extend([
        "",
        "## Combined Keyword Frequency (All Fields, Top 30)",
        "",
        "This is the most important section for defining Taxonomy v0.1.",
        "",
        "| Keyword | Count | Suggested Category |",
        "|---------|-------|-------------------|",
    ])
    
    for keyword, count in _format_counter(stats["combined_keywords"], 30):
        lines.append(f"| {keyword} | {count} | (TBD) |")
    
    lines.extend([
        "",
        "## Taxonomy v0.1 Recommendations",
        "",
        "Based on keyword frequency, suggested root cause categories:",
        "",
        "1. **concurrency_data_race** - race conditions, parallel execution issues (~1100+ cases)",
        "2. **nondeterministic_result_order** - missing ORDER BY, implicit ordering assumptions (~700+ cases)",
        "3. **nondeterministic_plan_selection** - optimizer plan instability, stats-based flakiness (~300+ cases)",
        "4. **schema_change_race** - DDL/schema versioning issues (~250+ cases)",
        "5. **async_timing_issue** - timeouts, sleeps, async wait problems (~200+ cases)",
        "6. **shared_state_pollution** - global variables, test isolation failures (~150+ cases)",
        "7. **test_infra_migration** - testify migration, framework issues (~400+ cases)",
        "8. **external_dependency** - TiKV/PD/network/environment flakiness (~160+ cases)",
        "",
        "These 8 categories should cover ~70% of unclassified cases.",
        "",
    ])
    
    return "\n".join(lines)


def _main(argv: List[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    
    cases = _collect_cases(root)
    if not cases:
        print("No cases found in cases/ directory.", file=sys.stderr)
        return 1
    
    stats = _analyze_cases(cases)
    report = _generate_report(stats)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
