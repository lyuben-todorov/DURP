# Failure-taxonomy literature scan (modern, 2020–2026)

Positions DURP's two failure taxonomies against current work, and records
which categories have a literature precedent (adopt/align) versus which are a
genuine gap (position as novel). Every source below was **verified from the
primary PDF** (held in the thesis working notes, `rp2026/docs/related-work/pdfs/`,
outside this repo) — citation metadata, category
names, corpus sizes, and Cohen's κ values were read from the paper, not from a
secondary summary. Items that could not be primary-verified are explicitly
flagged.

DURP's two schemes, for reference:
- **Scheme 1** — breaking-update failures (pre-bump builds, post-bump fails):
  BUMP-style top level (`COMPILATION_FAILURE / TEST_FAILURE /
  DEPENDENCY_RESOLUTION_FAILURE / ENVIRONMENT_FAILURE / OTHER`) + rustc
  E-code subcategories.
- **Scheme 2** — *reproduction* failures (pre-bump baseline won't rebuild in a
  pinned environment): 15 categories organized by *corpus-property
  (irreducible) vs pipeline-fixable*.

## Direct answer

**No modern taxonomy supersedes DURP's anchors; the recent work complements
them, and DURP's reproduction-failure taxonomy (Scheme 2) is a genuine,
under-studied contribution.**

- **Scheme 1** should keep BUMP (Reyes et al. 2024) as its top-level anchor for
  cross-ecosystem comparability. Cite **Zheng et al. 2025** as the modern,
  κ-validated general CI-failure taxonomy, and **Breaking-Good (Reyes et al.
  2024)** for the transitive-dependency sub-category precedent.
- **Scheme 2** has exactly one close precedent — **Fu et al. 2026**
  (historical embedded-CI reconstruction failures, 5 coarse categories) — which
  DURP extends to a 15-category, Rust-specific scheme. The reproducible-builds
  literature is *orthogonal* (bit-for-bit identity, not historical
  build-success), confirming the gap.
- DURP's organizing **axis** (corpus-property vs pipeline-fixable) has **no
  direct precedent** found; only a loose analogy (reproducible-builds
  "fixability" hierarchies). Claim it as novel.

---

## Axis 1 — dependency-update / breaking-change taxonomies

### BUMP — Reyes, Gamage, Skoglund, Baudry, Monperrus (SANER 2024)
arXiv:2401.09906; DOI 10.1109/SANER60148.2024.00024. 571 reproducible breaking
dependency updates, 153 Java/Maven projects. Of the 571, **243 are compilation
failures** (≈43%), the rest test / enforcer / dependency-lock /
dependency-resolution. Manual log analysis. **No Cohen's κ reported.**
→ *DURP's Scheme-1 anchor; unchanged.* Verified.

### Breaking-Good — Reyes, Baudry, Monperrus (SCAM 2024)
arXiv:2407.03880v2; DOI 10.1109/scam63643.2024.00014. An explanation tool
evaluated **on BUMP data** (no new corpus). Sub-taxonomy of the 243 BUMP
compilation failures into four: **Werror failure, Java version incompatibility,
Direct compilation failure, Indirect compilation failure**; 38 of the 243 are
*indirect* (root cause in a **transitive** dependency). Derivation =
log-pattern + dependency-tree diffing; validation = developer user study.
**No Cohen's κ.**
→ *Adopt "indirect compilation failure" as a sub-category precedent under
DURP's `COMPILATION_FAILURE`* — DURP currently has no transitive-root-cause
sub-label. Verified.

### Kong, Liu, Bao, Lo — "Towards Better Comprehension of Breaking Changes in
the NPM Ecosystem" (arXiv:2408.14431v2, Oct 2024)
381 popular npm projects; a dataset of explicitly-documented breaking changes.
Taxonomy of **JS/TS syntactic** BCs + **behavioral** BC types; also a
*reasons-for-BC* taxonomy. Cohen's κ = **0.80** (reason-related info), **0.77**
(commit-type), **0.94** (assigning reason). Key finding: 19% of BCs undetectable
by regression testing.
→ *Classifies the cause/nature of upstream changes, not build-failure symptoms
— complements, doesn't compete with Scheme 1. Cite as a modern κ benchmark
(0.77–0.94).* ⚠ **Venue unconfirmed**: the PDF is a preprint with a placeholder
DOI; a TOSEM 2025 publication was claimed by a secondary source but **not**
verified — cite as arXiv 2024 unless the journal version is confirmed.

