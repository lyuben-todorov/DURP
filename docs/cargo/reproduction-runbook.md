# Reproduction runbook — verifying the DURP Cargo results

**Audience:** an examiner or independent researcher who wants to verify
the headline claims of the Cargo sub-question from the published
artifacts, not take them on trust.

**Artifact under verification:** the `ds1-full-crack-r2` branch of the
data repository
([`lyuben-todorov/dep-updates-rp-data`](https://github.com/lyuben-todorov/dep-updates-rp-data/tree/ds1-full-crack-r2)),
wired into this repo as the `data/cargo/` submodule. It contains **1,415
reproduced dependency-update entries**, one JSON per PR, each carrying
the full environment fingerprint needed to rebuild and re-verify it.

This runbook has three tracks of increasing cost and strength:

| Track | What it proves | Needs | Time |
| --- | --- | --- | --- |
| **A. Verify the published entries** | The 1,415 entries are schema-valid, internally consistent, and the numerator-side claims (counts, breaking rate, version-type split) are exactly as reported | Python only | ~10 min |
| **B. Re-verify a reproduction** | A specific entry's build is *actually* reproducible — rebuild its fat image, confirm the environment fingerprint matches, re-run the test pair | Docker + network | ~15 min/entry |
| **C. Full re-run from raw DS1** | The whole pipeline, end to end, reproduces the cohort | Docker + GitHub token + days | ~4 days |

Track A is what most verifiers want. Track B is the strongest single
check — it independently re-derives an entry's reproducibility from the
recipe. Track C is for someone reproducing the *study*, not just the
*results*; it is covered by [`running-a-batch.md`](running-a-batch.md)
and summarised here.

---

## 0. The headline claims, and what each track can verify

The claims a verifier should be able to check:

| # | Claim | Verifiable by |
| --- | --- | --- |
| C1 | The reproduced cohort is **1,415 entries**, all schema v0.0.5 | Track A |
| C2 | Among reproduced PRs, the **breaking rate is 6.1 %** (86/1,415) | Track A |
| C3 | Version-update split: **1,224 patch / 170 minor / 20 major / 1 other** | Track A |
| C4 | Each entry's recorded environment fingerprint **rebuilds to the same digest** | Track B |
| C5 | **Reproducibility rate is 54.3 %** (1,415 of 2,608 candidates), 95 % Wilson CI 52.3–56.2 % | Track C (see §5 on the denominator) |

**Read this boundary carefully — it is deliberate.** The *numerator*
(the 1,415 reproduced entries) is fully published, so C1–C4 are
independently verifiable from the artifact alone. The *denominator* (the
2,608-candidate input cohort and the per-candidate `drive_state` ledger)
is **not** in the published artifact — it lives in the run host's working
data (`data/rebatchi/ds1_candidates_enriched.jsonl` and
`data/pipeline.sqlite`, both git-ignored). So **C5's rate cannot be
recomputed from the published data alone**; it requires either the run
host's database or a full Track-C re-run. §5 explains how to obtain or
regenerate the denominator. We flag this rather than imply the rate is
checkable from the entries — it is not.

### The headline is layered (do not skip)

Several numbers appear in the project's notes; all are correct and they
measure different things. The published artifact is the **merged**
cohort — Run B plus two documented image-substitution sub-cohorts:

| Layer | Reproduced / 2,608 | Rate | 95 % Wilson CI |
| --- | ---: | ---: | --- |
| **Run B alone** (`ds1-full-crack-r2`, single end-to-end pass) | 1,359 | **52.1 %** | 50.2–54.0 % |
| **+ OpenSSL-stretch sub-cohort** (+48) | 1,407 | 53.9 % | 52.0–55.9 % |
| **+ native-dep recovery sub-cohort** (+8) → **published** | **1,415** | **54.3 %** | 52.3–56.2 % |

Each sub-cohort is an environment-substitution recovery run with its own
`run_id`, kept as a measured delta and then merged into the published
branch:

- **OpenSSL-stretch (+48):** candidates failing under their era-floor fat
  image (Debian shipping only libssl 1.1.x) that reproduce under a
  stretch-era image (libssl 1.0.2 + 1.1.0 dual). See §6.
- **native-dep (+8):** `NATIVE_DEP_MISSING` candidates recovered by
  rebuilding stale fat images with the round-2 native-dep apt layer (+ a
  few added packages). See
  [`../findings/native-dep-case-study.md`](../findings/native-dep-case-study.md).

A verifier who wants the strict single-contract number should cite Run
B's **52.1 %**; the published artifact's **54.3 %** includes both
deliberate, separately-run recoveries — not silent inflation.

---

## 1. Prerequisites

```bash
# Clone the repo WITH the data submodule on the verified branch.
# (The repository root IS the project root — no nested subdirectory.)
git clone --recurse-submodules https://github.com/lyuben-todorov/DURP.git
cd DURP

# Point the data submodule at the artifact branch under verification.
git -C data/cargo fetch origin ds1-full-crack-r2
git -C data/cargo checkout ds1-full-crack-r2

# Install the shared library (schema validator + models).
pip install -e .
```

Confirm you have the artifact:

```bash
ls data/cargo/cargo-*.json | wc -l        # expect: 1415
```

If this prints 1415 you are on the verified branch. (The submodule's
default branch `main` carries the two seed entries only; the
`ds1-full-crack-r2` checkout is what holds the full cohort.)

For Track B you additionally need Docker with buildx (a
`docker-container` driver) and outbound network to
`snapshot.debian.org` and crates.io. For Track C see
[`running-a-batch.md`](running-a-batch.md) §Prerequisites.

---

## 2. Track A — verify the published entries (Python only)

This recomputes C1–C3 directly from the entry JSONs and validates every
entry against the shipped JSON Schema. No Docker, no network.

### A.1 Schema-validate all 1,415 entries

```bash
python3 - <<'PY'
import glob, json, sys
sys.path.insert(0, "lib")
from bump_ext import validate_entry, SchemaError

bad = 0
files = sorted(glob.glob("data/cargo/cargo-*.json"))
for f in files:
    try:
        validate_entry(json.load(open(f)))
    except SchemaError as e:
        bad += 1
        print(f"INVALID {f}: {e}")
print(f"validated {len(files) - bad}/{len(files)} entries against schema v0.0.5")
PY
```

Expected: `validated 1415/1415 entries against schema v0.0.5`. This
proves the artifact conforms to the contract in
[`../../schema/entry.schema.json`](../../schema/entry.schema.json).

### A.2 Recompute the headline counts (C1–C3)

```bash
python3 - <<'PY'
import glob, json, collections
E = [json.load(open(f)) for f in glob.glob("data/cargo/cargo-*.json")]
N = len(E)
cat = collections.Counter(e["category"] for e in E)
vut = collections.Counter(e["update"]["versionUpdateType"] for e in E)
sv  = collections.Counter(e["schemaVersion"] for e in E)

print(f"C1  total reproduced entries : {N}")
print(f"    schema versions          : {dict(sv)}")
print(f"C2  category split           : {dict(cat)}")
br = cat.get("breaking", 0)
print(f"    breaking rate            : {br}/{N} = {100*br/N:.1f}%")
print(f"C3  versionUpdateType split  : {dict(vut)}")
PY
```

Expected output:

```
C1  total reproduced entries : 1415
    schema versions          : {'0.0.5': 1415}
C2  category split           : {'non-breaking': 1329, 'breaking': 86}
    breaking rate            : 86/1415 = 6.1%
C3  versionUpdateType split  : {'patch': 1224, 'minor': 170, 'major': 20, 'other': 1}
```

**What this establishes.** Every reproduced PR carries an explicit
category decided by the pre/post build outcome (breaking = post-bump
build fails where pre-bump passed; non-breaking = both pass). 6.1 % of
*reproducible* Cargo Dependabot updates in this cohort are breaking —
notably lower than Maven's BUMP, and a result a reader can recompute
in one command.

### A.3 Spot the cross-field consistency the schema can't catch

```bash
python3 - <<'PY'
import glob, json
issues = 0
for f in glob.glob("data/cargo/cargo-*.json"):
    e = json.load(open(f))
    # A reproduced entry must carry at least one environment fingerprint
    # and no unreproducibilityReason.
    fps = e["reproduction"]["environmentFingerprints"]
    if not fps:
        issues += 1; print(f"{e['id']}: no fingerprint")
    if e.get("unreproducibilityReason"):
        issues += 1; print(f"{e['id']}: has unreproducibilityReason but is an entry")
    # breaking ⇒ failure populated; non-breaking ⇒ failure null
    if e["category"] == "breaking" and e["failure"] is None:
        issues += 1; print(f"{e['id']}: breaking but no failure block")
print(f"cross-field issues: {issues}")
PY
```

Expected: `cross-field issues: 0`.

---

## 3. Track B — re-verify a single reproduction (Docker)

This is the strongest check: take one published entry, rebuild the exact
fat image from its recorded recipe, confirm the environment fingerprint
matches what the entry claims, and re-run the pre/post test pair. If the
fingerprint matches and the build outcome matches the recorded category,
the entry's reproducibility is independently confirmed.

### B.1 Worked example

```bash
ENTRY=data/cargo/cargo-370021bc.json
python3 -m json.tool "$ENTRY" | head -40
```

`cargo-370021bc` is `swift-nav/ntripping#27`, a Dependabot bump of
`vergen 3.2.0 → 5.0.1` (a **major** bump) that **breaks** the build.
Its recorded `reproduction.fatImage` is
`rustVersion 1.56.0, debianRelease buster, aptSnapshot 20211231T000000Z`.

### B.2 Rebuild the fat image and verify

`cargo_regenerate.py` does the whole loop: it reads the entry, rebuilds
the fat image from the recorded `(rustVersion, debianRelease,
sourceDateEpoch)`, extracts `/manifest/*`, recomputes the environment
fingerprint, and compares it against the digest stored in the entry for
this host's container platform.

```bash
python3 -m pipelines.cargo.cargo_regenerate \
  --entry "$ENTRY" \
  --build-missing-bases \
  --host "$(hostname)"
```

Interpreting the exit code:

| Exit | Meaning |
| --- | --- |
| `0` | **Fingerprint matched** and (if tests ran) the build outcome matched the recorded category. The entry is independently re-verified. |
| `1` | Fingerprint **mismatch** — the rebuilt environment differs from what the entry was validated against. See §3.3. |
| `2` | Thin-image build failed (toolchain/network issue on your host, not an entry problem). |
| `3` | Fat image missing and `--build-missing-bases` not passed. |
| `4` | Build outcome didn't match the recorded category (pass/fail flipped). |

A `0` appends a `verifiedOn` record to the entry — over time these
accumulate cross-host verifications, which is itself reproducibility
evidence.

`--images-only` is a faster, weaker check: it builds the fat + thin
images and checks the environment fingerprint, but **does not compile or
run `cargo test`**. So it proves the *environment* rebuilds to the same
fingerprint — not that the code compiles, and not that the
breaking/non-breaking outcome holds. The `verifiedOn` record it writes
has `outcomeMatch: null` to reflect that. The default (full) verify is
the one that confirms reproduction; reach for `--images-only` only when
you specifically want a cheap environment-determinism check. (The old
flag name `--skip-tests` still works as an alias.)

### B.3 On a platform-architecture mismatch

Each entry stores fingerprints **per container platform** (e.g.
`linux/amd64`, `linux/arm64`), because `packages.txt` and `rustc.txt`
differ by architecture while the reproduction contract (same apt
snapshot, same SDE, same rust) is architecture-agnostic. If you verify
on an architecture not yet recorded in the entry, `cargo_regenerate`
runs in **append mode**: it does not fail, it adds your architecture's
fingerprint to the entry. A hard fingerprint *mismatch* (exit 1) only
happens when your architecture **is** already recorded and the digest
differs — that is the real failure signal. See
[`reproducible-builds.md`](reproducible-builds.md) for why the contract
is environment-fingerprint equality and not byte-identical OCI digests.

### B.4 How many entries should you re-verify?

One proves the mechanism. For a defensible sample, re-verify ~10–20
spanning different fat images (the cohort uses six: `1.49.0-buster`
covers 641 entries, `1.39.0-stretch` 364, `1.56.0-buster` 211,
`1.35.0-stretch` 113, `1.39.0-buster` 77, `1.56.0-bullseye` 1). The
distribution is recomputable:

```bash
python3 - <<'PY'
import glob, json, collections
c = collections.Counter()
for f in glob.glob("data/cargo/cargo-*.json"):
    fi = json.load(open(f))["reproduction"]["fatImage"]
    c[f'{fi["rustVersion"]}-{fi["debianRelease"]}'] += 1
for k, v in c.most_common():
    print(f"  {k}: {v}")
PY
```

---

## 4. Track C — full re-run from raw DS1

Reproducing the *study* rather than the *results*: mine candidates from
Rebatchi DS1, enrich, build fat images, drive the batch, classify. This
is fully documented in [`running-a-batch.md`](running-a-batch.md). The
parameters that reproduce `ds1-full-crack-r2` specifically:

- **Input:** all 2,608 of `ds1_candidates_enriched.jsonl` (see §5 on
  obtaining this).
- **Driver:** `--max-sde-date 2023-12-31`, `--relax-locked`,
  `--attempts 1`, `--shuffle --shuffle-seed 1337`. Run B used
  `--parallel 8`; the findings note this inflated TIMEOUT via disk
  contention and recommend `--parallel 5`.
- **Fat images:** the bucketer selects them; the six families above plus
  the `1.30.0-stretch-20181231` image (96 candidates, all
  non-reproducible, hence no entries). All are rebuildable from
  [`../../docker/cargo-fat/index.json`](../../docker/cargo-fat/index.json).
- **Then** the OpenSSL-stretch (+48, §6) and native-dep (+8) recovery
  sub-cohorts to reach the merged 1,415.

Expect ~4 days wall-clock at `--parallel 5` on a 16-core/32 GiB host.
Reproducing to the *exact* entry set is not guaranteed — a handful of
candidates are sensitive to upstream repo availability and
`snapshot.debian.org` coverage at run time (see the
`REPO_GONE`/`NETWORK_ERROR` discussion in
[`../findings/ds1-full-r2-findings.md`](../findings/ds1-full-r2-findings.md)).
The reproducibility *rate* should land within the reported CI; the
specific reproduced set may differ by a few candidates.

---

## 5. The denominator (the 2,608 candidates)

To compute the **rate** (C5) you need the input cohort, which is not in
the published entry artifact. Three ways to obtain it, strongest first:

1. **Re-mine it (Track C, fully independent).** Run
   [`running-a-batch.md`](running-a-batch.md) §3 Option B: stream the
   Rebatchi DS1 rar archives through `rebatchi_ds1_filter.py`, then
   enrich with `rebatchi_to_candidate.py --require-cargo`. This
   regenerates `ds1_candidates_enriched.jsonl` from the public Rebatchi
   dataset. The candidate count is sensitive to upstream repo
   availability at mining time, so expect ~2,608 ± a few.

2. **Obtain the run host's database.** `data/pipeline.sqlite` holds a
   `drive_state` row for all 2,608 candidates under `run_id =
   'ds1-full-crack-r2'`, plus the two recovery sub-cohorts under their own
   run_ids (`…-openssl-stretch`, `…-native-deps`, `…-native-deps-followon`).
   Run B alone (52.1 %):

   ```sql
   SELECT
     SUM(status IN ('ok','ok_after_relock'))                AS reproduced,
     COUNT(*)                                                AS candidates,
     ROUND(100.0*SUM(status IN ('ok','ok_after_relock'))/COUNT(*), 1) AS pct
   FROM drive_state WHERE run_id = 'ds1-full-crack-r2';
   ```

   The published 54.3 % adds the candidates the sub-cohort runs flipped to
   `ok` (48 + 8) on top of Run B's numerator — i.e. count distinct
   candidate_keys that reached `ok`/`ok_after_relock` in *any* of the
   four run_ids, over the 2,608 denominator. This DB is git-ignored (a
   rebuildable index, not a source of truth); it is the artifact to
   request if you want to check the rate without a full re-run.

3. **Trust the numerator, bound the denominator.** The published 1,415
   entries are the verified numerator. If you independently establish the
   denominator is 2,608 (from the Rebatchi DS1 Cargo cohort), the rate
   follows: 1,415 / 2,608 = 54.3 %, Wilson CI 52.3–56.2 %.

We state plainly: **only path 1 or 2 lets you recompute C5
independently.** The entries alone do not contain the denominator.

---

## 6. The recovery sub-cohorts (+48 OpenSSL, +8 native-dep)

The published cohort merges Run B (1,359 entries) with two
image-substitution recovery sub-cohorts: OpenSSL-stretch (+48) and
native-dep (+8), reaching 1,415. Both are worked examples of the same
move — diagnose an *environment-caused* failure, substitute a corrected
environment, re-run under a distinct `run_id`, merge the recovered
entries as a measured delta.

### 6a. OpenSSL-stretch (+48)

- **Problem.** Crates using `openssl-sys` < 0.9.x link against libssl
  1.0.x. The era-floor bucketer routes 2018–2020 candidates to
  buster/bullseye fat images, which ship only libssl 1.1.x. The link
  fails; the classifier records `OPENSSL_MISMATCH`.
- **Intervention.** Debian **stretch** dual-ships libssl 1.0.2 and 1.1.0.
  The `OPENSSL_MISMATCH` candidates were re-run under a forced stretch
  image (`--force-fat-image rp2026/cargo-fat:1.39.0-stretch-20191231`)
  with a distinct `run_id`, so results never polluted the parent run.
- **Result.** 48 of the cohort reproduced under stretch and were merged
  into the published branch.

This is run, recorded, and merged transparently — not folded silently
into Run B's number. The full method, the 48/64 recovery, and the
DB-verified classifier-precision finding it surfaced (14 of the 64 were
really `TEST_FAILURE`, not OpenSSL) are written up in
[`../findings/openssl-case-study.md`](../findings/openssl-case-study.md).

### 6b. native-dep (+8)

`NATIVE_DEP_MISSING` candidates whose fat image was missing a system
`-dev` package. The 12 "missing-package" cases (`cannot find -lLIB`) sat
on stale 1.39 stretch/buster images built before the round-2 native-dep
apt layer; rebuilding those images (+ adding libsfml/libcsfml/SDL2
companion packages) recovered **8**. The 6 "undefined-reference" cases
(libgcrypt/CPython ABI) did *not* recover — confirming the
missing-package vs ABI split. Full write-up, including the
provisioning-vs-runtime floor the experiment found, in
[`../findings/native-dep-case-study.md`](../findings/native-dep-case-study.md).

A verifier who wants the strict single-image-policy result should use Run
B's 52.1 %; the published artifact's **54.3 %** includes both documented
recoveries.

---

## 7. What this artifact does and does not establish

Stated honestly, because a defense should pre-empt the question:

**Establishes:**

- 1,415 real-world Cargo dependency-update PRs reproduce under a pinned
  environment (rustc + Debian release + apt snapshot), each with a
  rebuildable fingerprint (Track A + B).
- Of reproducible updates, 6.1 % are build-breaking (Track A).
- The reproduction contract is environment-fingerprint equality, robust
  to OCI-digest jitter (Track B; rationale in
  [`reproducible-builds.md`](reproducible-builds.md)).

**Does not establish (and we don't claim it):**

- **Bitwise reproducibility.** Unlike Maven's BUMP (byte-identical Docker
  images, multi-OS), our contract is environment-fingerprint match on a
  single OS family. This is a deliberate trade for coverage of older
  corpora where the maintainer's exact toolchain is unrecoverable.
- **Multi-execution / multi-OS sanity.** Run B is single-attempt on amd64.
  Flaky-test sensitivity (`--attempts N`) and cross-OS agreement are
  future work; BUMP performs both.
- **Classifier precision beyond the audited samples.** The failure
  taxonomy was audited at ~80–95 % precision on samples (see findings
  doc); two classes have full-cohort ground-truth checks via the §6
  recovery runs — `OPENSSL_MISMATCH` (the +48 study) and
  `NATIVE_DEP_MISSING` (the +8 study, which also split the class into
  missing-package vs ABI). Category *counts* elsewhere are upper bounds,
  not exact.

---

## 8. Provenance and references

- **Verified branch:** `ds1-full-crack-r2`,
  [`lyuben-todorov/dep-updates-rp-data`](https://github.com/lyuben-todorov/dep-updates-rp-data/tree/ds1-full-crack-r2),
  1,415 entries, schema v0.0.5.
- **Run findings (authoritative numbers):**
  [`../findings/ds1-full-r2-findings.md`](../findings/ds1-full-r2-findings.md)
  — Run B headline, per-category deltas, per-year rates, audit results.
  See also [`../findings/`](../findings/) for the baseline run and
  dataset provenance.
- **Schema:** [`../../schema/entry.schema.json`](../../schema/entry.schema.json)
  + [`../shared/schema.md`](../shared/schema.md).
- **Failure taxonomy:** [`../../schema/failure-taxonomy.md`](../../schema/failure-taxonomy.md).
- **Reproduction model (why fingerprint, not OCI digest):**
  [`reproducible-builds.md`](reproducible-builds.md).
- **Image selection logic:** [`image-selection.md`](image-selection.md).
- **Full re-run runbook:** [`running-a-batch.md`](running-a-batch.md).

All numbers in §0–§3 were recomputed directly from the 1,415 published
entries; the commands above regenerate them.
