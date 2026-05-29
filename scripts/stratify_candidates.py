"""Reorder a candidate JSONL so any prefix is month-stratified.

The driver's `--limit N` takes the first N candidates in *file order*
(after the resume skip-list, before shuffle). So if we want each
`--limit`-bounded batch — and any partial run — to be representative
across the cohort's time span, the input file itself must be
interleaved by month rather than sorted.

This does a round-robin (deal-the-deck) interleave by `post_commit_date`
month: month buckets are filled, then we emit one candidate from each
non-empty bucket in rotation. A prefix of length N then contains an even
draw across all months present, proportional to each month's size.

Deterministic given the input (within-month order is preserved; no RNG).

Usage:
  python -m scripts.stratify_candidates \\
      --in  data/live-mine/candidates_enriched.jsonl \\
      --out data/live-mine/candidates_stratified.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--in", dest="in_path", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--date-field", default="post_commit_date",
                   help="Candidate field holding an ISO date; the YYYY-MM "
                        "prefix is the stratum. Default post_commit_date.")
    args = p.parse_args()

    by_month: dict[str, deque] = defaultdict(deque)
    n_read = no_date = 0
    with open(args.in_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            n_read += 1
            d = row.get(args.date_field)
            month = d[:7] if d else "0000-00"
            if not d:
                no_date += 1
            by_month[month].append(row)

    months = sorted(by_month)
    # Round-robin deal: one from each non-empty month per rotation, in
    # chronological month order, until all buckets drain.
    ordered = []
    active = [m for m in months if by_month[m]]
    while active:
        still = []
        for m in active:
            ordered.append(by_month[m].popleft())
            if by_month[m]:
                still.append(m)
        active = still

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in ordered:
            f.write(json.dumps(row) + "\n")

    print(f"read {n_read} candidates across {len(months)} month-strata "
          f"({no_date} without a date -> '0000-00')", file=sys.stderr)
    print(f"wrote {len(ordered)} interleaved -> {out_path}", file=sys.stderr)
    # Show the stratification of the first 600 (the planned batch size) as a
    # sanity check that a prefix really is spread across months.
    head = ordered[:600]
    head_months: dict[str, int] = defaultdict(int)
    for r in head:
        d = r.get(args.date_field)
        head_months[d[:7] if d else "0000-00"] += 1
    print("first-600 month spread:", file=sys.stderr)
    for m in sorted(head_months):
        print(f"  {m}: {head_months[m]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