> **Dropped:** "Jayasuriya et al., *An extended study of syntactic breaking
> changes in the wild*, EMSE 2024/2025, DOI 10.1007/s10664-024-10563-4" was
> surfaced by the automated scan but the DOI does not resolve and the paper
> could not be located. **Treat as a likely fabrication; do not cite.**

---

## Axis 2 — general build / CI failure taxonomies (post-Rausch/Vassallo)

### Zheng, Li, Huang, Huang, Lin, Chen, Xuan — "Why Do GitHub Actions Workflows
Fail? An Empirical Study" (ACM, DOI 10.1145/3749371, 2025)
First author **Lianyu Zheng** (Wuhan University). Manually analyzed **375 failed
workflow executions across 260 open-source Java projects**; **card-sorting** →
a taxonomy of **16 failure types**; validated by a **151-developer survey**.
Inter-rater agreement **Cohen's κ = 0.708** ("substantial agreement", citing
McHugh 2012).
→ *The modern successor to Rausch (2017) / Vassallo (2017): a 2020s,
κ-validated, CI-platform-specific failure taxonomy. **Cite as the current
state of the art for Axis 2, and as the closest κ benchmark for DURP's
validation** (0.708 on a multi-category build-failure labeling task — the most
comparable task to DURP's Scheme-2 coding).* Fully verified.
> Note: distinct from the unrelated `zheng2023security.pdf` already in the repo.

---

## Axis 3 — build reproduction / "software archaeology" failures

### Fu, Ermedahl, Eldh, Wiklund, Haller, Artho — "Where did we fail? —
Reproducing build failures in embedded open source software" (EASE 2026)
arXiv:2604.27075v1 (29 Apr 2026; KTH + Ericsson). >10,000 PR/MRs across **four
embedded projects** (OpenIPC, STM32, RTEMS, Zephyr); of **4628 failing CI
runs**, reconstructed 91.8%, **380 reconstruction failures**. Table 4 categorizes
those 380: **Hardware dependency missing 34% (129)**, **Removed package
repository 27% (103)**, **Proprietary toolchain unavailable 19% (72)**,
**Implicit environment dependency 15% (57)**, **Other 5% (19)**. **No Cohen's κ
found.**
→ *The single closest precedent for Scheme 2 — genuine historical-build
reconstruction-failure classification (environment drift / dependency decay).
But coarse (5 vs DURP's 15) and embedded-firmware, not Rust.* Mapping:
- Fu "Removed package repository" ≈ DURP `REPO_GONE` / `NETWORK_ERROR`
- Fu "Proprietary toolchain" / "Implicit environment dep" ≈ DURP
  `NATIVE_DEP_MISSING` / `OPENSSL_MISMATCH` (loosely)
- DURP `RUSTC_BITROT`, `MSRV_TOO_LOW`, `NIGHTLY_REQUIRED`, `LOCK_FILE_STALE`,
  `OLD_MESSAGE_FORMAT` have **no precedent in Fu** — language/ecosystem-specific
  reproduction failures are the gap DURP fills.

> ⚠ Fu's text says reconstruction failures were "mainly caused by changes in
> external dependencies rather than methodological limitations" — *adjacent* to
> DURP's corpus-vs-fixable axis, but the adversarial verification **refuted**
> citing Fu as validating that axis (different domain + granularity). Cite Fu as
> a *domain precedent*, not as validation of the organizing axis.

### Malka, Zacchiroli, Zimmermann — "Reproducibility of Build Environments
through Space and Time" (ICSE-NIER 2024)
arXiv:2402.00424; DOI 10.1145/3639476.3639767. Rebuilt **99.94% of ~14k
packages from a 6-year-old Nixpkgs revision** (2017→2023). Non-reproducing jobs
described by an informal 3-bucket scheme (sandbox leakage / flaky / past
leakage); **no κ**; relied on the Nix binary cache; does not check bit-for-bit.
→ *Cite as supporting evidence for Scheme 2's premise — environment-pinning
enables historical reproduction (DURP's fat-image mechanism). Weak precedent for
the taxonomy itself.* Verified.

### Reproducible-builds literature (orthogonal — confirms the gap)
Lamb & Zacchiroli (IEEE Software 2022, arXiv:2104.06020); Goswami et al. (ICSME
2020); Miller et al. ("Empirical Study on Reproducible Packaging", multi-
ecosystem incl. Cargo). These target **bit-for-bit artifact identity from the
latest source in a fixed environment** — *not* rebuilding a historical pre-bump
baseline under a pinned toolchain. Cargo measured ~100% bitwise-reproducible
as-is. Miller et al.'s "reproducible as-is / with config / with patched PM /
non-reproducible" hierarchy is a *de facto fixability axis* that **parallels**
(but does not predate) Scheme 2's corpus-vs-fixable axis.
→ *Orthogonal problem; confirms Scheme 2 addresses something distinct.* The
**Benedetti/IEEE-S&P 2025** attribution from the automated scan was **refuted**
(wrong attribution); the correct multi-ecosystem reference is the Miller-hosted
"Empirical Study on Reproducible Packaging" PDF.

---

## Mapping summary: adopt vs. position-as-gap

| DURP element | Precedent | Action |
| --- | --- | --- |
| Scheme 1 top level | BUMP 2024 (Java) | **Adopt/align** — keep as anchor for comparability |
| Scheme 1: transitive root cause | Breaking-Good 2024 "indirect compilation failure" | **Adopt** as a sub-category note under `COMPILATION_FAILURE` |
| Scheme 1 vs cause-of-change | Kong 2024 (npm), classifies *causes* not symptoms | **Cite as complementary**, distinguish symptom-vs-cause |
| General CI-failure taxonomy / κ method | Zheng 2025 (GHA, 16 cats, κ 0.708) | **Cite** as modern Axis-2 SoTA + κ benchmark (~0.7 target) |
| Scheme 2 (reproduction failures) | Fu 2026 (5 coarse cats, embedded) | **Position as extension** — DURP is finer-grained + Rust-specific |
| Scheme 2 premise (pinning enables historical rebuild) | Malka 2024 (Nix 99.94%/6yr) | **Cite as supporting evidence** |
| Scheme 2 organizing axis (corpus-vs-fixable) | none (only loose analogy) | **Claim as novel** |
| `RUSTC_BITROT`, `MSRV_TOO_LOW`, `NIGHTLY_REQUIRED`, `LOCK_FILE_STALE` | none found | **Claim as novel** (Rust-ecosystem-specific) |

## κ target for DURP's own validation

Surveyed, primary-verified values: **Zheng 0.708** (GHA failures, multi-category
build-failure labeling — the most comparable task), **Kong 0.77/0.80/0.94** (BC
classification). Targeting/reporting **κ ≈ 0.7 ("substantial")** for DURP's
Scheme-2 hand-validation is defensible and literature-aligned. (Harness, codebook
and scorer for this are in `scripts/build_taxonomy_sample.py`,
`scripts/score_taxonomy_kappa.py`, `docs/taxonomy-codebook.md`.)

## Provenance / caveats

- All citations above verified from the primary PDF except where flagged.
- **Kong venue** (TOSEM 2025) unconfirmed — cite as arXiv 2024 preprint.
- **Jayasuriya et al.** dropped as an unverifiable/likely-fabricated reference.
- The corpus-vs-fixable-axis novelty and the Fu-axis-validation refutation came
  from adversarial verification of the automated scan (3-vote); honored here.
- PDFs (thesis working notes, outside this repo):
  `rp2026/docs/related-work/pdfs/{kong2024breaking,fu2026reproducing,
  zheng2025ghactions}.pdf` (+ the existing BUMP / malka / rausch set).
