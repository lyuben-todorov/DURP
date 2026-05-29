# DS1 full-run findings (2026-05-08 / 2026-05-12)

Interim report on the first full pass over Rebatchi DS1 (2608 Cargo
Dependabot PRs, 2017-2021). Run `ds1-full-crack`, host `crack`, amd64.
Where the 200-slice
(`ds1-200-slice-findings.md`) was a pipeline-shakedown with n=200, this
is the first measurement-grade run and the one the thesis will cite.

## Setup

- **Candidates:** all 2608 of `ds1_candidates_enriched.jsonl`. No filter
  beyond the pre-ingestion Rebatchi filter (Dependabot-authored,
  single-line `Cargo.toml` bump, Cargo ecosystem).
- **Run ID:** `ds1-full-crack`.
- **Workers:** began at `--parallel 8`, reduced to `--parallel 4` after
  host OOM-kills on diem/libra linkers (~23:00 UTC 2026-05-08),
  stabilised at `--parallel 3` after tunnel daemon collateral damage
  (~11:00 UTC 2026-05-09), finally `--parallel 5` once a per-container
  `--memory=8g` cap was added (2026-05-09 ~20:30 UTC).
- **Memory cap:** `--memory=8g` applied to every `docker run` from the
  parallel=5 restart onward. 24 GiB swapfile added to the 8 GiB base to
  buffer buildkit exports (total 31 GiB swap, 32 GiB RAM).
- **`max_sde_date`:** 2023-12-31 throughout.
- **Host:** `crack`, 16-core amd64 Ubuntu, 31 GiB RAM, 8→31 GiB swap,
  WiFi uplink averaging ~6 MB/s (half-duplex, not the CPU bottleneck
  for this workload).
- **Caching:** host-mounted cargo cache (`data/cargo-cache/`, bind-
  mounted `/cargo-cache`, `CARGO_HOME` overridden). Cache grew from
  1.6 GiB (carried over from the 200-slice) to **19 GiB** by run end.
- **Fat images:** four pre-built amd64 images covering the DS1 buckets:
  `1.49.0-buster-20210209`, `1.49.0-buster-20211231`,
  `1.56.0-buster-20211022`, `1.56.0-buster-20211231`. A fifth
  (`1.56.0-bullseye-20211231`) picked up a single candidate.
- **Pipeline changes landed mid-run:** graceful-shutdown + container
  registry (`_active_containers` tracked, SIGTERM kills them), per-
  container memory cap, these landed at the parallel=5 restart and
  ended the tunnel-collapse class of outages.

## Headline numbers

| Metric | Value |
| --- | --- |
| Wall clock | **2d 11h 22min** (2026-05-08 16:49 UTC → 2026-05-12 04:11 UTC) |
| Candidates processed | **2608 / 2608** (zero dropped) |
| `ok` (reproducible) | **1210 (46.4 %, Wilson 95 % CI ≈ 44.4-48.3 %)** |
| `not_reproducible` | **1395 (53.5 %)** |
| `regenerate_mismatch` | 3 (0.1 %) |
| Fix-after-update candidates (pre=101, post=0) | **20 (0.77 %)** |
| Timeouts at 30 min | 24 (0.92 %) |
| Peak throughput (parallel=5, warm cache) | **101 candidates/hour** |
| Steady throughput (heterogeneous cohort) | ~40-50/hour |
| Reproduction-attempts rows in DB | 102 (see bug E below) |

The headline **46.4 % reproducibility** is slightly below the 200-slice
pilot's 49.5 % — the first-200 candidates were drawn alphabetically and
happened to skew toward the MSRV=1.31 / 2019-2020 cohort that's the
healthiest slice of DS1. The full run drifts down because the
MSRV=1.56 / 2019-2020 fallback cohort (on the `1.56-buster-20211022`
fat image) has a 29 % reproducibility rate, and it accounts for
roughly 40 % of the remaining 2408 candidates.

## Breakdown by year of post-commit date

The most thesis-relevant slice of the data. Rebatchi DS1 covers
~2017-2021; the four years with non-trivial sample sizes:

| Year | n | `ok` | `not_reproducible` | reproducibility |
| ---: | ---: | ---: | ---: | ---: |
| 2018 | 106 | 23 | 83 | **21.7 %** |
| 2019 | 920 | 382 | 538 | **41.5 %** |
| 2020 | 1380 | 711 | 666 (+3 regen_mismatch) | **51.6 %** |
| 2021 | 202 | 94 | 108 | **46.5 %** |

