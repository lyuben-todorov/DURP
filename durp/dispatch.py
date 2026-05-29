"""In-process dispatch to the underlying pipeline/script main()s.

Every target module follows the same contract (verified): a module-level
`main() -> int` invoked via `raise SystemExit(main())`, no import-time
side effects beyond imports/constants. So durp dispatches by importing
the module, swapping `sys.argv` to what that module's argparse expects,
calling `main()`, and propagating the int return as our exit code.

This keeps a single process (fast, shared interpreter) and means a durp
subcommand is a thin argv-translation over the existing tool — no logic
is duplicated or reimplemented.
"""

from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager


@contextmanager
def _argv(argv: list[str]):
    """Temporarily replace sys.argv (argv[0] kept as the module name)."""
    saved = sys.argv
    sys.argv = argv
    try:
        yield
    finally:
        sys.argv = saved


def run_module_main(module_path: str, args: list[str]) -> int:
    """Import `module_path`, call its main() with `args` as sys.argv[1:].

    Returns the module's int exit code. A SystemExit raised inside main()
    (some argparse error paths) is caught and its code returned, so durp
    exits cleanly rather than tracebacking.
    """
    mod = importlib.import_module(module_path)
    if not hasattr(mod, "main"):
        print(f"durp: internal error — {module_path} has no main()", file=sys.stderr)
        return 2
    with _argv([module_path, *args]):
        try:
            rc = mod.main()
        except SystemExit as e:  # argparse/exit() inside the module
            code = e.code
            if code is None:
                return 0
            return code if isinstance(code, int) else 1
    return rc if isinstance(rc, int) else 0


def with_defaults(explicit: list[str], defaults: dict[str, str | None]) -> list[str]:
    """Append `--flag value` for each default NOT already present in `explicit`.

    Lets config supply a flag's value only when the user didn't pass it —
    explicit CLI flags always win. `None` default values are skipped.
    A default whose value is "" (empty) is still passed (some flags, e.g.
    --cargo-cache, treat empty as a meaningful "disable").
    """
    present = {tok for tok in explicit if tok.startswith("--")}
    out = list(explicit)
    for flag, value in defaults.items():
        if value is None:
            continue
        if flag in present:
            continue
        out += [flag, str(value)]
    return out
