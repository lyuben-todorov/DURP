# Findings & provenance

The evidence base behind the Cargo reproducibility results. These are
the working analysis notes that the headline numbers, the failure
taxonomy, and the reproduction runbook draw on. They are included in the
repository so an examiner can trace every claim to its source.

| Doc | What it covers |
| --- | --- |
| [`ds1-full-r2-findings.md`](ds1-full-r2-findings.md) | **The authoritative run report.** Run B (`ds1-full-crack-r2`): headline 52.1 % (Run B alone), per-category deltas vs the baseline run, per-year reproducibility, per-fat-image rates, and the four sub-agent verification audits (classifier precision per category). |
| [`ds1-full-findings.md`](ds1-full-findings.md) | The first full run (`ds1-full-crack`, baseline, 46.4 %). Superseded by the r2 report as the headline, kept for the before/after comparison. |
| [`rebatchi.md`](rebatchi.md) | Dataset provenance: how the candidate cohort derives from Rebatchi DS1, the filter recipe, and the Dataset-1-vs-2 decision. |
| [`openssl-case-study.md`](openssl-case-study.md) | The OpenSSL-stretch sub-cohort: image substitution recovers 48/64 (the +48 behind 53.9 % vs 52.1 %), and a DB-verified classifier-precision result (14/64 labelled `OPENSSL_MISMATCH` were really `TEST_FAILURE`). |
| [`native-dep-case-study.md`](native-dep-case-study.md) | A second image-substitution study over the 18 `NATIVE_DEP_MISSING` candidates: rebuilding stale fat images recovers 7 (all "missing-package"), confirms 0/6 "undefined-reference" (ABI) cases recover, and motivates splitting the taxonomy class. |
| [`live-mine-rq3-prep.md`](live-mine-rq3-prep.md) | Drive-prep for the 5,401-candidate 2024–2025 cohort (RQ3): cohort profile, the 5 fat images a drive must build, and falsifiable pre-registered predictions. Read-only; nothing driven yet. |

The merged published artifact (`ds1-full-crack-r2` branch, 1,407
entries, 53.9 %) is Run B plus the OpenSSL-stretch sub-cohort; see
[`../cargo/reproduction-runbook.md`](../cargo/reproduction-runbook.md)
§6 for that distinction.
