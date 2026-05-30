# RP 2025/2026 Q4 — Shared Infrastructure POC

Cross-ecosystem shared infrastructure for the TU Delft Research Project
*"Mining Reproducible Dependency Updates Across Ecosystems"* (extending
BUMP). Current state: schema v0.0.5, Fork B reproducibility model
(environmental equivalence over byte-identical OCI digests).

## What this POC is

1. A **shared JSON schema** (v0.0.5) for one reproducible dependency-update
   entry — covering `breaking`, `non-breaking`, and `fix-after-update`
   categories.
2. A **shared failure taxonomy** with an ecosystem-agnostic top level and
   ecosystem-specific subcategories.
3. A **shared Python library (`bump_ext`)** with Pydantic models, JSON
   Schema validation, and an entry writer.
4. A **Cargo pipeline** exercising the shared contracts end-to-end:
   candidate generation → fat-image resolution → reproduction →
   classification → assembly → optional regenerate-verify. Candidates
   come from two cohorts: the **historical** 2018–2021 set (Rebatchi DS1,
   via `rebatchi_ds1_filter.py` → `rebatchi_to_candidate.py`) and the
   **recent** 2024–2025 set (live-mined from GitHub, via the
   `scripts/cargo_live_*` + `launch_live_mine.sh` pipeline). Both feed
   the same enrichment + driver path.
5. A **fat-image toolkit** — index, resolver, deterministic canonical
   tags, build CLI — so the reproducibility story is "rebuild locally
   and verify fingerprint", not "pull a published image."

Other ecosystem owners (Maven, pip, npm) write their own pipeline against
the same schema + library. RQ1 / RQ2 consume the combined corpus. The seam
that makes this concrete — and evidence that the schema/taxonomy/contract
are already ecosystem-agnostic — is specified in
[`docs/ecosystem-plugin-interface.md`](docs/ecosystem-plugin-interface.md)
(design; Cargo is the reference implementation).

## Reproducibility model (Fork B)

The reproducibility contract is an **environment fingerprint** — a sha256
over the concatenation of five files emitted by the fat image:
`packages.txt`, `rustc.txt`, `cargo.txt`, `os-release`, `sources.list`.
Two hosts agree on "same environment" if and only if they agree on this
hash.

Byte-identical OCI digests proved impossible in practice due to
apt-internal non-determinism even with pinned `SOURCE_DATE_EPOCH` + apt
snapshot. Rationale and evidence in
[`docs/cargo/reproducible-builds.md`](docs/cargo/reproducible-builds.md).

## Directory layout

