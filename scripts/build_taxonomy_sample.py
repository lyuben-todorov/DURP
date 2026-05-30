"""Build a stratified validation sample for the Scheme-2 failure taxonomy.

Produces the artifacts for an inter-rater (Cohen's κ) validation of the
automated reproduction-failure classifier (`cargo_failure_classifier.py`),
the way the build-failure taxonomy literature validates its schemes
(Rausch 2017; Vassallo 2017; Alfadel 2021).

Reads the DB **read-only** (safe to run while a drive is writing) and the
candidates JSONL the run was driven from. For each sampled candidate it
pulls the pre-log excerpt so a human can code from the log alone.

Outputs three files:
  - <out>/label_sheet.csv   — BLIND: candidate_key, short, log excerpt, and
                              empty `human_label` / `coder_note` columns. NO
                              classifier label. Hand this to coders.
  - <out>/answer_key.csv    — candidate_key -> classifier's (category,
                              subcategory, evidence). Kept separate so coders
                              don't see it; used by score_taxonomy_kappa.py.
  - <out>/logs/<key>.log    — the full pre-log per sampled candidate (so a
                              coder can read past the excerpt if needed).

Stratified by category: take min(n, --per-class) per category, so rare
classes (MSRV_TOO_LOW, OTHER) are fully represented. Deterministic --seed.

Run ON the host that has the DB + logs (crack):
  python3 scripts/build_taxonomy_sample.py \\
    --db data/pipeline.sqlite --run-id ds1-full-crack-r2 \\
    --candidates data/rebatchi/ds1_candidates_enriched.jsonl \\
    --logs-dir data/cargo-logs --out data/taxonomy-validation \\
    --per-class 15 --seed 1337
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
from pathlib import Path


def _connect_readonly(db_path: str) -> sqlite3.Connection:
    """Open the DB read-only so a concurrent drive's writes are never at risk."""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _excerpt(text: str, head: int = 12, tail: int = 40) -> str:
    """A compact log excerpt: first `head` + last `tail` non-blank lines.
    The terminal cause (which the codebook says to read bottom-up) is in the
    tail; the head gives context. Full log is also written to disk."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) <= head + tail:
        body = lines
    else:
        body = lines[:head] + ["    … (%d lines elided) …" % (len(lines) - head - tail)] + lines[-tail:]
    return "\n".join(body)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--db", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--candidates", required=True,
                   help="The candidates JSONL the run was driven from "
                        "(maps candidate_key -> post_commit short hash).")
    p.add_argument("--logs-dir", required=True)
    p.add_argument("--out", required=True, help="Output directory.")
    p.add_argument("--per-class", type=int, default=15,
                   help="Max candidates sampled per category (all if fewer).")
    p.add_argument("--seed", type=int, default=1337)
    args = p.parse_args()

    rng = random.Random(args.seed)
    out = Path(args.out)
    (out / "logs").mkdir(parents=True, exist_ok=True)

    # 1. candidate_key -> short hash, from the candidates JSONL.
    key_to_short: dict[str, str] = {}
    with open(args.candidates) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            c = json.loads(line)
            key_to_short[f"{c['repo']}#{c['pr_number']}"] = c["post_commit"][:8]

    # 2. Frozen snapshot of classifications (read-only). Capture the full
    #    classifier verdict now, so later reclassify waves can't shift the
    #    answer key under us.
    conn = _connect_readonly(args.db)
    rows = conn.execute(
        "SELECT candidate_key, category, subcategory, evidence "
        "FROM drive_state_classifications WHERE run_id = ?",
        (args.run_id,),
    ).fetchall()
    conn.close()
    if not rows:
        print(f"ERROR: no classifications for run_id {args.run_id}", file=sys.stderr)
        return 1

    by_cat: dict[str, list[tuple]] = {}
    for r in rows:
        by_cat.setdefault(r[1], []).append(r)

    # 3. Stratified sample.
    logs_dir = Path(args.logs_dir)
    per_run = logs_dir / args.run_id
    log_base = per_run if per_run.is_dir() else logs_dir

    sample: list[dict] = []
    n_missing_log = 0
    for cat in sorted(by_cat):
        bucket = list(by_cat[cat])
        rng.shuffle(bucket)
        take = bucket[: args.per_class]
        for candidate_key, category, subcategory, evidence in take:
            short = key_to_short.get(candidate_key)
            log_text = ""
            if short:
                for name in (f"{short}-{args.run_id}-pre.log", f"{short}-pre.log"):
                    pth = log_base / name
                    if pth.is_file():
                        log_text = pth.read_text(errors="replace")
                        break
            if not log_text:
                n_missing_log += 1
            # full log to disk for the coder
            safe = candidate_key.replace("/", "_").replace("#", "_")
            (out / "logs" / f"{safe}.log").write_text(log_text or "(no log on disk)")
            sample.append({
                "candidate_key": candidate_key,
                "short": short or "",
                "classifier_category": category,
                "classifier_subcategory": subcategory or "",
                "classifier_evidence": evidence or "",
                "excerpt": _excerpt(log_text) if log_text else "(no log on disk)",
            })

    rng.shuffle(sample)  # shuffle so coders can't infer class from ordering

    # 4. Blind label sheet (NO classifier columns).
    sheet = out / "label_sheet.csv"
    with sheet.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_key", "short", "human_label", "coder_note", "log_file", "excerpt"])
        for s in sample:
            safe = s["candidate_key"].replace("/", "_").replace("#", "_")
            w.writerow([s["candidate_key"], s["short"], "", "",
                        f"logs/{safe}.log", s["excerpt"]])

    # 5. Hidden answer key (the classifier's verdict), separate file.
    key = out / "answer_key.csv"
    with key.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["candidate_key", "classifier_category",
                    "classifier_subcategory", "classifier_evidence"])
        for s in sample:
            w.writerow([s["candidate_key"], s["classifier_category"],
                        s["classifier_subcategory"], s["classifier_evidence"]])

    # report
    print(f"run_id: {args.run_id}", file=sys.stderr)
    print(f"sampled {len(sample)} candidates across {len(by_cat)} categories "
          f"(per-class cap {args.per_class}, seed {args.seed})", file=sys.stderr)
    for cat in sorted(by_cat):
        print(f"  {cat:22} {min(len(by_cat[cat]), args.per_class):3} of {len(by_cat[cat])}",
              file=sys.stderr)
    if n_missing_log:
        print(f"WARNING: {n_missing_log} sampled candidates had no pre-log on disk",
              file=sys.stderr)
    print(f"\nwrote:\n  {sheet}\n  {key}\n  {out/'logs'}/ ({len(sample)} logs)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
