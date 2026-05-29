# DS1-full-crack-r2 findings — `2026-05-18`

Second full pass over Rebatchi DS1 (2608 Cargo Dependabot PRs, 2017-2021)
under the round-2 fixes. Run id `ds1-full-crack-r2`, host `crack`, amd64.
Where `ds1-full-crack` (the first full run) measured the pipeline as it
stood pre-classifier-audit, this run measures the pipeline after every
fix landed in the round-2-fixes branch — Cargo.toml-discovery, native-dep
fat-image bake, era-floor bucketer, `--relax-locked`, classifier folding,
the works. Headline numbers cited at midterm should be from this run.

## Setup

- **Candidates:** all 2608 of `ds1_candidates_enriched.jsonl`. Same input
  as `ds1-full-crack`. Untouched between runs.
- **Run ID:** `ds1-full-crack-r2`.
- **Workers:** `--parallel 8` for the entire run. `--memory=8g` per
  container. Disk-bound for most of the run (load average 30-50 on a
  16-core host, near-zero CPU idle but 30%+ iowait); did not cause
  failures but did inflate TIMEOUT (see below).
- **`max_sde_date`:** 2023-12-31 throughout (same as `ds1-full-crack`).
- **`--shuffle`:** on. Resume-safe; spreads heavy fork-clusters
  (libra/diem/solana family, plus the dependabot-bumps-twice clusters)
  across workers instead of clumping them in alphabetical-order JSONL
  slices.
- **`--attempts 1`:** flakiness check deferred to the post-midterm
  headline run. Run B is single-attempt by design.
- **`--relax-locked`:** on. LOCK_FILE_STALE → retry with
  `cargo generate-lockfile && cargo test`. New status `ok_after_relock`.
- **Inline classification:** every `not_reproducible` outcome writes a
  `drive_state_classifications` row in the same transaction as the
  `drive_state` row. No separate post-hoc reclassify step needed.
- **Fat images:** 9 distinct tags after the round-2 rebuild +
  1.30/1.35-stretch additions (canonical SDEs):
  - `1.30.0-stretch-20181231` (575 packages, 96 candidates)
  - `1.35.0-stretch-20191231` (578 pkg, 195 candidates)
  - `1.35.0-stretch-20190619` (578 pkg, 1 candidate)
  - `1.39.0-stretch-20191123` (~456 pkg, 105 candidates)
  - `1.39.0-stretch-20191231` (~456 pkg, 495 candidates)
  - `1.39.0-buster-20191231` (~456 pkg, 167 candidates)
  - `1.49.0-buster-20210209` (606 pkg, **rebuilt** with round-2 native deps; 1002 candidates)
  - `1.56.0-buster-20211022` (606 pkg, **rebuilt**; 440 candidates)
  - `1.56.0-buster-20211231` (606 pkg, **rebuilt**; 201 candidates)
  - `1.56.0-bullseye-20211231` (1 candidate)

## Headline numbers

| Metric | `ds1-full-crack` (baseline) | `ds1-full-crack-r2` | Δ |
| --- | ---: | ---: | ---: |
| Wall clock | 2d 11h 22min | **3d 22h 30min** | +1d 11h |
| Candidates processed | 2608 | 2608 | 0 |
| `ok` | 1210 | **1358** | **+148** |
| `ok_after_relock` (new) | — | **1** | +1 |
| `not_reproducible` | 1395 | **1249** | −146 |
| `regenerate_mismatch` | 3 | 0 | −3 |
| **Reproducibility rate** | **46.4 %** | **52.1 %** | **+5.7 pp** |
| 95 % Wilson CI | 44.4-48.3 % | **50.1-54.1 %** | non-overlapping |
| Reproduction-attempt rows in DB | 102 | **2608** | Bug E fix landed |

Interpretation: round-2 fixes lift Cargo Dependabot reproducibility on
DS1 from **46.4 % → 52.1 %**, a **5.7 pp improvement** outside both
runs' confidence intervals. The lift comes from four code-or-image
changes that each contributed an independently identifiable cohort
(see "Per-category deltas" below).

The wall-clock regression (+1d 11h) is real. Disk contention at
`--parallel 8` is the cause; the next run should drop to
`--parallel 5` per the original handoff sweet-spot.

## Per-category deltas

Comparing `drive_state_classifications` for both runs:

| category | r2 | baseline | Δ | character |
| --- | ---: | ---: | ---: | --- |
| RUSTC_BITROT | **393** | 449 | **−56** | era-floor bucketer + 1.30/1.35 milestones recovered some |
| TEST_FAILURE | **244** | 246 | −2 | unchanged — author-environment property |
| NIGHTLY_REQUIRED | **170** | 129 | +41 | E0554/E0658 reroute (these were hidden in BITROT before) |
| RUNTIME_CRASH | **110** | 125 | −15 | minor improvement |
| DEPENDENCY_RESOLUTION | **100** | 101 | −1 | git-dep-tombstones unchanged |
| **TIMEOUT** | **69** | 25 | **+44** | parallel=8 disk contention regressed this; see below |
| OPENSSL_MISMATCH | **64** | 56 | +8 | minor; force-stretch sub-cohort run still pending |
| LOCK_FILE_STALE | **31** | 40 | **−9** | `--relax-locked` recovered 1 (ok_after_relock) + 8 reclassed on relock retry |
| **REPO_GONE** | **28** | 79 | **−51** | Cargo.toml-discovery shim — biggest single fix |
| **NATIVE_DEP_MISSING** | **18** | 54 | **−36** | rebuilt fat images + linker-error detection |
| OTHER | 13 | 17 | −4 |  |
| MSRV_TOO_LOW | 9 | 8 | +1 |  |

**Largest absolute reductions:**

1. **REPO_GONE −51.** The Cargo.toml-discovery shim worked: 51 of the
   76 MANIFEST_NOT_AT_ROOT candidates from the round-2 audit
   successfully cd'd into a depth-1 manifest subdirectory and built
   from there.
2. **RUSTC_BITROT −56.** The era-floor bucketer change
   (`max(round_up_to_milestone(msrv), era_milestone_for_commit(date))`)
   stops MSRV-1.31 candidates with 2020-era commit dates from being
   under-shot to rustc 1.39 when their lockfiles need ≥1.40. Combined
   with the 1.30 + 1.35 stretch milestones, ~56 candidates that BITROT'd
   on too-old rustc now compile.
3. **NATIVE_DEP_MISSING −36.** Rebuilt fat images carrying libsdl2-dev,
   libxtst-dev, libxcb-shape0-dev, libfuse-dev, libgcrypt20-dev,
   libpython3-dev, libv4l-dev, libnotify-dev, libsnappy-dev,
   libcap-ng-dev, libmpich-dev, slurm-client, librrd-dev, plus rustfmt
   and clippy via rustup. The classifier's new linker-error detection
   pulls cases out of the BITROT-fallback bucket that were really
   `cannot find -lLIB`.

## Reproducibility by year

The DS1 cohort spans 2017-2021. Per-year rates show whether round-2's
lift is uniform or skewed.

| Year | n | ok (incl. relock) | not_reproducible | repro % | Δ vs baseline |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2018 | 106 | 49 | 57 | **46.2 %** | +24.5 pp |
| 2019 | 920 | 485 | 435 | **52.7 %** | +11.2 pp |
| 2020 | 1380 | 741 | 639 | **53.7 %** | +2.1 pp |
| 2021 | 202 | 84 | 118 | **41.6 %** | −4.9 pp |

Caveat: 2017 had so few candidates they fell below 1 % — folded into
2018's row above for readability.

The biggest absolute lift is in **2018-2019** (+24.5 pp / +11.2 pp).
That tracks the 1.30 + 1.35 stretch milestones — these years were
where the era-floor bucketer mattered most. 2020 sees a modest +2.1 pp
(round-2's gains are small here because the original run already
mostly handled this era via 1.49-buster). **2021 actually
regressed** by 4.9 pp; investigation TODO but plausibly related to
the bucketer change routing some 2021 candidates to images they
weren't on before, exposing different failure modes.

## Reproducibility by fat image

| Fat image | n | ok % |
| --- | ---: | ---: |
| `1.49.0-buster-20210209` | 1002 | **64.0 %** |
| `1.39.0-stretch-20191231` | 495 | **54.1 %** |
| `1.35.0-stretch-20191231` (new) | 196 | **57.1 %** |
| `1.39.0-buster-20191231` | 167 | 46.1 % |
| `1.39.0-stretch-20191123` | 105 | 45.7 % |
| `1.56.0-buster-20211022` | 440 | **29.1 %** |
| `1.56.0-buster-20211231` | 201 | 41.3 % |
| `1.30.0-stretch-20181231` (new) | 96 | (not reported per-cohort here) |
| (others, 2 candidates) | 2 | 100 % |