```
schema/
  entry.schema.json         master contract, v0.0.5
  failure-taxonomy.md       shared top-level + Cargo subcategories
  examples/
    cargo-example.json      filled-in example entry
lib/
  bump_ext/                 shared Python library
    models.py               Pydantic models matching the schema
    validate.py             JSON Schema validator
    writer.py               EntryWriter
    __init__.py             SCHEMA_VERSION + re-exports
pipelines/
  cargo/
    _candidate.py           shared Candidate dataclass + GitHub helpers
    cargo_miner.py          live-GitHub PR miner
    cargo_toolchain.py      MSRV detection (file parsers + GitHub API)
    cargo_reproducer.py     pre/post/fix commit verification in Docker
    cargo_classifier.py     cargo log → failure taxonomy
    cargo_assemble_entry.py candidate + reproduction + classification → v0.0.5 entry
    cargo_regenerate.py     entry-driven rebuild + fingerprint verify
    cargo_drive.py          end-to-end driver (JSONL → entries)
    cargo_plan_fat_images.py batch planner, read-only
    fat_image.py            fat-image index + canonical bucketing + build CLI
scripts/
  rebatchi_ds1_filter.py    rar-stream pre-filter for DS1 (historical cohort)
  rebatchi_to_candidate.py  Rebatchi/live row → candidate JSONL (enrichment, shared)
  cargo_live_search.py      live-mine Stage 1 — GitHub Search API (recent cohort)
  cargo_live_sample.py      live-mine Stage 1.5 — stratified monthly sample
  launch_live_mine.sh       live-mine orchestrator (Stage 1 → 1.5 → 3)
  rebuild_index.py          rebuild pipeline.sqlite from canonical JSONs
  verify_index.py           CI drift check: on-disk JSONs vs SQLite index
  cargo_survey_sys_deps.py  Cargo *-sys coverage survey (one-off analysis)
  rebatchi_ds1_count.py     DS1 upstream-universe size verifier (one-off)
  rustsec_crossings.py      RustSec advisory cross-reference (one-off analysis)
docker/
  cargo-fat/
    Dockerfile              parameterised on RUST_VERSION, DEBIAN_RELEASE, SOURCE_DATE_EPOCH, INCLUDE_GUI
    repro-sources-list.sh   vendored apt-snapshot pinner (locally patched for buster-era)
    index.json              inventory of registered fat images
data/
  cargo/                    submodule → lyuben-todorov/dep-updates-rp-data
                            canonical v0.0.5 entry JSONs (Zenodo-bound)
  cargo-logs/               reproducer + driver logs (gitignored)
  cargo-dockerfiles/        transient thin-image Dockerfiles (gitignored)
  pipeline.sqlite           derived query index, rebuildable (gitignored)
  rebatchi/
    ds1_cargo_candidates.jsonl        DS1 filter output (pre-enrichment)
    ds1_candidates_enriched.jsonl     full DS1, enriched (msrv + commit_date), --require-cargo filtered
    ds1_candidates_enriched_500.jsonl first 500 of DS1, kept for regression
    sample-drive/                     output of the 5-candidate smoke test
docs/
  shared/
    schema.md               schema design + field-by-field tour
    bump_ext-library.md     library API
  cargo/
    running-a-batch.md      end-to-end runbook — from a fresh checkout to verified entries
    (rebatchi + reproducibility design moved to ../docs/ at repo root)
    survey-findings.md      *-sys crate coverage survey (93% under 35 packages)
pyproject.toml
README.md
CHANGELOG.md
```

## Quick start

```bash
# 1. Clone with submodules (data/cargo/ is a submodule).
git clone --recurse-submodules https://github.com/lyuben-todorov/DURP.git && cd DURP
# If you already cloned: git submodule update --init

# 2. Install (editable) — registers the `durp` CLI.
pip install -e '.[cargo]'

# 3. Token: put GITHUB_TOKEN=<your_pat> in a .env at the repo root.
#    durp auto-loads it — no `set -a; . .env` needed. (Or export it.)
echo 'GITHUB_TOKEN=<your_pat>' > .env

# 4. (Optional) cp durp.toml.example durp.toml and set host / paths.

# 5. Verify a published reproduction in one command:
durp verify data/cargo/cargo-001c45ac.json

# Or drive a small batch end-to-end against the bundled test slice:
durp reproduce \
  --candidates data/rebatchi/ds1_candidates_enriched_500.jsonl \
  --build-missing-bases --limit 5
```

### The `durp` CLI

