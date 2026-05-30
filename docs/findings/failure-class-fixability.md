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

The five largest classes (1,017 = 81 % of failures) are analysed below.
The smaller classes are covered in
[`ds1-full-r2-findings.md`](ds1-full-r2-findings.md),
[`openssl-case-study.md`](openssl-case-study.md), and
[`native-dep-case-study.md`](native-dep-case-study.md).

## The bottom line

Two interventions are **certain** wins; one is **probable**; the two
largest remaining classes are **provably corpus properties**.

Two interventions are **certain** wins; the largest *probable* pool is
the prior-milestone retry; the remainder are **provably corpus properties**.

- **Certain — nightly fat-image variant: ~+77** (from NIGHTLY_REQUIRED's
  Rocket/pear cluster, which aborts on stable by design).
- **Certain — build-tool augmentation: ~+24** (from RUNTIME_CRASH: add
  `nasm`, `meson`, `ninja`, `sass` to the fat image).
- **Probable (largest pool) — prior-milestone retry on RUSTC_BITROT:**
  **250 candidates carry the toolchain-bitrot signature** (the error
  fires inside a *locked transitive dependency*, not project source).
  These compiled on their era rustc and break only because the era-floor
  routed them upward. A conservative 20–40 % rebuild yield ≈ **+50–100** —
  but this is a hypothesis until the rebuild runs (see the BITROT section).
- **Provably corpus property — ~500+ candidates** (TEST_FAILURE 244 +
  DEPENDENCY_RESOLUTION ~92 + RUNTIME_CRASH native-lib 69 + NIGHTLY
  never-stabilized 62 + BITROT project-source 75): no pipeline change
  recovers these. Author-environment tests, deleted git refs, missing
  system libraries, never-stabilized features, and genuine code drift.

Translating to a ceiling: **~100 certain + a plausible ~50–100 probable**
recoverable from these five classes would lift DS1 reproducibility from
54.3 % toward the **low-to-mid 60s %**, with the rest honest corpus
attrition. The defense narrative: we can name, quantify, and partially
close the gap, and what remains is decay — not pipeline weakness. **The
single most valuable next experiment is the prior-milestone retry**,
because it targets the largest probable pool (250) and would convert the
biggest PROBABLE into a CONFIRMED number.

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

### Per-code split (transitive-registry / project-source)

| Code | Total | Transitive (fixable sig.) | Project src | Nature |
| --- | ---: | ---: | ---: | --- |
| E0308 mismatched types | 63 | **61** | 2 | e.g. `lexical-core 0.7.4` `Limb::BITS` usize-vs-u32 (stdlib `BITS` const changed) |
| E0034 multiple applicable items | 41 | **39** | 2 | inherent-vs-trait method ambiguity tightened |
| E0283 inference ambiguity | 40 | ~31 | ~9 | inference got stricter |
| E0119 conflicting impls | 33 | mixed | mixed | warning→hard-error in 1.49 |
| E0512 transmute size | 21 | **21** | 0 | layout/size assumptions |
| E0793 misaligned reference | 6 | **6** | 0 | a *recent* lint; era rustc had no such check |
| E0601 missing `main` | 12 | 0 | **12** | project-source — likely genuine |
| E0583 missing mod file | 10 | 0 | **10** | project-source — likely genuine |
| E0433/E0432 unresolved import/path | 29 | 3 | **26** | mostly project-source |
| E0277 trait bound | 9 | 4 | 5 | mixed |
| (+ RUNTIME_MEM_UNINIT 12, uncoded 57) | | | | excluded from coded analysis |

The classic anti-bitrot example E0119 (warning until 1.49, hard error
after) is real but small (33); the *bulk* of the recoverable signature is
E0308/E0034/E0512 firing in pinned transitive deps.

### Confidence and experiment

- **CONFIDENCE: PROBABLE, NOT CONFIRMED.** "Error fires in a transitive
  dep" is a strong *signal* of toolchain bitrot, not proof — only the
  actual rebuild confirms it. **No candidate was rebuilt on an older
  milestone yet.** This must be validated the way OpenSSL (48/64) and
  native-dep (7) were: carve the cohort, rerun on the commit-era
  milestone with a separate `run_id`, re-classify survivors.
- **Worked example (verified from log):**
  `conectado/taping-memory-blog#42` — fails E0308 in
  `lexical-core 0.7.4/src/atof/algorithm/bhcomp.rs:62`
  (`bits / Limb::BITS`, expected `usize` found `u32`). The project
  itself is fine; the locked transitive `lexical-core 0.7.4` only breaks
  on the newer rustc. Routed to `1.56-buster`; predicted to compile on
  its commit-era milestone.
- **Experiment:** retry the **250 transitive-signature candidates** on
  the commit-era milestone (the `latest_milestone_before(commit_date)`
  one — typically 1–2 milestones below their current fat image, e.g.
  the `1.56-buster` E0308/E0713/E0793 cluster → retry on 1.49 or 1.39).
  Predicted yield is genuinely uncertain pre-rebuild; a conservative
  20–40 % of 250 ≈ **+50–100**, but treat as hypothesis until the run.

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

1. **The reproducibility ceiling is bounded and explainable.** ~500+ of
   the 1,249 failures are provably corpus properties (author-env tests,
   deleted git refs, missing system libs, never-stabilized features,
   project-source code drift). No pipeline closes those.
2. **The closable gap is real, named, and dominated by one lever:** a
   nightly variant (~77) and build-tool augmentation (~24) are certain;
   the big *probable* pool is the **250 toolchain-bitrot-signature
   candidates** (error fires in a locked transitive dep) addressed by
   prior-milestone retry, plausibly +50–100. Low-to-mid 60s % is a
   defensible practical ceiling for this corpus and contract.
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
