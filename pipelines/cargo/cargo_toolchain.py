"""Detect the Rust toolchain a project expects.

Priority (highest wins):
  1. rust-toolchain.toml  -> [toolchain].channel
  2. rust-toolchain       -> raw channel string (legacy)
  3. Cargo.toml           -> [package].rust-version or [workspace.package].rust-version

Returns a Docker image tag like "rust:1.92-alpine". If nothing is found, returns
the provided default.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tomllib
from pathlib import Path

RUST_VER_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")


def _normalize_channel(channel: str) -> str | None:
    c = channel.strip().strip('"').strip("'")
    if not c:
        return None
    if c in {"stable", "beta", "nightly"}:
        return c
    m = RUST_VER_RE.match(c)
    if not m:
        return None
    major, minor = m.group(1), m.group(2)
    # Alpine images are tagged by major.minor (e.g. rust:1.92-alpine), not patch.
    return f"{major}.{minor}"


def detect_from_rust_toolchain_toml(path: Path) -> str | None:
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text())
    ch = (data.get("toolchain") or {}).get("channel")
    return _normalize_channel(ch) if ch else None


def detect_from_rust_toolchain(path: Path) -> str | None:
    if not path.is_file():
        return None
    return _normalize_channel(path.read_text())


def detect_from_cargo_toml(path: Path) -> str | None:
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text())
    ver = (
        (data.get("package") or {}).get("rust-version")
        or ((data.get("workspace") or {}).get("package") or {}).get("rust-version")
    )
    return _normalize_channel(ver) if ver else None


def detect_toolchain(repo_root: Path, default: str = "rust:1.75-alpine") -> str:
    root = Path(repo_root)
    for finder in (
        lambda: detect_from_rust_toolchain_toml(root / "rust-toolchain.toml"),
        lambda: detect_from_rust_toolchain(root / "rust-toolchain"),
        lambda: detect_from_cargo_toml(root / "Cargo.toml"),
    ):
        tc = finder()
        if tc is None:
            continue
        if tc in {"stable", "beta", "nightly"}:
            return f"rust:{tc}-alpine" if tc == "stable" else f"rustlang/rust:{tc}-alpine"
        return f"rust:{tc}-alpine"
    return default


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("repo_root")
    p.add_argument("--default", default="rust:1.75-alpine")
    a = p.parse_args()
    print(detect_toolchain(Path(a.repo_root), a.default))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
