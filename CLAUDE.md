# DURP — agent guide

Cargo/Rust dependency-update reproduction benchmark. Mines Dependabot PRs,
reproduces their builds in pinned "fat-image" Docker containers, classifies
failures. The Cargo counterpart to the Java/Maven BUMP benchmark.

## Use the `durp` CLI — it's the front door

Don't reach for `python -m pipelines.cargo.X` by reflex. There is a unified
CLI; **run `durp --help` first**, then `durp <verb> --help` for any verb's
full flag set (verb help passes through to the underlying tool's argparse).

```
durp verify <entry.json>          re-verify one published entry (rebuild + fingerprint + outcome)
durp reproduce --candidates X.jsonl   drive a cohort end-to-end (the main pipeline)
durp mine <owner/repo>            mine dependency-update PRs from one repo
durp plan --candidates X.jsonl    show which fat images a cohort needs (read-only)
durp index rebuild | verify       rebuild / drift-check the SQLite index
durp fat-image list|resolve|build|register|unregister
durp dev live-search|live-sample|rebatchi|reproducer|classify|assemble
```

- `durp` is registered by `pip install -e .`. If it's not on PATH (e.g. a
  Homebrew Python that blocks editable installs), use **`python3 -m durp ...`**
  — identical behaviour.
- durp auto-loads `.env` at the repo root (so `GITHUB_TOKEN` Just Works — no
  `set -a; . .env`) and reads optional `durp.toml` for default paths/host.
  Explicit flags always win. See `durp.toml.example`.
- It's a thin wrapper: every underlying flag still works, and
  `python -m pipelines.cargo.cargo_drive ...` etc. remain valid.

## Layout you need to know

- `pipelines/cargo/` — the pipeline modules (driver, reproducer, fat_image
  bucketer, classifiers). `lib/bump_ext/` — shared schema + SQLite layer.
  `durp/` — the CLI wrapper (no logic, just dispatch + config).
- `data/cargo/` is a **git submodule** (`dep-updates-rp-data`). The published
  cohort lives on its **`ds1-full-crack-r2` branch** (1,415 entries). Branches
  there are append-only — never amend/force-push.
- `data/rebatchi/`, `data/live-mine/`, `data/pipeline.sqlite` are git-ignored
  working data (the SQLite is a rebuildable index — `durp index rebuild`).
- `docker/cargo-fat/` — the fat-image Dockerfile + `index.json` registry.

## Reproducibility contract (don't break it)

Reproduction = **environment-fingerprint match** (rustc · Debian · apt
snapshot), NOT byte-identical OCI digests. A reproduction must run in the
candidate's **fat image** — never "just run cargo on the host." Rationale in
`docs/cargo/reproducible-builds.md`.

`durp verify --images-only` (alias `--skip-tests`) checks the fingerprint
ONLY — it does not compile or run `cargo test`, so it does not confirm the
build or the breaking/non-breaking outcome. The default full verify does.

## Where to read more

- `README.md` — overview + the durp command table.
- `docs/cargo/reproduction-runbook.md` — verify the published results (3 tracks).
- `docs/cargo/running-a-batch.md` — full from-scratch run.
- `docs/cargo/image-selection.md` — how (msrv, commit_date, debian) → fat-image tag.
- `schema/failure-taxonomy.md` — the failure classes.
- `docs/findings/` — run reports + the recovery case studies (OpenSSL, native-dep).

## Conventions

- Tests: `python -m unittest discover tests` (or `pytest`). CI runs both +
  an index drift check on push.
- Heavy runs happen on the remote host `crack` (Docker + the working DB);
  this laptop is arm64, `crack` is amd64 — cross-arch verify uses append mode.
- Don't commit secrets; `GITHUB_TOKEN` lives in `.env` (git-ignored).
