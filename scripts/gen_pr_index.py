#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple


DEFAULT_REF = "upstream/master"


RE_SQUASH_PR_AT_END = re.compile(r"\(#(?P<pr>[0-9]+)\)\s*$")
RE_MERGE_PR = re.compile(r"^Merge pull request #(?P<pr>[0-9]+)\b")


@dataclass(frozen=True)
class PRIndexItem:
    pr_merged_at: str
    pr_number: int
    pr_url: str
    title: str
    triage_status: str
    triage_notes: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "pr_merged_at": self.pr_merged_at,
                "pr_number": self.pr_number,
                "pr_url": self.pr_url,
                "title": self.title,
                "triage_notes": self.triage_notes,
                "triage_status": self.triage_status,
            },
            ensure_ascii=False,
            sort_keys=False,
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_git_log(*, tidb_repo: Path, ref: str, since: str, until: str) -> bytes:
    cmd = [
        "git",
        "-C",
        str(tidb_repo),
        "log",
        ref,
        "--first-parent",
        "--reverse",
        "--since",
        since,
        "--until",
        until,
        "--date=iso-strict",
        "--pretty=tformat:%cI%x00%s%x00%b%x00",
    ]
    try:
        return subprocess.check_output(cmd)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git log failed: {e}", file=sys.stderr)
        raise


def _parse_git_records(raw: bytes) -> Iterator[Tuple[str, str, str]]:
    # git-log may append a trailing newline even when the format ends with %x00.
    raw = raw.rstrip(b"\n")
    parts = raw.split(b"\x00")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    if len(parts) % 3 != 0:
        raise ValueError(f"unexpected git log output: field count {len(parts)} is not divisible by 3")
    for i in range(0, len(parts), 3):
        merged_at = parts[i].decode("utf-8", errors="replace").strip()
        subject = parts[i + 1].decode("utf-8", errors="replace")
        body = parts[i + 2].decode("utf-8", errors="replace")
        yield merged_at, subject, body


def _extract_pr_from_subject(subject: str, body: str) -> Optional[Tuple[int, str]]:
    # Squash merges (common in TiDB): "... (#12345)" at the end of the subject.
    m = RE_SQUASH_PR_AT_END.search(subject)
    if m:
        pr_number = int(m.group("pr"))
        title = subject[: m.start()].rstrip()
        return pr_number, title

    # Merge commits: "Merge pull request #12345 from ..."
    m = RE_MERGE_PR.match(subject)
    if m:
        pr_number = int(m.group("pr"))
        title = ""
        for line in body.splitlines():
            line = line.strip()
            if line:
                title = line
                break
        if not title:
            title = subject
        return pr_number, title

    return None


def _read_jsonl(path: Path) -> List[dict]:
    items: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _load_existing_triage(*, root: Path, year: int) -> Dict[int, Tuple[str, str]]:
    year_dir = root / "backlog" / "pr_index" / str(year)
    if not year_dir.exists():
        return {}
    triage: Dict[int, Tuple[str, str]] = {}
    for path in sorted(year_dir.glob("*.jsonl")):
        for obj in _read_jsonl(path):
            pr_number = obj.get("pr_number")
            if not isinstance(pr_number, int):
                continue
            status = obj.get("triage_status")
            notes = obj.get("triage_notes")
            if isinstance(status, str) and isinstance(notes, str):
                triage[pr_number] = (status, notes)
    return triage


def _gen_year_items(
    *,
    tidb_repo: Path,
    ref: str,
    year: int,
    existing_triage: Dict[int, Tuple[str, str]],
) -> List[PRIndexItem]:
    # Scan a slightly wider window and then filter by `pr_merged_at` year to be robust
    # to timezones and Git's inclusive `--until` behavior.
    since = f"{year - 1}-12-31"
    until = f"{year + 1}-01-02"

    raw = _run_git_log(tidb_repo=tidb_repo, ref=ref, since=since, until=until)
    items: List[PRIndexItem] = []

    for merged_at, subject, body in _parse_git_records(raw):
        if not merged_at.startswith(f"{year}-"):
            continue
        parsed = _extract_pr_from_subject(subject, body)
        if parsed is None:
            continue
        pr_number, title = parsed
        triage_status, triage_notes = existing_triage.get(pr_number, ("unreviewed", ""))
        items.append(
            PRIndexItem(
                pr_merged_at=merged_at,
                pr_number=pr_number,
                pr_url=f"https://github.com/pingcap/tidb/pull/{pr_number}",
                title=title,
                triage_status=triage_status,
                triage_notes=triage_notes,
            )
        )
    items.sort(key=lambda x: x.pr_merged_at)

    # Deduplicate by PR number. Some periods in the TiDB history contain repeated
    # (often empty) commits that end with the same "(#PR)" suffix.
    deduped: List[PRIndexItem] = []
    seen_prs: set[int] = set()
    dup_prs: List[int] = []
    for item in items:
        if item.pr_number in seen_prs:
            dup_prs.append(item.pr_number)
            continue
        seen_prs.add(item.pr_number)
        deduped.append(item)

    if dup_prs:
        unique_dups = sorted(set(dup_prs))
        print(
            f"WARNING: {year}: deduped {len(dup_prs)} duplicate entries across {len(unique_dups)} PRs "
            f"(keeping earliest pr_merged_at).",
            file=sys.stderr,
        )

    return deduped


def _bucket_by_month(items: Sequence[PRIndexItem]) -> Dict[str, List[PRIndexItem]]:
    buckets: Dict[str, List[PRIndexItem]] = {}
    for item in items:
        if len(item.pr_merged_at) < 7:
            continue
        month = item.pr_merged_at[5:7]
        buckets.setdefault(month, []).append(item)
    for month in buckets:
        buckets[month].sort(key=lambda x: x.pr_merged_at)
    return buckets


def _write_jsonl(path: Path, items: Sequence[PRIndexItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(item.to_json())
            f.write("\n")


def generate_year(*, tidb_repo: Path, ref: str, year: int) -> None:
    root = _repo_root()
    existing_triage = _load_existing_triage(root=root, year=year)
    items = _gen_year_items(tidb_repo=tidb_repo, ref=ref, year=year, existing_triage=existing_triage)
    by_month = _bucket_by_month(items)

    out_year_dir = root / "backlog" / "pr_index" / str(year)
    out_year_dir.mkdir(parents=True, exist_ok=True)

    # Write non-empty months; remove any stale empty placeholder files.
    for m in range(1, 13):
        month = f"{m:02d}"
        path = out_year_dir / f"{month}.jsonl"
        month_items = by_month.get(month, [])
        if not month_items:
            if path.exists():
                path.unlink()
            continue
        _write_jsonl(path, month_items)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate monthly PR index JSONL files from TiDB git history.")
    parser.add_argument("--tidb-repo", type=Path, default=Path("../tidb"), help="Path to the tidb git repo.")
    parser.add_argument("--ref", default=DEFAULT_REF, help=f"Git ref to scan (default: {DEFAULT_REF}).")
    parser.add_argument("--year", type=int, required=True, help="Year to generate, e.g. 2021.")
    args = parser.parse_args(argv)

    if not args.tidb_repo.exists():
        print(f"ERROR: --tidb-repo not found: {args.tidb_repo}", file=sys.stderr)
        return 2

    generate_year(tidb_repo=args.tidb_repo, ref=args.ref, year=args.year)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
