# `bump_ext` — shared Python library

A thin library that makes the shared schema ergonomic from Python. Three
source files under `lib/bump_ext/`. Optional for pipelines not written in
Python — those can validate against `schema/entry.schema.json` directly in
their own language.

## Why it exists

Without a shared library, every ecosystem pipeline re-implements:
- Schema validation.
- Docker image naming.
- JSON output shape (field ordering, null handling, enum serialisation).

Drift is inevitable. The library enforces one source of truth for all three.

## What's in it

### `models.py` — Pydantic v2 models

Every nesting level of the schema has a corresponding Python class:
`Project`, `PR`, `Commits`, `Update`, `Reproduction`, `Failure`, `Entry`.
Enums are mirrored as Python enums: `Ecosystem`, `UpdateCategory`,
`AuthorType`, `BotType`, `VersionUpdateType`, `Scope`, `TopFailureCategory`,
`UnreproducibilityReason`.

Pydantic enforces at construction time:
- Enum membership — `Ecosystem("xcode")` raises.
- Numeric ranges — `PR(number=0)` raises (minimum 1).
- Regex patterns — `Entry(id="nope")` raises (must match
  `^(cargo|maven|pip|npm)-[a-f0-9]{7,40}$`).
- Extra fields — typos like `reproductions` instead of `reproduction` raise
  (`extra="forbid"`).

`use_enum_values=True` on `Entry` ensures that when you dump to JSON, enums
serialise as their string values, not as Python repr.

### `validate.py` — JSON Schema validator

Two responsibilities:
1. Load `schema/entry.schema.json` once (cached at module level).
2. Expose `validate_entry(dict)` which raises `SchemaError` with readable
   messages when the dict does not match.

### Why validate twice (Pydantic + JSON Schema)?

They validate different things:
- **Pydantic** validates Python objects at the *construction* boundary.
- **JSON Schema** validates JSON at the *serialisation* boundary.

They can disagree. If `models.py` drifts from `entry.schema.json`, pydantic
will happily build an `Entry` that fails schema validation. Running both at
the write boundary (Python object → `model_dump()` → `validate_entry()` →
disk) catches drift at the point where it matters.

Cost is negligible — schema validation on a single entry is microseconds.

### `writer.py` — entry writer + image naming

`image_ref(ecosystem, breaking_commit, kind, registry=...)` — canonical
Docker image reference. Every pipeline calls this instead of constructing
strings by hand. If the registry or format ever changes, we update one
function.

`EntryWriter(output_dir)` — pipeline handoff. Under the hood:
`entry.model_dump()` → `validate_entry()` → `json.dump()`. An invalid entry
never touches disk.

### `__init__.py` — public API

Re-exports everything consumers need. Constants like `SCHEMA_VERSION`
ensure everyone stamps the same version on their entries.

## How the library reduces coordination

The same questions keep coming up across pipelines. The library answers
them once:

| Question | Library answer |
| --- | --- |
| What do I call my Docker images? | `image_ref()` |
| What schema version do I stamp? | `SCHEMA_VERSION` |
| Is this field required or optional? | Pydantic model tells you |
| Is my JSON valid? | `EntryWriter.write()` validates on write |
| What are the valid enum values? | Python enum classes |

A new ecosystem owner writes their pipeline against `Entry`/`Project`/etc.,
never hand-crafts JSON. Tests pass locally, output is guaranteed to validate
against the shared schema.

## Usage from Python pipelines

```python
from bump_ext import (
    Entry, EntryWriter, Ecosystem, UpdateCategory,
    Project, PR, Commits, Update, Reproduction, Failure,
    TopFailureCategory, SCHEMA_VERSION, image_ref,
)

entry = Entry(
    id=f"cargo-{breaking[:8]}",
    schemaVersion=SCHEMA_VERSION,
    ecosystem=Ecosystem.cargo,
    category=UpdateCategory.breaking,
    project=Project(url="...", organisation="foo", name="bar"),
    pr=PR(url="...", number=42, author="dependabot[bot]",
          authorType="bot", botType="dependabot"),
    commits=Commits(preBreaking=pre, breaking=breaking),
    update=Update(
        dependencyName="serde",
        previousVersion="1.0.150", newVersion="1.0.160",
        versionUpdateType="minor", scope="runtime",
    ),
    reproduction=Reproduction(
        preImage=image_ref("cargo", breaking, "pre"),
        breakingImage=image_ref("cargo", breaking, "breaking"),
        toolchain="rust-1.75",
        verifiedOn=["linux/amd64"],
    ),
    failure=Failure(
        topCategory=TopFailureCategory.COMPILATION_FAILURE,
        subCategory="TRAIT_BOUND_NOT_SATISFIED",
        errorCodes=["E0277"],
    ),
)
EntryWriter("./data/cargo").write(entry)
```

## Usage from non-Python pipelines

The schema is language-agnostic. Java/JS/Rust pipelines can:

1. Read `schema/entry.schema.json`.
2. Build their JSON using whatever they want.
3. Validate against the schema with any JSON Schema 2020-12 validator
   (`ajv` for JS, `everit-json-schema` for Java, `jsonschema` crate for
   Rust).
4. Call `image_ref()`'s rules themselves — the convention is one line of
   string formatting.

The library is a convenience, not a requirement. The schema is the contract.

## What goes in (and what doesn't)

**In:**
- Types mirroring the schema.
- Helpers that enforce conventions (image naming, ID format).
- Validation.

**Out:**
- Ecosystem-specific logic (that lives in `pipelines/<eco>/`).
- Mining/reproduction/classification code (ditto).
- Analysis or aggregation (that lives with RQ1/RQ2).

Keep the library small. The whole point is that a new ecosystem owner can
read it in one sitting.

## Versioning

`SCHEMA_VERSION` in `__init__.py` tracks the schema's semver.
`pyproject.toml` tracks the library's package version (usually the same).
Breaking API changes in the library bump the library's major version;
breaking schema changes bump both.
