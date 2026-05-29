# Running a Cargo batch — fresh-checkout runbook

From a freshly-cloned repo to verified entries. Written for a second
machine picking up the project: Lyuben's VM, a TU Delft CI runner, or
just this laptop reset.

Target audience: someone who has the repo + a recent Linux/macOS + Docker
+ a GitHub token, and wants to run the DS1 batch unattended.

## Prerequisites

| Thing | Version | Why |
| --- | --- | --- |
| Docker Desktop or Engine | 27.x+ (buildx v0.20+) | Fat-image builds use `buildx`, `--output type=image,rewrite-timestamp=true`, which needs a docker-container driver |
| Python | 3.11+ | `tomllib` stdlib module |
| Disk (Docker VM) | ≥ 80 GB free | Fat images are 2-3 GB each; thin-image build cache adds ~5 GB per candidate |
| Disk (host) | ≥ 30 GB free | Rebatchi rar archives + extracted JSON if you're re-running DS1 filter |
| GitHub PAT | read-only | 5000 req/hour vs 60 unauthenticated |

```bash
# Verify prerequisites
docker version --format '{{.Server.Version}}'   # want 27.x+
docker buildx version                           # want 0.20+
python3 --version                               # want 3.11+
df -h ~                                         # check available disk
```

## Step 1 — Clone + install

```bash
git clone --recurse-submodules <repo-url> rp2026 && cd rp2026/dep-updates-poc
pip install -e '.[cargo]'
```

