# Scheme-2 coding codebook (for human raters)

This is the manual for hand-labelling **reproduction failures** — candidates
whose *pre-bump* build failed in the controlled fat-image environment. It exists
to validate the automated classifier (`cargo_failure_classifier.py`) against
human judgement and report inter-rater agreement (Cohen's κ), the standard the
build-failure taxonomy literature uses (Rausch et al. 2017; Vassallo et al.
2017, κ 0.62–0.8; Alfadel et al. 2021, κ 0.96).

## How to code

1. You are given a **pre-build log** and a candidate id. You see **no**
   classifier label. Read the log and assign **exactly one** category from the
   list below, by the decision rules — *not* by guessing what a regex would do.
2. Read the log **from the bottom up**. The *terminal cause* (the last
   substantive `error:` line) is what matters, not the first error or the
   generic summary. **Ignore** these summary lines — they appear on every failed
   build and say nothing about the cause:
   - `error: build failed`
   - `error: could not compile <crate> due to N previous errors`
3. If two categories seem to fit, apply the **precedence / disambiguation**
   rules in §"Confusable pairs". If still unsure, pick the category whose
   *decision rule* most specifically matches and note your uncertainty in the
   `coder_note` column.
4. Code what the log **shows**, not what you think the project "really" is. If
   the log is empty or truncated with no error line, that's `NO_LOG`.

The categories split on one underlying axis the study cares about — **is this
recoverable by more pipeline engineering, or is it a property of the corpus?**
You do **not** need to judge recoverability while coding; just apply the rules.
That axis is summarised at the end for context only.

## Categories

### REPO_GONE
The repository cloned, but the project's `Cargo.toml` / source is **absent or
gutted** — renamed, moved into a subdir we didn't find, or deleted since the PR.
- **Code it when:** the log says the manifest/source can't be found at the
  expected path; the build never really started because there was nothing to
  build.
- **Not:** a clone that failed for *network* reasons (→ `NETWORK_ERROR`); a repo
  that built but failed later.

### LOCK_FILE_STALE
`Cargo.lock` cannot be honoured under `--locked` against the pinned snapshot —
the locked versions are yanked, archive-removed, or the checksum changed.
- **Code it when:** the log mentions the lockfile needing update but `--locked`/
  `--frozen` forbidding it, a checksum-changed-between-lockfiles error, or
  "cannot update the lock file" under `--locked`.
- **Not:** a resolver failure that isn't about the *existing* lockfile (→
  `DEPENDENCY_RESOLUTION`).

### OPENSSL_MISMATCH
The `openssl-sys` (or `ring`) build script fails against the image's libssl —
version-detection failure or a link against the wrong libssl ABI. Dominant in
2018–2020 code on buster+ images (which ship only libssl 1.1.x).
- **Code it when:** the terminal failure is in openssl-sys's build, "unable to
  detect openssl version", or an openssl build-command failure.
- **Not:** a *different* missing system lib (→ `NATIVE_DEP_MISSING`).

### NATIVE_DEP_MISSING
A **non-openssl** system library/header is missing: pkg-config "Package X was
not found", or a linker "cannot find -lX" / "undefined reference to <sym>" for a
C dependency (SDL2, fuse, v4l2, snappy, gcrypt, python, …).
- **Code it when:** the terminal cause is a missing native lib at config or link
  time, and it is **not** openssl.
- **Not:** openssl (→ `OPENSSL_MISMATCH`); a pure-Rust compile error (→
  `RUSTC_BITROT`).

### NIGHTLY_REQUIRED
The crate **requires a nightly toolchain** and cannot build on any stable rustc.
- **Code it when:** a build.rs aborts with "incompatible compiler" (Rocket
  0.3/0.4, pear), a `-Z`/`#![feature(...)]`-gated feature is used, or the rustc
  error is a nightly-only feature gate (`E0554` `#![feature]` on stable, `E0658`
  use of unstable feature).
- **Not:** a stricter-but-stable rustc rejection (→ `RUSTC_BITROT`). The test:
  *would a newer **stable** rustc fix this?* If no, and it needs nightly →
  here.

### RUSTC_BITROT
Pure-Rust code that compiled on the author's (older) rustc **fails to compile on
the image's (usually newer) stable rustc** — stricter borrow-check, inference
regression, stdlib rename, a soundness fix turned hard error, etc.
- **Code it when:** the terminal cause is a rustc compile error (`error[EXXXX]`)
  that is *not* a nightly feature gate and *not* a missing native lib.
- **Subcategory (optional):** the dominant rustc error code.
- **Not:** `E0554`/`E0658` (→ `NIGHTLY_REQUIRED`); a linker error (→
  `NATIVE_DEP_MISSING`); a test that compiled but failed at runtime (→
  `TEST_FAILURE`).

### RUNTIME_CRASH
A process **ran and crashed**, rather than failing to compile: a build.rs panic,
or a SIGSEGV/signal-11 in a tool during the build.
- **Code it when:** the terminal cause is "panicked at …" inside a *build
  script* / custom build command, or a segfault.
- **Not:** a test panic that is part of `test result: FAILED` (→
  `TEST_FAILURE`); a compile error (→ `RUSTC_BITROT`).

### TEST_FAILURE
Compilation **succeeded** and the test suite **ran and reported failures** —
often author-environment assumptions (DNS, filesystem, env vars, hardware).
- **Code it when:** the log shows `test result: FAILED` / `error: test failed`,
  i.e. the build got far enough to run tests.
