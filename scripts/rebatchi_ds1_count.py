"""Stream Rebatchi DS1 rar archives and count items, no filtering.

Verifies the upstream universe size claimed by the paper abstract:
"9,916,318 pull request-related issues made in 1,743,035 projects".

For each JSON page in each rar, sums:
  - total items in payload.items
  - items that are PRs (have pull_request key)
  - distinct projects (owner/repo)
  - bump-title hits (BUMP_RE on title)
  - cargo-toml-body hits

Mirrors rebatchi_ds1_filter.py's rar-streaming approach (extract one
rar at a time into /tmp scratch, scan, delete) so it works on the
same 3.7 GB archive set without needing the 250 GB uncompressed.

Usage:
  python -m scripts.rebatchi_ds1_count \\
      --dataset-dir /path/to/rebatchi-ds1/ \\
      --out data/rebatchi/ds1_universe_count.json

Optionally pass --rars to restrict to a subset (good for sampling
one rar to estimate the total).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterator

BUMP_RE = re.compile(
    r"[Bb]ump\s+([A-Za-z0-9_\-\.]+)\s+from\s+([0-9][\w\.\-\+]*)\s+to\s+([0-9][\w\.\-\+]*)"
)


def _iter_rar_json(rar_path: Path, scratch: Path) -> Iterator[Path]:
    scratch.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["unar", "-q", "-f", "-o", str(scratch), str(rar_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if r.returncode != 0:
        raise RuntimeError(f"unar failed on {rar_path}: {r.stderr.decode(errors='replace')}")
    yield from scratch.rglob("*.json")


def _project_of(item: dict) -> str | None:
    url = item.get("html_url") or (item.get("pull_request") or {}).get("html_url") or ""
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/(?:pull|issues)/\d+", url)
    return f"{m.group(1)}/{m.group(2)}" if m else None


def scan_json(path: Path, projects: set[str], stats: dict) -> None:
    try:
        with path.open("rb") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        stats["json_decode_failures"] += 1
        return
    items = payload.get("items") or []
    stats["total_items"] += len(items)
    for item in items:
        if item.get("pull_request"):
            stats["total_prs"] += 1
        title = item.get("title") or ""
        body = item.get("body") or ""
        if BUMP_RE.search(title):
            stats["bump_title_hits"] += 1
        if "Cargo.toml" in body or "Cargo.toml" in title:
            stats["cargo_toml_mention_hits"] += 1
        proj = _project_of(item)
        if proj:
            projects.add(proj)


def process_rar(rar_path: Path, projects: set[str], stats: dict, log) -> None:
    pages = 0
    with tempfile.TemporaryDirectory(prefix="ds1_count_", dir="/tmp") as td:
        scratch = Path(td)
        for jp in _iter_rar_json(rar_path, scratch):
            pages += 1
            scan_json(jp, projects, stats)
            if pages % 1000 == 0:
                log(rar_path.name, pages, stats)
    stats["json_pages_scanned"] += pages


def main() -> int:
    p = argparse.ArgumentParser(description="Count Rebatchi DS1 universe size (no filtering).")
    p.add_argument("--dataset-dir", required=True)
    p.add_argument("--out", required=True, help="JSON output with counts.")
    p.add_argument("--rars", nargs="*", default=None,
                   help="Subset of rar names (default: all Part *.rar). "
                        "Useful for sampling — count one rar, multiply by ~16.")
    args = p.parse_args()

    dsd = Path(args.dataset_dir)
    rars = [dsd / n for n in args.rars] if args.rars else sorted(dsd.glob("Part *.rar"))
    if not rars:
        print(f"no Part *.rar files in {dsd}", file=sys.stderr)
        return 1

    projects: set[str] = set()
    stats = {
        "json_pages_scanned": 0,
        "json_decode_failures": 0,
        "total_items": 0,
        "total_prs": 0,
        "bump_title_hits": 0,
        "cargo_toml_mention_hits": 0,
    }

    def _log(name, pages, s):
        print(f"  {name}: pages={pages} items={s['total_items']} "
              f"prs={s['total_prs']} bump={s['bump_title_hits']} "
              f"cargo={s['cargo_toml_mention_hits']}",
              file=sys.stderr)

    for rar in rars:
        print(f"=== {rar.name} ===", file=sys.stderr)
        try:
            process_rar(rar, projects, stats, _log)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            stats.setdefault("rar_errors", []).append({"rar": rar.name, "error": str(e)})
        print(f"  done: items so far={stats['total_items']} "
              f"projects={len(projects)}",
              file=sys.stderr)

    stats["distinct_projects"] = len(projects)
    stats["rars_processed"] = [r.name for r in rars]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, indent=2) + "\n")
    print(f"\nwrote {out}", file=sys.stderr)
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
