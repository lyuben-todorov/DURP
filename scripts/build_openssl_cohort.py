"""Build the OPENSSL_MISMATCH sub-cohort from ds1-full-crack-r2."""
import json, sqlite3, sys
from pathlib import Path

DB = "data/pipeline.sqlite"
SRC = "data/rebatchi/ds1_candidates_enriched.jsonl"
DST = "data/rebatchi/ds1_openssl_stretch_cohort.jsonl"

conn = sqlite3.connect(DB)
keys = {r[0] for r in conn.execute(
    "SELECT a.candidate_key FROM drive_state a "
    "JOIN drive_state_classifications c USING (run_id, candidate_key) "
    "WHERE a.run_id='ds1-full-crack-r2' AND c.category='OPENSSL_MISMATCH'"
).fetchall()}
print(f"openssl cohort size: {len(keys)}", file=sys.stderr)

n_written = 0
with open(SRC) as src, open(DST, "w") as dst:
    for line in src:
        line = line.strip()
        if not line:
            continue
        c = json.loads(line)
        if f"{c['repo']}#{c['pr_number']}" in keys:
            dst.write(line + "\n")
            n_written += 1
print(f"wrote {n_written} candidates to {DST}", file=sys.stderr)
