# Shared Schema — explainer

Authoritative file: [`schema/entry.schema.json`](../../schema/entry.schema.json).
Failure taxonomy: [`schema/failure-taxonomy.md`](../../schema/failure-taxonomy.md).

One JSON file = one reproducible dependency-update entry. Every ecosystem
(Cargo, Maven, pip, npm) produces entries in this format. RQ1 and RQ2 consume
the union.

## Purpose

Make five parallel sub-projects combinable. The schema is the *only* contract
between ecosystems — pipelines can be written in any language as long as their
output validates.

## Top-level shape

Eight required fields, everything else optional (because not every entry
makes it all the way through the pipeline):

```
id                    — "<ecosystem>-<shortHash>", globally unique
schemaVersion         — semver, per the library's SCHEMA_VERSION constant
ecosystem             — cargo | maven | pip | npm (closed enum)
category              — breaking | non-breaking | fix-after-update | unreproducible
project               — { url, organisation, name }
pr                    — { url, number, author, authorType, botType, merged, mergedAt }
commits               — { preBreaking, breaking, + author types }
update                — { dependencyName, previousVersion, newVersion,
                          versionUpdateType, scope }
reproduction          — { preImage, breakingImage, toolchain, verifiedOn } (optional)
failure               — { topCategory, subCategory, errorCodes } (optional)
ecosystemMetadata     — open object, per-ecosystem extras
unreproducibilityReason — enum (only when category == unreproducible)
```

## Design decisions

### 1. Flat-ish with nested groupings (not BUMP's flat style)

BUMP flattens everything into top-level keys
(`dependencyGroupID`, `dependencyArtifactID`, `previousVersion`, etc.). This
works for Maven but leaks Maven terminology into cross-ecosystem consumers.

We group by concern (`project`, `pr`, `commits`, `update`, `reproduction`,
`failure`) so:

- each group can be optional as a whole (e.g. `reproduction = null`)
- consumers can destructure cleanly (`entry.update.dependencyName`)
- `jq` queries are still trivial (`.update.previousVersion`)

### 2. Closed top-level enums, open subcategories

`ecosystem`, `category`, `authorType`, `botType`, `versionUpdateType`,
`scope`, `failure.topCategory`: **closed enums**. Adding a value requires
a schema bump. This is deliberate — it protects cross-ecosystem consumers
from silent drift.

`failure.subCategory`: **open string**. Each ecosystem documents its own
enum in `schema/failure-taxonomy.md`. Cross-ecosystem consumers look only
at `topCategory`; ecosystem-specific analyses look at `subCategory`.

### 3. `unreproducible` is a first-class category

BUMP discards unreproducible candidates silently. We keep them, because:
- RQ1 analyses drop-out rates.
- RQ2 analyses which update types get "fixed after update" — we need a
  denominator that includes failures.
- If someone re-runs the pipeline on a stronger machine or with more system
  deps, an unreproducible entry can be promoted to breaking.

### 4. `ecosystemMetadata` escape hatch

Per-ecosystem free-form object. Cargo uses it for `edition`,
`cargoLockChanged`, `transitivesChanged`, etc. Keeps the core schema clean.
Cross-ecosystem consumers can ignore it; ecosystem papers can use it freely.

### 5. Docker image references live inside `reproduction`

The canonical ref is produced by `bump_ext.image_ref()` from `(ecosystem,
breakingCommit, kind)`. Everyone uses the same helper → everyone produces
the same string. If we ever change the registry or naming, one function
gets updated.

### 6. `id` is derived, not random

Format: `<ecosystem>-<first-8-chars-of-breaking-commit>`. Pros:
- Deterministic — same input, same ID, idempotent pipelines.
- Debuggable — you can tell at a glance what ecosystem an entry belongs to.
- Collision-resistant enough for the benchmark scale (hundreds to low
  thousands of entries).

### 7. Schema versioning

Semver on `schemaVersion`:
- **patch** — doc-only changes.
- **minor** — additive (new optional fields, new enum values that don't
  break existing entries).
- **major** — breaking (renamed/removed fields, tightened constraints).

Migration scripts for major bumps live under `migrations/<from>-to-<to>.py`.
Old entries are valid until a migration is run.

## How to validate

From Python:

```python
import json
from bump_ext import validate_entry, SchemaError

try:
    validate_entry(json.load(open("data/cargo/cargo-9ac20c07.json")))
except SchemaError as e:
    print(e)
```

From any language: use a JSON Schema 2020-12 validator against
`schema/entry.schema.json`.

From the command line:

```bash
jq . data/cargo/*.json >/dev/null   # syntax check only
```

(A `python -m bump_ext.validate` CLI is planned but not yet implemented.)

## What NOT to put in the schema

- Anything derivable from the commit hashes (file sizes, commit timestamps)
  — consumers can compute it themselves from the Docker image or the repo.
- Analysis outputs (per-RQ statistics, aggregations). Those live alongside
  the paper, not in the entry.
- Ecosystem-specific fields that need top-level status in every entry —
  put them in `ecosystemMetadata` instead.