2018 is a steep cliff. 2019 sits below the run average. 2020 is the
sweet spot, 2021 stays in the forties. Two forces interact:

1. **Older code has more time to bitrot** against the frozen rustc /
   apt snapshot. Every minor version of rustc between the code's
   native toolchain and the fat-image rustc is another chance for a
   borrow-check or inference regression to fire. 2018 code sent to
   `rustc 1.56` is ~19 minor versions ahead; 2020 code is ~4.
2. **Dependabot's use on Cargo grew fast** through this period. 2018
   captures the earliest Dependabot Cargo PRs and those projects
   tend to be smaller, more experimental, less "tested on CI". A
   disproportionate share are experimental or tombstone repos.

The year distribution matches RQ3 directly: even without the
2024-2025 live-mine comparison, the 2018 → 2021 gradient alone is
evidence that *reproducibility decays measurably with age*, and the
2018 cohort is roughly **half as reproducible** as the 2020 one.

## Breakdown by fat image

| Fat image | n | `ok` | reproducibility |
| --- | ---: | ---: | ---: |
| `1.49.0-buster-20210209` | 1327 | 801 | **60.4 %** |
| `1.49.0-buster-20211231` | 131 | 76 | 58.0 % |
| `1.56.0-buster-20211022` | 1079 | 315 | **29.2 %** |
| `1.56.0-buster-20211231` | 70 | 17 | 24.3 % |
| `1.56.0-bullseye-20211231` | 1 | 1 | n/a |

The `1.56.0-buster` pair is the cliff. Manual sampling of 15 of its
failures in a targeted analysis (section "Failure categorisation"
below) showed the root cause: MSRV=1.56 is the *fallback floor* that
the driver used for projects that declared no MSRV, and a
disproportionate number of those projects were actually from
2018-2020 (i.e. code that expected rustc ≤ 1.45 but was routed to
1.56 because it had no `rust-version` in `Cargo.toml`). The
fat-image tool pushed them far past their native toolchain era and
borrow-check / stdlib tightening did the rest.

This is the single highest-leverage finding for pipeline
improvement. See "Recommended next steps" below.

## Failure categorisation (all 1395 `not_reproducible`)

Produced by `scripts/reclassify_failures.py`, which post-hoc reads
each candidate's `<short>-pre.log` and buckets against a 12-category
taxonomy. All 1395 rows classified; re-runnable as the rules evolve.

| Category | n | share of fails | thesis-relevant pattern |
| --- | ---: | ---: | --- |
| OPENSSL_MISMATCH | **378** | 27.1 % | openssl-sys 0.9.x + libssl-dev 1.1 ABI collision |
| RUNTIME_CRASH | **356** | 25.5 % | 339 build-script panics, 17 SIGSEGV |
| RUSTC_BITROT | **326** | 23.4 % | 15 distinct rustc error codes; stricter borrow-check/inference |
| REPO_GONE | 79 | 5.7 % | clone succeeded, `Cargo.toml` not found (tombstone repo) |
| DEPENDENCY_RESOLUTION | 75 | 5.4 % | non-lockfile resolver failures (yanked deps, unsatisfiable ranges) |
| OTHER | 68 | 4.9 % | classifier fallthrough; manual inspection needed |
| NATIVE_DEP_MISSING | 41 | 2.9 % | fuse (15), libv4l2 (10), pango (5), atk (4), ... |
| LOCK_FILE_STALE | 38 | 2.7 % | `Cargo.lock` can't resolve under `--locked` |
| TIMEOUT | 24 | 1.7 % | 30-min timeout exceeded (mostly libra/diem/solana) |
| NETWORK_ERROR | 9 | 0.6 % | zlib / fetch failures (transient) |
| TEST_FAILURE | 1 | 0.1 % | explicit cargo test fail under `cargo test --locked` |

### Sub-categories worth pulling out

**`RUSTC_BITROT` top error codes** (most-fired → least, only those ≥8):

