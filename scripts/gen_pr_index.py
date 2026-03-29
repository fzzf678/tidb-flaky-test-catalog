#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


GITHUB_REPO = "pingcap/tidb"
DEFAULT_BASE_BRANCH = "master"
DEFAULT_TIMEZONE = "Asia/Shanghai"


@dataclass(frozen=True)
class PRIndexItem:
    pr_merged_at: str
    pr_number: int
    pr_url: str
    title: str
    triage_status: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "pr_merged_at": self.pr_merged_at,
                "pr_number": self.pr_number,
                "pr_url": self.pr_url,
                "title": self.title,
                "triage_status": self.triage_status,
            },
            ensure_ascii=False,
            sort_keys=False,
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _compact_query(query: str) -> str:
    return " ".join(query.split())


def _parse_utc_datetime(iso: str) -> datetime:
    # GitHub returns RFC3339 timestamps like "2021-10-31T16:02:50Z".
    if iso.endswith("Z"):
        iso = iso[:-1] + "+00:00"
    return datetime.fromisoformat(iso).astimezone(timezone.utc)


def _local_tz(tz_name: str) -> timezone:
    # Python 3.8 lacks zoneinfo; implement a minimal fixed-offset parser.
    if tz_name in {"Asia/Shanghai", "UTC+8", "UTC+08", "UTC+08:00"}:
        return timezone(timedelta(hours=8))
    if tz_name in {"UTC", "Z", "+00:00", "UTC+0", "UTC+00:00"}:
        return timezone.utc

    # Support "+HH:MM" / "-HH:MM"
    if len(tz_name) == 6 and tz_name[0] in {"+", "-"} and tz_name[3] == ":":
        sign = 1 if tz_name[0] == "+" else -1
        try:
            hours = int(tz_name[1:3])
            minutes = int(tz_name[4:6])
        except ValueError:
            raise RuntimeError(f"unsupported timezone: {tz_name!r}")
        if hours > 23 or minutes > 59:
            raise RuntimeError(f"unsupported timezone: {tz_name!r}")
        return timezone(sign * timedelta(hours=hours, minutes=minutes))

    raise RuntimeError(
        f"unsupported timezone: {tz_name!r} (try {DEFAULT_TIMEZONE!r} or an offset like '+08:00')"
    )


def _month_window_local(*, year: int, month: int, tz_name: str) -> Tuple[datetime, datetime]:
    tz = _local_tz(tz_name)
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
    if month == 12:
        next_start = datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=tz)
    else:
        next_start = datetime(year, month + 1, 1, 0, 0, 0, tzinfo=tz)
    return start, next_start


def _utc_date_window_for_local_month(*, year: int, month: int, tz_name: str) -> Tuple[date, date]:
    # GitHub search's merged:YYYY-MM-DD..YYYY-MM-DD uses UTC dates.
    # We widen the query to the UTC-date window that fully covers the given local month.
    start_local, next_local = _month_window_local(year=year, month=month, tz_name=tz_name)
    start_utc = start_local.astimezone(timezone.utc)
    # next_local at 00:00 local is 16:00 UTC of the previous day for UTC+8.
    end_utc = (next_local.astimezone(timezone.utc) - timedelta(seconds=1))
    return start_utc.date(), end_utc.date()


def _gh_api_graphql(*, query: str, fields: Dict[str, Optional[str]]) -> dict:
    cmd = [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={_compact_query(query)}",
    ]
    for key, value in fields.items():
        if value is None:
            continue
        cmd.extend(["-f", f"{key}={value}"])
    try:
        out = subprocess.check_output(cmd)
    except FileNotFoundError:
        raise RuntimeError("missing dependency: gh (GitHub CLI). Install from https://cli.github.com/")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh api graphql failed: {e}")
    return json.loads(out.decode("utf-8"))


GQL_SEARCH_PRS = """
query($searchQuery: String!, $cursor: String) {
  search(type: ISSUE, query: $searchQuery, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number
        title
        url
        mergedAt
      }
    }
  }
}
"""


def _fetch_prs_by_search_query(*, query_str: str) -> Tuple[int, List[dict]]:
    items: List[dict] = []
    cursor: Optional[str] = None
    total: Optional[int] = None

    while True:
        data = _gh_api_graphql(query=GQL_SEARCH_PRS, fields={"searchQuery": query_str, "cursor": cursor})
        search = (data.get("data") or {}).get("search") or {}
        if total is None:
            total = int(search.get("issueCount") or 0)

        nodes = search.get("nodes") or []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("mergedAt") is None:
                continue
            items.append(node)

        page_info = search.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")

    return total or 0, items


