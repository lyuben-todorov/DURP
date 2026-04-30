# Failure Taxonomy

Two-level taxonomy shared across ecosystems. The top level is closed (all ecosystems map into it); the sub-level is open per ecosystem.

## Top-level categories

- `COMPILATION_FAILURE` — source code fails to compile after the update.
- `TEST_FAILURE` — compilation succeeds, tests fail.
- `DEPENDENCY_RESOLUTION_FAILURE` — the package manager cannot resolve or fetch the new dependency set.
- `ENVIRONMENT_FAILURE` — failure caused by the build environment (toolchain, OS, missing binaries) rather than the dependency update.
- `OTHER` — everything not captured above; must be rare.

Every ecosystem MUST map each confirmed failure to exactly one top-level category.

## Cargo subcategories (owned by Cargo RQ)

Under `COMPILATION_FAILURE`:
- `TRAIT_BOUND_NOT_SATISFIED` — rustc E0277.
- `TYPE_MISMATCH` — rustc E0308.
- `UNRESOLVED_IMPORT` — rustc E0432.
- `UNRESOLVED_PATH` — rustc E0433.
- `NO_METHOD_FOUND` — rustc E0599.
- `MISSING_TRAIT_IMPL` — rustc E0046, E0277 (when trait not implemented rather than bound unsatisfied).
- `OTHER_COMPILE_ERROR` — any other rustc error code.

Under `TEST_FAILURE`:
- `ASSERTION_FAILED`
- `PANIC`
- `TEST_TIMEOUT`
- `OTHER_TEST_FAILURE`

Under `DEPENDENCY_RESOLUTION_FAILURE`:
- `CRATE_NOT_FOUND`
- `VERSION_CONFLICT`
- `LOCK_INCOMPATIBLE`

Under `ENVIRONMENT_FAILURE`:
- `TOOLCHAIN_MISMATCH`
- `EDITION_MISMATCH`
- `MISSING_SYSTEM_DEPENDENCY`

## Adding new subcategories

Ecosystem owners may add subcategories to their ecosystem's section without a schema bump. Adding new top-level categories requires a schema bump (major version) and team consensus.
