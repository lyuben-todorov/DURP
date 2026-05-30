"""Build a candidates JSONL for the ds1-full-crack rerun.

Selects every candidate from drive_state under run_id='ds1-full-crack'
whose status='not_reproducible', joins back to the original
ds1_candidates_enriched.jsonl for the full candidate record (pre/post
commits, msrv, etc.), and writes to a fresh JSONL.
"""
import json, sqlite3, sys
from pathlib import Path

DB = "data/pipeline.sqlite"
SRC = "data/rebatchi/ds1_candidates_enriched.jsonl"
DST = "data/rebatchi/ds1_full_not_reproducible_rerun.jsonl"

conn = sqlite3.connect(DB)
nr_keys = {r[0] for r in conn.execute(
    "SELECT candidate_key FROM drive_state "
    "WHERE run_id=? AND status='not_reproducible'",
    ("ds1-full-crack",),
).fetchall()}
print(f"not_reproducible candidates in ds1-full-crack: {len(nr_keys)}", file=sys.stderr)

n_written = 0
with open(SRC) as src, open(DST, "w") as dst:
    for line in src:
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        key = f"{c['repo']}#{c['pr_number']}"
        if key in nr_keys:
            dst.write(line + "\n")
            n_written += 1

print(f"wrote {n_written} candidates to {DST}", file=sys.stderr)
if n_written != len(nr_keys):
    print(f"WARNING: {len(nr_keys) - n_written} candidates in DB not "
          f"found in source JSONL", file=sys.stderr)
