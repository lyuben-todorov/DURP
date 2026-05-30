# Ecosystem-plugin interface (design)

**Status: design document, not yet implemented.** The pipeline is Cargo-only
today. This specifies the seam that would let Maven / pip / npm plug in against
the same schema, driver, and reproducibility contract — and shows, with code
references, that the Cargo implementation already satisfies that seam. The point
is to demonstrate the infrastructure is **ecosystem-agnostic by design**, and to
bound how much work a second ecosystem actually is, without destabilising the
working Cargo pipeline that produces the published cohort.

## Why this is credible, not aspirational

The shared contracts are already in the code, not retrofitted:

- **The schema is polyglot.** `lib/bump_ext/models.py:15` —
  `Ecosystem = {cargo, maven, pip, npm}`; `schema/entry.schema.json:21` — the
  entry-id pattern is `^(cargo|maven|pip|npm)-[a-f0-9]{7,40}$`; the `Entry`
  fields `project / pr / commits / update / category / reproduction /
  verifiedOn` carry zero Cargo assumptions.
- **The failure taxonomy's top level is shared.** `models.py:56` —
  `TopFailureCategory = {COMPILATION_FAILURE, TEST_FAILURE,
  DEPENDENCY_RESOLUTION_FAILURE, ENVIRONMENT_FAILURE, OTHER}`. Only the
  *sub*categories (rustc E-codes, `OPENSSL_MISMATCH`, …) are ecosystem-owned.
- **The reproducibility contract is ecosystem-neutral.** "Environment
  fingerprint = sha256 over a small set of manifest files, matched per
  container platform" (`docs/cargo/reproducible-builds.md`) says nothing about
  Rust. `EnvironmentFingerprint{platform, digest, files, packageCount}` is
  generic.

So the Cargo-specificity is **localised**, not pervasive. The hardcoded
`ecosystem="cargo"` literals are exactly four call sites
(`cargo_assemble_entry.py:198,253`, `cargo_drive.py:527`, `cargo_miner.py:138`,
plus `scripts/rebatchi_to_candidate.py:106`) — all trivially parameterisable.
The real work of a second ecosystem is the six behavioural seams below.

## The pipeline, and where the seams are

```
mine → select/build fat image → reproduce (pre/post build) → classify → assemble → verify
  │            │                        │                       │           │         │
  S1           S2                       S3                      S4          (param)   S3'
```

Each `S*` is a method group an ecosystem plugin must supply. Everything else
(the driver loop, state/resume, the SQLite mirror, the schema, the Grafana
layer, `verifiedOn` accumulation) is shared and untouched.

---

## The interface

A plugin is one object implementing the groups below. Signatures are written to
match what the Cargo code *already does* — each is annotated with the concrete
Cargo function that is its de-facto implementation today.

```python
class EcosystemPlugin(Protocol):
    ecosystem: str            # "cargo" | "maven" | "pip" | "npm"
    image_prefix: str         # "rp2026/cargo-fat", "rp2026/pip-fat", ...
```

### S1 — Mining (what is a candidate?)

```python
def manifest_files(self) -> set[str]:
    """Files whose change signals a dependency bump.
       cargo: {"Cargo.toml", "Cargo.lock"}; maven: {"pom.xml"};
       pip: {"requirements*.txt","pyproject.toml","setup.py"};
       npm: {"package.json","package-lock.json"}."""

def parse_bump(self, diff_hunk: str) -> tuple[str,str,str] | None:
    """(dependency_name, previous_version, new_version) or None.
       The generic BUMP_RE on the PR *title* already works for all
       Dependabot/Renovate ecosystems; this is the manifest-diff fallback."""
```
*Cargo today:* `cargo_miner.py` — the `Cargo.toml`/`Cargo.lock` file check
(lines 108-109) and `CARGO_VERSION_LINE` regex (line 34). `BUMP_RE` in
`_candidate.py:25` is **already ecosystem-neutral** (it parses
"Bump X from A to B" titles, which Dependabot emits identically everywhere).

The output is the existing `Candidate` dataclass (`_candidate.py:31`), which is
already generic — `ecosystem` is a field, and `rust_msrv` is the one
Cargo-flavoured slot (rename to a neutral `toolchain_constraint` when a second
ecosystem lands).

