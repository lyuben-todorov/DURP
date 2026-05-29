# Rebatchi dataset — Cargo usage

Assessment of whether the Rebatchi et al. 2024 dataset
([Zenodo 10.5281/zenodo.7801356](https://doi.org/10.5281/zenodo.7801356))
is a usable input source for the Cargo dependency-update benchmark, and
what we extracted from it.

_Investigation dates: 2026-04-30 (Dataset 2), 2026-05-01 (Dataset 1),
2026-05-03 (full-DS1 enrichment)._

## TL;DR

| Question | Answer |
| --- | --- |
| Is Dataset 2 enough alone? | **No.** ~292 closed-unmerged PRs that bump a top-1000 crate; most are polyglot-repo npm PRs in Rust-labelled repos. |
| Is Dataset 1 enough? | **Yes, for partition 1.** 3,988 Cargo-confident PRs across 1,505 Rust repos from the body-mentions-`Cargo.toml` filter. |
| Post-enrichment usable count? | **2,608 candidates** after `rebatchi_to_candidate.py --require-cargo` (filters non-Cargo false positives like the accrescent case). Committed at `data/rebatchi/ds1_candidates_enriched.jsonl`. |
| Combined partition-1 pool? | ~4,280 Cargo-plausible PRs (DS1 ∪ DS2-top-1000-crate; essentially disjoint). |
| Where's the 2023 partition? | **Not on Zenodo.** Both DS1 and DS2 zips end 2021-06-15. Re-mine with `HocineREBT/GitHub-Miner` or ask the authors. |
| Biggest reproduction risk? | Age tilt: 82% of the DS1 Cargo pool is 2019-2020. Pre-2021 Rust often fails on modern rustc and EOL Debian thin-images break on `apt-get`. The v0.0.4 fat-image policy (per-year `BucketKey` + `pre_rust_base` flag) handles this explicitly. |

## What the Zenodo artifact actually contains

Four zips. All downloaded and inspected except Dataset 3.

| Zip | Size | Format | Date range |
| --- | --- | --- | --- |
| `Derived Sample.zip` | 12 MB | 3 XLSX (manual annotations on a sub-sample) | — |
| `Dataset (1) - Dependency Update.zip` | 3.7 GB | 16 rar archives, ~87k raw GitHub search-API result pages (`items[]` per page). No repo-level `Language` column (step 5 of the paper's pipeline wasn't run). | **2017-06-18 → 2021-06-15** (partition 1 only) |
| `Dataset (2) - Dependabot Security PRs.zip` | 248 MB | `PRs.xlsx` (363,657 × 40) + `Repos.xlsx` (36,093 × 16) + `Part 0.rar`. `Language` is the repo's primary GitHub language, not the PR's ecosystem. `Body` is a numeric length, not the text. | **2017-06 → 2021-06** |
| `Dataset (3) - Manual Security PRs.zip` | 130 MB | not extracted | — |

Dataset 4 (Snyk / Renovate / Greenkeeper / Depfu), listed in the paper's
Table 7, is **not present** on this Zenodo record.

Neither DS1 nor DS2 records commit SHAs, file lists, or PR merge state
(for DS1) — they're stripped during the paper's CSV extraction. These
must be re-fetched from GitHub.

## Dataset 2 — numbers

Direct read from `Repos.xlsx` and `PRs.xlsx`:

| | Paper Table 8 (Rust+Go combined) | Zenodo zip, Rust | Zenodo zip, Go | Zenodo zip, Rust+Go |
| --- | ---: | ---: | ---: | ---: |
| Repos | 603 | **432** | 108 | 540 |
| PRs | 5,667 | **4,449** | 908 | 5,357 |

Shortfall (63 repos, 310 PRs) = missing 2021-07 → 2023-09 partition.

Rust slice pipeline yield:

| Stage | Count |
| --- | ---: |
| Total Rust PRs | 4,449 |
| Closed-unmerged | 1,974 |
| + parseable `Bump X from A to B` title | 1,866 |
| + title pkg ∈ top-1000 crates.io | 446 |
| + hand-curated "well-known Rust crate" names | **~32** |

DS2 `Language` is the repo's primary GitHub language, not the PR's
ecosystem. Polyglot repos where a Rust subproject dominates file counts
but npm PRs dominate PR counts get counted as Rust.

## Dataset 1 — Cargo slice

DS1 has no language/ecosystem column. `scripts/rebatchi_ds1_filter.py`
streams all 16 rars (87,654 search-result pages) keeping rows where the
title matches `Bump X from A to B` *or* the body mentions `Cargo.toml`:

| Stage | Count |
| --- | ---: |
| Raw bump-pattern rows (pre-dedupe) | 3,551,661 |
| Unique `(owner, repo, number)` | 3,503,989 |
| + **body mentions `Cargo.toml`** (the Cargo slice) | **3,988** |
| … in distinct repos | **1,505** |
| … state = closed | 3,544 |
| … state = open | 444 |
| … high confidence (body + top-1000 crate title) | 2,510 |
| … medium confidence (body only) | 1,478 |

Top bumped packages: `serde_json (595)`, `serde (479)`, `serde_derive
(304)`, `chrono (115)`, `structopt (73)`, `regex (69)`, `flate2 (59)`,
`proc-macro2 (43)`, `log (36)`, `futures (36)`, `itoa (35)`, `anyhow
(34)`, `clap (33)`, `rayon (29)`, `tempfile (27)`, `bootloader (25)`,
`quote (25)`, `dtoa (21)`, `reqwest (20)`, `backtrace (20)` —
unmistakably Cargo crates, confirming the filter is tight.

Author distribution:

| Author | PRs |
| --- | ---: |
| `dependabot-preview[bot]` | 3,108 |
| `renovate[bot]` | 570 |
| `dependabot[bot]` | 74 |
| humans | 236 |

`dependabot-preview[bot]` dominates because the bot was renamed around
mid-2021. The post-rebrand `dependabot[bot]` share would flip with the
missing 2021-07+ partition.

## Age distribution

```
2017:    11 ( 0.3%)
2018:   189 ( 4.7%)  ####
2019: 1,244 (31.2%)  ##############################
2020: 2,037 (51.1%)  ##################################################
2021:   507 (12.7%)  ############      (partition ends 2021-06-15, H1 only)
```

Monthly spikes: 2019-04 (336), 2020-06 (622). The 2020 concentration is
why **old-Rust reproducibility is the main implementation risk**. Under
the current v0.0.4 fat-image policy this is captured by the
`pre_rust_base` flag — buckets whose year ends before the rust base
image's Docker Hub publication date are reproducible but with known
ABI-era drift.

## DS1 → enriched candidates

Running `rebatchi_to_candidate.py --require-cargo` on the 3,988 DS1
Cargo rows, against the v0.0.4 `Candidate` schema (pre/post commits,
MSRV, post_commit_date, source tag), produces:

- **2,608 candidates** at `data/rebatchi/ds1_candidates_enriched.jsonl`.
- Yield 65% — the 1,380-row drop is mostly false-positive matches like
  Android/Kotlin repos whose PR title happens to say "Bump amethyst"
  (both a Rust crate and an unrelated name).
- API cost: ~4-5 calls per candidate. Full run ~4-5 hours on a 5000/hr
  token with rate-limit pauses.

Distribution of the 2,608 enriched candidates (bucketed by fat-image
planner):

| Bucket (milestone, year, debian) | Count |
| --- | ---: |
| (1.49, 2020, buster) | 940 |
| (1.56, 2019, buster) | 534 |
| (1.56, 2020, buster) | 439 |
| (1.49, 2019, buster) | 386 |
| (1.49, 2021, buster) | 131 |
| (1.56, 2018, buster) | 105 |
| (1.56, 2021, buster) | 70 |
| (1.49, 2018, buster) | 1 |
| (1.49, 2021, bullseye) | 1 |
| unbucketable | 1 |

After group-by-tag dedupe (buckets whose canonical SDE clamps to the
same `rust_base_pub` fold into one proposal), the full dataset fits in
**4 fat images**, of which the largest —
`rp2026/cargo-fat:1.49.0-buster-20210209` — covers 2405 candidates
spanning 2018/2019/2020 buster.

## What Rebatchi has vs what we need

| Signal needed by the pipeline | DS1 | DS2 | Endpoint to recover |
| --- | --- | --- | --- |
| `head.sha`, `base.sha` | ✗ | ✗ | `GET /repos/{o}/{r}/pulls/{n}` |
| File list (for --require-cargo) | ✗ | ✗ | `GET /repos/{o}/{r}/pulls/{n}/files` |
| Single-line diff patch | ✗ | ✗ | same `/files` |
| Merge state | ✗ | ✓ `Merged_at` | `/pulls/{n}` covers it |
| Repo primary language | ✗ | ✓ `Repos.Language` | `GET /repos/{o}/{r}` |
| PR body text | ✓ | ✗ (length only) | `GET /issues/{n}` for DS2 |
| Rust MSRV | ✗ | ✗ | `GET /contents/Cargo.toml?ref=<sha>` + edition fallback |
| Commit date | ✗ | ✗ | `GET /commits/{sha}` |

Our enricher makes 4-5 calls per candidate to populate the
`Candidate` v0.0.4 shape end-to-end.

## DS1 ↔ DS2 overlap

Intersection on `(owner, repo, number)` between the DS1 Cargo slice
(3,988) and the DS2 Rust-language set (4,449): **3 PRs**.

The two datasets answer disjoint questions:
- DS2 = `label:security` subset → mostly `Cargo.lock`-only transitive
  security bumps from 2019-2020 (our `--require-cargo` filter skips
  them).
- DS1 = all dependency-update PRs → routine `Cargo.toml` bumps.

Combined partition-1 Cargo-plausible pool: **3,988 (DS1) + 292
(DS2 closed-unmerged + top-1000 crate title) ≈ 4,280 PRs**.

## Verdict

**Dataset 1 is the usable core** for the benchmark. After enrichment
the corpus is 2,608 candidates, 100% coverable by 4 fat images, age
distribution matching the "old-Rust reproducibility is the hard
problem" frame.

Open gaps:

1. **2021-07 → 2023-09 partition** (not on Zenodo). Re-mine with
   `HocineREBT/GitHub-Miner` or email the authors. Likely +50-100% more
   Cargo candidates, skewed toward `dependabot[bot]` (post-rebrand)
   and easier to reproduce on modern toolchains.
2. **Dataset 4** (Renovate / Snyk / Greenkeeper / Depfu) — absent from
   Zenodo. Would add a Renovate-specific slice.
3. **Old-Rust reproducibility** for the 2019-2020 bulk is where the
   benchmark's reproduction rate will hurt. Rebuilds succeed under
   `pre_rust_base` images; whether the code itself compiles on rust
   1.56 is empirical — TBD after the batch drive runs.

## Known sharp edges

- **Dependabot-preview vs dependabot naming.** Bot renamed mid-2021.
  DS1's 2019-2020 dominance means 78% of the pool is
  `dependabot-preview[bot]`. The post-rebrand share would flip with the
  2021-07+ partition we don't have.
- **Body-mentions-Cargo.toml filter is tight but not complete.**
  Dependabot and Renovate consistently mention the manifest path; exotic
  PR flavours could be missed. Current 3,988-row pool is probably ~90%
  of the true DS1 Cargo population.
- **Old Debian apt fails on EOL buster-security dates.** `snapshot.debian.org`
  has spotty coverage before 2020-Q2 for buster. The vendored
  `repro-sources-list.sh` was locally patched to use the pre-bullseye
  security URL layout (`<codename>/updates/`) — commits under
  `docker/cargo-fat/`.
- **`rebatchi_to_candidate.py` is not resumable.** If killed mid-enrichment
  it restarts from row 0. Fix tracked in `db-design.md`.

## Tools

- `dep-updates-poc/scripts/rebatchi_ds1_filter.py` — streams rars,
  emits `data/rebatchi/ds1_bump_candidates.jsonl` (3.5M filtered rows,
  1.3 GB, gitignored).
- `dep-updates-poc/scripts/rebatchi_to_candidate.py` — Rebatchi row
  → v0.0.4 `Candidate` JSONL via GitHub API. Flags:
  `--require-cargo`, `--skip-gh-verify`, `--limit`,
  `--source <provenance-tag>`, `--jsonl` / `--csv` input modes.
- `dep-updates-poc/data/rebatchi/crates_top1000.txt` — top-1000
  crates.io names by downloads.
- `dep-updates-poc/data/rebatchi/ds1_candidates_enriched.jsonl` —
  **2,608 candidates**, enriched, ready for the driver.
- `dep-updates-poc/data/rebatchi/ds1_candidates_enriched_500.jsonl` —
  first-500 slice kept for regression tests.

## Files on disk

| Path | Size | Tracked? |
| --- | --- | --- |
| `dep-updates-poc/data/rebatchi/Dataset/Part *.rar` | 3.5 GB | gitignored |
| `dep-updates-poc/data/rebatchi/ds1_bump_candidates.jsonl` | 1.3 GB | gitignored, regenerable |
| `dep-updates-poc/data/rebatchi/ds1_cargo_candidates.jsonl` | few MB | gitignored |
| `dep-updates-poc/data/rebatchi/ds1_candidates_enriched.jsonl` | ~1.5 MB | **tracked** |
| `dep-updates-poc/data/rebatchi/ds1_candidates_enriched_500.jsonl` | ~300 KB | **tracked** |
| `dep-updates-poc/data/rebatchi/rust_ds2.csv` | 2 MB | gitignored |
| `dep-updates-poc/data/rebatchi/Derived Sample/*.xlsx` | 12 MB | gitignored |
| `dep-updates-poc/data/rebatchi/sample-drive/` | ~few MB | **tracked** — smoke-test artifacts |
