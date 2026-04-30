"""Cargo reproducer — verify a candidate as a pair of pass/fail builds.

Given a candidate JSON line from cargo_miner.py, clone the repo at both commits
and run `cargo test` inside a Docker container. Records pass/fail and
captures the cargo JSON diagnostics for later classification.

The toolchain image is either passed explicitly (--toolchain) or, by default,
auto-detected per candidate by reading the repo's rust-toolchain.toml,
rust-toolchain, or Cargo.toml `rust-version`. Detection happens after a
throwaway shallow clone inside a small helper container so we don't need
git on the host.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cargo_toolchain import detect_toolchain  # noqa: E402

DEFAULT_RUST_IMAGE = "rust:1.75-alpine"
# Script fragments must be POSIX sh compatible (Alpine ships ash, not bash).
APK_DEPS = "apk add --no-cache git musl-dev gcc pkgconfig openssl-dev"
DEB_THIN_DEPS = "apt-get update >/dev/null && apt-get install -y --no-install-recommends git pkg-config build-essential libssl-dev >/dev/null"
BUILD_CMD = "cargo test --message-format=json-diagnostic-rendered-ansi --no-fail-fast"

# A tiny image used only for `git clone` + file-read during toolchain detection.
GIT_HELPER_IMAGE = "alpine/git:latest"

# Image-tag prefixes that are pre-provisioned with git + all *-dev packages
# (see docker/cargo-fat/Dockerfile). These skip the runtime install step.
FAT_IMAGE_PREFIXES = ("rp2026/cargo-fat", "ghcr.io/tudelft-rp2026/cargo-fat")


@dataclass
class ReproductionResult:
    repo: str
    pr_number: int
    breaking_commit: str
    pre_breaking_commit: str
    pre_passed: bool
    breaking_failed: bool
    pre_exit_code: int
    breaking_exit_code: int
    pre_log_path: str
    breaking_log_path: str
    toolchain: str
    reproducible: bool
    detected_toolchain: bool = False


def _image_flavor(image: str) -> str:
    """Rough classification: alpine or debian-ish."""
    return "alpine" if "alpine" in image else "debian"


def _install_deps_cmd(image: str) -> str:
    # Fat images already have git + every -dev package baked in.
    if any(image.startswith(p) for p in FAT_IMAGE_PREFIXES):
        return "true"
    return APK_DEPS if _image_flavor(image) == "alpine" else DEB_THIN_DEPS


def _fetch_toolchain_files(repo: str, commit: str, dest: Path) -> None:
    """Fetch rust-toolchain.toml / rust-toolchain / Cargo.toml at `commit`
    into `dest` using a throwaway container. No git required on host."""
    dest.mkdir(parents=True, exist_ok=True)
    script = (
        f"cd /tmp && "
        f"git clone --quiet --depth 50 https://github.com/{repo}.git repo && "
        f"cd repo && "
        f"(git checkout --quiet {commit} 2>/dev/null || "
        f"  (git fetch --quiet origin {commit}:_repro && git checkout --quiet _repro)) && "
        f"cp -f rust-toolchain.toml /out/ 2>/dev/null ; "
        f"cp -f rust-toolchain /out/ 2>/dev/null ; "
        f"cp -f Cargo.toml /out/ 2>/dev/null ; "
        f"true"
    )
    subprocess.run(
        [
            "docker", "run", "--rm", "--entrypoint", "sh",
            "-v", f"{dest}:/out",
            GIT_HELPER_IMAGE, "-c", script,
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=180,
    )


def _run_in_docker(
    repo: str,
    commit: str,
    toolchain_image: str,
    log_out: Path,
    timeout_s: int,
) -> int:
    """Clone repo, checkout commit (including PR refs), run cargo test."""
    repo_url = f"https://github.com/{repo}.git"
    # Handles both branch-tip commits and closed-PR commits that aren't
    # reachable from the default branch: first try a plain checkout, then
    # fall back to fetching the commit explicitly.
    inner_script = (
        f"{_install_deps_cmd(toolchain_image)} && "
        f"git clone --quiet {repo_url} /src && "
        f"cd /src && "
        f"(git checkout --quiet {commit} 2>/dev/null || "
        f"  (git fetch --quiet origin {commit}:_repro && git checkout --quiet _repro)) && "
        f"{BUILD_CMD}"
    )
    cmd = [
        "docker", "run", "--rm",
        "--network", "bridge",
        toolchain_image,
        "sh", "-c", inner_script,
    ]
    with log_out.open("wb") as f:
        try:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, timeout=timeout_s)
            return r.returncode
        except subprocess.TimeoutExpired:
            return 124


def _detect_toolchain_for_candidate(candidate: dict, default: str) -> tuple[str, bool]:
    """Return (toolchain_image, detected_bool)."""
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td)
        _fetch_toolchain_files(candidate["repo"], candidate["breaking_commit"], dest)
        tc = detect_toolchain(dest, default=default)
    return tc, tc != default


def reproduce(candidate: dict, logs_dir: Path, toolchain: str | None, timeout_s: int, default_image: str) -> ReproductionResult:
    if toolchain is None:
        tc, detected = _detect_toolchain_for_candidate(candidate, default_image)
    else:
        tc, detected = toolchain, False

    pre_log = logs_dir / f"{candidate['breaking_commit'][:8]}-pre.log"
    brk_log = logs_dir / f"{candidate['breaking_commit'][:8]}-breaking.log"

    pre_rc = _run_in_docker(candidate["repo"], candidate["pre_breaking_commit"], tc, pre_log, timeout_s)
    brk_rc = _run_in_docker(candidate["repo"], candidate["breaking_commit"], tc, brk_log, timeout_s)

    pre_passed = pre_rc == 0
    breaking_failed = brk_rc != 0
    reproducible = pre_passed and breaking_failed

    return ReproductionResult(
        repo=candidate["repo"],
        pr_number=candidate["pr_number"],
        breaking_commit=candidate["breaking_commit"],
        pre_breaking_commit=candidate["pre_breaking_commit"],
        pre_passed=pre_passed,
        breaking_failed=breaking_failed,
        pre_exit_code=pre_rc,
        breaking_exit_code=brk_rc,
        pre_log_path=str(pre_log),
        breaking_log_path=str(brk_log),
        toolchain=tc,
        reproducible=reproducible,
        detected_toolchain=detected,
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Reproduce a Cargo breaking-update candidate in Docker.")
    p.add_argument("--in", dest="inp", required=True, help="Candidate JSONL (one candidate = one line).")
    p.add_argument("--logs-dir", default="./data/cargo/logs")
    p.add_argument("--out", default="-", help="Output JSONL of reproduction results.")
    p.add_argument(
        "--toolchain",
        default=None,
        help="Override the toolchain image. Default: auto-detect per candidate.",
    )
    p.add_argument(
        "--default-image",
        default=DEFAULT_RUST_IMAGE,
        help="Fallback image when detection fails.",
    )
    p.add_argument("--timeout", type=int, default=1800)
    args = p.parse_args()

    logs_dir = Path(args.logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)

    out_fh = sys.stdout if args.out == "-" else open(args.out, "w")
    try:
        with open(args.inp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                cand = json.loads(line)
                print(f"reproducing {cand['repo']}#{cand['pr_number']} ...", file=sys.stderr)
                res = reproduce(cand, logs_dir, args.toolchain, args.timeout, args.default_image)
                print(f"  toolchain: {res.toolchain} ({'detected' if res.detected_toolchain else 'override/default'})", file=sys.stderr)
                out_fh.write(json.dumps(asdict(res)) + "\n")
                out_fh.flush()
                tag = "OK" if res.reproducible else f"NO (pre_rc={res.pre_exit_code}, brk_rc={res.breaking_exit_code})"
                print(f"  -> {tag}", file=sys.stderr)
    finally:
        if out_fh is not sys.stdout:
            out_fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
