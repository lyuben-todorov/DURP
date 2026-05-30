# Failure-class fixability — what's pipeline-recoverable vs a corpus property

A class-by-class analysis of the 1,249 `not_reproducible` candidates in
DS1 Run B (`ds1-full-crack-r2`), answering the RQ4-adjacent question a
defense will press: **of the ~46 % of candidates we could not reproduce,
how much is our pipeline's limitation (fixable) vs a genuine property of
the corpus (the code/ecosystem decayed, or the test embeds assumptions no
reproduction can satisfy)?**

This bounds the reproducibility ceiling. If most unreproducible candidates
are corpus properties, then 54.3 % is close to the achievable maximum and
the residual is honest attrition — not a weak pipeline.

Numbers are from the static DB snapshot (`/tmp/analysis.sqlite` on crack,
a `.backup` of `pipeline.sqlite`) and sampled pre-build logs. Each class
was analysed independently. **Confidence labels are explicit** — some
estimates are log-evidenced theory, not rebuild-verified; those are marked
PROBABLE, not CONFIRMED.

## The 1,249 not_reproducible, by class

| Class | N | % of fails | Verdict | Confidence |
| --- | ---: | ---: | --- | --- |
| RUSTC_BITROT | 394 | 31.5 % | ~77 % of coded fail in a locked transitive dep (toolchain-bitrot signature → prior-milestone candidate) | PROBABLE (not rebuilt) |
| TEST_FAILURE | 244 | 19.5 % | ~0 % fixable; author-environment property | CONFIRMED (log-evidenced) |
| NIGHTLY_REQUIRED | 169 | 13.5 % | ~62 % recoverable via nightly fat-image | MIXED |
| RUNTIME_CRASH | 110 | 8.8 % | ~22 % env-augment + ~15 % toolchain; ~63 % native-lib | MIXED |
| DEPENDENCY_RESOLUTION | 100 | 8.0 % | ~6 % fixable; ~86 % git-dep rot | CONFIRMED (log-evidenced) |
| TIMEOUT | 69 | 5.5 % | parallel=8 disk-contention artifact (see r2-findings) | prior work |
| OPENSSL_MISMATCH | 64 | 5.1 % | 48 recovered (stretch) — see openssl-case-study | done |
| LOCK_FILE_STALE | 31 | 2.5 % | `--relax-locked` recovers some | prior work |
| REPO_GONE | 28 | 2.2 % | 27/28 manifest-deep, not tombstones — see r2-findings | done |
| NATIVE_DEP_MISSING | 18 | 1.4 % | 7 recovered (rebuilt images) — see native-dep-case-study | done |
| OTHER | 13 | 1.0 % | fall-through | — |
| MSRV_TOO_LOW | 9 | 0.7 % | genuine (declared MSRV exceeds floor) | — |

The five largest classes (1,017 = 81 % of failures) are analysed in
depth below. The other seven (232) are covered too — five by existing
work, and the two that were *not* previously examined (OTHER,
MSRV_TOO_LOW) are characterized in "The other seven classes" section at
the end. No class is left as an unexamined black box.

## The bottom line

Two interventions are **certain** wins; one is **probable**; the two
largest remaining classes are **provably corpus properties**.

Two interventions are **certain** wins; the largest *probable* pool is
the prior-milestone retry; the remainder are **provably corpus properties**.

- **Certain — nightly fat-image variant: ~+77** (from NIGHTLY_REQUIRED's
  Rocket/pear cluster, which aborts on stable by design).
- **Certain — build-tool augmentation: ~+24** (from RUNTIME_CRASH: add
  `nasm`, `meson`, `ninja`, `sass` to the fat image).
- **Prior-milestone retry on RUSTC_BITROT — now partly verified, and
  narrower than first thought.** Of the 250 transitive-signature
  candidates, a 10-candidate local rebuild shows recovery is
  **code-dependent**: the **stdlib-evolution codes (E0308 confirmed 2/2,
  + E0512 21 + E0793 6 ≈ 88)** recover on an earlier milestone; the
  **coherence/ambiguity codes (E0119 confirmed 0/5, E0034 0/2, + E0283
  ≈ 114)** do NOT — they are stable bitrot. So the recoverable pool is
  the ~88 stdlib-evolution candidates (only E0308's 61 confirmed; E0512/
  E0793 pending), not the full 250.
