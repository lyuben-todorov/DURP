#!/usr/bin/env bash
# Drive a ~24h batch of the 2024-2025 live-mine cohort (RQ3 recent).
#
# Design (see docs/findings/live-mine-rq3-prep.md):
#   - Input is PRE-STRATIFIED (scripts/stratify_candidates.py) so any
#     prefix is even across months. The driver's --limit takes the first
#     N in file order, so a stratified file makes each --limit batch
#     representative.
#   - One stable --state file. Re-running this script processes the NEXT
#     BATCH automatically: candidates with a terminal record in --state
#     are skipped, so --limit then takes the next N unprocessed.
#   - Resume-safe within a batch: a crash/kill mid-batch, re-run, it skips
#     the done ones and continues.
#
# Batching:
#   Batch 1:  bash scripts/launch_livemine_drive.sh
#   Batch 2:  bash scripts/launch_livemine_drive.sh   (same command — next 600)
#   ...until the state file covers all 5401.
#
# Tunables via env: BATCH (default 600), PARALLEL (8), RUN_ID, MAX_SDE.

set -u
cd /home/ltodorov/rp2026
[ -f .env ] && set -a && . ./.env && set +a

BATCH="${BATCH:-600}"
PARALLEL="${PARALLEL:-8}"
RUN_ID="${RUN_ID:-livemine-2024-2025-crack}"
MAX_SDE="${MAX_SDE:-2025-12-31}"
SEED="${SEED:-1337}"

SRC="data/live-mine/candidates_enriched.jsonl"
STRAT="data/live-mine/candidates_stratified.jsonl"
STATE="data/cargo-logs/drive-${RUN_ID}.jsonl"
OUT="/tmp/livemine-entries"          # entries land here; NOT the data submodule
LOG="data/live-mine/drive-${RUN_ID}.log"

mkdir -p "$OUT" data/cargo-logs

echo "=== livemine drive $(date -u +%FT%TZ) ===" | tee -a "$LOG"

# 0. Guard: refuse to run if another cargo_drive is active (shared Docker
#    daemon + pipeline.sqlite; concurrent heavy drives hit DB-lock /
#    disk contention — see ds1-full-r2-findings.md parallel=8 TIMEOUTs).
if pgrep -f "cargo_drive" | grep -qv "$$"; then
  echo "ABORT: another cargo_drive is running. Wait for it to finish." | tee -a "$LOG"
  pgrep -af "cargo_drive" | tee -a "$LOG"
  exit 1
fi

# 1. Stratify once (idempotent; only if the stratified file is missing or
#    older than the source).
if [ ! -f "$STRAT" ] || [ "$SRC" -nt "$STRAT" ]; then
  echo "[stratify] building $STRAT" | tee -a "$LOG"
  .venv/bin/python3 -m scripts.stratify_candidates --in "$SRC" --out "$STRAT" >>"$LOG" 2>&1 \
    || { echo "stratify failed" | tee -a "$LOG"; exit 1; }
fi

# 2. Build the 5 fat images the cohort needs, if absent. The planner prints
#    exact build commands; we let the driver's preflight tell us what's
#    missing rather than hardcode. Build via cargo_plan_fat_images first
#    so a verifier sees the plan, then build_missing on the driver is OFF
#    (we want bases pre-built for --parallel > 1).
echo "[plan] fat images for the cohort:" | tee -a "$LOG"
.venv/bin/python3 -m pipelines.cargo.cargo_plan_fat_images \
  --candidates "$STRAT" --max-sde-date "$MAX_SDE" 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "NOTE: build any images the plan lists as 'new builds' before driving" | tee -a "$LOG"
echo "      with --parallel > 1 (index-write race forbids --build-missing-bases)." | tee -a "$LOG"
echo "      Build commands are printed above. Re-run this script after building." | tee -a "$LOG"

# 3. The actual drive. nohup so it survives disconnects; --parallel from env.
#    The driver runs its own preflight (image-presence check) at startup and
#    exits non-zero listing any missing image — that is the signal to build
#    the images the plan printed above, then re-run this script. We do NOT
#    pass --build-missing-bases (incompatible with --parallel > 1).
echo "[drive] batch=$BATCH parallel=$PARALLEL run_id=$RUN_ID" | tee -a "$LOG"
nohup .venv/bin/python3 -m pipelines.cargo.cargo_drive \
  --candidates "$STRAT" \
  --limit "$BATCH" \
  --out-dir "$OUT" \
  --logs-dir data/cargo-logs \
  --state "$STATE" \
  --db data/pipeline.sqlite \
  --run-id "$RUN_ID" \
  --max-sde-date "$MAX_SDE" \
  --shuffle --shuffle-seed "$SEED" \
  --relax-locked \
  --parallel "$PARALLEL" \
  --host crack \
  >>"$LOG" 2>&1 < /dev/null &

echo "launched pid=$! ; tail -f $PWD/$LOG" | tee -a "$LOG"
