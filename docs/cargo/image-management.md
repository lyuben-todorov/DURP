# Image Management (design note)

The pipeline must be able to run autonomously for many hours in an isolated
environment (a laptop left running overnight, or a VM). This document
captures the design constraints, the current state, and what is still
planned.

## Constraints

- Disk is finite. Each Rust toolchain image is ~500 MB (minimal) to ~2.7 GB
  (fat); one per-entry reproduction image pair could be hundreds of MBs.
- Network is flaky. Re-pulls should be rare.
- The host must not accumulate dangling images indefinitely.
- The pipeline must recover cleanly after SIGKILL or reboot.

## Tiers of images

| Tier | Role | Lifetime |
| --- | --- | --- |
| **Toolchain base (minimal)** | `rust:<ver>-alpine` — used when auto-detection fires and the project has no `*-sys` crates. | Cached forever |
| **Toolchain base (fat)** | `rp2026/cargo-fat:<ver>` — Debian bookworm + Rust + ~35 `-dev` packages. Built from `docker/cargo-fat/Dockerfile`. Recommended default for any non-trivial crate. | Cached forever; rebuilt when a new Rust minor lands |
| **Scratch helper** | `alpine/git` — used by the reproducer for per-candidate toolchain detection (fetches `rust-toolchain.toml`, `Cargo.toml` without needing git on the host). | Cached forever |
| **Per-entry pair** | `<registry>/breaking-updates-cargo:<hash>-{pre,breaking}` — the published benchmark artifact, produced by `cargo_dockerizer.py`. | Kept; this is what RQ1/RQ2 consume |

## Current state

- **Toolchain bases**: pulled once, cached by Docker's content-addressed
  store. Fat image is built locally via `docker build`. No manual cleanup
  needed.
- **Scratch helper**: `alpine/git:latest` pulled on first run, kept forever.
- **Per-entry pair**: `cargo_dockerizer.py` builds and (with `--push`)
  pushes to a registry; local tags remain unless manually removed.
- **Reproducer transient containers**: `cargo_reproducer.py` runs with
  `--rm`, so per-candidate containers are cleaned up automatically. Docker
  image layers persist in the build cache.

## Planned future additions (not built yet)

1. **Image GC.** After a successful push, `docker rmi` the local pre/breaking
   tags. Avoid filling the host disk when running at scale.
2. **Build cache warming.** Pre-populate a shared Docker volume with
   `~/.cargo/registry` so sibling reproductions don't each re-download deps.
3. **Resume log.** Maintain a JSONL of completed entries so restarts skip
   already-processed candidates.
4. **Autonomy mode.** `run_all.py` that drains a candidate queue, writes
   results to disk, pushes images, GCs locally — safe to leave running.
5. **Disk pressure watchdog.** If free disk drops below a threshold, pause
   new reproductions and trigger GC.

## Why this matters for Cargo specifically

Java/BUMP could get away with one base image for every project. Cargo needs
a toolchain per MSRV (1.70, 1.75, 1.80, …) because projects pin exact Rust
versions in `rust-toolchain.toml`. A year of reproductions may touch a
dozen toolchain images. Multiplying by two (alpine-minimal vs debian-fat)
gives 20+ cached bases. Plus per-entry images — easily 100+ GB. So image
lifecycle is a real first-class concern, not infrastructure bikeshedding.
