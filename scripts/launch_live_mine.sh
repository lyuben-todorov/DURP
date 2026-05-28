#!/usr/bin/env bash
# Live-mine pipeline launcher.
# Stage 1: search Github for dependency-update PRs in language:Rust repos
#          across the date window, both "Bump" and "update" title queries.
# Stage 1.5: stratified-sample N candidates, monthly stratification, drops
#            slash-named (GitHub Actions style) bumps.
# Stage 3: enrich via rebatchi_to_candidate.py --require-cargo, which does
#          the Cargo-only file-list check + commit/MSRV/date resolution.
#
# Outputs land in data/live-mine/. Safe to re-run — Stage 1 resumes from
# its windows log; Stage 1.5 is deterministic with the same seed; Stage
# 3 will overwrite its output.

set -u
cd /home/ltodorov/rp2026

[ -f .env ] && set -a && . ./.env && set +a

START="${START:-2024-01-01}"
END="${END:-2026-01-01}"
N="${N:-6000}"
SEED="${SEED:-1337}"

OUT_DIR="data/live-mine"
mkdir -p "$OUT_DIR"

LOG="$OUT_DIR/launch.log"
SEARCH_OUT="$OUT_DIR/search_hits.jsonl"
SAMPLE_OUT="$OUT_DIR/search_sample.jsonl"
ENRICHED_OUT="$OUT_DIR/candidates_enriched.jsonl"

echo "=== launch live-mine $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"
echo "window: $START -> $END   sample N=$N   seed=$SEED" >> "$LOG"

run() {
  echo "" >> "$LOG"
  echo "[$(date -u +%H:%M:%S)] $*" >> "$LOG"
  "$@" >> "$LOG" 2>&1
  rc=$?
  echo "[$(date -u +%H:%M:%S)] -> exit $rc" >> "$LOG"
  return $rc
}

(
  run .venv/bin/python3 -m scripts.cargo_live_search \
    --start "$START" --end "$END" \
    --out "$SEARCH_OUT" \
    --query-extra "language:Rust" \
  || { echo "Stage 1 (search) failed; aborting" >> "$LOG"; exit 1; }

  run .venv/bin/python3 -m scripts.cargo_live_sample \
    --in "$SEARCH_OUT" \
    --out "$SAMPLE_OUT" \
    --n "$N" --seed "$SEED" \
  || { echo "Stage 1.5 (sample) failed; aborting" >> "$LOG"; exit 1; }

  run .venv/bin/python3 -m scripts.rebatchi_to_candidate \
    --jsonl "$SAMPLE_OUT" \
    --out "$ENRICHED_OUT" \
    --source "live-gh-2024-2025" \
    --require-cargo \
  || { echo "Stage 3 (enrichment) failed; aborting" >> "$LOG"; exit 1; }

  echo "" >> "$LOG"
  echo "=== complete $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >> "$LOG"
  echo "search hits   : $(wc -l < "$SEARCH_OUT")" >> "$LOG"
  echo "sampled       : $(wc -l < "$SAMPLE_OUT")" >> "$LOG"
  echo "enriched      : $(wc -l < "$ENRICHED_OUT")" >> "$LOG"
) &

echo "launched pid=$!"
echo "log: $LOG"
echo "tail with: ssh crack 'tail -f $PWD/$LOG'"