A single entrypoint over the pipeline (`durp <verb> --help` shows each
underlying tool's full flag set):

| Command | Does |
| --- | --- |
| `durp verify <entry.json>` | rebuild the fat image + re-verify one entry's fingerprint |
| `durp reproduce --candidates X.jsonl` | drive a cohort end-to-end (the main pipeline) |
| `durp mine <owner/repo>` | mine dependency-update PRs from one repo |
| `durp plan --candidates X.jsonl` | show which fat images a cohort needs (read-only) |
| `durp index rebuild` / `verify` | rebuild / drift-check the SQLite index |
| `durp fat-image <list\|resolve\|build\|…>` | fat-image registry management |
| `durp dev <live-search\|rebatchi\|…>` | ingestion + cohort tooling |

durp injects defaults from `durp.toml` + `.env` for flags you omit and
forwards everything else through, so it's a thin layer over the same
modules (`python -m pipelines.cargo.cargo_drive …` still works directly).

For the full end-to-end workflow (planning → fat-image builds →
batch drive → verification), see
[`docs/cargo/running-a-batch.md`](docs/cargo/running-a-batch.md).

**To verify the published results** (the 1,415-entry `ds1-full-crack-r2`
cohort) rather than re-run the study, see
[`docs/cargo/reproduction-runbook.md`](docs/cargo/reproduction-runbook.md)
— a layered runbook for an external verifier, from a 10-minute
schema-and-counts check to rebuilding a fat image and re-verifying a
single reproduction's fingerprint.

## Proof it works

Two real v0.0.5 entries live in the `data/cargo/` submodule
([`lyuben-todorov/dep-updates-rp-data`](https://github.com/lyuben-todorov/dep-updates-rp-data)):

- `cargo-9ac20c07.json` — `fstubner/netscli#22`, Dependabot
  `ipnetwork 0.20 → 0.21`. Category `breaking`
  (COMPILATION_FAILURE / TYPE_MISMATCH / E0308). Reproduced under
  `rp2026/cargo-fat:1.92.0-bookworm-20260427`.
- `cargo-f82e5be0.json` — `passy/revmenu#21`, Dependabot-preview
  `im 10.2.0 → 12.3.1`. Category `breaking`. Reproduced under
  `rp2026/cargo-fat:1.56.0-buster-20211022`.

## Key design decisions

| Decision | See |
| --- | --- |
| Environment fingerprint over OCI digest | [`docs/cargo/reproducible-builds.md`](docs/cargo/reproducible-builds.md) |
| Fat image covers ~93% of Cargo *-sys crates | [`docs/cargo/survey-findings.md`](docs/cargo/survey-findings.md) |
| Dataset 1 over Dataset 2 for the paper corpus | [`docs/findings/rebatchi.md`](docs/findings/rebatchi.md) |
| Canonical fat-image tags (`<rust>-<debian>-<yyyymmdd>`) | `pipelines/cargo/fat_image.py` |
| `pre` / `post` / `fix` commit naming (not `preBreaking`/`breaking`) | `CHANGELOG.md` v0.0.4 |

## Status

**v0.0.5 — per-architecture environment fingerprints.** The scalar
`environmentFingerprint` field is replaced by a `environmentFingerprints[]`
list, each entry tagged by container platform (`linux/amd64`,
`linux/arm64`). A single entry can now accumulate cross-architecture
verifications: each arch has its own digest because `packages.txt`
and `rustc.txt` differ by arch, but the reproduction contract (same
apt snapshot, same SDE, same rust) is arch-agnostic.

DS1-full run completed 2026-05-12: 2608 candidates processed,
**1210 reproducible (46.4 %)**, 1395 not_reproducible, 3
regenerate_mismatch. See [`docs/findings/ds1-full-findings.md`](docs/findings/ds1-full-findings.md)
for the full breakdown, [`docs/findings/ds1-full-r2-findings.md`](docs/findings/ds1-full-r2-findings.md)
for the round-2 rerun (52.1 %, the headline base), and
`schema/failure-taxonomy.md` for the reproduction-failure taxonomy
(Scheme 2). The **published `ds1-full-crack-r2` artifact is 1,415
entries / 54.3 %** — Run B plus the OpenSSL-stretch (+48) and native-dep
(+8) image-substitution recovery sub-cohorts
([`docs/findings/`](docs/findings/) has both case studies).

Earlier milestones: v0.0.4 introduced the category-neutral schema +
fat-image internals refactor + SQLite index layer.
Layer 1 extracted to its own repo (`dep-updates-rp-data`, wired in
as a submodule at `data/cargo/`). `PipelineDB` / `rebuild_index.py` /
`verify_index.py` shipped; `cargo_drive` has optional `--db` mirror.

Next milestones: dissect the failure categories one by one for
recoverable wins, and ingest the live 2024-2025 mine (pipeline in
`scripts/cargo_live_*`; see
[`docs/cargo/running-a-batch.md`](docs/cargo/running-a-batch.md) §3
Option C) for RQ3's recent comparison cohort.
