"""Cargo failure classifier — map logs to the shared taxonomy.

Parses cargo JSON diagnostics (--message-format=json) and cargo test output
to produce a (topCategory, subCategory, errorCodes) tuple.

POC scope: covers the main rustc codes listed in schema/failure-taxonomy.md.
Unknown codes fall back to OTHER_COMPILE_ERROR under COMPILATION_FAILURE.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from bump_ext import TopFailureCategory  # noqa: E402

ERR_CODE_SUB = {
    "E0277": "TRAIT_BOUND_NOT_SATISFIED",
    "E0308": "TYPE_MISMATCH",
    "E0432": "UNRESOLVED_IMPORT",
    "E0433": "UNRESOLVED_PATH",
    "E0599": "NO_METHOD_FOUND",
    "E0046": "MISSING_TRAIT_IMPL",
}

TEST_FAIL_MARKERS = (
    "test result: FAILED",
    "panicked at",
    "assertion failed",
)

RESOLUTION_MARKERS = (
    "error: failed to select a version",
    "error: no matching package named",
    "error: failed to get `",
    "could not find `Cargo.toml`",
    "error: the lock file ",
)

ENV_MARKERS = (
    "error: toolchain '",
    "error: rustup could not",
    "cannot find -l",
    "linker `cc` not found",
)


@dataclass
class Classification:
    topCategory: str
    subCategory: str | None
    errorCodes: list[str]


def classify(log_text: str) -> Classification:
    codes: list[str] = []
    for line in log_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("reason") != "compiler-message":
            continue
        msg = obj.get("message") or {}
        code = (msg.get("code") or {}).get("code")
        if code and code not in codes:
            codes.append(code)

    if codes:
        sub = ERR_CODE_SUB.get(codes[0], "OTHER_COMPILE_ERROR")
        return Classification(
            topCategory=TopFailureCategory.COMPILATION_FAILURE.value,
            subCategory=sub,
            errorCodes=codes,
        )

    low = log_text.lower()

    if any(m.lower() in low for m in RESOLUTION_MARKERS):
        return Classification(
            topCategory=TopFailureCategory.DEPENDENCY_RESOLUTION_FAILURE.value,
            subCategory=None,
            errorCodes=[],
        )

    if any(m.lower() in low for m in TEST_FAIL_MARKERS):
        return Classification(
            topCategory=TopFailureCategory.TEST_FAILURE.value,
            subCategory="OTHER_TEST_FAILURE",
            errorCodes=[],
        )

    if any(m.lower() in low for m in ENV_MARKERS):
        return Classification(
            topCategory=TopFailureCategory.ENVIRONMENT_FAILURE.value,
            subCategory=None,
            errorCodes=[],
        )

    return Classification(
        topCategory=TopFailureCategory.OTHER.value,
        subCategory=None,
        errorCodes=[],
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Classify a cargo build/test log.")
    p.add_argument("log", help="Path to log file (cargo --message-format=json output + stdout).")
    args = p.parse_args()
    text = Path(args.log).read_text(errors="replace")
    c = classify(text)
    print(json.dumps(c.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
