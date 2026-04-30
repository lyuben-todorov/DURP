# Cargo pipeline

Mining and reproduction pipeline for Rust/Cargo dependency updates. Produces
schema-valid entries under `data/cargo/` that conform to the shared
[`entry.schema.json`](../../schema/entry.schema.json).

The pipeline is split into five single-purpose scripts that compose via JSON
on disk. Each step reads the previous step's output, so you can re-run any
stage in isolation.

```
cargo_miner.py        GitHub PRs        → candidates.jsonl
cargo_reproducer.py   candidates.jsonl  → reproduction.jsonl  (+ build logs)
cargo_classifier.py   breaking.log      → classification.json
cargo_assemble_entry  all of the above  → data/cargo/<id>.json
```

`cargo_toolchain.py` is a helper used by `cargo_reproducer.py` (not run
directly).
`cargo_dockerizer.py` packages a reproducible candidate as a published pair
of Docker images (separate from reproduction-on-the-fly).

## Prerequisites

- Docker daemon running.
- `GITHUB_TOKEN` exported (5000 req/hour instead of 60).
  ```bash
  source .env
  export GITHUB_TOKEN
  ```
- Shared library installed: `pip install -e '.[cargo]'` (from the repo root).
- Fat Rust image built for the Rust minor you need:
  ```bash
  docker build --build-arg RUST_VERSION=1.92 -t rp2026/cargo-fat:1.92 docker/cargo-fat
  ```

## Worked example: `fstubner/netscli#22`

A Dependabot PR bumping `ipnetwork` from `0.20` to `0.21`. The PR was closed
without merge (CI failed). We mine, reproduce, classify, and write a
schema-valid entry.

### 1. Mine

```bash
PYTHONPATH=lib python3 -m pipelines.cargo.cargo_miner \
  fstubner/netscli \
  --out /tmp/candidates.jsonl \
  --limit 20
```

Output: one JSON object per candidate PR on stdout/JSONL. Example:

```json
{
  "ecosystem": "cargo",
  "repo": "fstubner/netscli",
  "pr_number": 22,
  "pr_url": "https://github.com/fstubner/netscli/pull/22",
  "pr_author": "dependabot[bot]",
  "bot_type": "dependabot",
  "merged": false,
  "breaking_commit": "9ac20c0770be0a5d2f88f470dde8874f02be39db",
  "pre_breaking_commit": "8b979b8d9439408ff20a767c7100a758bf8c2495",
  "dependency_name": "ipnetwork",
  "previous_version": "0.20",
  "new_version": "0.21"
}
```