### S2 — Build-environment selection (the fat image)

This is the largest seam and the heart of the reproducibility contract: map a
candidate to a **pinned, rebuildable build image + deterministic snapshot
date**. The *structure* is generic; the *constants* are per-ecosystem.

```python
def toolchain_at_commit(self, repo: str, sha: str) -> str | None:
    """The declared min-toolchain at a commit, or None.
       cargo: rust-version / rust-toolchain(.toml).
       maven: <maven.compiler.release> in pom.xml.
       pip: requires-python in pyproject.toml."""

def bucket_for(self, toolchain: str|None, commit_date: date, os_release: str
               ) -> BucketKey | None:
    """(toolchain, commit-era, os-era) -> a reusable bucket. The era-floor +
       MSRV-floor + max() logic and the 'reroute upward if the registry
       doesn't publish this (toolchain, os) pair' rule are GENERIC; only the
       milestone set and support matrix are per-ecosystem."""

def canonical_sde_for(self, bucket: BucketKey, *, max_sde_date: date
                      ) -> CanonicalSde:
    """Deterministic SOURCE_DATE_EPOCH for the bucket. The rule
       (Dec-31-of-bucket-year clamped to base-image publish date) is generic."""

def image_tag(self, bucket: BucketKey, sde: int) -> str:
    """Canonical tag, e.g. rp2026/pip-fat:3.11-bookworm-20240101."""
```
*Cargo today:* `fat_image.py` — `bucket_for` (line 253), `canonical_sde_for`,
`round_up_to_milestone`, `era_milestone_for_commit`, and the constants
`MILESTONES` / `MILESTONE_RELEASE_DATES` / `MILESTONE_DEBIAN_SUPPORTED`
(lines 54-99). `cargo_toolchain.py:msrv_at_commit` is `toolchain_at_commit`;
`debian_release_for` is the OS-era mapping.

**What a Maven/pip plugin must supply here:** its milestone set (Java
`{8,11,17,21}`; Python `{3.7…3.13}`), their release dates, the
`(milestone, os)` pairs its base-image registry actually publishes, and the
base image family (`maven:<v>-eclipse-temurin-<jdk>`, `python:<v>-<debian>`).
The bucketing *algorithm* is reused verbatim.

### S3 — Reproduction (build pre/post in the image)

```python
def build_command(self, *, relaxed: bool=False) -> list[str]:
    """The in-container build+test invocation.
       cargo: ['cargo','test','--locked','--message-format=json','--no-fail-fast']
       maven: ['mvn','-B','clean','verify']
       pip:   ['pytest'] after an install step
       relaxed=True is the lockfile-regenerate retry (cargo: drop --locked)."""

def vendor_command(self) -> list[str] | None:
    """Pre-fetch deps so the build can run --offline / --network none.
       cargo: 'cargo vendor'; npm: 'npm ci'; pip: 'pip download'; None if n/a."""

def manifest_root_marker(self) -> str:
    """The file that marks the buildable dir when it isn't repo-root.
       cargo: 'Cargo.toml' (the depth-≤2 discovery shim keys on this)."""
```
*Cargo today:* `cargo_reproducer.py` — `BUILD_CMD` (line ~105),
`BUILD_CMD_RELAXED`, the `cargo vendor` step, the `Cargo.toml` workdir-discovery
heuristic (lines ~290-302). The clone → checkout → run → capture-exit-code +
log loop (`_run_in_docker`) is **fully generic** and stays in the driver. The
`ReproductionResult.matches_category()` logic (pre-passes/post-fails ⇒ breaking,
etc.) is ecosystem-neutral and already shared.

### S4 — Failure classification

Two-scheme split, already designed this way (`schema/failure-taxonomy.md`):