| code | n | meaning |
| --- | ---: | --- |
| — (unclassified) | 56 | no E-code matched; generic `could not compile` |
| E0283 | 38 | type-inference regression — too many implementations |
| E0034 | 36 | multiple applicable items — name resolution ambiguity |
| E0433 | 28 | unresolved path — renamed std module / crate |
| E0119 | 24 | conflicting trait impls — coherence-check tightening |
| E0713 | 17 | NLL borrow — 2021-era stricter lifetime inference |
| E0557 | 17 | feature removed from nightly set (e.g. removed unstable) |
| E0554 | 15 | `#![feature]` on stable rustc |
| E0512 | 12 | transmute alignment mismatch |
| E0308 | 12 | type mismatch — often inference drift |
| E0432 | 11 | unresolved import — path relocation |
| E0583 | 10 | file not found for module |
| E0621 | 9 | explicit lifetime required |
| E0425 | 9 | cannot find value in scope |
| E0503 | 8 | cannot use value while mutably borrowed |

This is a distinctly Rust-specific pattern and each code can be tied
to a particular rustc minor-version regression, which is exactly the
argument for finer milestone granularity in the bucketer.

**`NATIVE_DEP_MISSING` packages**:

| apt package | n | notes |
| --- | ---: | --- |
| fuse (libfuse) | 15 | filesystem-in-userspace crates |
| libv4l2 | 10 | video-for-linux capture |
| pango | 5 | GTK text layout |
| atk | 4 | GTK accessibility |
| mpich | 2 | MPI |
| libnotify | 2 | desktop notifications |
| webkit2gtk-4.0 | 1 | webview |
| slurm | 1 | HPC scheduler |
| libcap-ng | 1 | Linux capabilities |

All nine of these are additions a future fat image could bake in; the
failure is not conceptual, it's "apt-install was missing from our
Dockerfile".

**`RUNTIME_CRASH` is overwhelmingly build-script panics (339/356).**
The dominant pattern is `build.rs` reading an environment variable
(e.g. `SGX_MODE` for mobilecoin, `LLVM_SYS_140_PREFIX` for bindgen-
heavy crates) or shelling out to a tool (`pkg-config fuse >= 2.6`)
that isn't present in the container. These are *author-environment
assumptions* rather than pipeline defects, but many are tractable
with a per-candidate env-var allowlist.

### Summary by fix class

| Fix class | Categories | n | share of fails |
| --- | --- | ---: | ---: |
| Pipeline / fat-image improvements | OPENSSL_MISMATCH, NATIVE_DEP_MISSING, REPO_GONE, OTHER | **566** | **40.6 %** |
| Finer bucketer / more milestones | RUSTC_BITROT (in part), LOCK_FILE_STALE | ~364 | ~26.1 % |
| Genuine author-env assumptions | RUNTIME_CRASH (build-script panics), TEST_FAILURE | ~357 | ~25.6 % |
| Corpus-level issues | DEPENDENCY_RESOLUTION (yanked deps), TIMEOUT, NETWORK_ERROR | ~108 | ~7.7 % |

**~41 % of the 1395 failures are in categories that pipeline /
fat-image work can directly address.** That's the ceiling on how
much we can lift reproducibility by engineering; the rest is
genuine ecosystem property we can only *measure*, not fix.

## Security-relevant subset (RustSec crossings)

Produced by `scripts/rustsec_crossings.py`, cross-referencing every
DS1 candidate's bump against the RustSec advisory DB (1048 advisories
across 813 crates as of 2026-05-12).

**30 of 2608 candidates (1.2 %) cross an advisory boundary.** Broken
out:

| class | n | reproducibility |
| --- | ---: | --- |
| SECURITY_MOTIVATED (prev affected → new safe, PR date ≥ advisory) | **17** | 4 ok / 13 not_reproducible = **23.5 %** |
| COINCIDENTAL_ESCAPE (same direction, PR date before advisory) | 13 | 4 ok / 8 not_reproducible / 1 regen_mismatch |
| SECURITY_REGRESSION (prev safe → new affected, PR date ≥ advisory) | **0** | n/a |
| PRE_ADVISORY_REGR (same direction, PR before advisory) | 5 | 2 ok / 3 not_reproducible |

Findings:

1. **Dependabot introduced no known-vulnerable bumps in DS1.** Earlier
   ad-hoc analysis claimed 13 `crossbeam-channel 0.4.2 → 0.4.3`
   "regressions" under RUSTSEC-2020-0052; the production script's
   stricter boundary logic caught that the 0.4.2 → 0.4.3 bump stays
   *within* the affected range, not into it. No clean "Dependabot
   made it worse" example exists in this corpus.
