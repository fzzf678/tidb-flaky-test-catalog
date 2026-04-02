#!/usr/bin/env python3

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


try:
    from jsonschema import Draft202012Validator, FormatChecker
except ModuleNotFoundError:
    print(
        "Missing dependency: jsonschema\n\n"
        "Install with:\n"
        "  python -m pip install -r requirements.txt\n",
        file=sys.stderr,
    )
    sys.exit(2)


RE_CASE_ID = re.compile(r"^pr-(?P<pr>[0-9]+)(-(?P<idx>[0-9]+))?$")
RE_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass
class Finding:
    path: Path
    message: str


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_schema(root: Path, name: str) -> Dict[str, Any]:
    return _read_json(root / "schemas" / name)


def _schema_validate(
    *,
    instance: Any,
    schema: Dict[str, Any],
    path: Path,
) -> List[Finding]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    findings: List[Finding] = []
    for error in sorted(validator.iter_errors(instance), key=str):
        loc = "".join(f"[{p!r}]" for p in error.absolute_path)
        if loc:
            findings.append(Finding(path=path, message=f"{loc}: {error.message}"))
        else:
            findings.append(Finding(path=path, message=error.message))
    return findings


def _unique(items: Sequence[str]) -> Tuple[bool, List[str]]:
    seen: Set[str] = set()
    dups: List[str] = []
    for item in items:
        if item in seen:
            dups.append(item)
        else:
            seen.add(item)
    return (len(dups) == 0, dups)


def _index_keys(items: Iterable[Dict[str, Any]], *, path: Path, kind: str) -> Tuple[Set[str], List[Finding]]:
    keys: List[str] = []
    findings: List[Finding] = []
    for i, item in enumerate(items):
        key = item.get("key")
        if not isinstance(key, str) or not key:
            findings.append(Finding(path=path, message=f"[{kind}][{i}].key must be a non-empty string"))
            continue
        if not RE_KEY.match(key):
            findings.append(Finding(path=path, message=f"[{kind}][{i}].key {key!r} must match {RE_KEY.pattern!r}"))
            continue
        keys.append(key)

    ok, dups = _unique(keys)
    if not ok:
        for dup in sorted(set(dups)):
            findings.append(Finding(path=path, message=f"duplicate {kind}.key: {dup!r}"))
    return set(keys), findings


def _check_replaced_by(
    *,
    items: Iterable[Dict[str, Any]],
    all_keys: Set[str],
    path: Path,
    kind: str,
) -> List[Finding]:
    findings: List[Finding] = []
    for i, item in enumerate(items):
        key = item.get("key")
        replaced_by = item.get("replaced_by")
        if replaced_by is None:
            continue
        if not isinstance(replaced_by, str) or not replaced_by:
            findings.append(Finding(path=path, message=f"[{kind}][{i}].replaced_by must be a non-empty string"))
            continue
        if replaced_by not in all_keys:
            findings.append(
                Finding(path=path, message=f"[{kind}][{i}] {key!r} replaced_by {replaced_by!r} not found in keys")
            )
            continue
        if key == replaced_by:
            findings.append(Finding(path=path, message=f"[{kind}][{i}] {key!r} replaced_by itself"))
    return findings


def _check_related_refs(
    *,
    items: Iterable[Dict[str, Any]],
    field: str,
    valid_keys: Set[str],
    path: Path,
    kind: str,
) -> List[Finding]:
    findings: List[Finding] = []
    for i, item in enumerate(items):
        key = item.get("key")
        refs = item.get(field)
        if refs is None:
            continue
        if not isinstance(refs, list):
            findings.append(Finding(path=path, message=f"[{kind}][{i}].{field} must be an array"))
            continue
        for j, ref in enumerate(refs):
            if not isinstance(ref, str) or not ref:
                findings.append(Finding(path=path, message=f"[{kind}][{i}].{field}[{j}] must be a non-empty string"))
                continue
            if ref not in valid_keys:
                findings.append(
                    Finding(path=path, message=f"[{kind}][{i}] {key!r} {field}[{j}] {ref!r} not found in keys")
                )
    return findings


def _parse_case_pr_number(case_id: str) -> Optional[int]:
    m = RE_CASE_ID.match(case_id)
    if not m:
        return None
    try:
        return int(m.group("pr"))
    except ValueError:
        return None


