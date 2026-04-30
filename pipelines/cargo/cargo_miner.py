"""Cargo miner — find candidate breaking-update PRs.

Given a GitHub repo slug (owner/name), enumerate PRs authored by Dependabot
or Renovate that touch only Cargo.toml / Cargo.lock, and emit a JSON per
candidate with the metadata needed by the reproducer.

POC scope: single repo, single-line version bumps, no scaling concerns.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import requests

GITHUB_API = "https://api.github.com"
CARGO_VERSION_LINE = re.compile(
    r'^\s*([A-Za-z0-9_\-]+)\s*=\s*"([^"]+)"\s*$'
)
CARGO_TABLE_ENTRY = re.compile(
    r'^\s*version\s*=\s*"([^"]+)"\s*$'
)


@dataclass
class Candidate:
    ecosystem: str
    repo: str  # owner/name
    pr_number: int
    pr_url: str
    pr_author: str
    bot_type: str | None
    merged: bool
    breaking_commit: str
    pre_breaking_commit: str
    dependency_name: str
    previous_version: str
    new_version: str


def _gh_headers() -> dict[str, str]:
    tok = os.environ.get("GITHUB_TOKEN")
    hdrs = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if tok:
        hdrs["Authorization"] = f"Bearer {tok}"
    return hdrs


def _get(url: str, params: dict | None = None) -> dict | list:
    r = requests.get(url, headers=_gh_headers(), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _list_pulls(repo: str, state: str = "all") -> Iterator[dict]:
    page = 1
    while True:
        pulls = _get(
            f"{GITHUB_API}/repos/{repo}/pulls",
            {"state": state, "per_page": 100, "page": page},
        )
        if not pulls:
            return
        yield from pulls
        if len(pulls) < 100:
            return
        page += 1


def _pr_files(repo: str, number: int) -> list[dict]:
    return _get(f"{GITHUB_API}/repos/{repo}/pulls/{number}/files")


def _classify_author(login: str) -> tuple[str, str | None]:
    low = (login or "").lower()
    if "dependabot" in low:
        return "bot", "dependabot"
    if "renovate" in low:
        return "bot", "renovate"
    if low.endswith("[bot]"):
        return "bot", "other"
    return "human", None


def _diff_oneline_bump(patch: str) -> tuple[str, str] | None:
    """Return (old_version, new_version) if the patch is a single-line version bump."""
    added: list[str] = []
    removed: list[str] = []
    for line in patch.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") and line[1:].strip():
            added.append(line[1:])
        elif line.startswith("-") and line[1:].strip():
            removed.append(line[1:])
    if len(added) != 1 or len(removed) != 1:
        return None
    old_m = CARGO_VERSION_LINE.match(removed[0]) or CARGO_TABLE_ENTRY.match(removed[0])
    new_m = CARGO_VERSION_LINE.match(added[0]) or CARGO_TABLE_ENTRY.match(added[0])
    if not old_m or not new_m:
        return None
    old_ver = old_m.group(old_m.lastindex)
    new_ver = new_m.group(new_m.lastindex)
    return old_ver, new_ver


def _extract_dependency_name(added_line: str) -> str | None:
    m = CARGO_VERSION_LINE.match(added_line)
    return m.group(1) if m else None


def _parent_commit(repo: str, sha: str) -> str | None:
    data = _get(f"{GITHUB_API}/repos/{repo}/commits/{sha}")
    parents = data.get("parents", [])
    if not parents:
        return None
    return parents[0]["sha"]


def mine_repo(repo: str) -> Iterator[Candidate]:
    for pr in _list_pulls(repo):
        files = _pr_files(repo, pr["number"])
        if not files:
            continue
        paths = {f["filename"] for f in files}
        touched_cargo_toml = any(p.endswith("Cargo.toml") for p in paths)
        only_cargo = all(p.endswith(("Cargo.toml", "Cargo.lock")) for p in paths)
        if not (touched_cargo_toml and only_cargo):
            continue

        cargo_toml = next(f for f in files if f["filename"].endswith("Cargo.toml"))
        patch = cargo_toml.get("patch") or ""
        bump = _diff_oneline_bump(patch)
        if not bump:
            continue
        prev, new = bump

        added = [
            line[1:]
            for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++") and line[1:].strip()
        ]
        if not added:
            continue
        dep_name = _extract_dependency_name(added[0]) or "<unknown>"

        breaking_commit = pr["head"]["sha"]
        pre = _parent_commit(repo, breaking_commit)
        if not pre:
            continue

        author = (pr.get("user") or {}).get("login", "")
        author_type, bot_type = _classify_author(author)

        yield Candidate(
            ecosystem="cargo",
            repo=repo,
            pr_number=pr["number"],
            pr_url=pr["html_url"],
            pr_author=author,
            bot_type=bot_type,
            merged=bool(pr.get("merged_at")),
            breaking_commit=breaking_commit,
            pre_breaking_commit=pre,
            dependency_name=dep_name,
            previous_version=prev,
            new_version=new,
        )


def main() -> int:
    p = argparse.ArgumentParser(description="Mine Cargo breaking-update candidates from a GitHub repo.")
    p.add_argument("repo", help="owner/name")
    p.add_argument("--out", default="-", help="Output file (JSONL). Default: stdout.")
    p.add_argument("--limit", type=int, default=0, help="Cap candidates (0 = no cap).")
    args = p.parse_args()

    out_fh = sys.stdout if args.out == "-" else open(args.out, "w")
    try:
        n = 0
        for cand in mine_repo(args.repo):
            out_fh.write(json.dumps(asdict(cand)) + "\n")
            out_fh.flush()
            n += 1
            if args.limit and n >= args.limit:
                break
        print(f"mined {n} candidate(s) from {args.repo}", file=sys.stderr)
    finally:
        if out_fh is not sys.stdout:
            out_fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