def _fetch_prs_for_utc_date_range(
    *,
    start_utc_date: date,
    end_utc_date: date,
    base_branch: str,
) -> List[dict]:
    if start_utc_date > end_utc_date:
        return []

    query_str = (
        f"repo:{GITHUB_REPO} "
        f"is:pr is:merged base:{base_branch} "
        f"merged:{start_utc_date.isoformat()}..{end_utc_date.isoformat()}"
    )
    total, items = _fetch_prs_by_search_query(query_str=query_str)

    # GitHub search is capped at 1000 results; split the range if needed.
    if total > 1000:
        if start_utc_date == end_utc_date:
            raise RuntimeError(f"GitHub search results exceed 1000 for a single day: {start_utc_date.isoformat()}")
        mid = start_utc_date + timedelta(days=(end_utc_date - start_utc_date).days // 2)
        left = _fetch_prs_for_utc_date_range(start_utc_date=start_utc_date, end_utc_date=mid, base_branch=base_branch)
        right = _fetch_prs_for_utc_date_range(
            start_utc_date=mid + timedelta(days=1), end_utc_date=end_utc_date, base_branch=base_branch
        )
        # Dedup by PR number just in case.
        merged: Dict[int, dict] = {}
        for node in left + right:
            n = node.get("number")
            if isinstance(n, int) and n not in merged:
                merged[n] = node
        return list(merged.values())

    # Dedup by PR number in-page (can happen due to search pagination quirks).
    deduped: Dict[int, dict] = {}
    for node in items:
        n = node.get("number")
        if isinstance(n, int) and n not in deduped:
            deduped[n] = node
    return list(deduped.values())


def _read_jsonl(path: Path) -> List[dict]:
    items: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _load_existing_triage(*, root: Path, year: int) -> Dict[int, str]:
    year_dir = root / "backlog" / "pr_index" / str(year)
    if not year_dir.exists():
        return {}
    triage: Dict[int, str] = {}
    for path in sorted(year_dir.glob("*.jsonl")):
        for obj in _read_jsonl(path):
            pr_number = obj.get("pr_number")
            if not isinstance(pr_number, int):
                continue
            status = obj.get("triage_status")
            if isinstance(status, str):
                triage[pr_number] = status
    return triage


def _gen_year_items(
    *,
    year: int,
    existing_triage: Dict[int, str],
    base_branch: str,
    tz_name: str,
) -> List[PRIndexItem]:
    items: List[PRIndexItem] = []
    for month in range(1, 13):
        start_utc_date, end_utc_date = _utc_date_window_for_local_month(year=year, month=month, tz_name=tz_name)
        nodes = _fetch_prs_for_utc_date_range(start_utc_date=start_utc_date, end_utc_date=end_utc_date, base_branch=base_branch)

        start_local, next_local = _month_window_local(year=year, month=month, tz_name=tz_name)
        for node in nodes:
            pr_number = node.get("number")
            title = node.get("title")
            url = node.get("url")
            merged_at = node.get("mergedAt")
            if not isinstance(pr_number, int) or not isinstance(title, str) or not isinstance(url, str) or not isinstance(merged_at, str):
                continue

            merged_at_utc = _parse_utc_datetime(merged_at)
            merged_at_local = merged_at_utc.astimezone(_local_tz(tz_name))
            if not (start_local <= merged_at_local < next_local):
                continue

            triage_status = existing_triage.get(pr_number, "unreviewed")
            items.append(
                PRIndexItem(
                    pr_merged_at=merged_at_local.isoformat(),
                    pr_number=pr_number,
                    pr_url=url,
                    title=title,
                    triage_status=triage_status,
                )
            )

    items.sort(key=lambda x: x.pr_merged_at)

    # PR numbers are unique; still dedup defensively in case a PR appears in multiple month queries.
    deduped: List[PRIndexItem] = []
    seen_prs: set[int] = set()
    for item in items:
        if item.pr_number in seen_prs:
            continue
        seen_prs.add(item.pr_number)
        deduped.append(item)

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


def generate_year(*, year: int, base_branch: str, tz_name: str) -> None:
    root = _repo_root()
    existing_triage = _load_existing_triage(root=root, year=year)
    items = _gen_year_items(year=year, existing_triage=existing_triage, base_branch=base_branch, tz_name=tz_name)
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
    parser = argparse.ArgumentParser(description="Generate monthly PR index JSONL files from GitHub merged PR history.")
    parser.add_argument("--year", type=int, required=True, help="Year to generate, e.g. 2021.")
    parser.add_argument("--base", default=DEFAULT_BASE_BRANCH, help=f"Base branch filter (default: {DEFAULT_BASE_BRANCH}).")
    parser.add_argument("--tz", default=DEFAULT_TIMEZONE, help=f"Timezone for bucketing (default: {DEFAULT_TIMEZONE}).")
    args = parser.parse_args(argv)

    generate_year(year=args.year, base_branch=args.base, tz_name=args.tz)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
