# Recovery experiments — every proposed lever, rebuilt

We took every recovery lever the failure-class analysis proposed
([`failure-class-fixability.md`](failure-class-fixability.md)) and
**actually rebuilt at least one candidate per bucket** rather than
trusting the estimate. 22 candidates across 9 buckets + the earlier
E0308 probe. This is the strongest evidence we have on the
unreproducible cohort: not "we think X is recoverable," but "we forced
the proposed fix and watched what happened."

Run on this arm64 laptop via `durp reproduce --force-fat-image <img>
--skip-preflight --relax-locked` against locally-built images. Cross-arch
caveat applies (crack is amd64), but the failing **error codes matched
crack's amd64 records exactly**, so the arch did not change the verdicts.
Probe images (`nightly-probe`, `nasm-probe`) are throwaway, registered
locally only — not committed to the canonical index.

## Results — the whole matrix

| Bucket | Lever tried | N | Recovered | What actually happened |
| --- | --- | ---: | ---: | --- |
| **E0308** (stdlib-evolution) | prior-milestone 1.56→1.49 | 2 | **2 ✓** | `u32::BITS` (1.53) ambiguity in pinned dep; pre-1.53 milestone compiles |
| **RUNTIME_CRASH nasm** | build-tool-augmented image | 2 | **2 ✓** | `nasm` added → `rav1e-by-gop` assembly compiles |
| TEST_FAILURE | clean retry (network on) | 2 | **1** | `cargo-deny#208` was a transient (now ok); `mnemesis#57` panics on `$USER` (author-env) |
| E0512 (transmute) | prior-milestone 1.56→1.49 | 2 | 0 | still E0512 in `socket2` — the size assertion exists on 1.49 too |
| E0793 (misaligned ref) | prior-milestone 1.56→1.49 | 2 | 0 | still E0793 in `tendril` (also a classifier-vs-rustc-era anomaly, below) |
| E0283 (inference) | prior-milestone →1.39 | 2 | 0 | still E0283 in `sample` — inference ambiguity stable |
| NIGHTLY (rocket/pear) | nightly-channel image | 3 | 0 | **cleared the build.rs abort**, then E0119 in `traitobject` — current nightly is too NEW for 2020 code |
| RUNTIME_CRASH llvm-sys | forward-milestone →1.56 | 2 | 0 | still fails — `llvm-sys 70` needs a system LLVM lib, not a rustc version |
| LOCK_FILE_STALE | `--relax-locked` | 2 | 0 | relock retry failed: regenerated lock pulls deps with MSRV > image |
| git-dep-gone (DEP_RES) | plain retry | 1 | 0 | git ref genuinely gone — corpus property, confirmed |

**Confirmed recoverable: E0308 prior-milestone, nasm build-tool
augmentation, and a slice of transient TEST/DEP failures.** Everything
else in this sample did **not** recover with the proposed lever.

## What each result means for the thesis

### Two confirmed wins

1. **Build-tool augmentation (RUNTIME_CRASH): real and cheap.** Adding
   `nasm`/`meson`/`ninja`/`sass` to the fat image recovered 2/2 rav1e
   candidates outright. This validates the agent's ~+24 estimate as a
   *certain* lever — it's a one-line Dockerfile change. The caveat: it
   only helps the ~24 build-tool-missing subset, NOT the ~69 native-lib
   (ATK/systemd/hidapi) subset, which need libraries that aren't
   generically installable.

2. **E0308 prior-milestone: real, with a precise mechanism.** Confirmed
   earlier (2/2) — a newer stdlib item (`u32::BITS`, 1.53) created an
   ambiguity in a pinned old dep; an earlier milestone lacking that item
   compiles. Mechanistic and predictive.

### The instructive failures (each refines a claim)

3. **The nightly lever half-works — and that's the finding.** Forcing a
   nightly channel **did** clear the Rocket/pear `build.rs` abort (the
   original NIGHTLY_REQUIRED blocker) — but a *2026* nightly then broke
   the 2020 code on `traitobject` (E0119 coherence). So "nightly recovers
   ~77" needs qualifying: it needs an **era-appropriate (2020) nightly**,
   not a current one. Pinning a reproducible 2020 nightly is the harder
   half the estimate glossed over. **The lever is directionally right but
   the cost is higher than estimated**, and a current nightly is *not*
   sufficient.

4. **Prior-milestone retry is narrower than the transitive-signature
   count suggested.** E0512/E0793/E0283 all stayed failing one milestone
   back — only E0308 has a milestone-sensitive mechanism. So the
   "~88 stdlib-evolution recoverable" figure is too generous: **E0308
   (~61) is the confirmed core; E0512/E0793 do not recover at 1.49.**
   (They might at a *much* older milestone, untested.)

5. **`--relax-locked`, llvm forward-retry, git-dep-gone, author-env tests:
   confirmed dead ends.** Each failed for the structural reason the
   analysis predicted — relock hits post-regeneration MSRV walls, llvm-sys
   needs a system library, git refs are deleted, and `$USER`-dependent
   tests can't run in a clean container. These are corpus properties; no
   pipeline lever moves them.

6. **Transients are real and worth a cheap retry.** `cargo-deny#208`
   reproduced `ok` on a clean re-run — its original `not_reproducible`
   was a transient (network/flake), not a real failure. This suggests a
   **plain N-attempt retry** (the deferred Run A) would recover a small
   tail across *all* classes, independent of the targeted levers.

## Revised recoverable estimate (evidence-based)

| Lever | Confirmed on sample | Realistic class-wide yield |
| --- | --- | --- |
| nasm/build-tool augmentation | 2/2 | ~24 (the build-tool subset of RUNTIME_CRASH) |
| E0308 prior-milestone | 2/2 | ~61 (the E0308 transitive cohort) |
| era-appropriate nightly | 0/3 with *current* nightly; lever clears the abort | ≤109 Rocket/pear, but needs a pinned 2020 nightly — unquantified |
| transient N-attempt retry | 1/2 | small tail across all classes |

**Honest headline:** two levers are confirmed (build-tools ~24, E0308
~61 ≈ **+85 certain-mechanism**); the nightly lever is real but costlier
than estimated and unconfirmed pending an era-pinned nightly; everything
else tested is a corpus property. So the practical recoverable headroom
is **~85 confirmed + a conditional Rocket/pear pool**, lifting DS1 from
54.3 % toward **~57–60 %** on confirmed levers alone — and the rest is
genuinely irreducible (deleted refs, missing system libs, author-env
tests, stable coherence bitrot).

## Method note

Every cell above is a real `cargo test` rebuild, logged under
`/tmp/recover/logs/recover-*` (run_ids `recover-B1_e0512` …
`recover-B8`, `recover-B4-nightly3`, `recover-B5-nasm`, `pmretry-*`).
The canonical confirmation — for the entries that *did* recover — should
re-run on amd64 (crack) to produce committable fingerprinted entries,
the same bar OpenSSL (48/64) and native-dep (7) met. This laptop run
establishes the *verdicts*; crack establishes the *artifacts*.