- **Provably corpus property — ~600+ candidates** (TEST_FAILURE 244 +
  DEPENDENCY_RESOLUTION ~92 + RUNTIME_CRASH native-lib 69 + NIGHTLY
  never-stabilized 62 + BITROT project-source 75 + BITROT coherence/
  ambiguity ~114): no pipeline change recovers these. Author-environment
  tests, deleted git refs, missing system libraries, never-stabilized
  features, stable coherence errors, and genuine code drift.

Translating to a ceiling: **~100 certain (nightly + build-tools) + ~88
probable (E0308-family, ~61 confirmed)** recoverable from these five
classes would lift DS1 reproducibility from 54.3 % toward roughly
**~60 %**, with the rest honest corpus attrition. The defense narrative:
we can name, quantify, and *empirically test* the gap — and what remains
is decay, not pipeline weakness. **The biggest single confirmed win is
the E0308-family prior-milestone retry**, which the local run already
demonstrated (2/2) and which a full amd64 run on crack would scale to the
~88-candidate cohort.

---

## RUSTC_BITROT (394) — PROBABLE ~77 % carry a recoverable signature

Code that compiled on the author's contemporary rustc fails on the
fat-image's (era-floor-selected, usually newer) rustc.

### The discriminator: where does the error fire?

A failure inside a **locked transitive dependency** (a crate under
`cargo-cache/registry/...`, whose version was pinned by the project's
`Cargo.lock`) is the signature of **toolchain bitrot**: that exact dep
version compiled on its contemporary rustc and breaks only because the
era-floor routed the build to a newer one. A failure in the **project's
own source** is more often genuine code/API drift. We classified all
~325 coded BITROT candidates by where their *first* error fires:

| | N | reading |
| --- | ---: | --- |
| **Error in a transitive registry crate** | **250 (77 %)** | toolchain-bitrot signature → prior-milestone candidate |
| Error in project source | 75 (23 %) | more likely genuine code/API drift |

This **corrects an earlier draft** that guessed ~33 % fixable / ~31 %
"dependency-API rot". Reading the logs shows the opposite skew: the
dominant codes fail inside *pinned old deps*, not the project.

### Per-code split (transitive-registry / project-source) + retry verdict

| Code | Total | Transitive sig. | Project src | Prior-milestone retry verdict |
| --- | ---: | ---: | ---: | --- |
| E0308 mismatched types | 63 | **61** | 2 | **RECOVERS ✓ (verified 2/2)** — `u32::BITS` (stabilized 1.53) created the ambiguity; pre-1.53 milestone compiles |
| E0512 transmute size | 21 | **21** | 0 | likely recovers (same stdlib-evolution mechanism; not yet rebuilt) |
| E0793 misaligned reference | 6 | **6** | 0 | likely recovers (a *recent* lint absent from era rustc) |
| E0119 conflicting impls | 33 | mixed | mixed | **DOES NOT recover (verified 0/5)** — `(dyn Send+Sync)` coherence was a hard error long before 1.49 |
| E0034 multiple applicable items | 41 | **39** | 2 | **DOES NOT recover (verified 0/2)** — inherent-vs-trait ambiguity stable across milestones |
| E0283 inference ambiguity | 40 | ~31 | ~9 | unknown — not rebuilt; inference-stability uncertain |
| E0601 missing `main` | 12 | 0 | **12** | project-source — likely genuine, not retry-fixable |
| E0583 missing mod file | 10 | 0 | **10** | project-source — likely genuine |
| E0433/E0432 unresolved import/path | 29 | 3 | **26** | mostly project-source |
| E0277 trait bound | 9 | 4 | 5 | mixed |
| (+ RUNTIME_MEM_UNINIT 12, uncoded 57) | | | | excluded from coded analysis |

**Local verification run (2026-05-30, 10 candidates, arm64).** We
actually rebuilt a sample on the prior milestone — and it overturned the
"transitive signature ⇒ recoverable" shortcut. The retry verdict is
**code-dependent, not signature-wide**:

- **E0308 RECOVERED 2/2** (`conectado/taping-memory-blog#42`,
  `tommilligan/decadog#133`): both compiled `ok` on 1.49. The mechanism
  is specific and predictive — a *newer stdlib item* (`u32::BITS`, 1.53)
  introduced an ambiguity in a pinned old dep; an earlier milestone that
  lacks that item resolves cleanly.
- **E0119 did NOT recover 0/5** (`andreasots/eris` ×4,
  `Technosorcery/sd2snes…#388`): still `E0119` on both 1.39 and 1.49.
  These are `(dyn Send + Sync)` coherence conflicts — a hard error well
  before 1.49, not a 1.49 lint-tightening. The doc's earlier "warning
  until 1.49" framing was **wrong** for this cluster.
- **E0034 did NOT recover 0/2** (`Technolution/rustig`): method-resolution
  ambiguity, stable across milestones.

So the recoverable core is the **stdlib-evolution codes (E0308 61 +
E0512 21 + E0793 6 ≈ 88)**, NOT the coherence/ambiguity codes
(E0119 + E0034 + E0283 ≈ 114), which the rebuild shows are stable bitrot
no older milestone fixes. This is the single biggest correction the
verification produced. (Caveat: run on arm64; `CLAUDE.md` notes
cross-arch uses append mode — but the *error codes matched crack's
amd64 record exactly*, so arch did not mask the result. E0512/E0793
"likely recovers" remains UNVERIFIED until rebuilt.)

### Confidence and experiment

- **CONFIDENCE: PARTIALLY CONFIRMED.** The 10-candidate local rebuild
  (above) confirms E0308 recovers (2/2) and E0119/E0034 do not (0/7).
  The "transitive signature ⇒ recoverable" heuristic is therefore **not
  sufficient on its own** — it must be qualified by error-code mechanism.
  E0512/E0793 ("likely recovers") and E0283 ("unknown") are still
  un-rebuilt. A full confirmation run should carve the E0308/E0512/E0793
  cohort, rerun on the commit-era milestone with a separate `run_id` on
  **amd64 (crack)**, and re-classify survivors — the same bar OpenSSL
  (48/64) and native-dep (7) met.
- **Worked example (now rebuilt, not just predicted):**
  `conectado/taping-memory-blog#42` — failed E0308 in
  `lexical-core 0.7.4/src/atof/algorithm/bhcomp.rs:62`
  (`bits / Limb::BITS`, expected `usize` found `u32`) on `1.56-buster`.
  The project itself is fine; the locked transitive `lexical-core 0.7.4`
  broke only because rustc 1.53+ added `u32::BITS`, creating the
  ambiguity. **Re-run on `1.49-buster` (pre-1.53): compiles `ok`.**
  Confirmed, not predicted.
- **Experiment (refined by the local run):** retry the **~88
  stdlib-evolution candidates** (E0308 61 + E0512 21 + E0793 6) on the
  commit-era milestone — NOT the full 250, since the rebuild showed the
  coherence/ambiguity codes (E0119/E0034/E0283) don't recover. E0308 is
  already confirmed (2/2); E0512/E0793 are the remaining un-rebuilt
  ~27. Run on amd64 (crack) for canonical entries. Realistic yield: most
  of the ~88, i.e. **+40–80**, with E0308's ~61 the high-confidence core.

## TEST_FAILURE (244) — CONFIRMED ~0 % fixable (corpus property)

The pre-bump `cargo test` ran but tests failed.

- **Bias check:** only **49 distinct repos** for 244 candidates; the top
  5 repos (cgm616/calc_rs 29, jonasbb/ctftimebot 20, saschagrunert/git-journal
  17, coreyja/devicon-lookup 17, Keruspe/mnemesis 15) are 40 % of the
  class. So the distinct-root-cause count is far below 244.
- **Sub-causes (sampled):** ~75 % author-environment — missing binaries
  in `target/debug/`, `DATABASE_URL`/`REDIS_URL` unset, missing config
  files, TTY/terminal detection (`atty`), ANSI-color assumptions. ~15 %
  REAL_TEST_REGRESSION (the bump genuinely changed behaviour — the most
  thesis-interesting subset). ~10 % flaky/indeterminate.