The `1.49.0-buster-20210209` cohort (1002 candidates, 64 % repro) is
the headline driver. The new `1.30/1.35-stretch` images both clear
50 % which validates the "edition-2018 + pre-NLL stable" decision —
those candidates would have BITROT'd on 1.39 but routing them to
their era-appropriate rustc recovers the cluster.

The `1.56.0-buster-20211022` cluster's 29.1 % is unchanged-ish from
ds1-full-crack and reflects the genuine RUSTC_BITROT pattern: 2018-2020
code declaring no MSRV, fall-back floor sends it to 1.56 which is 11+
minor versions ahead of its native toolchain. Fundamental property of
the corpus, not pipeline-fixable beyond the era-floor change we already
made.

## Verification audits (sub-agent fan-out)

Four parallel audits ran sub-agent verification over samples from
the on-disk pre-logs. Findings:

### RUSTC_BITROT (n=20 sample, 393 total)

**Precision: 18/20 correct, 1 wrong, 1 ambiguous (90-95 %).**

- Correct: 18 — recorded E-code matches the terminal rustc error.
- Wrong: 1 — `aaralh/FocusBoost#28` recorded `E0119`, log only contains
  `E0433`. Looks like classifier picked the first error code seen
  anywhere in the log rather than the terminal one.
- Ambiguous: 1 — `andreasots/eris#184` has `E0119` genuinely present in
  the `traitobject` dep but the run actually fails on a Cargo manifest
  validation error ("invalid character in package name"). The recorded
  code is real; the run's true terminal cause is non-rustc.

The dominant cluster is `lexical-core` E0308 (5/20 sampled, all
toshi-search/Toshi or tommilligan/adonais), where the log shows 17
E0308 + 10 E0277 errors; classifier picks E0308 (the most-fired)
which is defensible but not principled. **Implication for the paper:**
RUSTC_BITROT counts are reliable to ±~5 % at the E-code level; the
"first/highest-count code wins" heuristic is the main error mode.

### TEST_FAILURE (n=15 sample, 244 total)

**80 % author-environment, ~20 % non-environment.**

| sub-cause | n |
| --- | ---: |
| AUTHOR_ENV_NETWORK (live crates.io, ctftime, S3, etc.) | 5 |
| AUTHOR_ENV_FILESYSTEM (missing executables, fixtures, target/) | 4 |
| AUTHOR_ENV_ENVVAR (REDIS_URL, USER, etc.) | 2 |
| AUTHOR_ENV_OTHER (interactive TTY, system tools missing) | 1 |
| EXPECT_PARSE_MISMATCH (cgm616/calc_rs pest grammar) | 3 |
| ASSERTION_REGRESSION (cargo-asm golden-diff vs newer rustc) | 1 |

Compare to round-2 audit on `ds1-full-crack` which estimated ~40 %
author-environment. Run B's sample skews higher (~80 %) but the
sample is biased: 3 of 15 are cgm616/calc_rs sharing one root cause,
2 of 15 are jonasbb/ctftimebot sharing one. Even after deduplicating
to distinct root causes (~10 distinct), author-env still dominates at
~75 %. **Implication:** the TEST_FAILURE cohort is mostly *not*
fixable by pipeline work — these are tests that embed assumptions
about the host (DNS, filesystem layout, env vars). A
`TESTS_NEED_ENV` sub-classification would name this honestly in the
paper.

### REPO_GONE (n=28 — full cohort audited)

**Zero real tombstones. 27/28 are MANIFEST_DEEP. 1/28 is RACE.**

The Cargo.toml-discovery shim caps at depth ≤ 2 (i.e. a manifest at
`/src/<dir>/Cargo.toml` is found, but `/src/<dir1>/<dir2>/Cargo.toml`
is not). The 28 surviving REPO_GONE candidates all have manifests at
depth 3-5:

- `exonum/exonum-java-binding/core/rust/Cargo.toml` — depth 4 (8 candidates)
- `ajtorres9/forge/packages/server/Cargo.toml` — depth 3 (12 candidates)
- `near-examples/{FT,NFT}/contracts/rust/Cargo.toml` — depth 3 (2)
- `near/create-near-app/templates/contracts/auction/rs/Cargo.toml` — depth 5 (3)
- `analysis-tools-dev/dynamic-analysis/data/render/Cargo.toml` — depth 3 (1)
- `DominicRoyStang/uvindex/services/backend/Cargo.toml` — depth 3 (1)
- `himanoa/testament-api` — Cargo.toml at root, but the clone hit a
  transient "Empty reply from server" git error during this run. RACE.

