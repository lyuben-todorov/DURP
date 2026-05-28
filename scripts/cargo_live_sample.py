"""Stratified sample of search-API hits for the live-mine pipeline.

Stage 1.5. Reads `cargo_live_search.py`'s output (one row per matched PR),
filters to titles whose `Bump X from A to B` pattern parses cleanly with
a non-slashed dep name (drops GitHub-Actions-style bumps which use
`actions/checkout` etc.), dedupes by (owner, repo, number) across the
two source queries, and stratified-samples by month so the temporal
coverage is uniform across the input window.

Output schema is unchanged from Stage 1 — the same lowercase-keyed rows
that `rebatchi_to_candidate.py --jsonl --require-cargo` consumes.

Usage:
  python -m scripts.cargo_live_sample \\
      --in   data/live-mine/search_hits.jsonl \\
      --out  data/live-mine/search_sample.jsonl \\
      --n    6000 \\
      --seed 1337
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

BUMP_RE = re.compile(
    r"[Bb]ump\s+([A-Za-z0-9_\-\.]+)\s+from\s+([0-9][\w\.\-\+]*)\s+to\s+([0-9][\w\.\-\+]*)"
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--in", dest="in_path", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, required=True,
                   help="Total sample size. Distributed across months as "
                        "evenly as possible.")
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    rng = random.Random(args.seed)

    seen: set[tuple[str, str, int]] = set()
    by_month: dict[str, list[dict]] = defaultdict(list)
    n_read = n_kept = n_dedup_drop = n_bump_drop = 0

    with open(args.in_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_read += 1

            key = (r["owner"], r["repo"], int(r["number"]))
            if key in seen:
                n_dedup_drop += 1
                continue
            seen.add(key)

            m = BUMP_RE.search(r.get("title") or "")
            if not m or "/" in m.group(1):
                n_bump_drop += 1
                continue

            month = (r.get("created_at") or "0000-00")[:7]
            by_month[month].append(r)
            n_kept += 1

    months = sorted(by_month.keys())
    if not months:
        print("ERROR: no rows passed the BUMP-regex / dedupe filter",
              file=sys.stderr)
        return 1

    # Stratified sampling: target n/m per month, but redistribute slack
    # from underfilled months to others.
    target_per_month = args.n // len(months)
    chosen: list[dict] = []
    deficit = 0
    for m in months:
        rows = by_month[m]
        rng.shuffle(rows)
        take = min(target_per_month, len(rows))
        chosen.extend(rows[:take])
        if take < target_per_month:
            deficit += target_per_month - take

    # Top up with random sampling across the remainder pool.
    if len(chosen) < args.n:
        chosen_keys = {(r["owner"], r["repo"], int(r["number"])) for r in chosen}
        remainder: list[dict] = []
        for m in months:
            for r in by_month[m]:
                k = (r["owner"], r["repo"], int(r["number"]))
                if k not in chosen_keys:
                    remainder.append(r)
        rng.shuffle(remainder)
        need = args.n - len(chosen)
        chosen.extend(remainder[:need])

    chosen.sort(key=lambda r: r.get("created_at") or "")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for r in chosen:
            f.write(json.dumps(r) + "\n")

    per_month_chosen = defaultdict(int)
    for r in chosen:
        per_month_chosen[(r.get("created_at") or "0000-00")[:7]] += 1

    print(f"input: {n_read} rows", file=sys.stderr)
    print(f"  dedup drops: {n_dedup_drop}", file=sys.stderr)
    print(f"  non-Cargo (BUMP-regex) drops: {n_bump_drop}", file=sys.stderr)
    print(f"  passed: {n_kept}  ({len(months)} months)", file=sys.stderr)
    print(f"output: {len(chosen)} rows -> {out_path}", file=sys.stderr)
    print(f"per-month sample sizes:", file=sys.stderr)
    for m in months:
        print(f"  {m}: {per_month_chosen[m]} (pool {len(by_month[m])})",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