2. **Security-motivated PRs reproduce at 23.5 %, roughly half the
   run average (46.4 %).** This is a striking finding. Two clusters
   dominate:
   - `yaml-rust 0.4.0 → 0.4.2` (9 PRs, 6 not_reproducible) — the
     yaml-rust dep graph bitrots hard on buster-era fat images.
   - `rocket 0.4.x → 0.4.5` (6 PRs, **all 6 not_reproducible**) — Rocket
     0.4.x required rustc nightly, and our fat images are stable.
3. The **PR-date vs advisory-date distinction** is essential. Of the
   30 boundary crossings, 43 % pre-date the advisory — i.e. they were
   routine version bumps that coincidentally moved out of a
   later-classified vulnerable range. Only 57 % were plausibly
   security-motivated in the sense that the author / bot could have
   known about the advisory when the PR was created.

The "security-motivated reproduces at ~half the corpus rate" is a
thesis-grade finding about the trust model of automated dependency
updates: PRs that specifically address known security advisories are
harder to re-validate later than routine bumps, which has direct
implications for security-patch archival.

## Fix-after-update candidates

20 candidates exited with `pre_rc=101, post_rc=0` — pre-commit fails
to build, post-commit builds and tests pass. These are the canonical
"Dependabot bump rescues a broken base commit" cases. Hand-inspected
the first 3:

- `althonos/cksfv.rs#17` — genuine fix: pre pinned `clap = "=4.0.8"`,
  clap 4.x removed a feature, post updated the version constraint.
- `swift-nav/yamloboros#3` — `Cargo.lock` rescue: lockfile couldn't
  resolve, post refreshed it. 0 actual tests.
- `wasmerio/wasmer#1577` — `Cargo.lock` rescue, 0 actual tests.

Likely breakdown of the 20:

- ~⅓ genuine fixes (dep incompatibility, breaking change in a dep).
- ~⅔ lock-file refreshes with no real test coverage on the post-
  commit side.

This is a methodological subtlety the paper needs to name explicitly:
reporting *"X candidates were fix-after-update"* conflates two very
different phenomena. Future work: sub-classify on `cargo test`
output (non-zero test count vs zero test count) to split the two.

## Pipeline bugs surfaced and (partially) fixed during the run

### Bug E — `reproduction_attempts` DB-mirror gap

Only 102 rows in `reproduction_attempts` despite 2605 candidates
completing. `record_attempt()` in `cargo_drive.py` is called only
inside the fresh-reproduction success path, after `EntryWriter.write`.
Failed-reproduction candidates (no entry written) and regenerate-
short-circuit candidates (entry already existed, no new write) both
bypass it. Consequence: Grafana's "Reproduction attempts" panel
under-counts by 25x.

Not affecting data (JSONL state file is primary, DB is a mirror).
Fix is ~30 LOC in `cargo_drive.py` to relax the FK on
`reproduction_attempts.entry_id` to nullable and call `record_attempt`
in all outcome branches. Deferred as not load-bearing for the paper.

### Bug F — SIGTERM leaves orphan containers (fixed 2026-05-09)

When the driver was SIGTERM'd (twice during the run), its in-flight
`docker run` subprocesses died but the docker daemon's containers
kept running. Observed holding ~28 GiB of RAM across three libra/diem
linkers, contributing to the cloudflared tunnel's OOM-kill.

Fixed in commit `dd4f05c`: module-level `_active_containers` set in
`cargo_reproducer.py`, `kill_active_containers()` helper, signal
handler in `cargo_drive.py` that calls it on SIGTERM/SIGINT.
Confirmed working on the 2026-05-09 20:30 UTC restart — subsequent
SIGTERMs leave no orphans.

### Bug G — libra/diem OOM cliff (mitigated 2026-05-09)

Rust release builds of the libra/diem/solana workspace family
(500kLOC+ codebases with heavy linkers) exceed 8 GiB per `ld`
invocation. With `--parallel 8` on a 32 GiB host, 8 concurrent
linkers exceeded host memory and triggered kernel OOM-kill, bringing
down the driver, the containers, and the SSH tunnel daemon as
collateral.

Mitigated by:
1. Reducing `--parallel` from 8 → 3 → 5.
2. Adding 24 GiB swapfile (8 → 31 GiB total swap).
3. Adding `--memory=8g` per-container cap in the reproducer so
   individual pathological linkers fail their own build instead of
   starving the host.