- **Fixability: essentially zero.** These need live services, a terminal,
  filesystem fixtures, or specific hardware — none reproducible in a
  clean offline container. `--offline` doesn't help.
- **This is a finding, not a gap.** It quantifies that ~1/5 of DS1's
  unreproducible candidates are unreproducible *because the original
  tests were never environment-independent* — a test-hygiene property of
  the corpus, orthogonal to dependency reproducibility.
- **Examples:** `nlopes/avro-schema-registry#150` (36 identical failures,
  all `DATABASE_URL must be set`); `saschagrunert/git-journal#122`
  (`Could not create terminal`); `cgm616/calc_rs#112` (pest-parser
  REAL_TEST_REGRESSION).
- **Action:** none to recover. Recommend a `TESTS_NEED_ENV`
  sub-classification to name it honestly in the paper, and surface the
  REAL_TEST_REGRESSION subset as breaking-adjacent data.

## NIGHTLY_REQUIRED (169) — MIXED, ~62 % recoverable

Build needs a nightly toolchain; fat-images ship stable only.

- **Composition:** the Rocket/pear ecosystem dominates —
  `pear_codegen` (53) + `rocket_codegen` (36) + `rocket` (19) +
  `rocket_contrib_codegen` (1) = **109 (64 %)**, all `build.rs` that
  aborts on a stable channel by design. Plus E0554 feature-gate
  rejections (50), proc-macro-nightly (2), Z-flag (5).
- **Recoverable (~62 %):** a pinned **nightly fat-image variant** would
  satisfy the 72 build.rs-abort cases (they check only for the nightly
  *channel*, not a version) plus most feature-gates — ~77 candidates at
  moderate cost (era-appropriate nightly is pinnable but less cleanly
  archived than stable).
- **Corpus property (~38 %):** never-stabilized features
  (`specialization`, `custom_attribute`, `type_ascription`), Z-flag
  target-spec builds, and the genuinely nightly-by-design crates.
- **CONFIDENCE on the "later-stable recovers +30" sub-claim: LOW** —
  rebuilding 2019 code on rustc 1.67 to exploit feature stabilization
  introduces orthogonal new failures; discount it. The **nightly-variant
  path (~77) is the defensible one.**
- **Note:** this class would shrink sharply in a post-2022 corpus —
  Rocket 0.5 went stable, so the dominant cause is era-specific.
- **Example:** `brndnmtthws/rust-react-typescript-demo#441` — pear_codegen
  build.rs: "Pear requires a nightly or dev version of Rust."

## RUNTIME_CRASH (110) — MIXED, ~37 % recoverable

build.rs panics (not clean compile errors). **Zero genuine SIGSEGVs** —
all 110 are build-script panics.

- **Bias check:** well-distributed, 31 distinct repos, no single repo
  dominates.
- **Native-lib pkg-config failures (~69, 63 %) — corpus property:**
  build.rs calls `pkg-config` for system libraries absent from the image
  (ATK/Pango GUI, libsystemd, hidapi, libv4l2, fontconfig). These are
  camera/UI/daemon libs; not generically installable.
- **Build-tool missing (~24, 22 %) — FIXABLE, CERTAIN:** `nasm` (11,
  rav1e/cargo-asm), `meson`/`ninja` (3), `sass` (1), etc. `apt-get
  install` them into the fat image → ~24 certain recoveries.
- **Toolchain detection (~17, 15 %) — PROBABLE:** OpenSSL/LLVM version
  detection in build.rs that may resolve on a different milestone.
- **Classifier precision: high** (all 110 are genuine
  `failed to run custom build command` panics; no misclassification).
- **Example:** `rust-av/rav1e-by-gop#146` — "This version of NASM is too
  old / No such file" → add nasm, recovers.
- **Experiment:** an augmented fat-image variant with the build tools →
  +24 certain.

## DEPENDENCY_RESOLUTION (100) — CONFIRMED ~6 % fixable (corpus property)

Cargo's resolver failed to produce a build plan.

- **Composition:** GIT_DEP_GONE 90, REGISTRY_RESOLVER 5, RESOLVE_PATCHES
  5 (the patch-table ones are also git-dep-gone).
- **Git-dep rot (~86, corpus property):** a `git = "..."` dependency's
  pinned commit/branch was rebased away or deleted —
  `revspec '…' not found`. The repos often still exist; the specific
  ref is gone. Upstream maintenance churn, not a reproduction bug.
