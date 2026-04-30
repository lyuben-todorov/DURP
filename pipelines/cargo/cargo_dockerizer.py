"""Cargo dockerizer — package a reproducible candidate as two images.

Given a candidate + reproduction result, build <hash>-pre and <hash>-breaking
images with all dependencies vendored (cargo vendor) so they run offline.

POC scope: generates a Dockerfile per commit, builds with `docker build`,
tags according to the shared naming convention.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path

# Allow running this script directly without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from bump_ext import image_ref  # noqa: E402

DOCKERFILE = textwrap.dedent("""\
    FROM rust:{rust_version}-alpine AS build
    RUN apk add --no-cache git musl-dev
    WORKDIR /src
    RUN git clone --depth 2 {repo_url} .
    RUN git checkout {commit}
    RUN cargo vendor vendor > /src/.cargo-config.toml || true
    RUN mkdir -p .cargo && printf '%s\\n' \\
        '[source.crates-io]' \\
        'replace-with = "vendored-sources"' \\
        '[source.vendored-sources]' \\
        'directory = "vendor"' > .cargo/config.toml
    CMD ["cargo", "test", "--offline", "--no-fail-fast"]
""")


def _write_dockerfile(tmp: Path, repo_url: str, commit: str, rust_version: str) -> Path:
    p = tmp / f"Dockerfile.{commit[:8]}"
    p.write_text(DOCKERFILE.format(rust_version=rust_version, repo_url=repo_url, commit=commit))
    return p


def _build(dockerfile: Path, tag: str, context: Path) -> None:
    cmd = ["docker", "build", "-f", str(dockerfile), "-t", tag, str(context)]
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"docker build failed for {tag}")


def dockerize(
    repo: str,
    pre_commit: str,
    breaking_commit: str,
    rust_version: str,
    registry: str,
    push: bool,
) -> tuple[str, str]:
    repo_url = f"https://github.com/{repo}.git"
    tmp = Path("./data/cargo/dockerfiles")
    tmp.mkdir(parents=True, exist_ok=True)

    pre_tag = image_ref("cargo", breaking_commit, "pre", registry=registry)
    brk_tag = image_ref("cargo", breaking_commit, "breaking", registry=registry)

    pre_df = _write_dockerfile(tmp, repo_url, pre_commit, rust_version)
    brk_df = _write_dockerfile(tmp, repo_url, breaking_commit, rust_version)

    _build(pre_df, pre_tag, tmp)
    _build(brk_df, brk_tag, tmp)

    if push:
        for tag in (pre_tag, brk_tag):
            subprocess.run(["docker", "push", tag], check=True)

    return pre_tag, brk_tag


def main() -> int:
    p = argparse.ArgumentParser(description="Build Docker image pair for a reproducible Cargo update.")
    p.add_argument("--candidate", required=True, help="Candidate JSON (single object).")
    p.add_argument("--rust-version", default="1.75")
    p.add_argument("--registry", default="ghcr.io/tudelft-rp2026")
    p.add_argument("--push", action="store_true")
    args = p.parse_args()

    with open(args.candidate) as f:
        cand = json.load(f)

    pre_tag, brk_tag = dockerize(
        repo=cand["repo"],
        pre_commit=cand["pre_breaking_commit"],
        breaking_commit=cand["breaking_commit"],
        rust_version=args.rust_version,
        registry=args.registry,
        push=args.push,
    )
    print(json.dumps({"preImage": pre_tag, "breakingImage": brk_tag}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
