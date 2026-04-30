# Changelog

## v0.0.2 — 2026-04-30

- Real end-to-end reproduction of a Dependabot breaking update: `fstubner/netscli#22` (`ipnetwork 0.20 → 0.21`) now produces `data/cargo/cargo-9ac20c07.json` classified as `COMPILATION_FAILURE` / `TYPE_MISMATCH` / `E0308`.
- Built `docker/cargo-fat/Dockerfile` — Debian-bookworm-based Rust image with ~35 `-dev` packages. Survey shows ~93% coverage of real-world Cargo projects (up from ~15% on Alpine).
- Added Cargo toolchain auto-detection (`cargo_toolchain.py`). Reads `rust-toolchain.toml`, `rust-toolchain`, or `Cargo.toml:rust-version` and returns the matching Rust image tag.
- Reproducer (`cargo_reproducer.py`) now fetches closed-unmerged PR commits via `git fetch origin <sha>:_repro` when the commit isn't on the default branch.
- Reproducer recognises fat images (`rp2026/cargo-fat:*`) and skips the runtime apt install.
- Schema: `commits.preBreakingAuthorType` and `commits.breakingAuthorType` are now nullable (caught by the schema validator on the first real reproduction).
- Renamed all Cargo-specific files with `cargo_` prefix for clarity alongside shared infra.
- Reorganised docs into `docs/shared/` (schema, library) and `docs/cargo/` (survey findings, image management).
- Added `pipelines/cargo/README.md` with the full end-to-end worked example.
- Added `docs/shared/schema.md` and `docs/shared/bump_ext-library.md` — explainers for the two shared contracts.

## v0.0.1 — 2026-04-30

- Initial POC draft.
- Schema: `entry.schema.json` v0.0.1 with required fields for project, PR, commits, update, category; optional reproduction and failure; open `ecosystemMetadata` escape hatch.
- Failure taxonomy: 5 top-level categories; Cargo subcategories defined.
- Python library `bump_ext`: Pydantic models, JSON Schema validator, `EntryWriter`, canonical `image_ref` helper.
- Cargo pipeline: miner, reproducer, dockerizer, classifier, assemble_entry.
- Docker contract: `ghcr.io/tudelft-rp2026/breaking-updates-<ecosystem>:<shortHash>-{pre|breaking}`.
