# RP 2025/2026 Q4 — Shared Infrastructure POC

Cross-ecosystem shared infrastructure for the TU Delft Research Project *"Mining Reproducible Dependency Updates Across Ecosystems"* (extending BUMP). This POC defines:

1. A **shared JSON schema** for one reproducible dependency-update entry.
2. A **shared failure taxonomy** with an ecosystem-agnostic top level and ecosystem-specific subcategories.
3. A **shared Docker image naming convention** and entrypoint contract.
4. A **shared Python library (`bump_ext`)** with Pydantic models, validation, and an entry writer.
5. A **Cargo pipeline** (miner → reproducer → dockerizer → classifier → assemble_entry) that exercises the shared contracts end-to-end.

Other ecosystem owners (Maven, pip, npm) write their own pipeline against the same library. RQ1/RQ2 consume the combined output.

## Directory layout

```
schema/
  entry.schema.json         # the master contract
  failure-taxonomy.md       # shared top-level + Cargo subcategories
  examples/
    cargo-example.json      # filled-in example entry
lib/
  bump_ext/                 # shared Python library (Pydantic + schema validator + writer)
pipelines/
  cargo/                    # this student's ecosystem pipeline
    cargo_miner.py
    cargo_reproducer.py
    cargo_dockerizer.py
    cargo_classifier.py
    cargo_toolchain.py
    cargo_assemble_entry.py
scripts/
  cargo_survey_sys_deps.py  # Cargo *-sys coverage survey
docker/
  cargo-fat/                # fat Debian+Rust image (~35 -dev packages)
data/
  cargo/                    # output: <id>.json per entry, plus reproduction logs
docs/
  shared/
    schema.md               # shared schema design and rationale
    bump_ext-library.md     # shared Python library design
  cargo/
    survey-findings.md      # Cargo *-sys coverage results
    image-management.md     # Cargo Docker image lifecycle notes
pyproject.toml
README.md
CHANGELOG.md
```

## Documentation

- `docs/shared/schema.md` — why the schema is shaped the way it is.
- `docs/shared/bump_ext-library.md` — what the Python library provides and why.
- `docs/cargo/survey-findings.md` — empirical survey of Cargo `*-sys` crate coverage under a fat Debian base image (~93% of sampled projects).
- `docs/cargo/image-management.md` — design notes for running the Cargo pipeline unattended (image GC, autonomy).

## Quick start

```bash
# Install the shared library (editable, with Cargo extras).
pip install -e '.[cargo]'

# Build the fat Rust image for the toolchain you need
# (see docs/cargo/survey-findings.md for why fat > minimal).
docker build --build-arg RUST_VERSION=1.92 -t rp2026/cargo-fat:1.92 docker/cargo-fat

# Run the end-to-end Cargo pipeline on a real PR.
# Full worked example: pipelines/cargo/README.md.
```

For a full worked example (mine → reproduce → classify → assemble a
schema-valid entry from a real Dependabot breaking update), see
[`pipelines/cargo/README.md`](pipelines/cargo/README.md).

## Proof it works

End-to-end on a real case, committed under `data/cargo/cargo-9ac20c07.json`:

- **Repo:** `fstubner/netscli`
- **PR:** #22, Dependabot bump `ipnetwork 0.20 → 0.21`, closed unmerged (CI failed).
- **Toolchain:** `rp2026/cargo-fat:1.92` (matches project's pinned `rust-toolchain.toml`).
- **Pre-breaking:** exit 0 ✓
- **Breaking:** exit 101 ✓
- **Failure:** `COMPILATION_FAILURE / TYPE_MISMATCH / E0308`.

## Shared Docker contract

- **Registry:** `ghcr.io/tudelft-rp2026` — placeholder. Supervisor action item: create the GitHub org for the team.
- **Image name:** `breaking-updates-<ecosystem>:<shortHash>-{pre|breaking}`.
- **Entrypoint:** `docker run <image>` with no args reproduces the build.
- **Exit code:** `0` for pre-breaking images (must pass), non-zero for breaking images (must fail).
- **Base images** (Cargo): `rp2026/cargo-fat:<rust-minor>` — Debian bookworm + Rust + ~35 `-dev` packages. Built locally from `docker/cargo-fat/`; to be published once the org lands.
- **No `:latest` tags.**

## Schema contract (entry.schema.json)

One JSON file per reproducible update under `data/<ecosystem>/<id>.json`. `<id>` is `<ecosystem>-<breakingShortHash>`.

Consumers (RQ1, RQ2) can enumerate entries by globbing `data/*/*.json` and validating against `schema/entry.schema.json`.

## Status

**v0.0.2 — POC draft.**
