# Session handoff — 2026-05-29 (session "rp2")

Snapshot of project state so a fresh or forked session picks up cold.
Supersedes nothing in `docs/findings/`; this is operational state, not
results. Delete or update freely — it is a working note, not an artifact.

## TL;DR

This session did **repo-hardening for the final defense**, not new
research: a reproduction runbook, the first test suite + CI, a docs
cleanup, branch hygiene, the 2024–2025 live-mine, a second
image-substitution recovery experiment (native-dep), and DB tidy-up.
RQ3 (driving the 5,401 live-mined candidates) is being handled by a
separate agent.

## Git state (current)

**Main repo (`DURP`, https://github.com/lyuben-todorov/DURP), branch `master`:**
- `master` is **in sync with origin** (`origin/master..master` = 0).
- `origin` remote URL repointed to `git@github.com:lyuben-todorov/DURP.git`
  (was the old `dep-updates-rp` name).
- **Default branch is `master`** (not `main`). Only `master` exists;
  `db` and `round-2-fixes` were deleted this session (both fully merged).
- Working tree clean except the RQ3 agent's WIP (`launch_livemine_drive.sh`
  and `docs/findings/live-mine-rq3-prep.md`).

**Data submodule (`data/cargo/` → dep-updates-rp-data), branch `ds1-full-crack-r2`:**
- **1,415 entries**, pushed (`origin/ds1-full-crack-r2` = `fd3f7e0`).
  Main-repo submodule pointer bumped to match (`6ab6b88`).
- History: Run B (1,359) → OpenSSL-stretch +48 (1,407) → native-dep +8
  (1,415) → README at 54.3 %. Append-only; entries never rewritten.

### Pending outward actions (need user trigger)
- None outstanding — main repo and data branch are both pushed and in
  sync.

## What landed this session (all on `master`, pushed unless noted)

1. **Cleanup commit `ade0133`** — removed 4 spent one-shots
   (`reclassify_failures.py` shim, `migrate_v0_0_5.py`, two `migrate_*.sql`
   whose columns are now in `db.py`'s baseline schema), fixed the wrong
   "`--parallel` is a stub" claim in both the doc AND `cargo_drive.py`'s
   docstring, documented the live-mine pipeline + all CLI flags, added a
   CHANGELOG "Unreleased" section.
2. **Tests + CI commit `929023e`** — first test suite (62 tests, stdlib
   `unittest`, also pytest-collectable) under `tests/`: bucketing/era-floor,
   MSRV parser incl. the workspace-inheritance regression, schema
   validation, sampler filter. `.github/workflows/ci.yml` (2 jobs:
   compile+pytest on 3.11/3.12; rebuild+verify index). **CI is green**
   (verified via API; first-ever run on the repo). pyproject version
   0.0.2→0.0.5, dropped phantom PyGithub dep, added `dev` extra + pytest
   config.
3. **Reproduction runbook (uncommitted)** — `docs/cargo/reproduction-runbook.md`,
   defense-grade, for an external verifier of the `ds1-full-crack-r2`
   artifact. Three tracks: A (verify entries, Python-only, ~10min),
   B (rebuild a fat image + re-verify one reproduction's fingerprint),
   C (full re-run). All Track-A commands verified against the live cohort
   (now 1,415 after the native-dep merge). Brought `docs/findings/` into
   the repo (provenance docs)
   so the runbook's citations resolve; fixed all outside-repo dead links
   across README + docs/cargo.

## Key numbers (recomputed from the 1,415 published entries)

- **Reproducibility: 54.3 %** (1,415/2,608), 95 % Wilson CI 52.3–56.2 %.
  This is the **merged** headline = Run B (1,359, 52.1 %) + OpenSSL-stretch
  (+48) + native-dep (+8) recovery sub-cohorts. The layered 52.1 → 53.9 →
  54.3 story is in runbook §0 and §6 — do not conflate the layers.
- **Breaking rate (RQ2): 6.1 %** of reproduced (86 breaking / 1,329 non-breaking).
- **Version split:** 1,224 patch / 170 minor / 20 major / 1 other.
- **Denominator caveat:** the 2,608-candidate input and `pipeline.sqlite`
  are git-ignored (crack only). Numerator (1,415 entries) is fully
  published & independently verifiable; the *rate* needs the crack DB or
  a full re-run. Runbook §5 is explicit about this.
- **DB run_ids:** the three recovery sub-cohorts were merged in
  `pipeline.sqlite` into one run_id `ds1-full-crack-r2.1` (82 candidates,
  56 ok), recovery-wins dedup. Pre-merge backup on crack at
  `/tmp/pipeline.sqlite.bak-premerge-*`.

## Live-mine (2024–2025 recent cohort, for RQ3) — COMPLETE

- **Done.** `data/live-mine/candidates_enriched.jsonl` on crack =
  **5,401 enriched candidates** (5,357 fresh + 44 resumed), ~90 % of the
  6,000 monthly-stratified sample survived `--require-cargo`. Almost all
  Dependabot (5,393) + 8 human.
- Pipeline: `cargo_live_search.py` (957K raw hits, `language:Rust`, dual
  Bump+update queries) → `cargo_live_sample.py` (6,000 stratified, seed
  1337) → `rebatchi_to_candidate.py --require-cargo`. Launched via
  `scripts/launch_live_mine.sh`.
- The MSRV workspace-inheritance parser crash that bit Stage 3 mid-run
  was fixed (commit `e72f931`, in `master`); the fix held through the
  full rerun.
- **NEXT STEP (the big one):** drive this cohort through `cargo_drive`
  to produce the recent-cohort reproductions, then the RQ3
  historical-vs-recent comparison becomes possible. Not yet started.
  Note: 5,401 candidates × reproduction time is a multi-day run; will
  need fat images for 2024–2025-era toolchains (bookworm/trixie, 1.75+).

## Open threads / deferred

- **Run A** (multi-attempt `--attempts 3` headline run on DS1) — deferred
  by user; user will ask supervisors whether a defensible p-value sample
  multi-run is an acceptable alternative to the full 12-day run.
- **Grafana `dataset-results.json`** still filters on the old
  `ds1-full-crack-r2-openssl-stretch` run_id, which was merged into
  `ds1-full-crack-r2.1` — that panel will read empty until repointed.
- **2021 cohort −4.9pp regression** and the single `ok_after_relock` —
  open questions in `docs/findings/ds1-full-r2-findings.md` §Open questions.

Resolved since first draft: `register_fingerprint` deleted; OpenSSL +
native-dep case studies written (`docs/findings/*-case-study.md`); the
two cohort-builder scratch scripts committed to `scripts/`;
origin repointed to `DURP`.

## Presentation

7-slide midterm deck is built (Google Slides, user's machine): Title →
Why&What (DURP, Cargo counterpart to BUMP) → Research Questions (RQ1
reproducibility / RQ2 breaking / RQ3 historical-vs-recent / RQ4 failure
taxonomy) → Pipeline & Reproduction Contract → Dataset funnel → [Grafana
live for results] → Where-we-are/What's-next. Results shown via Grafana,
not slides.

## Environment / access reminders

- Run host is **crack** (`ssh crack`, repo at `~/rp2026`, flat layout —
  scripts/pipelines/lib/data directly under it, NOT under dep-updates-poc/).
- `GITHUB_TOKEN` is in `crack:~/rp2026/.env`.
- `.venv` is on crack; local Mac python has no pytest (suite runs via
  `python -m unittest discover tests`).