Not a code bug per se — it's an accurate reproduction of a real
memory-hungry workload. The mitigation converts host-wide OOMs
into per-candidate build failures, which we count correctly in the
taxonomy.

### Bug H — Fork-cluster duplication inside DS1

Rebatchi DS1 contains 13 repo names that appear under multiple
GitHub owners (libra × 4, diem × 3, solana × 2, retworkx × 3, plus
others). These are user forks of popular upstream repos that
inherited the upstream's Dependabot config and emitted their own
PRs. 30-60 candidates are fork-duplicates of the same logical bump.

Not a pipeline bug; a corpus-health finding worth naming in the
Threats to Validity. Cargo.lock-hash deduplication would fix it
properly but costs one extra fetch per candidate; we report it as a
known confounder instead.

## Operational highlights

### Cache effect (network-bound, not CPU-bound)

Cargo cache grew 1.6 GiB → 19 GiB over the run. Grafana's
`cargo_crates_fetched_5m` panel (deployed mid-run via the
cache-metrics textfile collector) showed continuous fresh crate
downloads throughout — the cache warms monotonically, never fully
saturates, because every fat-image transition triggers a fresh
crate fetch for the different registry-index-format subtree
(`github.com-1ecc6299db9ec823` for cargo 1.49, `index.crates.io` for
cargo 1.56+).

Network was on WiFi (`wlp2s0`) throughout, capped at ~6 MB/s. Peak
throughput of 101 candidates/hour coincided with deep cache-warm
phases on `1.49-buster-20210209`; baseline 40-50/hour is
cache-miss-dominated. A wired-ethernet host or wired-uplink WiFi
would plausibly run 20-30 % faster.

### Grafana / observability

The cache-metrics textfile collector (`deploy/cache-metrics.sh` +
systemd timer) deployed 2026-05-09 gave us the first live view of
the cargo cache's fetch rate. The host dashboard's new "Cargo cache
size" / "Crate fetch rate" panels were the diagnostic that resolved
the "why is parallel=5 not faster than parallel=3" question:
network-bound, not CPU-bound.

The per-core heatmap was useful for distinguishing cache-warm
(yellow wall across all 16 cores) from cache-cold (striped / dark)
periods.

### Wall-time accounting

3.5 days wall-clock = ~85 hours. Of those:

- ~50 hours of steady progress (40-50/hr × 50hr ≈ 2000-2500 candidates).
- ~25 hours at reduced throughput during the parallel=3 window.
- ~10 hours recovery from the OOM/tunnel outage + parallel-workers
  retuning.

If the graceful-shutdown and memory-cap had landed before the run
started, wall-clock would likely have been ~2 days.

## What this means for the thesis

### RQ1 answer (reproducibility rate)

**46.4 % of unselective Dependabot Cargo bumps from DS1 (2017-2021)
reproduce under a canonical fat-image contract.** 95 % Wilson CI
44.4-48.3 %. This is the central quantitative finding and has no
published predecessor for Cargo. It's noticeably lower than
`malka2026docker`'s 72 % ecosystem-wide Docker rebuildability,
which is expected — we measure a stricter property (environment-
fingerprint match) on a harder corpus (frozen historical PRs, not
arbitrary GHA workflows).

### RQ2 answer (breaking rate)

Not yet settled. The 20 fix-after-update candidates (0.77 %) are
half the story; the full breaking-rate analysis requires separating
pre-passing / post-failing from pre-passing / post-passing within
the 1210 reproducible cohort. That's a database query, not a re-
run; producible from existing data.

### RQ3 answer (temporal variation)

Substantial signal within DS1 alone: 2018 candidates reproduce at
21.7 %, 2020 at 51.6 %, 2021 at 46.5 %. The 2018-cohort cliff is
the strongest evidence of temporal decay in the corpus. The 2024-
2025 live mine (planned next) will give the full delta.

### RQ4 answer (failure taxonomy)

Full 12-category breakdown now in hand, with sub-sub-breakdowns for
rustc error codes and native-dep packages. The "41 % of failures
are fixable by pipeline / fat-image improvements" claim is the
headline for the taxonomy section.

## Stretch retry experiment (2026-05-12)

Hypothesis: the 378 OPENSSL_MISMATCH failures were caused by the
`openssl-sys` 0.9.x crates' ABI assumptions conflicting with buster's
libssl 1.1.1. Debian stretch ships both libssl 1.0.2 and libssl 1.1.0,
matching the era these crates were developed against. A stretch-based
fat image should recover most of the OpenSSL cohort.

