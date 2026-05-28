"""Live-mine Cargo dependency-update PRs from GitHub for a date range.

Stage 1 of the live-mine pipeline. Hits the GitHub Search API for PRs
matching dependency-update title patterns (Dependabot's "Bump X from A
to B" plus Renovate's "update X to Y" / "chore(deps)" forms), splitting
the date range into windows narrow enough to stay under the API's
1,000-results-per-query cap.

Output: one JSONL row per matched PR, with the same lowercase keys as
`rebatchi_ds1_filter.py`'s output, so downstream stages
(`cargo_live_filter.py` and `rebatchi_to_candidate.py --require-cargo`)
can consume both data sources interchangeably.

Two queries run, results dedupe by (owner, repo, number):
  Q1 (Dependabot-style):   "Bump" in:title is:pr created:<window>
  Q2 (Renovate / generic): "update" in:title is:pr created:<window>

Q2 is much noisier than Q1 — most "update" PRs are not dependency
bumps. Pre-filtering happens in Stage 2 (cargo_live_filter.py); this
stage captures everything matching the search and lets the next stage
narrow.

Auto-recursive window splitting: starts daily, halves the window
recursively when a query returns the API-cap'd 1,000 results. Logs the
split tree so you can audit which days saturated.

Usage:
  GITHUB_TOKEN=... python -m scripts.cargo_live_search \\
      --start 2024-01-01 --end 2025-12-31 \\
      --out   data/live-mine/search_hits.jsonl

Resume: re-running with the same --out file will detect previously
written rows and skip windows already covered. Windows are tracked in
a sidecar `<out>.windows.jsonl` log file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterator

import requests

# Reuse the existing GitHub auth helper to keep token handling consistent.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipelines.cargo._candidate import gh_headers  # noqa: E402

GITHUB_API = "https://api.github.com"
PER_PAGE = 100
MAX_RESULTS_PER_QUERY = 1000  # GitHub Search API hard cap.

# Known queries. Each entry: (label, query_template). The {window}
# placeholder gets `created:YYYY-MM-DDTHH:MM:SSZ..YYYY-MM-DDTHH:MM:SSZ`.
QUERIES = [
    ("bump", '"Bump" in:title is:pr {window}'),
    ("update", '"update" in:title is:pr {window}'),
]


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _window_clause(start: dt.datetime, end: dt.datetime) -> str:
    return f"created:{_iso(start)}..{_iso(end)}"


def _search_once(query: str, page: int) -> dict:
    """One paginated Search API call. Caller handles retry / rate-limit."""
    r = requests.get(
        f"{GITHUB_API}/search/issues",
        headers=gh_headers(),
        params={"q": query, "per_page": PER_PAGE, "page": page,
                "sort": "created", "order": "asc"},
        timeout=60,
    )
    if r.status_code == 403:
        # Rate limit. Sleep until the documented reset time, then retry.
        reset = int(r.headers.get("X-RateLimit-Reset", "0"))
        now = int(time.time())
        nap = max(reset - now, 5)
        print(f"[search] rate-limited, sleeping {nap}s", file=sys.stderr)
        time.sleep(nap + 1)
        return _search_once(query, page)
    if r.status_code == 422:
        # The Search API throws 422 when offset would exceed 1000.
        return {"items": [], "total_count": 0, "_offset_exceeded": True}
    r.raise_for_status()
    return r.json()


def _search_all_pages(query: str) -> tuple[int, list[dict]]:
    """Return (total_count_reported, all_items_fetched).

    total_count is what GitHub reports as the matching set size; items is
    what we actually got (limited to 1000 by the API cap).
    """
    items: list[dict] = []
    total = 0
    page = 1
    while True:
        body = _search_once(query, page)
        if page == 1:
            total = int(body.get("total_count") or 0)
        page_items = body.get("items") or []
        items.extend(page_items)
        if body.get("_offset_exceeded"):
            break
        if len(page_items) < PER_PAGE:
            break
        page += 1
        if len(items) >= MAX_RESULTS_PER_QUERY:
            break
    return total, items


def _normalize_item(item: dict, query_label: str) -> dict | None:
    """Extract the lowercase-keyed row shape used by Stage 2.

    Mirrors rebatchi_ds1_filter.py's output schema so the downstream
    enrichment script (rebatchi_to_candidate.py) can consume both.
    """
    pr = item.get("pull_request") or {}
    html_url = item.get("html_url") or pr.get("html_url") or ""
    # Parse owner/repo/number out of the URL.
    # Form: https://github.com/<owner>/<repo>/pull/<n>
    parts = html_url.rstrip("/").split("/")
    if len(parts) < 7 or parts[-2] not in ("pull", "issues"):
        return None
    owner, repo = parts[-4], parts[-3]
    try:
        number = int(parts[-1])
    except ValueError:
        return None
    title = item.get("title") or ""
    body = item.get("body") or ""
    user = (item.get("user") or {}).get("login") or ""
    return {
        "owner": owner,
        "repo": repo,
        "number": number,
        "title": title,
        "body": body,  # kept for Stage 2 pre-filter; not in DS1 schema
        "state": item.get("state"),
        "created_at": item.get("created_at"),
        "closed_at": item.get("closed_at"),
        "user": user,
        "labels": [lab.get("name") for lab in (item.get("labels") or [])
                   if lab.get("name")],
        "pr_url": html_url,
        "_query_label": query_label,  # which search produced this hit
    }


def _windows(start: dt.datetime, end: dt.datetime,
             initial: dt.timedelta) -> Iterator[tuple[dt.datetime, dt.datetime]]:
    """Yield non-overlapping [start, end) windows of size `initial`."""
    cur = start
    while cur < end:
        nxt = min(cur + initial, end)
        yield cur, nxt
        cur = nxt


def _split(start: dt.datetime, end: dt.datetime
           ) -> tuple[tuple[dt.datetime, dt.datetime],
                      tuple[dt.datetime, dt.datetime]]:
    """Halve a window. Used when a query saturates."""
    mid = start + (end - start) / 2
    return (start, mid), (mid, end)


def _seen_windows(log_path: Path) -> set[tuple[str, str, str]]:
    """Read window log, return set of completed (label, start, end) tuples."""
    seen: set[tuple[str, str, str]] = set()
    if not log_path.exists():
        return seen
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") == "done":
                seen.add((rec["query_label"], rec["start"], rec["end"]))
    return seen


def _seen_pr_keys(out_path: Path) -> set[tuple[str, str, int]]:
    seen: set[tuple[str, str, int]] = set()
    if not out_path.exists():
        return seen
    with out_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                seen.add((rec["owner"], rec["repo"], int(rec["number"])))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    return seen


def _process_window(query_label: str, q_template: str,
                    start: dt.datetime, end: dt.datetime,
                    out_fh, log_fh,
                    seen_pr_keys: set,
                    saturation_threshold: int = 1000) -> int:
    """Recurse if the query saturates; otherwise dump items.

    Returns the number of new (deduped) PRs written.
    """
    query = q_template.format(window=_window_clause(start, end))
    total, items = _search_all_pages(query)

    # Saturated when GitHub reports more than 1000 matches; even though we
    # got 1000, we know there are extras we can't paginate to.
    saturated = total > saturation_threshold

    if saturated and (end - start) > dt.timedelta(hours=1):
        # Halve and recurse. Hour-resolution is the floor — any saturating
        # hour is just kept truncated and a warning is logged.
        a, b = _split(start, end)
        log_fh.write(json.dumps({
            "status": "split",
            "query_label": query_label,
            "start": _iso(start), "end": _iso(end),
            "total": total,
        }) + "\n")
        log_fh.flush()
        n = _process_window(query_label, q_template, a[0], a[1],
                            out_fh, log_fh, seen_pr_keys)
        n += _process_window(query_label, q_template, b[0], b[1],
                             out_fh, log_fh, seen_pr_keys)
        return n

    new = 0
    for item in items:
        rec = _normalize_item(item, query_label)
        if rec is None:
            continue
        key = (rec["owner"], rec["repo"], int(rec["number"]))
        if key in seen_pr_keys:
            continue
        seen_pr_keys.add(key)
        out_fh.write(json.dumps(rec) + "\n")
        new += 1
    out_fh.flush()

    log_fh.write(json.dumps({
        "status": "done",
        "query_label": query_label,
        "start": _iso(start), "end": _iso(end),
        "total": total, "fetched": len(items), "new": new,
        "saturated_at_hour_floor": saturated and (end - start) <= dt.timedelta(hours=1),
    }) + "\n")
    log_fh.flush()

    print(f"[{query_label}] {_iso(start)}..{_iso(end)}: "
          f"total={total} fetched={len(items)} new={new}",
          file=sys.stderr)
    return new


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--start", required=True, help="ISO date YYYY-MM-DD (inclusive).")
    p.add_argument("--end", required=True, help="ISO date YYYY-MM-DD (exclusive).")
    p.add_argument("--out", required=True,
                   help="Output JSONL. Resume-aware: existing PRs are kept and "
                        "their windows skipped via the sidecar .windows.jsonl log.")
    p.add_argument("--initial-window-days", type=int, default=1,
                   help="Starting window size in days (default 1). The recursive "
                        "splitter halves on saturation.")
    p.add_argument("--queries", nargs="*", default=None,
                   help="Subset of query labels to run (default: all). "
                        f"Available: {[q[0] for q in QUERIES]}.")
    p.add_argument("--query-extra", default=None,
                   help="Additional GitHub-search qualifier appended to every "
                        "query (e.g. 'path:Cargo.toml' or 'language:Rust'). "
                        "Use to narrow the search universe.")
    args = p.parse_args()

    if not os.environ.get("GITHUB_TOKEN"):
        print("WARNING: GITHUB_TOKEN not set. Search API allows only ~10 "
              "queries/min unauthenticated; this run will be very slow.",
              file=sys.stderr)

    start = dt.datetime.fromisoformat(args.start).replace(tzinfo=None)
    end = dt.datetime.fromisoformat(args.end).replace(tzinfo=None)
    if end <= start:
        print("ERROR: --end must be after --start", file=sys.stderr)
        return 1

    queries = QUERIES
    if args.queries:
        labels = set(args.queries)
        queries = [q for q in QUERIES if q[0] in labels]
        if not queries:
            print(f"ERROR: no matching query labels in {args.queries}",
                  file=sys.stderr)
            return 1
    if args.query_extra:
        queries = [(label, f"{tmpl} {args.query_extra}")
                   for label, tmpl in queries]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log_path = out_path.with_suffix(out_path.suffix + ".windows.jsonl")

    seen_windows = _seen_windows(log_path)
    seen_pr_keys = _seen_pr_keys(out_path)
    print(f"[resume] {len(seen_pr_keys)} PRs already on disk, "
          f"{len(seen_windows)} windows already complete",
          file=sys.stderr)

    initial_window = dt.timedelta(days=args.initial_window_days)

    out_fh = out_path.open("a")
    log_fh = log_path.open("a")
    try:
        total_new = 0
        for label, q_template in queries:
            for ws, we in _windows(start, end, initial_window):
                if (label, _iso(ws), _iso(we)) in seen_windows:
                    continue
                total_new += _process_window(
                    label, q_template, ws, we,
                    out_fh, log_fh, seen_pr_keys,
                )
        print(f"\ndone: wrote {total_new} new PRs to {out_path}",
              file=sys.stderr)
    finally:
        out_fh.close()
        log_fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
