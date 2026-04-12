#!/usr/bin/env python3
"""
Generate Review Checklist markdown from review_smells.json
"""

import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    smells = json.load(open(root / "review_smells.json"))["smells"]

    lines = [
        "# TiDB Flaky Test Review Checklist v0.1",
        "",
        "This checklist helps reviewers identify potential flaky test patterns during code review.",
        "Each item includes: what to look for → why it is risky → what questions to ask → how to fix.",
        "",
        "## Quick Reference by Category",
        "",
    ]

    # Group by related root cause
    cause_groups = {}
    for smell in smells:
        if smell.get("status") == "deprecated" or smell["key"] == "unclassified":
            continue
        for cause in smell.get("related_root_causes", []):
            if cause not in cause_groups:
                cause_groups[cause] = []
            cause_groups[cause].append(smell)

    for cause, smell_list in sorted(cause_groups.items()):
        lines.append(f"### {cause}")
        for s in smell_list:
            lines.append(f'- [ ] **{s["title"]}** (`{s["key"]}`)')
        lines.append("")

    lines.extend([
        "## Detailed Checklist",
        "",
    ])

    for smell in smells:
        if smell.get("status") == "deprecated" or smell["key"] == "unclassified":
            continue

        lines.extend([
            f"### {smell['title']}",
            "",
            f"**Key:** `{smell['key']}`",
            "",
        ])
        
        related = smell.get("related_root_causes", [])
        lines.append(f"**Related Root Causes:** {', '.join(related)}")
        lines.extend([
            "",
            f"**Description:** {smell['description']}",
            "",
            f"**Why Risky:** {smell['why_risky']}",
            "",
            "**Review Questions:**",
        ])

        for q in smell["review_questions"]:
            lines.append(f"- {q}")

        lines.append("")
        lines.append("**Suggested Fixes:**")

        for fix in smell["suggested_fixes"]:
            lines.append(f"- {fix}")

        lines.append("")

    output_path = root / "docs" / "review_checklist.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"Checklist generated: {output_path}")


if __name__ == "__main__":
    main()
