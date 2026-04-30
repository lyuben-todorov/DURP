# Survey: System-library dependency coverage in Cargo projects

## What was measured

We sampled **50 closed-unmerged Dependabot/Renovate PRs** on Rust GitHub
repositories (single-dependency Cargo.toml bumps, via the GitHub search API).
For each repo we fetched `Cargo.lock` at the breaking commit and counted
`*-sys` crates — the convention for Rust bindings to native C libraries.

Source: `scripts/cargo_survey_sys_deps.py`. Raw data saved to
`/tmp/survey.json` when the script is run.

## Headline numbers (N = 41 analyzed, 9 lockfiles missing)

| Strategy | Repos covered | % |
| --- | --- | --- |
| Minimal Alpine + cargo (like BUMP) | ~6 | ~15% |
| Fat Debian with 35 `-dev` packages | **38** | **~93%** |

The fat image (`docker/cargo-fat/Dockerfile`) installs, among others:
`libssl-dev`, `libsqlite3-dev`, `libzstd-dev`, `zlib1g-dev`, `libbz2-dev`,
`liblzma-dev`, `liblz4-dev`, `libonig-dev`, `libpcap-dev`, `libudev-dev`,
`libdbus-1-dev`, `libasound2-dev`, the GTK3 stack (`libgtk-3-dev`,
`libglib2.0-dev`, `libpango1.0-dev`, `libcairo2-dev`, `libgdk-pixbuf2.0-dev`,
`libatk1.0-dev`), `libsoup-3.0-dev`, `libwebkit2gtk-4.1-dev`,
`libayatana-appindicator3-dev`, `clang` + `libclang-dev`, `cmake`,
`build-essential`. Final image weighs ~2.7 GB.

The remaining ~7% needed exotic deps: `llama_cpp_sys` (LLaMA inference),
`rdkafka-sys` (Kafka client), `lmdb-master-sys`, `ort-sys` (ONNX Runtime).
These are reasonable to exclude or handle as special cases.

## What this means for the thesis

1. **Minimal base images are not viable for Cargo.** Unlike BUMP/Java, a
   single "Alpine + rust + musl" will discard the majority of real-world
   projects.
2. **A fat Debian base is a practical sweet spot.** Covers >90% of sampled
   projects at ~2.7 GB. Ships a pinned image tag per Rust minor for
   reproducibility.
3. **Per-entry toolchain detection is required.** The `netscli` project
   pins Rust 1.92 via `rust-toolchain.toml`. Using a default Rust 1.75 image
   rejects the build before `cargo test` even runs. Implemented in
   `pipelines/cargo/cargo_toolchain.py`.
4. **Some `*-sys` crates are false positives for this concern**:
   `js-sys`, `web-sys`, `linux-raw-sys`, `fsevent-sys`, `windows-sys`,
   `core-foundation-sys`, `dirs-sys`, etc. are pure-Rust bindings to
   language runtimes, kernel APIs, or platforms without an apt equivalent.
   The classifier excludes these explicitly via the `IGNORE_SYS` list in
   `scripts/cargo_survey_sys_deps.py`.
5. **Dataset bias.** ~22% of sampled repos had no `Cargo.lock` committed,
   which is a meaningful drop-out (applications usually commit one;
   libraries usually don't). The benchmark should be biased toward
   applications — they are the ones where `cargo test` is meaningful anyway.

## Operational conclusions

- **Default to the fat image.** `docker/cargo-fat/` covers ~93% of the
  sample. Minimal Alpine is kept as a fallback only.
- **Record per entry which base image succeeded.** This becomes a new axis
  in the benchmark ("base-image tier required for reproduction").
- **When a project needs a dep outside the fat image**, log it with
  `unreproducibilityReason = "toolchain_unavailable"` and include the
  missing library in `ecosystemMetadata`.

## Caveats

- Sample size is small (50 repos via search API). A larger survey against
  Rebatchi et al.'s dataset will sharpen the numbers.
- `Cargo.lock` tells us the *resolved* graph, not the *features enabled*.
  Some `*-sys` crates build only under specific feature flags. Our count
  is therefore an upper bound on required system deps.
- apt package names differ between Debian and Ubuntu. We target Debian
  bookworm.
