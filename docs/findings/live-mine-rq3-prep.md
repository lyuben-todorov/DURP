# Live-mine (2024–2025) cohort — RQ3 drive prep

Read-only analysis of the recent cohort that the live-mine produced, to
plan the reproduction drive that will answer RQ3 (historical
2018–2021 vs recent 2024–2025). **Nothing here has been driven yet** —
the 5,401 candidates are mined and enriched but not reproduced.

Source: `data/live-mine/candidates_enriched.jsonl` on crack (5,401 rows),
profiled against the live `fat_image.bucket_for` / `debian_release_for`
logic. Numbers regenerate from that file; no DB or Docker needed.

## Cohort shape

- **5,401 enriched candidates**, all `ecosystem=cargo`, `--require-cargo`
  confirmed.
- **Author split: 5,393 Dependabot, 8 human.** Essentially a pure
  Dependabot cohort — the same author profile as DS1, which keeps the
  RQ3 comparison like-for-like.
- **Date coverage:** 2024 → 2,723; 2025 → 2,664; 2026 → 14. Clean split
  across the two target years; the 14 in 2026 are January stragglers.
- **MSRV declared in only 25 %** (1,350 / 5,401). The other 75 % fall
  back to the era-floor — and because these are 2024–2025 commits, the
  era floor lands on recent rustc (1.85 / 1.92), not old toolchains. This
  is the opposite regime from DS1, where the era floor pulled candidates
  *down* to 1.30–1.56. Top declared MSRVs: 1.85, 1.74, 1.75, 1.81, 1.80.
- **Top bumped crates:** clap (716), serde (371), serde_json (340),
  tokio (299), anyhow (199), thiserror (173), reqwest (163), syn (101),
  tempfile (89), toml (78), chrono (67), **openssl (65)**, regex,
  uuid. Typical modern-Rust dependency surface.

## The drive plan: 5 fat images, all new

Running every candidate through `bucket_for` (with `max_sde_date =
2025-12-31`, the right cap for a 2024–2025 cohort) maps the 5,401 into
**5 buckets / 5 canonical fat-image tags**, none of which is in
`docker/cargo-fat/index.json` today:

| Canonical tag to build | Candidates | Note |
| --- | ---: | --- |
| `rp2026/cargo-fat:1.85.0-bookworm-20250318` | 2,723 | the 2024 cohort; `pre_rust_base` (SDE clamps fwd to base pub) |
| `rp2026/cargo-fat:1.92.0-bookworm-20260113` | 1,237 | 2025 bookworm; `pre_rust_base` |
| `rp2026/cargo-fat:1.92.0-trixie-20260122` | 1,016 | 2025 trixie; `pre_rust_base` |
| `rp2026/cargo-fat:1.85.0-bookworm-20251231` | 411 | 2025 commits with MSRV ≤ 1.85 on bookworm |
| `rp2026/cargo-fat:1.92.0-trixie-20261231` | 14 | the 2026 stragglers |

`bucket_for` returned `None` for **0** candidates — every one is
routable, no `rust_base_unknown` gaps on these tracks.

**Note on the existing 1.92 images.** `index.json` already has
`1.92.0-bookworm-20260415` and `-20260427`, but the bucketer wants
`1.92.0-bookworm-20260113` — a *different* canonical SDE. The existing
two are pre-canonical seed images and will **not** be reused; the drive
needs the canonical builds above. (Confirm with
`python -m pipelines.cargo.cargo_plan_fat_images --candidates <live-mine
jsonl>` before building — it prints the exact build commands.)

Two images (the bulk: 2,723 + others) carry the `pre_rust_base` flag,
meaning the canonical Dec-31 SDE predates the Docker Hub `rust:<ver>`
base publication, so the SDE is clamped forward to the base's pub date.
This is expected and harmless (same situation as DS1's 2018–2020 buster
buckets); it just means the apt snapshot is slightly newer than the
calendar year-end.

## Predictions for the drive (testable hypotheses, not results)

These are what RQ3 will check; recording them now so the drive isn't
post-hoc rationalised:

1. **Reproducibility should be *higher* than DS1's 53.9 %.** The dominant
   DS1 failure modes were era-driven: RUSTC_BITROT (code on too-new
   rustc) and OPENSSL_MISMATCH (old libssl ABI). A 2024–2025 cohort built
   on contemporary rustc (1.85 / 1.92) and bookworm/trixie (libssl 3.x)
   should largely avoid both. If recent reproducibility is *not* higher,
   that itself is the interesting finding.

2. **OpenSSL should mostly vanish as a failure class.** 65 candidates bump
   `openssl`, but modern `openssl` crates target libssl 3.x, which
   bookworm/trixie ship. The DS1 OPENSSL_MISMATCH cluster (see
   [`openssl-case-study.md`](openssl-case-study.md)) was an *old*-libssl
   phenomenon; it should not recur here. Worth confirming, not assuming.

3. **New failure modes may appear at the recent edge.** Edition-2024
   features, `rust-version` constraints newer than 1.92, and crates that
   already require a nightly past our newest milestone could surface a
   small NIGHTLY_REQUIRED / MSRV_TOO_LOW tail. Magnitude unknown.

4. **TEST_FAILURE should remain roughly flat as a *fraction*.** It's an
   author-environment property (DNS, fixtures, env vars), not era-driven,
   so it should persist at a similar rate in both cohorts — a useful
   invariant to check the comparison against.

## Operational notes for whoever runs it

- **Do not run concurrently with another crack drive.** Shares the Docker
  daemon and `pipeline.sqlite`; concurrent heavy drives hit the
  `database is locked` / disk-contention regime (see
  [`ds1-full-r2-findings.md`](ds1-full-r2-findings.md), the parallel=8
  TIMEOUT inflation). Use `--parallel 5`.
- **Build the 5 images first**, then drive with bases pre-built (don't
  use `--build-missing-bases` with `--parallel > 1` — index-write race).
- **Use a fresh `run_id`** (suggest `live-2024-2025` or
  `livemine-crack`), `--max-sde-date 2025-12-31`, `--relax-locked`. For a
  like-for-like RQ3 contract, mirror Run B's flags otherwise.
- 5,401 candidates ≈ 2× DS1; at `--parallel 5` budget multiple days of
  wall-clock. Consider `--shuffle --shuffle-seed 1337` to spread the
  heavy-workspace clusters, same as Run B.
- The input file is on crack at `data/live-mine/candidates_enriched.jsonl`.

## What this prep does NOT do

It does not drive, build any image, or touch the DB. It is a plan plus
falsifiable predictions, written before the run so RQ3's analysis can be
held to them.