def _validate_cases(
    *,
    root: Path,
    case_schema: Dict[str, Any],
    taxonomy_keys: Set[str],
    smell_keys: Set[str],
) -> List[Finding]:
    cases_dir = root / "cases"
    if not cases_dir.exists():
        return [Finding(path=cases_dir, message="missing directory: cases/")]

    findings: List[Finding] = []
    case_files = sorted(p for p in cases_dir.rglob("*.json") if p.is_file())
    seen_ids: Set[str] = set()

    for path in case_files:
        try:
            instance = _read_json(path)
        except Exception as e:
            findings.append(Finding(path=path, message=f"failed to read JSON: {e}"))
            continue

        findings.extend(_schema_validate(instance=instance, schema=case_schema, path=path))

        case_id = instance.get("id")
        if isinstance(case_id, str):
            if case_id in seen_ids:
                findings.append(Finding(path=path, message=f"duplicate case id: {case_id!r}"))
            else:
                seen_ids.add(case_id)

            expected = path.stem
            if case_id != expected:
                findings.append(Finding(path=path, message=f"case id {case_id!r} must match filename stem {expected!r}"))

            pr_num = _parse_case_pr_number(case_id)
            source_pr = instance.get("source_pr") or {}
            if pr_num is not None and isinstance(source_pr, dict):
                src_num = source_pr.get("number")
                if isinstance(src_num, int) and src_num != pr_num:
                    findings.append(
                        Finding(path=path, message=f"source_pr.number {src_num} must match PR in id ({pr_num})")
                    )

        root_causes = instance.get("root_cause_categories")
        if isinstance(root_causes, list):
            ok, dups = _unique([x for x in root_causes if isinstance(x, str)])
            if not ok:
                for dup in sorted(set(dups)):
                    findings.append(Finding(path=path, message=f"duplicate root_cause_categories entry: {dup!r}"))
            for item in root_causes:
                if isinstance(item, str) and item and taxonomy_keys and item not in taxonomy_keys:
                    findings.append(Finding(path=path, message=f"unknown root_cause_categories key: {item!r}"))

        smells = instance.get("review_smells")
        if isinstance(smells, list):
            ok, dups = _unique([x for x in smells if isinstance(x, str)])
            if not ok:
                for dup in sorted(set(dups)):
                    findings.append(Finding(path=path, message=f"duplicate review_smells entry: {dup!r}"))
            for item in smells:
                if isinstance(item, str) and item and smell_keys and item not in smell_keys:
                    findings.append(Finding(path=path, message=f"unknown review_smells key: {item!r}"))

    return findings


def _main(argv: Sequence[str]) -> int:
    if argv:
        print("Usage: scripts/validate.py (no args)", file=sys.stderr)
        return 2

    root = Path(__file__).resolve().parents[1]

    taxonomy_path = root / "taxonomy.json"
    smells_path = root / "review_smells.json"

    taxonomy_schema = _load_schema(root, "taxonomy.schema.json")
    smells_schema = _load_schema(root, "review_smells.schema.json")
    case_schema = _load_schema(root, "case.schema.json")

    findings: List[Finding] = []

    # Taxonomy
    if not taxonomy_path.exists():
        findings.append(Finding(path=taxonomy_path, message="missing file: taxonomy.json"))
        taxonomy = {"categories": []}
    else:
        taxonomy = _read_json(taxonomy_path)
        findings.extend(_schema_validate(instance=taxonomy, schema=taxonomy_schema, path=taxonomy_path))

    categories = taxonomy.get("categories") if isinstance(taxonomy, dict) else None
    if not isinstance(categories, list):
        categories = []

    taxonomy_keys, taxonomy_key_findings = _index_keys(categories, path=taxonomy_path, kind="categories")
    findings.extend(taxonomy_key_findings)

    # Smells
    if not smells_path.exists():
        findings.append(Finding(path=smells_path, message="missing file: review_smells.json"))
        smells = {"smells": []}
    else:
        smells = _read_json(smells_path)
        findings.extend(_schema_validate(instance=smells, schema=smells_schema, path=smells_path))

    smell_items = smells.get("smells") if isinstance(smells, dict) else None
    if not isinstance(smell_items, list):
        smell_items = []

    smell_keys, smell_key_findings = _index_keys(smell_items, path=smells_path, kind="smells")
    findings.extend(smell_key_findings)

    # Cross references between dictionaries
    findings.extend(_check_replaced_by(items=categories, all_keys=taxonomy_keys, path=taxonomy_path, kind="categories"))
    findings.extend(_check_replaced_by(items=smell_items, all_keys=smell_keys, path=smells_path, kind="smells"))

    findings.extend(
        _check_related_refs(
            items=categories,
            field="related_smells",
            valid_keys=smell_keys,
            path=taxonomy_path,
            kind="categories",
        )
    )
    findings.extend(
        _check_related_refs(
            items=smell_items,
            field="related_root_causes",
            valid_keys=taxonomy_keys,
            path=smells_path,
            kind="smells",
        )
    )

    # Cases
    findings.extend(
        _validate_cases(
            root=root,
            case_schema=case_schema,
            taxonomy_keys=taxonomy_keys,
            smell_keys=smell_keys,
        )
    )

    if findings:
        for finding in findings:
            rel = finding.path.relative_to(root) if finding.path.is_absolute() else finding.path
            print(f"[ERROR] {rel}: {finding.message}", file=sys.stderr)
        print(f"\nValidation failed: {len(findings)} error(s).", file=sys.stderr)
        return 1

    print("OK: validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