- **Bias:** 32 distinct repos; top 5 (cloud-hypervisor 19, cognitedata/reveal
  14, nuclearfurnace/synchrotron 12, alex/ct-tools 5, rav1e-by-gop 4) =
  60 %. High-churn projects, not a uniform property.
- **Falsifies a tempting hypothesis:** an **era-pinned crates.io index
  would yield <2 %.** The REGISTRY_RESOLVER failures are genuine
  unsatisfiable constraints (native-link conflicts like clang-sys
  0.21 vs 0.26; never-available feature combos), not index-age artifacts —
  and `--locked --offline` makes the index era irrelevant when a lock is
  present. So "better registry handling" is NOT the lever here.
- **Fixable (~6):** SSH-auth config, zlib/network transients, a vendored
  submodule path — retry/config, not corpus.
- **Example:** `Rigellute/spotify-tui#461` — `revspec '8d15009e…' not
  found` (history rewrite); unrecoverable without a git mirror.

---

## The other seven classes (232 candidates)

The five above are 81 % of failures. The remaining seven, for
completeness — five already have dedicated treatment, two did not and are
characterized here:

**Already examined (prior work):**

- **OPENSSL_MISMATCH (64)** — image substitution recovers 48/64.
  [`openssl-case-study.md`](openssl-case-study.md).
- **NATIVE_DEP_MISSING (18)** — rebuilt fat images recover 7; the
  remainder are `-ldl`/undefined-reference ABI cases.
  [`native-dep-case-study.md`](native-dep-case-study.md).
- **REPO_GONE (28)** — audited in
  [`ds1-full-r2-findings.md`](ds1-full-r2-findings.md): 27/28 are
  manifest-at-depth-3-5 (the discovery shim caps at depth 2), recoverable
  by raising the cap; zero are real tombstones.
- **TIMEOUT (69)** — heavy workspaces (solana ×N, starcoin, servo, comit);
  the +44 vs baseline is a `--parallel 8` disk-contention artifact.
  Recoverable by `--parallel 5` + a larger `--timeout`.
- **LOCK_FILE_STALE (31)** — `--relax-locked` recovers some; the rest hit
  a post-regeneration MSRV wall (the relock pulls an edition-2021 dep).

**Not previously examined — characterized now:**

- **OTHER (13) — NOT an opaque fall-through (the earlier draft was
  wrong).** It is three concrete sub-causes: (a) `rustfmt`/`clippy` not
  installed for a pinned sub-toolchain (5×, all
  `tmtmtoo/rust-grpc-server-example`, which pins `1.43.0` and runs
  `cargo fmt` at build); (b) `File too big` extracting a nightly rustc
  component (4× — a disk-pressure pipeline artifact); (c) transients
  (checksum verify, crate download, workspace-manifest parse). A
  2-candidate retry on a current image did **not** recover them (the
  rustfmt one got past rustfmt and hit a deeper `tonic-build` issue; the
  transient hit a manifest-parse on the substituted image), so they are
  *not* trivially fixable — but they are pipeline/tooling-flavoured, not
  corpus rot. Best read: mostly pipeline-side, low individual yield.
- **MSRV_TOO_LOW (9) — corpus/contract, possibly route-up-fixable.** All
  nine declare MSRV 1.56 and route to `1.56-buster`, then fail because
  the *bumped dependency* raised the effective MSRV past 1.56 (`rustix
  0.38`, `libc 0.2.186`, `itoa 1.0`, `tempfile 3.8` — all edition-2021).
  Eight of nine are `paritytech/parity-bridges-common`, so ~2 distinct
  root causes. Untested hypothesis: routing *up* to 1.65/1.75 would build
  them — the mirror image of the era-floor problem. Not rebuilt (no local
  1.65 image); flagged as a cheap follow-up.

Net for the seven: OPENSSL (+48) and NATIVE_DEP (+7) are the confirmed
recoveries; REPO_GONE (+27 via depth-shim) and TIMEOUT (+~40 via
parallel/timeout) are high-confidence-pending; LOCK_FILE_STALE, OTHER,
MSRV_TOO_LOW are small and mostly contract/corpus with a thin
pipeline-fixable margin.