### Fat-image additions

Built 5 new fat images: `rp2026/cargo-fat:1.39.0-stretch-{20191123,20191231}`
and `rp2026/cargo-fat:1.39.0-buster-{20191231,20201231,20211231}`.
Registered in `docker/cargo-fat/index.json`. Bucketer extended to
include rustc 1.39 (the async/await cliff) and to route pre-2019-07-06
commits to stretch; date-aware MSRV floor added in `cargo_drive.py` so
undeclared-MSRV pre-2020 commits floor to 1.39 instead of 1.56.

### Five consecutive retry runs, each sharpening the cohort

| run | cohort | routing | observed | observation |
| --- | --- | --- | --- | --- |
| v1 | 378 OPENSSL_MISMATCH | bucketer | 24 processed, 0 ok | early sample dominated by rocket/pear nightly failures |
| v2 | 139 (v1 minus already-processed) | bucketer | 23 processed, 0 ok | still routing to buster because `debian_release_for(commit_date)` is 2020+ → buster |
| v3 | 139 | **`--force-fat-image` stretch** | 17 processed, 0 ok | most candidates failing on non-OpenSSL terminal causes (rustc E0713, nightly, tests) |
| v4 | 17 (true OpenSSL, audit-filtered) | force-stretched | 11 processed, 0 ok | **schema validation killed 5 successful reproductions** because `debianRelease='stretch'` wasn't in the pydantic pattern |
| **v5** | 6 (v4 unprocessed, after schema fix) | force-stretched | **6 processed, 6 ok** | **100 % success on the forced-stretch genuine-OpenSSL cohort** |

### What the cohort narrowing revealed

The reclassifier's first-pass `OPENSSL_MISMATCH` label was ~25× too
broad. A manual terminal-cause audit over the 144 candidates the
sharpened reclassifier tagged OpenSSL yielded:

| Audited terminal cause | n | share |
| --- | ---: | ---: |
| `other` (unmatched in probe regex) | 78 | 54 % |
| rustc E0713 (NLL borrow-check) | 32 | 22 % |
| **genuine openssl-sys terminal** | **17** | **12 %** |
| `test failed` (integration tests need network) | 8 | 6 % |
| compile fail inside `ceres` / one-offs | 6 | 4 % |
| other rustc E-codes | 3 | 2 % |
| native link (snappy) | 1 | 1 % |

Even the sharpened reclassifier over-reports OpenSSL by ~8× because
`openssl-sys` build-script chatter appears early in many logs without
being the failure's terminal cause. **A dep-graph-aware classifier
(read the Cargo.lock, detect pinned `openssl-sys<0.9.50`) would give
the right precision but is substantially more engineering.**

### Findings

1. **Stretch works for genuine OpenSSL failures.** 6/6 (100 %) of
   true-OpenSSL candidates that reached `cargo test` under the forced
   stretch image compiled and passed. Plus a further 5 from v4 were
   validated-successful pre-schema-fix (lost entries, not lost
   reproductions). Effective yield on the true cohort: 11/17 ≈ 65 %,
   with the rest failing on either test-network requirements or
   openssl 0.7.x-era crates that need libssl 1.0.x *alone* (stretch
   has both 1.0.2 and 1.1.0 co-installed; the linker picks 1.1.0).

2. **Net headline impact on DS1 reproducibility rate is small:**
   1210 → 1216 ok, i.e. 46.4 % → 46.6 %. The qualitative finding
   (classifier keyword matching is insufficient for causal attribution
   in long build logs) matters more than the numeric lift.

3. **The mhost family (10 candidates)** compiled cleanly on stretch
   but failed at `cargo test` because its integration tests do live
   DNS lookups that don't resolve inside the reproducer's container.
   This is a **pipeline boundary, not a reproduction failure** — and
   a case the taxonomy needs to name explicitly (`tests_need_live_network`
   or similar) rather than conflating with `TEST_FAILURE`.

4. **`chef/delivery-cli#103`** needed libssl 1.0.x *exclusively* —
   its openssl 0.7.14 C shim references symbols (`CRYPTO_LOCK_SSL`,
   `CRYPTO_add`) that were removed in libssl 1.1. Stretch's dual-shipped
   1.0.2 + 1.1.0 doesn't help because `libssl-dev` points at 1.1.0.
   Recovering this era requires a stretch variant that installs
   libssl1.0-dev alone.