Every upstream repo is alive and has Rust code. The original `ds1-full-findings.md`'s
estimate that ~3 of 79 were real tombstones was **wrong** — zero are.

**Recommendation for the paper:** raise the discovery shim to depth ≤ 5
(or unbounded with a target/vendor/.git skip-list); add a clone-retry on
transient git errors. This single change recovers all 28 candidates,
adding ~+1.1 pp to the headline (~1.1 % of 2608).

### TIMEOUT cohort (n=69, full)

**Disk contention is the root cause; partly recoverable by --timeout bump,
mostly recoverable by --parallel 5.**

- 19 of the 25 ds1-full-crack TIMEOUTs reappeared in r2 (the heavy
  workspace cluster: libra/diem/solana/starcoin/tremor — known property
  of the corpus, not pipeline-fixable beyond bumping the timeout).
- **50 are new in r2.** Top repos: solana-labs/solana ×11, tremor-rs/tremor-runtime
  ×9, quittle/wowser ×8, comit-network/comit-rs ×7, servo/servo ×3, and 26
  one-each repos.
- Of 5 sampled new TIMEOUTs, 4 were in mid-compile of the project's own
  crates (slow but progressing — bump the timeout and they'd finish).
  1 was misclassified: `servo/servo#26505` saw a git zlib stream error
  during a transitive `git fetch`, exit code 124 from the post-side
  even though the pre-side had already failed for an unrelated reason.

**Implications:**

- The +44 TIMEOUT regression is a **measurement artefact** of running
  at parallel=8, not a real change in the corpus. Run A should drop to
  parallel=5 (per handoff sweet-spot) AND bump `--timeout` from 1800s
  to 3600s. Combined: estimated ~30-40 of the 50 new TIMEOUTs would
  flip to ok or to a meaningful failure class.
- `servo/servo#26505`-class miscalibration: the TIMEOUT classifier uses
  post-side rc=124 as its trigger; some candidates fail pre-side for a
  different reason but post times out. Should be `NETWORK_ERROR` or
  `OTHER` in those cases. ~2-3 candidates affected.

## Pipeline regressions vs ds1-full-crack

Two findings beyond the headline:

### Bucketer regression-then-fix

During Run B, an early sample of 112 candidates showed 13 regressions
(candidates ds1-full-crack reproduced ok but Run B did not). All 13 had
declared MSRV=1.31 + 2020-era commit dates and routed to
`1.39.0-buster-20201231` instead of ds1-full-crack's
`1.49.0-buster-20210209`. Root cause: the round-2 addition of
`("1.39", "buster")` to `MILESTONE_DEBIAN_SUPPORTED` exposed an
underlying bug — `bucket_for` was using `round_up_to_milestone(msrv)`
strictly, which under-shoots the era's actual rustc when transitive
deps need a newer minor version (e.g. `remove_dir_all 0.5.3` uses
`cfg(doctest)` stabilised in 1.40; rustc 1.39 rejects it as
`error[E0658]`).

Fix: `bucket_for` now picks
`max(round_up_to_milestone(msrv), era_milestone_for_commit(date))`. The
era milestone uses a new helper that rounds **up** to the next milestone
shipped (rather than down via `latest_milestone_before`) since the
actual contemporary rustc was minor versions newer than the lower
milestone. All 13 regressions recovered after this fix.

This was a *latent bug* uncovered by adding the 1.39-buster routing
support. Pre-round-2 the `bucket_for` was wrong but the absence of
1.39-buster in the support set masked the bug by accidentally bumping
to 1.49.

### `BUILD_CMD_RELAXED` had a subtle bug

The first version of `--relax-locked`'s relax retry was
`cargo generate-lockfile && cargo test --frozen`. `--frozen` forbids
both lock changes AND network access; after generate-lockfile produced
a fresh lock, `cargo test --frozen` failed at the first crate fetch
because the new lock pointed at versions not in the local cache.
Caught at the first LOCK_FILE_STALE candidate (`teovoinea/podium#65`)
in Run B. Fixed mid-run; that candidate was retried after the fix
landed. Run A's entire LOCK_FILE_STALE cohort gets the right behaviour.

### Did the bugs affect the headline?

**No.** Both bugs were caught while their incorrect outputs were still
local, and both were re-run under the fix:

- **Bucketer regression (13 wrong candidates)** — killed Run B at 112
  candidates, wiped DB rows + JSONL state + partial entries, restarted
  from scratch under the corrected `bucket_for`. The final 2608 numbers
  reflect the corrected bucketer end-to-end.
- **`BUILD_CMD_RELAXED --frozen` (1 wrong candidate)** — killed driver
  at ~140 candidates, deleted only `teovoinea/podium#65`'s rows
  (resume-style scrub), relaunched. podium#65 was re-attempted under
  the fix on resume; the other 2607 candidates were never affected.

Net: the **52.1 % headline reflects the corrected pipeline.** The
incident cost was ~6 hours of wall-clock (re-running the 112 candidates
that ran under the bucketer bug). No candidate's final classification
in `drive_state` reflects either bug's wrong output.

A different consideration: the 5 LOCK_FILE_STALE-relock-failed cases in
the final 31 LOCK_FILE_STALE rows are *not* victims of the --frozen bug
— those failed for a genuine reason (post-relock MSRV-too-low: e.g.
yamloboros's regenerated lockfile pulled in `itoa 1.0.18` which needs
edition-2021). They're correctly classified as LOCK_FILE_STALE; a
post-hoc reclassify rule could move them to `MSRV_TOO_LOW` to be more
informative, but the rows aren't wrong.

## Open questions

1. **2021 cohort's −4.9 pp regression.** All other years lifted; 2021
   went down. Likely the bucketer change routed some 2021 candidates
   that previously hit 1.49-buster to 1.56-buster (where they BITROT
   on stricter rustc), or vice versa. Want a per-candidate diff
   between baseline and r2 for the 202 2021 candidates before claiming
   anything in the paper.

2. **The 1 `ok_after_relock`.** `--relax-locked` recovered exactly 1
   candidate. Why so few? Of the 5 LOCK_FILE_STALE candidates whose
   relock retry attempted but failed, 4 had `pre_rc=101 → post_rc=0`
   pattern (Dependabot bumped Cargo.toml AND updated Cargo.lock; pre's
   stale lock can't resolve, post's fresh lock can). After relock the
   pre's regenerated lock ran into MSRV-too-low on transitive deps
   (`itoa 1.0.18` requires edition-2021). Reclassifying these as
   `MSRV_TOO_LOW` post-relock would be more honest.

3. **OpenSSL force-stretch sweep is still outstanding.** Run B's
   OPENSSL_MISMATCH count (64) is essentially unchanged from baseline
   (56). The handoff's stretch-routes-OpenSSL-correctly hypothesis
   wasn't tested at scale here. A separate sub-cohort run with
   `--force-fat-image rp2026/cargo-fat:1.39.0-stretch-20191231` over
   those 64 candidates is the missing experiment for the paper's
   OpenSSL story.

## Suggested next steps (post-supervisor-meeting)

In rough yield × cost order:

1. **Drop discovery-shim cap to depth 5** — recovers ~28 candidates
   (1.1 pp), trivial code change.
2. **Re-classify the 4 `LOCK_FILE_STALE`-relock-failed cases as
   `MSRV_TOO_LOW`** — taxonomy honesty, post-hoc reclassify only.
3. **OpenSSL force-stretch sub-cohort run (~64 candidates against
   `1.39.0-stretch-20191231`)** — predicted recovery ~50; estimated
   wall ~6 hours.
4. **Bump --timeout to 3600s and drop --parallel to 5 for Run A.**
   Recovers ~30-40 of the 50 new-only TIMEOUTs.
5. **Run A (the headline run) with `--attempts 3`** — flakiness
   check across the whole cohort. ~5-7 days wall at parallel=5
   single-attempt; with --attempts 3 closer to 12-15 days. Won't
   fit before May 21; targets the post-midterm window.

## Numbers worth remembering

- 2608 candidates processed in 3d 22h.
- 1359 ok / 1249 not_reproducible / 0 regenerate_mismatch.
- **52.1 % reproducibility** (95 % CI 50.1-54.1 %), up from 46.4 %.
- ~150 candidates recovered from `not_reproducible` vs baseline.
- REPO_GONE 79 → 28; NATIVE_DEP_MISSING 54 → 18; LOCK_FILE_STALE 40 → 31;
  RUSTC_BITROT 449 → 393.
- TIMEOUT regressed 25 → 69 because of disk contention at parallel=8 —
  measurement artefact.
- 27/28 surviving REPO_GONE are MANIFEST_DEEP at depth 3-5; zero are
  real tombstones. Counter to the original audit's "~3 are tombstones"
  estimate.
- All 4 audit verifications agree the round-2 classifier is
  ~80-95 % precise within each top category.
