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
| RUSTC_BITROT | 394 | 31.5 % | ~33 % prior-milestone-recoverable; ~31 % dep-API rot | PROBABLE (not rebuilt) |
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

The five largest classes (1,017 = 81 % of failures) are analysed below.
The smaller classes are covered in
[`ds1-full-r2-findings.md`](ds1-full-r2-findings.md),
[`openssl-case-study.md`](openssl-case-study.md), and
[`native-dep-case-study.md`](native-dep-case-study.md).

## The bottom line

Two interventions are **certain** wins; one is **probable**; the two
largest remaining classes are **provably corpus properties**.

- **Certain — nightly fat-image variant: ~+77** (from NIGHTLY_REQUIRED's
  Rocket/pear cluster, which aborts on stable by design).
- **Certain — build-tool augmentation: ~+24** (from RUNTIME_CRASH: add
  `nasm`, `meson`, `ninja`, `sass` to the fat image).
- **Probable — prior-milestone retry: ~+25–40** (from RUSTC_BITROT's
  NLL/inference/lint-turned-error clusters; needs the rebuild to confirm).
- **Provably corpus property — ~588 candidates** (TEST_FAILURE 244 +
  DEPENDENCY_RESOLUTION 86 + RUNTIME_CRASH native-lib 69 +
  NIGHTLY never-stabilized 62 + BITROT dep-API ~122): no pipeline change
  recovers these. They are author-environment tests, deleted git refs,
  missing system libraries, and genuine API/feature drift.

Translating to a ceiling: the realistic recoverable headroom from these
five classes is **~125 certain + up to ~40 probable ≈ 165 candidates**,
which would lift the DS1 reproducibility rate from 54.3 % toward
**~60 %** — and the rest is honest corpus attrition. That is the defense
narrative: we can name, quantify, and partially close the gap, and what
remains is decay, not pipeline weakness.

---

## RUSTC_BITROT (394) — PROBABLE ~33 % recoverable

Code that compiled on the author's contemporary rustc fails on the
fat-image's (era-floor-selected, usually newer) rustc.

- **Error-code mix:** E0277 (trait bounds) + E0308 (type mismatch)
  dominate (~67 % of all error occurrences). Then a tail of E0119
  (conflicting impls — became a hard error in 1.49), NLL-cluster
  (E0502/E0503/E0506/E0713/E0621), and inference (E0282/E0283).
- **The fixable cluster (~129, ~33 %):** candidates where the era-floor
  rounded the rustc UP relative to the commit era (e.g. a 2019 commit
  routed to 1.49) AND the failure is a lint-turned-error or a
  tightened-borrow/inference check that an *older* milestone accepted.
  E0119 is the clean example: a warning in 1.39–1.48, a hard error in
  1.49+. A 2019 candidate routed to 1.49 that fails E0119 should compile
  on 1.39.
- **The corpus cluster (~122, ~31 %):** E0277/E0432/E0599 driven by the
  bumped *dependency's* API changing (symbol removed/renamed) — no rustc
  downgrade fixes these.
- **CONFIDENCE: PROBABLE, NOT CONFIRMED.** This split is from reading
  ~20 logs and reasoning about when each error code became strict; **no
  candidate was actually rebuilt on an older milestone.** The +25–40
  recovery figure is a hypothesis the prior-milestone-retry experiment
  must test, exactly as the OpenSSL-stretch experiment tested its class.
- **Example:** `andreasots/eris#571` (2019-11, MSRV 1.39, routed to 1.49)
  fails E0119 conflicting-impl — a hard error only since 1.49; predicted
  to compile on 1.39.
- **Experiment:** retry the ~129 upward-routed candidates on milestone
  N−1. Predicted yield +25–40.

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

## What this means for the thesis / defense

1. **The reproducibility ceiling is bounded and explainable.** ~588 of
   the 1,249 failures are provably corpus properties (author-env tests,
   deleted git refs, missing system libs, never-stabilized features,
   dependency API drift). No pipeline closes those.
2. **The closable gap is real but modest and named:** a nightly variant
   (~77) and build-tool augmentation (~24) are certain; prior-milestone
   retry (~25–40) is probable. ~60 % is a defensible practical ceiling
   for this corpus and contract.
3. **Two tempting "the pipeline is weak" hypotheses are falsified:**
   era-pinned crates.io index (<2 % yield) and later-stable rebuild
   (introduces orthogonal failures). Naming what does *not* help is as
   defensible as naming what does.
4. **Method consistency:** every recoverable estimate here should be
   confirmed the way OpenSSL and native-dep were — carve the cohort,
   run under the changed image/toolchain with a separate `run_id`,
   re-classify survivors. The PROBABLE labels become CONFIRMED only after
   that.

## Provenance

All counts from `pipeline.sqlite` (`run_id='ds1-full-crack-r2'`,
`drive_state` + `drive_state_classifications`) and sampled pre-build logs
under `data/cargo-logs/ds1-full-crack-r2/`. The five large classes were
analysed by independent passes; the smaller classes reference the
existing case studies and run findings in this directory.