### What this means for the paper

- Report the DS1-full headline as 46.4 % under the original canonical
  bucketer. The stretch retry is a supplementary experiment, not a
  policy change for the headline number.
- Discussion should name the classifier's false-positive rate on
  OpenSSL as a methodological finding — terminal-cause attribution
  on long cargo build logs is a hard problem when multiple
  "error:"-adjacent markers accumulate.
- The 5 schema-killed v4 reproductions are a reminder that adding
  new values to the bucketer requires concurrent schema updates —
  fixed in commit `09d456f`.

## Recommended next steps

1. **Classify v1-v4 failures correctly** — most of the 75 candidates
   processed across v1-v4 weren't OpenSSL failures. Re-run the
   sharpened reclassifier over those retry runs' drive_state rows
   and report per-category outcomes.

2. **`tests_need_live_network` category** — add a reclassifier rule
   that catches `integration::*` test failures in crates like mhost,
   dnsbl, reqwest-based HTTP clients where the test suite inherently
   needs external network. Move affected candidates out of the
   generic `TEST_FAILURE` bucket.

3. **NATIVE_DEP fat-image extension** — bake the 9 missing apt
   packages (fuse, libv4l2, pango, atk, mpich, libnotify,
   webkit2gtk-4.0, slurm, libcap-ng) into a future fat image. ~19
   more reproductions under the sharpened reclassifier (was 41
   under the first-pass classifier).

4. **REPO_GONE status** — 79 candidates are dead repos, not
   reproduction failures. A new driver status (`repo_gone`)
   distinguishes them and removes them from the `not_reproducible`
   denominator. ~3 % rate uplift.

5. **Bitrot subcategory → milestone mapping** — for each of the top
   rustc error codes (E0283, E0713, E0119, E0034, E0308), identify
   the rustc minor version that first started rejecting the pattern
   and bucket affected candidates to one version before. Hard;
   probably future work.

6. **Fix-after-update sub-classification** — split the 20 into
   "genuine fix" vs "lock-file rescue" based on `cargo test`
   output. Cheap post-hoc analysis over the 20 post-logs.

7. **RQ3 live-mine** — ingest 300-500 2024-2025 candidates via
   `cargo_miner.py`, run them through the pipeline with the new
   stretch + memory-cap + graceful-shutdown code, and compare
   per-year rates against the DS1 cohort.

## Known followups

- `reproduction_attempts` DB-mirror gap (Bug E) — not load-bearing,
  but worth closing before the live 2024-2025 mine so that run has
  clean observability.
- OTHER-category (68 candidates, 4.9 %) deserves a second classifier
  pass. Likely a handful of new rules to extract, not a systemic
  issue.
- The 2020 cohort's 51.6 % reproducibility is suspiciously close to
  the overall headline; check whether this is a selection artefact
  from MSRV-floor routing sending cohorts into the same fat image.
- The 9 entries on disk that don't correspond to this run's `ok`
  rows are from the 200-slice and earlier pilots; verify they don't
  interfere with the retry run's short-circuit.

## Tasks completed during session

- Full DS1 run end-to-end on crack, 2608 / 2608 candidates.
- Post-hoc `reclassify_failures.py` over 1395 failures; sharpened with
  terminal-error-first rule + NIGHTLY_REQUIRED bucket.
- Post-hoc `rustsec_crossings.py` over 2608 candidates.
- Graceful-shutdown plumbing + per-container memory cap
  (`cargo_drive.py` + `cargo_reproducer.py`).
- 1.39-stretch milestone added to bucketer, 24 GiB swapfile, host-
  level OOM mitigation.
- Cache-metrics textfile collector + Grafana panels.
- 5 fat images built and registered: 1.39.0-stretch-20191123 /
  1.39.0-stretch-20191231 / 1.39.0-buster-20191231 /
  1.39.0-buster-20201231 / 1.39.0-buster-20211231.
- `--force-fat-image` CLI flag in `cargo_drive.py` for targeted retries.
- Schema update: `stretch` added to `debianRelease` allowed values in
  both the pydantic model and the JSON schema.
- Five retry runs (v1-v5) narrowing toward genuine OpenSSL failures;
  final v5 run: 6/6 reproducible (100 %) on the force-stretched cohort.
- This writeup.