```python
def classify_breaking(self, log: str) -> tuple[TopCategory, str|None, dict]:
    """Scheme 1: map a failing post-build log to the SHARED top-level taxonomy,
       plus an ecosystem subcategory + raw error-code counts.
       The top level (COMPILATION/TEST/DEP_RESOLUTION/ENV/OTHER) is shared;
       subcategories are the plugin's (cargo: rustc E-codes)."""

def classify_unreproducible(self, log: str, candidate: dict
                            ) -> tuple[str, str|None, str]:
    """Scheme 2: why a *pre*-build failed. Entirely ecosystem-owned
       (cargo: REPO_GONE / OPENSSL_MISMATCH / RUSTC_BITROT / …). Consumers
       doing cross-ecosystem RQ2 analysis use only the Scheme-1 top level."""
```
*Cargo today:* `cargo_classifier.py` (Scheme 1: `ERR_CODE_SUB` E-code map,
line 22) and `cargo_failure_classifier.py` (Scheme 2: the 15-category set,
line ~95). The top-level `TopFailureCategory` enum is in shared `models.py`.

### Assembly & verify (no new seam)

`cargo_assemble_entry.py` is *already* generic except the hardcoded
`ecosystem=Ecosystem.cargo` (line 253) and `f"cargo-{short}"` id (line 198) —
both become `self.ecosystem`. Fingerprint extraction from `/manifest/*` is
ecosystem-neutral. `cargo_regenerate.py` (verify) reuses S2's `image_tag` +
S3's `build_command`; nothing new.

---

## Worked example: what a `pip` plugin supplies

To make "drop-in" concrete — a `PipPlugin` would be roughly:

| Seam | Cargo | pip |
| --- | --- | --- |
| `manifest_files` | `Cargo.toml`, `Cargo.lock` | `requirements*.txt`, `pyproject.toml`, `setup.py` |
| `toolchain_at_commit` | `rust-version` | `requires-python` |
| milestone set | `1.30…1.92` | `3.7…3.13` |
| base image | `rust:<v>-<debian>` | `python:<v>-<debian>` |
| `build_command` | `cargo test --locked` | `pip install . && pytest` |
| `vendor_command` | `cargo vendor` | `pip download -d vendor` |
| `manifest_root_marker` | `Cargo.toml` | `pyproject.toml` |
| Scheme-1 subcats | rustc E-codes | Python `SyntaxError`/`ImportError`/… |
| Scheme-2 cats | `OPENSSL_MISMATCH`, `RUSTC_BITROT`, … | `WHEEL_BUILD_FAIL`, `C_EXT_TOOLCHAIN`, … |

Everything else — the driver, resume/state, SQLite mirror, schema validation,
fingerprint matching, `verifiedOn`, Grafana — is inherited unchanged. The
estimated implementation surface for a second ecosystem is the ~8 methods above
plus its milestone/support-matrix constants, *not* a parallel pipeline.

## Open design questions (honest)

1. **Manifest parsing.** Cargo (TOML) / Maven (XML) / pip (3 formats) differ a
   lot. Title-based `BUMP_RE` already covers the common Dependabot case; the
   manifest-diff parser is the fallback and is the messiest per-ecosystem bit.
2. **Lockfile semantics.** `--locked` / `--relax-locked` is a clean Cargo
   concept; Maven (BOMs) and pip (hash-pinned requirements) differ enough that
   the `relaxed` flag may need to be richer than a bool.
3. **Snapshot source.** Cargo pins the *OS* package state via
   `snapshot.debian.org`; an ecosystem whose breakage comes from the *language*
   registry (npm, PyPI) may also need a registry-time pin, which the fat-image
   model doesn't currently capture.
4. **Scope inference.** `[dependencies]` vs `[dev-dependencies]` →
   `<scope>` → npm `devDependencies`; the `Scope` enum exists but extraction is
   per-ecosystem.

These are the questions a second-ecosystem implementer would resolve; flagging
them is part of the honesty of the design, not a gap in it.

## Why we are not implementing it now

Refactoring the live `cargo_drive` to route through this Protocol is pure risk
for zero new research output: it is the code path that produced the published
1,415-entry cohort. The thesis contribution is the *reproduction methodology +
the Cargo benchmark*; the polyglot interface is the **infrastructure's
extensibility story**, and a committee's "does this generalise?" is answered by
this document + the already-shared schema/taxonomy/contract — not by a
half-built Maven pipeline. Implementing a second ecosystem is the natural
follow-on project, and `durp` (the CLI) is the place a `--ecosystem` switch
would dispatch.
```
durp --ecosystem pip reproduce --candidates pip_cohort.jsonl   # the future shape
```