`data/cargo/` is a git submodule pointing at
[`lyuben-todorov/dep-updates-rp-data`](https://github.com/lyuben-todorov/dep-updates-rp-data)
— the canonical v0.0.4 entry JSONs. If you cloned without
`--recurse-submodules`, run `git submodule update --init` now.

Dependencies pulled: `pydantic>=2`, `jsonschema`, `requests`,
`tomllib` (stdlib on 3.11+).

## Step 2 — Configure GitHub token

```bash
# Create a fine-grained PAT at github.com/settings/tokens with
# "public repo: read" scope. Paste below.
cat > .env <<'EOF'
GITHUB_TOKEN=ghp_...your-token-here...
EOF

# Source into the shell (need to do this in each new shell)
set -a; . .env; set +a
```

Verify:

```bash
curl -sf -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/rate_limit \
  | python3 -c "import json,sys; d=json.load(sys.stdin)['resources']['core']; print(f'remaining={d[\"remaining\"]}/{d[\"limit\"]}')"
# Expected: remaining=5000/5000
```

## Step 3 — Pick a candidate set

Two options.

### Option A: use the committed enriched JSONL (fastest)

The repo ships with `data/rebatchi/ds1_candidates_enriched.jsonl`
(2608 candidates, already filtered by `--require-cargo` and enriched
with `rust_msrv` + `post_commit_date`). Jump to step 4.

### Option B: regenerate from raw DS1

Only needed if you want a fresh enrichment (e.g., to pick up new
`edition` parsing logic). Costs ~4-5 hours and ~20k GitHub API calls.

```bash
# 1. Download DS1 (from Rebatchi's Zenodo drop, ~3.7 GB)
#    See ../../../docs/rebatchi.md for the URL + filter recipe.

# 2. Filter to candidates (streams the rar archives, keeps plausible
#    Cargo PRs)
python3 scripts/rebatchi_ds1_filter.py \
  --dataset-dir data/rebatchi/Dataset \
  --out data/rebatchi/ds1_cargo_candidates.jsonl

# 3. Enrich with GitHub API (SHAs, MSRV, commit date, --require-cargo filter)
python3 scripts/rebatchi_to_candidate.py \
  --jsonl data/rebatchi/ds1_cargo_candidates.jsonl \
  --require-cargo \
  --source rebatchi-ds1 \
  --out data/rebatchi/ds1_candidates_enriched.jsonl
```

`rebatchi_to_candidate.py` is **resume-aware**: point `--out` at an
existing file and it skips any `(repo, pr_number)` already enriched, so
a crashed run picks up where it left off without re-burning API calls.
For overnight runs, wrap it in `nohup` + redirect stderr.

### Option C: live-mine the recent 2024–2025 cohort (RQ3)

For the recent comparison cohort, mine dependency-update PRs across all
`language:Rust` GitHub repos in a date window. Three stages, chained by
`scripts/launch_live_mine.sh`:

```bash
# Defaults: 2024-01-01 → 2026-01-01, N=6000, seed=1337. Override via env.
START=2024-01-01 END=2026-01-01 N=6000 bash scripts/launch_live_mine.sh
# logs to data/live-mine/launch.log; output → data/live-mine/candidates_enriched.jsonl
```

What each stage does:

1. **`cargo_live_search.py`** — `/search/issues` with `language:Rust`,
   two title queries (`"Bump"` for Dependabot, `"update"` for Renovate),
   deduped. Auto-recursively splits the window on the Search API's
   1000-result cap; resume-aware via the sidecar `.windows.jsonl`. Stage
   1 alone can take several hours for a 2-year window (~1M raw hits).
2. **`cargo_live_sample.py`** — stratified-by-month sample of `--n`,
   dropping slash-named (GitHub Actions) bumps. Deterministic with
   `--seed`.
3. **`rebatchi_to_candidate.py --require-cargo`** — the same enrichment
   step as Option B, so the recent cohort is methodologically identical
   to the historical one.

Then continue from step 4 with
`--candidates data/live-mine/candidates_enriched.jsonl`.

> **Note on `path:Cargo.toml`**: the GitHub *issues*-search endpoint does
> not honor the `path:` qualifier (it's code-search only), so we narrow
> with `language:Rust` instead and rely on Stage 3's `--require-cargo`
> file-list check to drop non-Cargo PRs (GitHub Actions bumps, etc.) that
> ride along in Rust repos.

## Step 4 — Plan the fat images

Read-only. Shows which images you need to build.

```bash
python3 -m pipelines.cargo.cargo_plan_fat_images \
  --candidates data/rebatchi/ds1_candidates_enriched.jsonl
```

Expected output for the full DS1 (as of 2026-05-06, default
`max_sde_date=2025-12-31`):

```
Run parameters:
  max_sde_date:                  2025-12-31
Candidates read:                 2608
Buckets (rust milestone × year × debian):    6
Proposed fat images:             4
  existing reused:               0
  new builds:                    4
Covers candidates:               2607 / 2608  (100.0%)
```

The largest proposal (`1.49.0-buster-20210209`) serves 2405 candidates
— all 2018/2019/2020 buster buckets dedupe into this one tag because
their canonical SDEs all clamp up to `rust:1.49.0-buster`'s publication
date.

The planner prints exact `fat_image build` commands for each
to-be-built image. Flags to watch for:

- `pre_rust_base` — bucket's year ends before the rust base image was
  published on Docker Hub; SDE clamped forward to the publication
  date. Image will build, but ABI era will be off from the commit era.
  Expected for 2018-2020 buster buckets.
- `rust_base_unknown` — Docker Hub doesn't have a
  `rust:<ver>-<debian>` tag. Build will fail. Pick a different rust
  milestone or debian release.

## Step 5 — Build fat images

Each fat image takes ~5-10 minutes and uses ~3 GB disk. Run from the
planner's command list.

```bash
# Example for the full-DS1 plan:
python3 -m pipelines.cargo.fat_image build \
  --rust-version 1.56.0 --debian-release buster \
  --source-date-epoch 1634860800

python3 -m pipelines.cargo.fat_image build \
  --rust-version 1.56.0 --debian-release buster \
  --source-date-epoch 1640908800

# Each build auto-registers into docker/cargo-fat/index.json.

# Verify all expected images are present:
python3 -m pipelines.cargo.fat_image list
```

Skip the builds that show up as `existing reused` in the plan — those
are already in the index (e.g., `1.56.0-buster-20211022` is committed
seed-built).

**Optional**: `--include-gui=0` to skip the GTK/Tauri stack
(automatically disabled for bullseye/buster since those packages
don't exist there; bookworm+ gets GUI by default).

## Step 6 — Drive the batch

```bash
mkdir -p data/cargo-logs data/rebatchi/batch

nohup python3 -m pipelines.cargo.cargo_drive \
  --candidates data/rebatchi/ds1_candidates_enriched.jsonl \
  --out-dir data/cargo/ \
  --logs-dir data/cargo-logs/ \
  --state data/rebatchi/batch/drive-state.jsonl \
  --db data/pipeline.sqlite \
  --run-id ds1-$(date +%Y%m%d)-$(hostname) \
  --max-sde-date 2023-12-31 \
  --timeout 1800 \
  --parallel 5 \
  --host $(hostname) \
  >> data/rebatchi/batch/drive.log 2>&1 &
```

`nohup ... &` plus the `--state` JSONL means the run survives SSH
disconnects and resumes correctly on reconnect / restart.

Note: `--out-dir data/cargo/` writes into the submodule working tree.
To publish entries, `cd data/cargo && git commit + push` after the run
(or in batches during a long run). `--db` mirrors drive state +
reproduction attempts + entries into `data/pipeline.sqlite` for
querying; the JSONL remains authoritative for resume logic.

Per-candidate work:
- 5-15 min reproduction (pre + post commits inside Docker, `cargo test`).
  Heavy workspaces (libra/diem/solana) take much longer.
- Instant classification + assembly.

Full DS1 wall time on `crack` (16-core, 32 GiB) at `--parallel 5`:
**~2.5 days** observed (2608 candidates, 2026-05-08 → 2026-05-12),
peak ~50 candidates/hour with warm cache. Network-bound rather than
CPU-bound on a WiFi uplink.

Can stop + resume — on restart, candidates with a terminal status in
the state JSONL are skipped. SIGTERM/SIGINT trigger a graceful
shutdown that kills tracked containers cleanly (no orphan
`cargo-repro-*` containers under the docker daemon).

### Useful flags

Throughput / scheduling:

- `--parallel N` — thread-pool worker count. 5 is the sweet spot on
  a 32 GiB host with the per-container memory cap. 8 risks linker
  OOM on libra/diem-sized workspaces. See [Parallelism](#parallelism).
- `--shuffle` / `--shuffle-seed N` — shuffle the to-do list (after the
  resume skip-list filter) so expensive fork-clusters don't pile onto
  the same workers. `--shuffle-seed` makes it deterministic.
- `--cargo-cache DIR` — bind-mount a host dir at `/usr/local/cargo` in
  every reproducer container so candidates share the crates.io index +
  tarball cache (~3-5× less network). Default: `data/cargo-cache/` next
  to the state file; pass `""` to disable.
- `--timeout S` — per-stage timeout (default 1800 s). Heavy workspaces
  hit this; it's the dominant cause of the `TIMEOUT` failure class.

Reproduction contract / sanity:

- `--attempts N` — repeat each candidate's pre and post `cargo test`
  N times. Mixed pass/fail across attempts marks the candidate
  `ok_flaky` / `not_reproducible_flaky` (BUMP-style multi-run sanity;
  default 1). Wall-clock multiplies roughly by N.
- `--relax-locked` — on a `not_reproducible` outcome classified
  `LOCK_FILE_STALE`, retry once with `cargo generate-lockfile && cargo
  test --frozen` instead of `--locked`. Successful retries get the
  distinct status `ok_after_relock` (kept separate so the headline rate
  doesn't conflate strict-contract reproductions with
  lockfile-regenerated ones).

Bucketing / images:

- `--force-fat-image TAG` — bypasses the bucketer, routes every
  candidate to TAG. Used for hypothesis-driven retries (e.g.
  routing the OPENSSL_MISMATCH cohort to a stretch image regardless
  of commit date). TAG must already be registered in the index and
  present in the local Docker daemon.
- `--reassemble-stale` — when an existing entry's recorded fatImage
  doesn't match what the bucketer produces today, re-reproduce from
  scratch instead of parking the candidate as `entry_bucket_stale`.
- `--skip-preflight` — skip the fat-image presence check. Failures
  for missing images get recorded as `fat_image_missing`. Useful for
  partial runs where some images aren't built yet.

Post-hoc:

- `--reclassify` — skip reproduction entirely; re-read each candidate's
  `<short>-pre.log` under `--logs-dir`, re-run the Scheme-2 classifier,
  and upsert `drive_state_classifications`. Applies newer classifier
  rules to an old run without re-running cargo. Requires `--db` +
  `--run-id`.

### Status distribution you should expect

DS1-full (n=2608) under canonical bucketer, 2026-05-12:

- **46.4 %** `ok` — entries written. The reproducible cohort.
- **53.5 %** `not_reproducible` — pre-commit build failed; subdivided
  by the Scheme-2 classifier (`cargo_failure_classifier.py`, wired into
  the driver) into categories such as RUSTC_BITROT, RUNTIME_CRASH,
  OPENSSL_MISMATCH, NIGHTLY_REQUIRED, REPO_GONE, LOCK_FILE_STALE,
  NATIVE_DEP_MISSING, TEST_FAILURE, … — `schema/failure-taxonomy.md`
  Scheme 2 is the canonical list. Classification happens inline during a
  run; to re-apply newer rules to an old run's logs without
  re-reproducing, use `cargo_drive --reclassify` (see below).
- **0.1 %** `regenerate_mismatch` — entry already existed on disk
  but `cargo_regenerate` produced a different outcome on this host
  vs the entry's recorded category.

Within `ok`, `cargo_classifier.py` runs only on candidates whose post
commit fails (BUMP-style breaking). DS1-full produced ~20 fix-after-
update candidates and a similar order of breaking; the bulk of `ok`
rows are `non-breaking` (pre passed and post passed).

Non-breaking PRs *do* produce entries — they're data, not silence.
The pipeline emits an entry for every outcome whose pre/post pattern
matches a schema-defined category.

## Step 7 — Verify (optional)

Sanity-check a handful of produced entries by re-running them through
the regenerator:

```bash
for entry in data/cargo/cargo-*.json; do
  python3 -m pipelines.cargo.cargo_regenerate \
    --entry "$entry" --host $(hostname) --skip-tests
done
```

`--skip-tests` runs just the fingerprint check (fast). Drop the flag
to re-run the full `cargo test` pair (slow, rebuilds thin images).

Each run appends a `verifiedOn` record to the entry. Over time, the
entry accumulates cross-host verifications that become the paper's
reproducibility-rate evidence.

## Operational concerns

### Rate limits

GitHub: 5000 req/hour authenticated. `rebatchi_to_candidate.py`
burns ~5 per candidate — at 2608 candidates, you'll hit the limit
twice. The script has retry logic (`rate-limited, sleeping Ns`), so
just let it run; or split the input.

Docker Hub: 100 pulls/6-hour anonymous. Authenticate if building many
fat images at once (`docker login`).

### Disk

```bash
# Check Docker VM disk usage
docker system df

# Reclaim: delete stopped containers, dangling images, build cache
docker container prune -f
docker image prune -f
docker builder prune -af
```

Each fat image is ~3 GB; thin-image build cache adds ~5 GB per driver
run per candidate. Full DS1 can consume ~100 GB if you don't GC
periodically. Set a cron or run `docker builder prune -af` after every
N candidates.

### Resume

```bash
# Just re-run the same command. Terminal status in state JSONL =
# skip that candidate.
python3 -m pipelines.cargo.cargo_drive \
  --candidates ... --state data/rebatchi/batch/drive-state.jsonl ...
```

To re-process a candidate (e.g., after fixing the pipeline), delete its
line from the state file.

### Parallelism

`--parallel N` runs a `ThreadPoolExecutor` of N workers, each driving an
independent candidate while the Docker daemon handles the concurrent
containers. No manual sharding needed — one driver process, one `--state`
JSONL, one `--db`. DB writes are serialized under a lock when N>1.

Two constraints:

- **Pre-build all fat images first.** `--parallel N>1` is incompatible
  with `--build-missing-bases` (concurrent index writes would race). Run
  step 4/5 to completion before driving in parallel.
- **RAM-bound, not CPU-bound.** Each `cargo test` can use ~4-8 GB. On a
  32 GiB host, `--parallel 5` is the sweet spot; 8 risks linker OOM on
  libra/diem-sized workspaces. Good starting points: 4 on a 16-core box,
  8 on a 32-core box.

`--shuffle` (optionally with `--shuffle-seed`) spreads expensive
fork-clusters (libra/diem/solana families, or runs of adjacent PRs that
share heavy deps) across workers, so one 30-min linker doesn't block N
workers while its siblings queue behind it. Shuffle happens after the
resume skip-list filter, so it's resume-safe.

## Troubleshooting

### "fat image not present locally" / `EXIT_FAT_IMAGE_MISSING`

Either:
- The planner proposed a new build you haven't run yet → run it.
- You're re-driving entries from another host and the local index
  doesn't have the tag → use `--build-missing-bases` on
  `cargo_drive.py` / `cargo_regenerate.py` to build on demand.

### "environment fingerprint mismatch"

`cargo_regenerate.py` rebuilt the fat image and got a *different*
`/manifest/*` fingerprint than what the entry was validated against.
Likely causes, ordered by frequency:

1. The `docker/cargo-fat/Dockerfile` changed between when the entry was
   produced and now. Check `git log docker/cargo-fat/`.
2. The vendored `repro-sources-list.sh` was updated. Check its
   `sha256sum`.
3. `snapshot.debian.org` evicted the date being requested (rare but
   documented for very old buster snapshots).
4. Docker Buildx version skew changed layer metadata in ways the
   fingerprint picks up. Compare `docker buildx version` across hosts.

Next step: `cargo_regenerate.py` prints a per-file diff. Inspect which
manifest file changed; the name tells you the category of change.

### apt install fails on old buster fat images

`snapshot.debian.org` has spotty coverage for `buster-security` dates
before ~2020-Q2. If you need a fat image with `SOURCE_DATE_EPOCH <
2020-04-01` on buster, test the exact date first:

```bash
curl -sI http://snapshot.debian.org/archive/debian-security/YYYYMMDDT000000Z/dists/buster/updates/Release
```

404 → pick a later SDE.

### "Docker daemon out of space" mid-batch

```bash
docker system df                # see what's taking it
docker builder prune -af        # reclaims ~30 GB typically
docker image prune -f           # dangling images
```

If still full, shrink Docker's VM disk image in Docker Desktop
settings (trickier on Linux).

### "rust_base_unknown" warning in planner

Docker Hub doesn't have a `rust:X.Y.Z-<debian>` tag for that combination.
Check Hub manually:

```bash
curl -sI https://registry.hub.docker.com/v2/repositories/library/rust/tags/<tag>
```

Fix: pick a different Debian release, or pick a rust version that
existed on that release. See
<https://hub.docker.com/_/rust/tags> for available combinations.

## Expected artifacts at the end

```
data/cargo/                (submodule → dep-updates-rp-data)
  cargo-<hash>.json        one per ok-status candidate (hundreds to low thousands)

data/cargo-logs/
  <hash>-pre.log           cargo test output for pre commit
  <hash>-post.log          cargo test output for post commit
  <hash>-fix.log           only for fix-after-update entries

data/rebatchi/batch/
  drive-state.jsonl        per-candidate: {status, fat_image_tag, reason, timestamp}
  drive.log                full stderr stream

data/pipeline.sqlite       SQLite index (only if --db was set; gitignored)

docker/cargo-fat/
  index.json               append-only registry of built fat images
```

Cross-check at end of run:

```bash
# Status distribution
cut -d'"' -f6 data/rebatchi/batch/drive-state.jsonl | sort | uniq -c | sort -rn

# How many entries produced
ls data/cargo/cargo-*.json | wc -l

# Which fat images got used
jq -r '.fat_image_tag' data/rebatchi/batch/drive-state.jsonl | sort | uniq -c
```

## Shipping the results

Entries live in the `data/cargo/` submodule
(`lyuben-todorov/dep-updates-rp-data`). Publishing:

1. `cd data/cargo && git add cargo-*.json && git commit -m "Run <run-id>: N entries" && git push`.
2. Tag a release on the data repo for the Zenodo drop
   (`git tag v0.0.4-ds1 && git push --tags`); Zenodo picks up GitHub
   release tags automatically if the integration is enabled.
3. From the main repo, bump the submodule pointer + commit:
   `git add data/cargo && git commit -m "Bump data submodule to <tag>"`.

Images are never shipped — anyone with the repo (+ data submodule) can
rebuild them from `docker/cargo-fat/index.json` + the Dockerfile.

## When things finish

Next logical steps (not covered here):

1. Cross-host regenerate-verify on a different architecture (x86_64 if
   the batch ran on arm64, or vice versa). Each run appends to
   `verifiedOn[]`; after N hosts verify an entry, it's
   cross-host-reproducible.
2. Write up the reproduction rate per (year, milestone, debian) cell.
   `reproduction_attempts` in the SQLite index + `drive_state`'s
   `status` + `fat_image_tag` are the data you need.
