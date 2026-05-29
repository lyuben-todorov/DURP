# Session handoff — 2026-05-29 (session "rp2")

Snapshot of project state so a fresh or forked session picks up cold.
Supersedes nothing in `docs/findings/`; this is operational state, not
results. Delete or update freely — it is a working note, not an artifact.

## TL;DR

This session did **repo-hardening for the final defense**, not new
research: a reproduction runbook, the first test suite + CI, a docs
cleanup, branch hygiene, and it kicked off + completed the 2024–2025
live-mine. The live-mine output (5,401 candidates) is **mined but not
yet driven** — that is the obvious next work.

## Git state (as of this handoff)

**Main repo (`DURP`, https://github.com/lyuben-todorov/DURP), branch `master`:**
- Three commits this session, latest two **unpushed**:
  - `ade0133` cleanup (pushed)
  - `929023e` tests + CI (pushed)
  - `aad3bc5` reproduction runbook + docs/findings + link/clone fixes +
    submodule pointer bump to `9e536f8` (**unpushed** — `origin/master..master` = 1)
- **Untracked:** `docs/SESSION-HANDOFF.md` (this file). Working tree
  otherwise clean.
- **Default branch is `master`** (not `main`). Only `master` exists now;
  `db` and `round-2-fixes` were deleted this session (both fully merged).
- `origin` remote URL still points at the old `dep-updates-rp` name; it
  redirects to `DURP`. Optional: `git remote set-url origin
  git@github.com:lyuben-todorov/DURP.git`.

**Data submodule (`data/cargo/` → dep-updates-rp-data), branch `ds1-full-crack-r2`:**
- Checked out at `ds1-full-crack-r2`, **1,407 entries** (was 1,359 at
  session start; fetched + fast-forwarded this session). Main-repo
  pointer already bumped to it in `aad3bc5`.
- **1 unpushed commit:** `9e536f8` — README updated to v0.0.5 + cohort
  docs. Entries untouched. Append-only, safe to push.

### Pending outward actions (need user trigger)
1. Push main `master` to origin (1 commit ahead: `aad3bc5`).
2. Push the submodule's `9e536f8` to `origin/ds1-full-crack-r2`.
3. Commit `docs/SESSION-HANDOFF.md` if you want it tracked (optional —
   it's a working note).

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
   C (full re-run). All Track-A commands verified against the live 1,407
   entries. Brought `docs/findings/` into the repo (3 provenance docs)
   so the runbook's citations resolve; fixed all outside-repo dead links
   across README + docs/cargo.

## Key numbers (recomputed from the 1,407 published entries this session)

- **Reproducibility: 53.9 %** (1,407/2,608), 95 % Wilson CI 52.0–55.9 %.
  This is the **merged** headline = Run B (1,359, 52.1 %) + OpenSSL-stretch
  sub-cohort (+48). The 53.9 vs 52.1 distinction is documented in the
  runbook §0 and §6 — do not conflate them.
- **Breaking rate (RQ2): 6.1 %** of reproduced (86 breaking / 1,321 non-breaking).
- **Version split:** 1,218 patch / 168 minor / 20 major / 1 other.
- **Denominator caveat:** the 2,608-candidate input and `pipeline.sqlite`
  are git-ignored (crack only). Numerator (1,407 entries) is fully
  published & independently verifiable; the *rate* needs the crack DB or
  a full re-run. Runbook §5 is explicit about this.

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
- **Two untracked scratch scripts on crack** (`scripts/build_openssl_cohort.py`,
  `scripts/build_rerun_cohort.py`) — real artifacts, untracked. Decide:
  commit as provenance or gitignore.
- **`fat_image.py::register_fingerprint()`** — verified dead (uncalled,
  the unwired multi-arch path). Flagged, not deleted.
- **OpenSSL case study writeup** — exists scattered across findings docs;
  could be a standalone `docs/findings/openssl-case-study.md` (48/64
  recovered = 75 %; the 14 misclassified-as-OPENSSL were really
  TEST_FAILURE → classifier-precision evidence).
- **2021 cohort −4.9pp regression** and the single `ok_after_relock` —
  open questions in `docs/findings/ds1-full-r2-findings.md` §Open questions.

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
