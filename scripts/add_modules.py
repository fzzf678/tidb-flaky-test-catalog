#!/usr/bin/env python3

import argparse
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Pattern, Sequence, Tuple


MODULE_KEYS: List[str] = [
    "planner",
    "executor",
    "ddl",
    "statistics",
    "session",
    "domain",
    "server",
    "parser",
    "expression",
    "kv",
    "txn",
    "gc",
    "br",
    "lightning",
    "security",
    "test_infra",
    "module_unknown",
]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return json.dumps(x, ensure_ascii=False, sort_keys=True)


_RE_PATH_LIKE = re.compile(r"\b[a-zA-Z0-9_.-]+(?:/[a-zA-Z0-9_.-]+)+\b")
_RE_FILE_LIKE = re.compile(r"\b[a-zA-Z0-9_.-]+\.(go|rs|py|sh|java|cc|h|hpp|proto|sql|txt|md)\b", re.I)


def _strip_path_noise(text: str) -> str:
    # The user requirement for `module` is "based on test/PR semantics, not mechanically derived from paths".
    # Many fields (analysis/symptoms) contain file paths; strip them to avoid path-driven classification.
    text = _RE_PATH_LIKE.sub(" ", text)
    text = _RE_FILE_LIKE.sub(" ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_title_prefix(title: str) -> Optional[str]:
    if not title:
        return None
    m = re.match(r"^\s*([^:]{1,60})\s*:\s+.+$", title)
    if not m:
        return None
    prefix = m.group(1).strip().lower()
    prefix = re.sub(r"\s+", " ", prefix)
    return prefix or None


def _tokenize_prefix(prefix: str) -> List[str]:
    # Handles: "planner, executor" / "plan, executor" / "pkg/domain/affinity"
    parts: List[str] = []
    for chunk in prefix.split(","):
        chunk = chunk.strip().lower()
        if not chunk or chunk == "*":
            continue
        parts.append(chunk)
        for seg in re.split(r"[\\/\\s]+", chunk):
            seg = seg.strip()
            if seg and seg != "*":
                parts.append(seg)
    # De-dup while preserving order
    seen = set()
    out: List[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


PREFIX_ALIAS_TO_MODULE: Dict[str, str] = {
    "plan": "planner",
    "planner/core": "planner",
    "planner, executor": "planner",
    "plan, executor": "planner",
    "executor, tests": "executor",
    "executor, test": "executor",
    "statistics": "statistics",
    "stats": "statistics",
    "store/tikv": "kv",
    "store": "kv",
    "tikv": "kv",
    "kv": "kv",
    "txn": "txn",
    "transaction": "txn",
    "infoschema": "domain",
    "info schema": "domain",
    "disttask": "domain",
    "dxf": "domain",
    "bazel": "test_infra",
    "makefile": "test_infra",
    "ci": "test_infra",
    "test": "test_infra",
    "tests": "test_infra",
}


def _module_from_prefix(prefix: Optional[str]) -> Optional[str]:
    if not prefix:
        return None

    # Exact alias mapping first.
    hit = PREFIX_ALIAS_TO_MODULE.get(prefix)
    if hit:
        return hit

    # Token-based mapping (priority order matters).
    tokens = _tokenize_prefix(prefix)
    for t in tokens:
        if t in PREFIX_ALIAS_TO_MODULE:
            return PREFIX_ALIAS_TO_MODULE[t]
        if t in MODULE_KEYS:
            return t

    # Heuristic containment mapping.
    joined = " ".join(tokens)
    if "planner" in joined or "optimizer" in joined:
        return "planner"
    if "executor" in joined:
        return "executor"
    if "ddl" in joined or "schema" in joined:
        return "ddl"
    if "infoschema" in joined or "information_schema" in joined:
        return "domain"
    if "stat" in joined or "analyze" in joined:
        return "statistics"
    if "session" in joined or "sysvar" in joined:
        return "session"
    if "domain" in joined or "infosync" in joined or "affinity" in joined:
        return "domain"
    if "server" in joined or "mysql" in joined or "http" in joined or "grpc" in joined:
        return "server"
    if "parser" in joined or "ast" in joined or "lexer" in joined:
        return "parser"
    if "expression" in joined or "builtin" in joined or "types" in joined:
        return "expression"
    if "br" in joined or "backup" in joined or "restore" in joined:
        return "br"
    if "lightning" in joined:
        return "lightning"
    if "ttl" in joined:
        return "domain"
    if "gc" in joined:
        return "gc"
    if "security" in joined or "privilege" in joined or "auth" in joined or "tls" in joined:
        return "security"
    return None


# Weighted patterns: prefer strong semantic signals; path-like tokens are stripped earlier.
MODULE_PATTERNS: Dict[str, List[Tuple[Pattern[str], int]]] = {
    "planner": [
        (re.compile(r"\bplanner\b", re.I), 3),
        (re.compile(r"\boptimizer\b|\boptimiser\b", re.I), 2),
        (re.compile(r"\bexplain\b", re.I), 2),
        (re.compile(r"\bcascades\b|\bmemo\b", re.I), 2),
        (re.compile(r"\blogical plan\b|\bphysical plan\b", re.I), 2),
    ],
    "executor": [
        (re.compile(r"\bexecutor\b", re.I), 3),
        (re.compile(r"\bcoprocessor\b|\bcopr\b", re.I), 2),
        (re.compile(r"\bmpp\b", re.I), 2),
        (re.compile(r"\bchunk\b", re.I), 1),
        (re.compile(r"\bimport into\b|\bimportinto\b|\bload data\b", re.I), 2),
    ],
    "ddl": [
        (re.compile(r"\bddl\b", re.I), 3),
        (re.compile(r"\bschema\b", re.I), 2),
        (re.compile(r"\bpartition\b", re.I), 2),
        (re.compile(r"\badd index\b|\bcreate index\b|\bdrop index\b", re.I), 2),
    ],
    "statistics": [
        (re.compile(r"\bstatistics\b|\bstats\b", re.I), 3),
        (re.compile(r"\banalyze\b", re.I), 2),
        (re.compile(r"\bhistogram\b|\bcmsketch\b|\bselectivity\b|\bfeedback\b", re.I), 2),
    ],
    "session": [
        (re.compile(r"\bsession\b", re.I), 3),
        (re.compile(r"\bsysvar\b|\bsystem variable\b|\bglobal variable\b", re.I), 2),
        (re.compile(r"\bsessionctx\b", re.I), 2),
        (re.compile(r"\bplan cache\b|\bprepared statement\b", re.I), 2),
    ],
    "domain": [
        (re.compile(r"\bdomain\b", re.I), 3),
        (re.compile(r"\binfosync\b", re.I), 2),
        (re.compile(r"\bowner\b", re.I), 2),
        (re.compile(r"\baffinity\b", re.I), 2),
        (re.compile(r"\binfoschema\b|\binformation_schema\b|\binfo schema\b", re.I), 2),
        (re.compile(r"\bschema tracker\b|\bschema sync\b|\bschema version\b", re.I), 2),
        (re.compile(r"\bttl\b", re.I), 2),
        (re.compile(r"\bdisttask\b|\bdxf\b", re.I), 2),
    ],
    "server": [
        (re.compile(r"\bserver\b", re.I), 3),
        (re.compile(r"\bgrpc\b|\bhttp\b|\bstatus api\b", re.I), 2),
        (re.compile(r"\bmysql protocol\b", re.I), 2),
        (re.compile(r"\bmetrics\b|\btopsql\b", re.I), 2),
    ],
    "parser": [
        (re.compile(r"\bparser\b", re.I), 3),
        (re.compile(r"\bast\b", re.I), 2),
        (re.compile(r"\blexer\b|\btoken\b", re.I), 2),
        (re.compile(r"\bcharset\b|\bcollation\b", re.I), 2),
    ],
    "expression": [
        (re.compile(r"\bexpression\b", re.I), 3),
        (re.compile(r"\bbuiltin\b", re.I), 2),
        (re.compile(r"\bcast\b|\btype inference\b", re.I), 2),
    ],
    "kv": [
        (re.compile(r"\btikv\b|\bpd\b", re.I), 3),
        (re.compile(r"\bregion\b|\braft\b", re.I), 2),
    ],
    "txn": [
        (re.compile(r"\btxn\b|\btransaction\b", re.I), 3),
        (re.compile(r"\bpessimistic\b|\boptimistic\b", re.I), 2),
        (re.compile(r"\bdeadlock\b|\block\b|\b2pc\b", re.I), 2),
        (re.compile(r"\btso\b|\bsnapshot\b", re.I), 2),
    ],
    "gc": [
        (re.compile(r"\bgc\b|\bgc_worker\b", re.I), 3),
        (re.compile(r"\bmvcc\b", re.I), 2),
        (re.compile(r"\bsafe point\b|\bsafepoint\b", re.I), 2),
    ],
    "br": [
        (re.compile(r"\bbr\b", re.I), 3),
        (re.compile(r"\blog backup\b", re.I), 2),
        (re.compile(r"\bbackup\b|\brestore\b", re.I), 2),
    ],
    "lightning": [
        (re.compile(r"\blightning\b", re.I), 3),
        (re.compile(r"\btidb-lightning\b", re.I), 2),
    ],
    "security": [
        (re.compile(r"\bsecurity\b", re.I), 3),
        (re.compile(r"\bprivilege\b|\bauth\b|\bauthentication\b", re.I), 2),
        (re.compile(r"\btls\b|\bcertificate\b|\bcert\b", re.I), 2),
    ],
    "test_infra": [
        (re.compile(r"\btestify\b", re.I), 3),
        (re.compile(r"\btestkit\b", re.I), 2),
        (re.compile(r"\bcheck\\.c\b|\bsuite\\.", re.I), 2),
        (re.compile(r"\bfixture\b|\bsetup\b|\bteardown\b", re.I), 2),
        (re.compile(r"\bbazel\b", re.I), 2),
        (re.compile(r"flaky\\s*=\\s*true", re.I), 2),
        (re.compile(r"race\\s*=\\s*\"(on|off)\"", re.I), 2),
        (re.compile(r"\bghpr_|\bgithub actions\b|\bci run\b", re.I), 2),
    ],
}


def _joined_text_for_module(case: Dict[str, Any]) -> str:
    pr = case.get("source_pr") if isinstance(case.get("source_pr"), dict) else {}
    title = _safe_str(pr.get("title"))
    body = _safe_str(pr.get("body"))
    fix_pattern = _safe_str(case.get("fix_pattern"))

    symptoms = case.get("symptoms") or []
    symptoms_txt = "\n".join(_safe_str(s) for s in symptoms if s is not None)

    failure_sig = _safe_str(case.get("failure_signature"))
    analysis = _safe_str(case.get("analysis"))

    # NOTE: We intentionally do NOT include changed_files/test.path to avoid a purely path-driven module assignment.
    chunks = [title, body, fix_pattern, symptoms_txt, failure_sig, analysis]
    blob = "\n".join(c for c in chunks if c).strip()
    return _strip_path_noise(blob).lower()


SMELL_TO_MODULE: Dict[str, str] = {
    # Planner / plan selection
    "assert_exact_plan_or_cost": "planner",
    "nondeterministic_plan_tie_break": "planner",
    "plan_cache_dependency": "session",
    # DDL / schema
    "ddl_without_wait": "ddl",
    "async_schema_propagation": "domain",
    # KV / real cluster dependency
    "real_tikv_dependency": "kv",
    # Test infra
    "deprecated_test_framework_usage": "test_infra",
    "incomplete_testify_migration": "test_infra",
    "test_suite_setup_issue": "test_infra",
    "bazel_flaky_attr": "test_infra",
}


ROOT_CAUSE_TO_MODULE: Dict[str, str] = {
    "nondeterministic_plan_selection": "planner",
    "schema_change_race": "ddl",
}


MIN_CONFIDENCE_SCORE = 2


def _score_modules(case: Dict[str, Any], *, text: str) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    for module, patterns in MODULE_PATTERNS.items():
        scores[module] = sum(weight for (p, weight) in patterns if p.search(text))

    smells = case.get("review_smells") or []
    if isinstance(smells, list):
        for smell in smells:
            if isinstance(smell, str) and smell in SMELL_TO_MODULE:
                m = SMELL_TO_MODULE[smell]
                scores[m] = scores.get(m, 0) + 2

    root_causes = case.get("root_cause_categories") or []
    if isinstance(root_causes, list):
        for rc in root_causes:
            if isinstance(rc, str) and rc in ROOT_CAUSE_TO_MODULE:
                m = ROOT_CAUSE_TO_MODULE[rc]
                scores[m] = scores.get(m, 0) + 1
    return scores


def _choose_best_module(scores: Dict[str, int]) -> str:
    best_module = "module_unknown"
    best_score = 0
    ties: List[str] = []
    for module, score in scores.items():
        if score > best_score:
            best_score = score
            best_module = module
            ties = [module]
        elif score == best_score and score > 0:
            ties.append(module)

    if best_score < MIN_CONFIDENCE_SCORE:
        return "module_unknown"
    if len(set(ties)) > 1:
        # Quality-first: avoid guessing when multiple modules are equally plausible.
        return "module_unknown"
    return best_module


def _generate_module(case: Dict[str, Any]) -> str:
    title = _safe_str((case.get("source_pr") or {}).get("title"))
    prefix = _extract_title_prefix(title)
    by_prefix = _module_from_prefix(prefix)
    if by_prefix:
        return by_prefix

    text = _joined_text_for_module(case)
    scores = _score_modules(case, text=text)
    chosen = _choose_best_module(scores)
    if chosen not in MODULE_KEYS:
        return "module_unknown"
    return chosen


def _inject_module(case: Dict[str, Any], *, module: str) -> Dict[str, Any]:
    insert_after = "root_cause_explanation" if "root_cause_explanation" in case else "review_smells"
    out: "OrderedDict[str, Any]" = OrderedDict()
    inserted = False
    for k, v in case.items():
        if k == "module":
            continue
        out[k] = v
        if (not inserted) and k == insert_after:
            out["module"] = module
            inserted = True
    if not inserted:
        out["module"] = module
    return out


def _iter_case_files(paths: Sequence[Path]) -> Iterable[Path]:
    for p in paths:
        if p.is_file() and p.suffix == ".json":
            yield p
            continue
        if p.is_dir():
            yield from sorted(pp for pp in p.rglob("pr-*.json") if pp.is_file())


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description="Add `module` to case JSON files.")
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
        help="Overwrite existing module values (default: only fill missing).",
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
    dist: Counter[str] = Counter()
    for path in case_files:
        case = _read_json(path)
        if not isinstance(case, dict):
            skipped += 1
            continue

        existing = case.get("module")
        if existing and not args.overwrite:
            dist[str(existing)] += 1
            skipped += 1
            continue

        module = _generate_module(case)
        if module not in MODULE_KEYS:
            module = "module_unknown"
        dist[module] += 1

        out = _inject_module(case, module=module)
        if args.dry_run:
            print(f"{path}: {module}")
        else:
            _write_json(path, out)
        updated += 1

    action = "Would update" if args.dry_run else "Updated"
    print(f"{action} {updated} file(s); skipped {skipped} file(s).")
    print("Module distribution (updated targets only):")
    for k, v in dist.most_common():
        print(f"- {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
