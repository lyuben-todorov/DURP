"""Glue step — combine mining, reproduction, classification into a schema-valid Entry.

Reads a candidate, its reproduction result, and the classified failure,
and writes a schema-valid <id>.json under data/cargo/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from bump_ext import (  # noqa: E402
    Commits,
    Ecosystem,
    Entry,
    EntryWriter,
    Failure,
    PR,
    Project,
    Reproduction,
    TopFailureCategory,
    Update,
    UpdateCategory,
    VersionUpdateType,
    SCHEMA_VERSION,
    image_ref,
)

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def classify_version_bump(prev: str, new: str) -> VersionUpdateType:
    p = SEMVER_RE.match(prev)
    n = SEMVER_RE.match(new)
    if not p or not n:
        return VersionUpdateType.other
    if p.group(1) != n.group(1):
        return VersionUpdateType.major
    if p.group(2) != n.group(2):
        return VersionUpdateType.minor
    if p.group(3) != n.group(3):
        return VersionUpdateType.patch
    return VersionUpdateType.other


def build_entry(
    candidate: dict,
    reproduction: dict | None,
    classification: dict | None,
    toolchain: str,
    registry: str,
) -> Entry:
    org, name = candidate["repo"].split("/")
    short = candidate["breaking_commit"][:8]
    entry_id = f"cargo-{short}"

    reproducible = bool(reproduction and reproduction.get("reproducible"))
    if reproducible:
        category = UpdateCategory.breaking
    elif candidate.get("merged"):
        category = UpdateCategory.non_breaking
    else:
        category = UpdateCategory.unreproducible

    repro_obj = None
    if reproducible:
        repro_obj = Reproduction(
            preImage=image_ref("cargo", candidate["breaking_commit"], "pre", registry=registry),
            breakingImage=image_ref("cargo", candidate["breaking_commit"], "breaking", registry=registry),
            toolchain=toolchain,
            verifiedOn=["linux/amd64"],
        )

    fail_obj = None
    if classification:
        fail_obj = Failure(
            topCategory=TopFailureCategory(classification["topCategory"]),
            subCategory=classification.get("subCategory"),
            errorCodes=classification.get("errorCodes", []),
        )

    return Entry(
        id=entry_id,
        schemaVersion=SCHEMA_VERSION,
        ecosystem=Ecosystem.cargo,
        category=category,
        project=Project(
            url=f"https://github.com/{candidate['repo']}",
            organisation=org,
            name=name,
        ),
        pr=PR(
            url=candidate["pr_url"],
            number=candidate["pr_number"],
            author=candidate["pr_author"],
            authorType="bot" if candidate.get("bot_type") else "human",
            botType=candidate.get("bot_type"),
            merged=candidate.get("merged"),
        ),
        commits=Commits(
            preBreaking=candidate["pre_breaking_commit"],
            breaking=candidate["breaking_commit"],
        ),
        update=Update(
            dependencyName=candidate["dependency_name"],
            previousVersion=candidate["previous_version"],
            newVersion=candidate["new_version"],
            versionUpdateType=classify_version_bump(
                candidate["previous_version"], candidate["new_version"]
            ),
            scope="runtime",
        ),
        reproduction=repro_obj,
        failure=fail_obj,
        ecosystemMetadata={},
    )


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--candidate", required=True)
    p.add_argument("--reproduction", required=False)
    p.add_argument("--classification", required=False)
    p.add_argument("--toolchain", default="rust-1.75")
    p.add_argument("--registry", default="ghcr.io/tudelft-rp2026")
    p.add_argument("--out-dir", default="./data/cargo")
    args = p.parse_args()

    candidate = json.loads(Path(args.candidate).read_text())
    reproduction = (
        json.loads(Path(args.reproduction).read_text()) if args.reproduction else None
    )
    classification = (
        json.loads(Path(args.classification).read_text()) if args.classification else None
    )

    entry = build_entry(candidate, reproduction, classification, args.toolchain, args.registry)
    out = EntryWriter(args.out_dir).write(entry)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
