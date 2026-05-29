# OpenSSL-stretch sub-cohort — a case study in image substitution and classifier precision

A self-contained account of the OpenSSL recovery experiment on the
`ds1-full-crack-r2` cohort. It does two things at once: it **recovers 48
candidates** the main run could not reproduce, and — more interestingly
for the thesis — it **measures the failure classifier's precision** on
one category against ground truth, which is otherwise unobservable.

All numbers below are recomputable from `data/pipeline.sqlite` on the run
host; the exact queries are inline so the claims are checkable, not
asserted.

## The problem

Rust crates that bind OpenSSL through `openssl-sys` link against the
system libssl. Older crates (`openssl-sys` 0.9.x and earlier) assume
libssl **1.0.x**. The era-floor bucketer routes 2018–2020 candidates to
buster- or bullseye-era fat images, and those Debian releases ship only
libssl **1.1.x**. The link step fails on the ABI gap, and the failure
classifier — reading the build log — labels the candidate
`OPENSSL_MISMATCH`.

In the main Run B (`ds1-full-crack-r2`), **64 candidates** were
classified `OPENSSL_MISMATCH`:

```sql
SELECT category, COUNT(*) FROM drive_state_classifications
WHERE run_id = 'ds1-full-crack-r2' AND category = 'OPENSSL_MISMATCH';
-- 64
```

These contributed nothing to the reproducible cohort — all 64 were
`not_reproducible` under their era-floor images.

## The intervention: image substitution

Debian **stretch** (the release before buster) dual-ships libssl
**1.0.2 and 1.1.0**. A stretch-era fat image can therefore satisfy
crates that need either ABI. We carved the 64 `OPENSSL_MISMATCH`
candidates into a sub-cohort and re-ran them under a forced stretch
image, bypassing the bucketer, with a distinct `run_id` so results never
contaminated the main run:

```
python -m pipelines.cargo.cargo_drive \
  --candidates data/rebatchi/openssl_cohort.jsonl \
  --force-fat-image rp2026/cargo-fat:1.39.0-stretch-20191231 \
  --run-id ds1-full-crack-r2-openssl-stretch \
  ...
```

All 64 ran against the single image
`rp2026/cargo-fat:1.39.0-stretch-20191231`:

```sql
SELECT fat_image_tag_used, COUNT(*) FROM reproduction_attempts
WHERE run_id = 'ds1-full-crack-r2-openssl-stretch'
GROUP BY fat_image_tag_used;
-- rp2026/cargo-fat:1.39.0-stretch-20191231 | 64
```

## Result 1 — recovery: 48 of 64 (75 %)

```sql
SELECT status, COUNT(*) FROM drive_state
WHERE run_id = 'ds1-full-crack-r2-openssl-stretch'
GROUP BY status;
-- ok               | 48
-- not_reproducible | 16
```

**48 of 64 candidates (75 %) reproduce under stretch** — a cohort the
main run scored 0/64. These 48 are merged into the published
`ds1-full-crack-r2` artifact; they are the difference between the Run B
headline (1,359 / 52.1 %) and the published merged headline
(1,407 / 53.9 %). Example recovered candidates:
`fishbrain/ssh-auth-github#134`, `sanisoclem/calcver-cli#58`.

This validates image substitution as a principled recovery technique:
when the bucketer's era-appropriate image is wrong for a *specific*
ABI reason, substituting an image that resolves that reason recovers the
candidate without weakening the contract (the reproduction still happens
in a single pinned environment; only the environment chosen differs).

## Result 2 — classifier precision: 14 of 64 were never OpenSSL

This is the more valuable finding. The 16 candidates that **still failed**
under stretch were re-classified from their new logs:

```sql
SELECT c.category, COUNT(*)
FROM drive_state d
JOIN drive_state_classifications c
  ON c.run_id = d.run_id AND c.candidate_key = d.candidate_key
WHERE d.run_id = 'ds1-full-crack-r2-openssl-stretch'
  AND d.status = 'not_reproducible'
GROUP BY c.category;
-- TEST_FAILURE      | 14
-- OPENSSL_MISMATCH  | 1
-- NIGHTLY_REQUIRED  | 1
```

