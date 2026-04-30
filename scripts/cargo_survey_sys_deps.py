"""Survey: how much of real-world Cargo depends on native system libraries?

Samples closed-unmerged Dependabot/Renovate Cargo PRs, pulls each repo's
Cargo.lock at the breaking commit, counts `*-sys` crates, and classifies
which `-dev` OS packages would be needed.

Output: JSON summary + per-repo breakdown written to survey.json.
Intent: feasibility estimate for a "fat Debian" base image.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

GITHUB_API = "https://api.github.com"

# Known *-sys crate -> apt package(s) it roughly needs.
# Incomplete but covers the common ground for the survey.
SYS_CRATE_TO_APT = {
    "openssl-sys": ["libssl-dev", "pkg-config"],
    "libsqlite3-sys": ["libsqlite3-dev"],
    "libz-sys": ["zlib1g-dev"],
    "zstd-sys": ["libzstd-dev"],
    "bzip2-sys": ["libbz2-dev"],
    "libpcap-sys": ["libpcap-dev"],
    "pcap-sys": ["libpcap-dev"],
    "libpq-sys": ["libpq-dev"],
    "mysqlclient-sys": ["libmysqlclient-dev"],
    "curl-sys": ["libcurl4-openssl-dev"],
    "libgit2-sys": ["libgit2-dev"],  # often vendored
    "libssh2-sys": ["libssh2-1-dev"],
    "libudev-sys": ["libudev-dev"],
    "libdbus-sys": ["libdbus-1-dev"],
    "dbus-sys": ["libdbus-1-dev"],
    "alsa-sys": ["libasound2-dev"],
    "systemd-sys": ["libsystemd-dev"],
    "expat-sys": ["libexpat1-dev"],
    "cairo-sys-rs": ["libcairo2-dev"],
    "pango-sys": ["libpango1.0-dev"],
    "atk-sys": ["libatk1.0-dev"],
    "gdk-sys": ["libgtk-3-dev"],
    "gdk-pixbuf-sys": ["libgdk-pixbuf2.0-dev"],
    "gtk-sys": ["libgtk-3-dev"],
    "gio-sys": ["libglib2.0-dev"],
    "glib-sys": ["libglib2.0-dev"],
    "gobject-sys": ["libglib2.0-dev"],
    "javascriptcore-rs-sys": ["libwebkit2gtk-4.0-dev"],
    "webkit2gtk-sys": ["libwebkit2gtk-4.0-dev"],
    "soup2-sys": ["libsoup2.4-dev"],
    "soup3-sys": ["libsoup-3.0-dev"],
    "librocksdb-sys": ["librocksdb-dev", "clang", "libclang-dev"],
    "rocksdb-sys": ["librocksdb-dev", "clang", "libclang-dev"],
    "onig_sys": ["libonig-dev"],
    "libxml2-sys": ["libxml2-dev"],
    "x11-sys": ["libx11-dev"],
    "x11-dl-sys": ["libx11-dev"],
    "wayland-sys": ["libwayland-dev"],
    "libusb1-sys": ["libusb-1.0-0-dev"],
}

# These crates commonly vendor their C source so they don't need system libs
# when the right feature flag is set. We still flag them but note them.
VENDORABLE = {"openssl-sys", "libgit2-sys", "libssh2-sys", "libz-sys", "zstd-sys", "bzip2-sys"}

# Crates whose name ends in "-sys" but which do NOT require a system -dev
# package. These are pure Rust FFI type definitions, kernel syscall bindings,
# platform-framework bindings (not apt-installable), or wasm glue.
IGNORE_SYS = {
    # Windows bindings — no Linux equivalent, only fire on Windows builds.
    "windows-sys", "windows-targets", "windows-core",
    # macOS / Apple framework bindings — no apt package.
    "core-foundation-sys", "security-framework-sys", "mach-sys", "mach2",
    "system-configuration-sys", "objc-sys", "cocoa-sys",
    # Kernel / syscall bindings — no external package.
    "linux-raw-sys", "redox_syscall", "fsevent-sys", "inotify-sys",
    "kqueue-sys", "io-uring-sys",
    # Wasm / web.
    "js-sys", "web-sys", "wasm-bindgen-shared",
    # JVM / JNI.
    "jni-sys",
    # Platform dir helpers, pure Rust.
    "dirs-sys", "dirs-sys-next",
    # MSVC detection helpers, pure Rust.
    "vswhom-sys",
    # Android NDK bindings.
    "ndk-sys",
    # Assorted
    "webview2-com-sys",
}

SYS_RE = re.compile(r"^[a-zA-Z0-9_\-]+-sys(?:-rs)?$|^[a-zA-Z0-9_\-]+_sys$")


def gh_headers() -> dict:
    tok = os.environ.get("GITHUB_TOKEN")
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def gh_get(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, headers=gh_headers(), params=params or {}, timeout=30)
    if r.status_code == 403 and "rate limit" in r.text.lower():
        # Back off
        reset = int(r.headers.get("X-RateLimit-Reset", "0"))
        wait = max(1, reset - int(time.time()) + 1)
        print(f"  ... rate-limited, sleeping {wait}s", file=sys.stderr)
        time.sleep(min(wait, 60))
        r = requests.get(url, headers=gh_headers(), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def search_candidate_prs(max_results: int) -> list[dict]:
    """Closed-unmerged Dependabot/Renovate single-dep Cargo bumps."""
    out = []
    # Grab a mix of bot authors
    for q in [
        "is:pr author:app/dependabot language:rust is:closed is:unmerged bump in:title",
        "is:pr author:app/renovate language:rust is:closed is:unmerged bump in:title",
    ]:
        page = 1
        while len(out) < max_results:
            data = gh_get(
                f"{GITHUB_API}/search/issues",
                {"q": q, "per_page": 100, "page": page, "sort": "updated"},
            )
            items = data.get("items", [])
            if not items:
                break
            out.extend(items)
            page += 1
            if page > 3:  # hard cap
                break
    # Dedupe by repo
    seen = set()
    unique = []
    for it in out:
        repo_url = "/".join(it["repository_url"].split("/")[-2:])
        if repo_url in seen:
            continue
        seen.add(repo_url)
        unique.append({"repo": repo_url, "pr_url": it["html_url"], "pr_number": it["number"]})
    return unique[:max_results]


def fetch_cargo_lock_at_head(repo: str, pr_number: int) -> str | None:
    """Fetch Cargo.lock from the HEAD of the PR (breaking commit)."""
    try:
        pr = gh_get(f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}")
    except requests.HTTPError:
        return None
    sha = pr["head"]["sha"]
    # Raw content endpoint
    r = requests.get(
        f"https://raw.githubusercontent.com/{repo}/{sha}/Cargo.lock",
        timeout=30,
    )
    if r.status_code == 200:
        return r.text
    # try crates/*/Cargo.lock for workspaces — but Cargo.lock only lives at root normally
    return None


def parse_sys_crates(cargo_lock: str) -> set[str]:
    """Return the set of `*-sys` crate names appearing in a Cargo.lock."""
    sys_crates: set[str] = set()
    current_name: str | None = None
    for line in cargo_lock.splitlines():
        line = line.strip()
        if line.startswith("name ="):
            name = line.split("=", 1)[1].strip().strip('"')
            if SYS_RE.match(name) and name not in IGNORE_SYS:
                sys_crates.add(name)
    return sys_crates


def apt_packages_for(sys_crates: set[str]) -> tuple[set[str], set[str]]:
    """Return (known_apt_pkgs, unmapped_sys_crates)."""
    pkgs: set[str] = set()
    unmapped: set[str] = set()
    for c in sys_crates:
        if c in SYS_CRATE_TO_APT:
            pkgs.update(SYS_CRATE_TO_APT[c])
        else:
            unmapped.add(c)
    return pkgs, unmapped


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-repos", type=int, default=50)
    p.add_argument("--out", default="survey.json")
    args = p.parse_args()

    candidates = search_candidate_prs(args.max_repos)
    print(f"found {len(candidates)} unique-repo candidates", file=sys.stderr)

    per_repo: list[dict] = []
    sys_crate_counter: Counter[str] = Counter()
    apt_pkg_counter: Counter[str] = Counter()
    unmapped_counter: Counter[str] = Counter()
    n_none = 0
    n_pure_rust = 0

    for i, c in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {c['repo']}#{c['pr_number']}", file=sys.stderr)
        lock = fetch_cargo_lock_at_head(c["repo"], c["pr_number"])
        if lock is None:
            n_none += 1
            per_repo.append({**c, "status": "no-cargo-lock"})
            continue
        sys_crates = parse_sys_crates(lock)
        sys_crate_counter.update(sys_crates)
        pkgs, unmapped = apt_packages_for(sys_crates)
        apt_pkg_counter.update(pkgs)
        unmapped_counter.update(unmapped)
        if not sys_crates:
            n_pure_rust += 1
        per_repo.append({
            **c,
            "status": "ok",
            "sys_crates": sorted(sys_crates),
            "required_apt": sorted(pkgs),
            "unmapped_sys": sorted(unmapped),
        })

    summary = {
        "total_repos": len(candidates),
        "no_cargo_lock": n_none,
        "analyzed": len(candidates) - n_none,
        "pure_rust_no_sys_crates": n_pure_rust,
        "pure_rust_fraction": (n_pure_rust / max(1, len(candidates) - n_none)),
        "top_sys_crates": sys_crate_counter.most_common(20),
        "top_apt_packages": apt_pkg_counter.most_common(20),
        "unmapped_sys_crates": unmapped_counter.most_common(20),
    }

    out = {"summary": summary, "per_repo": per_repo}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