- **Not:** a compile error before tests (→ `RUSTC_BITROT`); a build-script panic
  (→ `RUNTIME_CRASH`).

### DEPENDENCY_RESOLUTION
The resolver failed for a reason **other than the existing lockfile**: no
matching version, a git-sourced dependency no longer reachable, an unresolvable
`[patch]` table.
- **Code it when:** "failed to select a version", "no matching package named", a
  git dep that can't be fetched/loaded, or patch-resolution failure.
- **Not:** the project's own `Cargo.lock` being rejected under `--locked` (→
  `LOCK_FILE_STALE`); a transient network blip (→ `NETWORK_ERROR`).

### NETWORK_ERROR
A **transient** network/fetch failure: zlib stream corruption mid-download,
connection timeout, DNS, git fetch failure, missing SSH auth sock.
- **Code it when:** the cause is clearly a network/transport hiccup that a retry
  would likely fix.
- **Not:** a dep that is *permanently* gone (→ `DEPENDENCY_RESOLUTION`/
  `REPO_GONE`).

### TIMEOUT
The reproducer's per-build timeout was exceeded (heavy workspaces:
libra/diem/solana). The build was progressing, just too slow.
- **Code it when:** the log/record shows the reproducer-timeout marker or
  `pre_build_timed_out`.
- **Not:** an OS-level kill for other reasons.

### OLD_MESSAGE_FORMAT
Cargo is **too old** (typically ≤ 1.34) to accept our
`--message-format=json-diagnostic-rendered-ansi` flag, so the invocation itself
is rejected. A pipeline-era artefact.
- **Code it when:** the failure is cargo rejecting our message-format flag, not
  the project's code.

### NO_LOG
The pre-log is **missing or empty** — a pipeline-side interruption (host crash,
SIGKILL) before the log flushed. Not a candidate-side failure.
- **Code it when:** there is no usable log content / no error line at all.

### OTHER
None of the above fits. The build failed for a reason the codebook doesn't name.
- **Code it when:** you've ruled out every category above. Always add a
  `coder_note` describing what you saw — `OTHER` is the signal that the taxonomy
  has a gap.

## Confusable pairs (the disambiguation rules that matter)

These pairs cause most inter-rater disagreement; apply these tests:

- **OPENSSL_MISMATCH vs NATIVE_DEP_MISSING** — both are missing-system-lib
  failures. If the lib is **openssl/ring** → `OPENSSL_MISMATCH`; **any other**
  system lib → `NATIVE_DEP_MISSING`.
- **RUSTC_BITROT vs NIGHTLY_REQUIRED** — both are rustc compile failures. Ask:
  *would a newer **stable** rustc compile it?* Stricter-stable → `RUSTC_BITROT`;
  needs **nightly** (feature gate, `-Z`, `E0554`/`E0658`, build.rs
  "incompatible compiler") → `NIGHTLY_REQUIRED`.
- **RUSTC_BITROT vs NATIVE_DEP_MISSING** — a *linker* "cannot find -lX" /
  "undefined reference" is `NATIVE_DEP_MISSING`, even though it surfaces at the
  end of compilation. A rustc `error[EXXXX]` is `RUSTC_BITROT`.
- **TEST_FAILURE vs RUNTIME_CRASH** — both involve a running process. A failure
  *inside the test suite* (`test result: FAILED`) → `TEST_FAILURE`. A panic/
  segfault in a **build script** (before/outside tests) → `RUNTIME_CRASH`.
- **TEST_FAILURE vs RUSTC_BITROT** — did compilation succeed? Tests ran and
  failed → `TEST_FAILURE`. Code never compiled → `RUSTC_BITROT`.
- **LOCK_FILE_STALE vs DEPENDENCY_RESOLUTION** — is the complaint about the
  *project's own committed `Cargo.lock`* under `--locked`? → `LOCK_FILE_STALE`.
  A resolver failure independent of the lockfile → `DEPENDENCY_RESOLUTION`.
- **NETWORK_ERROR vs DEPENDENCY_RESOLUTION** — transient (retry would fix) →
  `NETWORK_ERROR`. Permanent (the version/dep genuinely doesn't exist) →
  `DEPENDENCY_RESOLUTION`.
- **REPO_GONE vs NETWORK_ERROR** — clone failed because the repo is gone/renamed
  → `REPO_GONE`. Clone failed because of a transient fetch error →
  `NETWORK_ERROR`.

## Context: the recoverability axis (do not code on this)

For interpretation only — the study groups these categories by whether more
pipeline work could recover the candidate:

- **Corpus property (irreducible):** `REPO_GONE`, `NIGHTLY_REQUIRED`,
  `RUSTC_BITROT`, most `TEST_FAILURE` (author-environment), `DEPENDENCY_RESOLUTION`
  (genuinely-gone deps).
- **Pipeline-fixable:** `OPENSSL_MISMATCH` (era-correct image),
  `NATIVE_DEP_MISSING` (bake the package), `OLD_MESSAGE_FORMAT` (flag),
  `NETWORK_ERROR`/`TIMEOUT` (retry / more time), `LOCK_FILE_STALE` (relock).
- **Pipeline artefact (not a candidate failure):** `NO_LOG`.

Coders ignore this; it is what the validated counts ultimately feed.