Under stretch, libssl cannot be the cause — the ABI gap is resolved. So
these 16 reveal their *true* terminal cause. **14 of the original 64 were
actually `TEST_FAILURE`**, not OpenSSL failures at all. The classifier
had labelled them `OPENSSL_MISMATCH` because `openssl-sys` build-script
output appears early in the log; the classifier keyed on that chatter
rather than the terminal cause (a test panic later in the run).

This gives a **ground-truth precision estimate for the
`OPENSSL_MISMATCH` class**:

- Of 64 labelled `OPENSSL_MISMATCH`, at most 50 were genuinely OpenSSL
  (48 recovered + 1 still-OpenSSL + 1 NIGHTLY actually-not-openssl
  rounds the genuine set to ~49–50).
- **Precision ≈ 48–50 / 64 ≈ 75–78 %.** The dominant error mode (14/64 ≈
  **22 %**) is `TEST_FAILURE` misread as `OPENSSL_MISMATCH`.

Honest caveat on the misclassified set: the 14 cluster on a few repos
(`lukaspustina/mhost`, `lukaspustina/rat`), so they represent fewer than
14 *distinct* root causes. The precision figure is for the candidate
population, not for distinct failure signatures.

## Why this matters for the thesis

1. **The headline is honestly decomposed.** 53.9 % = 52.1 % (Run B) +
   the 48 recovered here. The recovery is a documented, separately-`run_id`'d
   sub-cohort, not a silent adjustment. A defender can show exactly where
   the +1.8 pp comes from.

2. **Failure-category counts are upper bounds, and we can prove it for
   one class.** This is the only category for which we have a full-cohort
   ground-truth check (because forcing stretch *removes* the OpenSSL
   variable and lets the true cause surface). The general lesson —
   that early build-script chatter can mask the terminal cause — applies
   to the whole Scheme-2 taxonomy, so every category count should be read
   as "at most this many," not "exactly this many." The sub-agent audits
   in [`ds1-full-r2-findings.md`](ds1-full-r2-findings.md) reach the same
   ~80–95 % precision conclusion by sampling; this experiment reaches it
   for `OPENSSL_MISMATCH` by construction.

3. **It demonstrates a reusable method.** The same shape — carve a
   suspected-pipeline-fixable cohort, force a different image, re-run with
   a separate `run_id`, re-classify the survivors — is how any future
   category (e.g. the `NATIVE_DEP_MISSING` recovery) should be both
   *recovered* and *precision-checked*.

## Relationship to the baseline run's OpenSSL experiment

The first full run (`ds1-full-crack`) ran an earlier, messier version of
this experiment (iterations v1–v5 in
[`ds1-full-findings.md`](ds1-full-findings.md)), where the *baseline*
classifier over-reported OpenSSL by ~8–25× (378 raw labels, ~17 genuine)
and a schema-validation bug initially discarded 5 successful stretch
reproductions. Run B's classifier is sharper (64 labels, ~50 genuine,
~78 % precision vs the baseline's ~12 %), and this clean
64→48/16 result is the version to cite. The baseline experiment is
retained as the methodological prehistory, not the headline.

## Reproducing this case study

The sub-cohort run lives in `data/pipeline.sqlite` under `run_id =
'ds1-full-crack-r2-openssl-stretch'` (64 rows). The four SQL queries
above regenerate every number here, and the `drive_state` rows for that
`run_id` are the authoritative list of which 48 candidates were
recovered.

Note on identifying the sub-cohort within the published entries: you
**cannot** isolate it by fat image alone. The recovered entries carry
`reproduction.fatImage = {rustVersion 1.39.0, debianRelease stretch}`,
but so do ~364 entries in total — the era-floor bucketer routes many
2018–2019 candidates to stretch legitimately, not just the forced
sub-cohort. The 48 are a subset of those 364, identifiable only by the
`ds1-full-crack-r2-openssl-stretch` `run_id` in the database (or by
cross-referencing the 48 `ok` candidate keys from the query above
against the entry `project`/`pr` fields). The merged artifact does not
itself record which run produced each entry.
