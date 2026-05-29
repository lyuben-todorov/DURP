"""Build the NATIVE_DEP_MISSING recovery sub-cohort from ds1-full-crack-r2.

Mirror of build_openssl_cohort.py. Carves the candidates the round-2 run
classified NATIVE_DEP_MISSING into a JSONL the driver can re-run under
rebuilt fat images (the stale 1.39 stretch/buster images predated the
round-2 native-dep apt layer; libsfml-dev was also added for the SFML
cases). Run with a separate run_id so results stay a measured delta, not
a silent edit to the parent headline.
"""
import json, sqlite3, sys

DB = "data/pipeline.sqlite"
SRC = "data/rebatchi/ds1_candidates_enriched.jsonl"
DST = "data/rebatchi/ds1_native_dep_cohort.jsonl"

conn = sqlite3.connect(DB)
keys = {r[0] for r in conn.execute(
    "SELECT a.candidate_key FROM drive_state a "
    "JOIN drive_state_classifications c USING (run_id, candidate_key) "
    "WHERE a.run_id='ds1-full-crack-r2' AND c.category='NATIVE_DEP_MISSING'"
).fetchall()}
print(f"native-dep cohort size: {len(keys)}", file=sys.stderr)

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
if n_written != len(keys):
    print(f"WARNING: {len(keys) - n_written} cohort keys not found in {SRC}",
          file=sys.stderr)