Filter rules (match BUMP's methodology):
- Only `Cargo.toml` (or `Cargo.toml` + `Cargo.lock`) touched.
- Exactly one added line and one removed line.
- Both lines parse as Cargo version strings.
- Author classified as `dependabot`, `renovate`, or `other`.

### 2. Reproduce

```bash
grep '"pr_number": 22' /tmp/candidates.jsonl > /tmp/pr22.jsonl

PYTHONPATH=lib python3 -m pipelines.cargo.cargo_reproducer \
  --in /tmp/pr22.jsonl \
  --out /tmp/reproduction_fat.jsonl \
  --toolchain rp2026/cargo-fat:1.92 \
  --logs-dir ./data/cargo/logs \
  --timeout 2400
```

By default (no `--toolchain`), the reproducer auto-detects the project's Rust
version via `cargo_toolchain.py`:

1. `rust-toolchain.toml` → `[toolchain].channel`
2. `rust-toolchain` (legacy)
3. `Cargo.toml` → `[package].rust-version` or `[workspace.package].rust-version`

and picks a matching `rust:<minor>-alpine` image. Override with
`--toolchain <image>` when a pre-built fat image is needed (recommended for
projects that pull in `*-sys` crates).

For each candidate the reproducer:

1. Spawns a container from the toolchain image.
2. `git clone`s the repo; falls back to `git fetch origin <sha>:_repro` for
   closed-unmerged PR commits that aren't on the default branch.
3. Checks out the `pre_breaking_commit`, runs `cargo test
   --message-format=json-diagnostic-rendered-ansi --no-fail-fast`.
4. Repeats for the `breaking_commit`.
5. Records exit codes and writes full build logs to `--logs-dir`.

Output for the worked example:

```json
{
  "pre_passed": true,
  "breaking_failed": true,
  "pre_exit_code": 0,
  "breaking_exit_code": 101,
  "toolchain": "rp2026/cargo-fat:1.92",
  "reproducible": true,
  "detected_toolchain": false
}
```

### 3. Classify

```bash
PYTHONPATH=lib python3 -m pipelines.cargo.cargo_classifier \
  ./data/cargo/logs/9ac20c07-breaking.log \
  > /tmp/classification.json
```

The classifier parses `cargo`'s JSON diagnostic stream, extracts `rustc`
error codes, and maps them into the shared taxonomy
(`schema/failure-taxonomy.md`):

```json
{
  "topCategory": "COMPILATION_FAILURE",
  "subCategory": "TYPE_MISMATCH",
  "errorCodes": ["E0308"]
}
```

If no compiler errors are found, the classifier falls back to keyword
matching for test failures, dependency-resolution failures, and environment
failures.

### 4. Assemble a schema-valid entry

```bash
python3 -c "
import json
rep = json.loads(open('/tmp/reproduction_fat.jsonl').read().strip())
open('/tmp/reproduction.json','w').write(json.dumps(rep))
"
cp /tmp/pr22.jsonl /tmp/candidate.json

PYTHONPATH=lib python3 -m pipelines.cargo.cargo_assemble_entry \
  --candidate /tmp/candidate.json \
  --reproduction /tmp/reproduction.json \
  --classification /tmp/classification.json \
  --toolchain rust-1.92 \
  --registry ghcr.io/tudelft-rp2026
```

This:

- Constructs a `bump_ext.Entry` Pydantic object.
- Derives the canonical Docker image refs via `bump_ext.image_ref()`.
- Validates against the shared JSON Schema.
- Writes `data/cargo/cargo-<shortHash>.json`.

Final artifact for the worked example: `data/cargo/cargo-9ac20c07.json`
(schema-valid, ready to be consumed by RQ1/RQ2 alongside entries from the
other ecosystems).

### 5. (Optional) Dockerize for publication

```bash
PYTHONPATH=lib python3 -m pipelines.cargo.cargo_dockerizer \
  --candidate /tmp/candidate.json \
  --rust-version 1.92 \
  --registry ghcr.io/tudelft-rp2026 \
  --push
```

Produces `<hash>-pre` and `<hash>-breaking` images with `cargo vendor` so
they run offline. This is the published benchmark artifact; step 2's
reproducer builds transient containers instead (faster for iteration).

## Toolchain handling (`cargo_toolchain.py`)

Respects the project's declared Rust version when it has one — critical
because Rust crates can pin an MSRV that is newer than the reproducer's
default (the `netscli` example above pins `1.92.0` via `rust-toolchain.toml`;
running under `rust:1.75-alpine` would fail to parse the manifest).

CLI usage:

```bash
python3 pipelines/cargo/cargo_toolchain.py /path/to/checkout
# -> rust:1.92-alpine
```

## `*-sys` crate coverage (why the fat image matters)

A survey of 50 real-world Rust projects found that ~85% pull in at least one
`*-sys` crate (bindings to a native C library via `pkg-config` / `cmake`).
An Alpine + `musl-dev` base covers maybe 15% of them; a fat Debian base with
~35 `-dev` packages covers ~93%. See
[`docs/cargo/survey-findings.md`](../../docs/cargo/survey-findings.md).

Consequence: the reproducer defaults to auto-detection which may produce a
minimal `rust:<ver>-alpine` image, but for any project beyond pure Rust you
probably want `--toolchain rp2026/cargo-fat:<ver>` explicitly.

## File outputs

| Path | Produced by | Purpose |
| --- | --- | --- |
| `candidates.jsonl` | `cargo_miner.py` | One line per PR candidate |
| `reproduction.jsonl` | `cargo_reproducer.py` | Pass/fail, exit codes, log paths |
| `data/cargo/logs/<hash>-{pre,breaking}.log` | `cargo_reproducer.py` | Raw build logs |
| `classification.json` | `cargo_classifier.py` | Failure taxonomy per entry |
| `data/cargo/cargo-<hash>.json` | `cargo_assemble_entry.py` | Schema-valid benchmark entry |
| `ghcr.io/.../<hash>-{pre,breaking}` | `cargo_dockerizer.py` | Published reproduction images |

## Known sharp edges

- Miner only parses the simple `name = "x.y.z"` form. Table entries
  (`[dependencies.name] \n version = "x.y.z"`) are regex-matched but untested.
- Dockerizer is less battle-tested than the reproducer; use the reproducer
  for iteration, dockerizer only when ready to publish.
- Flaky-test detection not yet implemented (BUMP runs each build 3×; we run
  once).
- `versionUpdateType` classification requires a three-part semver; versions
  like `0.20` → `0.21` currently classify as `other`.
