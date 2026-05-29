# NATIVE_DEP_MISSING recovery — image-rebuild sub-cohort

A second image-substitution recovery experiment, parallel to the
OpenSSL-stretch study. Run id `ds1-full-crack-r2-native-deps`, host
`crack`, 2026-05-29. Carved from the 18 candidates the round-2 run
(`ds1-full-crack-r2`) classified `NATIVE_DEP_MISSING`.

## Hypothesis

`NATIVE_DEP_MISSING` is not one failure but two, distinguishable by the
linker error:

- **missing-package** — `cannot find -lLIB`. The `-dev` package is
  absent from the fat image. *Predicted: recoverable by baking the
  package in.*
- **undefined-reference** — `undefined reference to <symbol>`. The
  library is present but the crate links it wrong (ABI/version/path
  mismatch, typically a `*-sys` build script). *Predicted: NOT
  recoverable by a package rebuild.*

The 12 missing-package candidates all sat on the three `1.39` stretch /
buster fat images built **2026-05-12**, before the round-2 native-dep
apt layer landed (2026-05-13). The libs they needed
(`libxtst-dev`, `libsdl2-dev`, `libsnappy-dev`, `librrd-dev`) were
already declared in the Dockerfile — the images were simply stale.
`libsfml-dev` was the one genuinely-missing package; it was added to the
Dockerfile for this run.

## Method

1. Add `libsfml-dev` to `docker/cargo-fat/Dockerfile` (available on
   stretch 2.4.1 → bookworm).
2. Rebuild the three stale images with the current Dockerfile:
   `1.39.0-stretch-20191231`, `1.39.0-stretch-20191123`,
   `1.39.0-buster-20191231`. Verified each carries the cohort's libs
   (`ldconfig -p`).
3. Carve the 18 `NATIVE_DEP_MISSING` candidates
   (`scripts/build_native_dep_cohort.py`) and re-drive under a separate
   `run_id`, normal bucketing (each candidate routes to its now-rebuilt
   era image). Results never touch the parent headline — measured as a
   delta, like OpenSSL-stretch.

## Result

| Original mechanism | n | → `ok` | → still fail |
| --- | ---: | ---: | ---: |
| missing-package (`cannot find -lLIB`) | 12 | **7** | 5 |
| undefined-reference (`undefined reference`) | 6 | **0** | 6 |
| **total** | **18** | **7** | **11** |

**Both predictions held.**

- **7 recovered** (`not_reproducible → ok`): the six `bvanrijn/image-to-mc`
  candidates (`-lXtst`) and `evanjs/rrbg` (`-lSDL2`). The bake worked.
- **0 of the 6 undefined-reference candidates recovered** — confirming
  they are ABI/linkage problems (`libgcrypt`'s `gcry_randomize`,
  CPython's `PyTuple_New` / `PyExc_Exception` in the `retworkx` /
  `ffizer` / `sc2-pathlib` `*-sys` crates), not missing packages. A
  rebuild cannot fix them; they need version-matched linkage work.

### The 5 missing-package non-recoveries advanced rather than regressed

In every one of the 5, the **original linker error cleared** — the fix
worked at the link level — and a *later, different* blocker surfaced:

| candidate | original | after rebuild | reading |
| --- | --- | --- | --- |
| `NoraCodes/deucalion#14,#17` | `-lsfml-graphics` | `cannot find -lcsfml-graphics` | the Rust `sfml` crate links the **C** binding `libcsfml`, not C++ `libsfml`. Needs `libcsfml-dev`. |
| `sunjay/caves#112` | `-lSDL2` | `cannot find -lSDL2_image` | SDL2 linked; needs the `SDL2_image` companion (`libsdl2-image-dev`). |
| `citahub/cita-common#184` | `-lsnappy` | `zmq-sys` build failure | snappy linked; a different native dep (libzmq) surfaced. |
| `GiantPlantsSociety/diamond#240` | `-lrrd` | `TEST_FAILURE` | **fully compiled and linked** — now reaches the test phase and fails there. No longer a native-dep miss at all. |

None regressed. `diamond#240` is now a genuine `TEST_FAILURE`
reproduction; the others are one apt package away.

## Implications

1. **A second worked example of image-substitution recovery**, distinct
   from OpenSSL: there, a *different Debian release* (stretch's dual
   libssl) was the substitution; here it is *rebuilding a stale image
   with an already-correct recipe* plus one package add. Same
   methodological shape (diagnose env-caused failure → substitute
   corrected env → measure delta under a separate run_id).

2. **`NATIVE_DEP_MISSING` should be split in the taxonomy.**
   "missing-package" (pipeline-fixable: bake the `-dev` package) vs
   "undefined-reference / ABI" (not fixable by baking). The class counts
   in the headline taxonomy conflate two very different recoverability
   profiles.

3. **Easy follow-on, ~+3 candidates.** `libcsfml-dev` (2.3-3) and
   `libsdl2-image-dev` (2.0.1) are both available on stretch and would
   recover `deucalion#14/#17` and `caves#112`. One Dockerfile line each.
   Diminishing returns past that — the remaining failures are real test
   failures or genuine ABI problems.

4. **Headline impact, if merged.** 7 recovered / 2,608 candidates =
   +0.27 pp. As an isolated number this is small; its value is
   methodological (the split) and compounding (native-dep recovery
   stacks with the OpenSSL +48 and any future sub-cohort). It is a
   *delta study*, not a correction to the 53.9 % — like OpenSSL, the
   decision to merge these 7 into the published branch is separate.

## Provenance

- Cohort builder: `scripts/build_native_dep_cohort.py`
- Run id: `ds1-full-crack-r2-native-deps` (18 candidates, `drive_state`
  + `drive_state_classifications` in `data/pipeline.sqlite` on the run
  host)
- Entries for the 7 `ok` written to `/tmp/native-dep-entries` (not yet
  merged into the published branch — pending the merge decision).
- Dockerfile change: `libsfml-dev` added to the graphics block.