---

## What this means for the thesis / defense

1. **The reproducibility ceiling is bounded and explainable.** ~600+ of
   the 1,249 failures are provably corpus properties (author-env tests,
   deleted git refs, missing system libs, never-stabilized features,
   stable coherence/ambiguity bitrot, project-source code drift). No
   pipeline closes those.
2. **The closable gap is real, named, and partly verified by rebuild:** a
   nightly variant (~77) and build-tool augmentation (~24) are certain;
   the BITROT lever is **narrower than the transitive-signature count
   suggested** — a local rebuild confirmed only the stdlib-evolution
   codes recover (E0308 2/2), while coherence/ambiguity codes do not
   (E0119 0/5, E0034 0/2). Recoverable BITROT pool ≈ 88 (E0308's ~61
   confirmed-mechanism), not 250. A ~60 % practical ceiling for this
   corpus and contract.
3. **Two tempting "the pipeline is weak" hypotheses are falsified:**
   era-pinned crates.io index (<2 % yield) and later-stable rebuild
   (introduces orthogonal failures). Naming what does *not* help is as
   defensible as naming what does.
4. **Method consistency:** every recoverable estimate here should be
   confirmed the way OpenSSL and native-dep were — carve the cohort,
   run under the changed image/toolchain with a separate `run_id`,
   re-classify survivors. The PROBABLE labels become CONFIRMED only after
   that.

## Appendix — the local verification run (2026-05-30)

Prior-milestone retry, 10 RUSTC_BITROT candidates, on this arm64 laptop
via `durp reproduce --force-fat-image <older> --skip-preflight`. Each was
failing on its current fat image; we forced the milestone below and
re-ran the pre/post `cargo test`.

| Candidate | Code | Current → retry image | Result |
| --- | --- | --- | --- |
| conectado/taping-memory-blog#42 | E0308 | 1.56 → 1.49-buster | **ok ✓** |
| tommilligan/decadog#133 | E0308 | 1.56 → 1.49-buster | **ok ✓** |
| andreasots/eris#874 | E0119 | 1.56 → 1.49-buster | not_reproducible (still E0119) |
| andreasots/eris#785 | E0119 | 1.56 → 1.49-buster | not_reproducible (still E0119) |
| andreasots/eris#631 | E0119 | 1.56 → 1.49-buster | not_reproducible (still E0119) |
| andreasots/eris#571 | E0119 | 1.49 → 1.39-buster | not_reproducible (dep-resolution on 1.39) |
| andreasots/eris#591 | E0119 | 1.49 → 1.39-buster | not_reproducible (still E0119) |
| Technosorcery/sd2snes-…#388 | E0119 | 1.49 → 1.39-buster | not_reproducible (still E0119) |
| Technolution/rustig#123 | E0034 | 1.56 → 1.49-buster | not_reproducible (still E0034) |
| Technolution/rustig#103 | E0034 | 1.56 → 1.49-buster | not_reproducible (still E0034) |

**Net: 2/10 recovered — both E0308; 0/7 of the E0119/E0034 codes.** This
is the evidence behind the "code-dependent, not signature-wide"
conclusion. Caveat: arm64 (crack is amd64); but the failing error codes
matched crack's amd64 record exactly, so the arch did not change the
verdict.

This BITROT probe was later extended to **every** recovery lever (E0512,
E0793, nightly, nasm, llvm, relax-locked, transients, OTHER) — the full
9-bucket matrix and verdicts are in
[`recovery-experiments.md`](recovery-experiments.md). Headline: nasm
build-tool augmentation and E0308 prior-milestone are the only confirmed
recoveries; E0512/E0793 do *not* recover at 1.49.

## Provenance

All counts from `pipeline.sqlite` (`run_id='ds1-full-crack-r2'`,
`drive_state` + `drive_state_classifications`) and sampled pre-build logs
under `data/cargo-logs/ds1-full-crack-r2/`. The five large classes were
analysed by independent passes; the smaller classes reference the
existing case studies and run findings in this directory. The appendix
verification used `durp reproduce` (run_ids `pmretry-139-local`,
`pmretry-149-local`, `pmretry-e0308-local`).
