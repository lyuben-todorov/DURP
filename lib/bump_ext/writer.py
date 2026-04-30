"""Entry writer and image-naming helpers.

Writes schema-valid JSON to disk and produces the canonical Docker image
references that every ecosystem pipeline must use.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Ecosystem, Entry
from .validate import validate_entry

DEFAULT_REGISTRY = "ghcr.io/tudelft-rp2026"


def image_ref(
    ecosystem: Ecosystem | str,
    breaking_commit: str,
    kind: str,
    registry: str = DEFAULT_REGISTRY,
) -> str:
    """Canonical image reference.

    Convention: <registry>/breaking-updates-<ecosystem>:<short-hash>-<kind>
    where kind is "pre" or "breaking".
    """
    if kind not in {"pre", "breaking"}:
        raise ValueError(f"kind must be 'pre' or 'breaking', got {kind!r}")
    eco = ecosystem.value if isinstance(ecosystem, Ecosystem) else ecosystem
    short = breaking_commit[:8]
    return f"{registry}/breaking-updates-{eco}:{short}-{kind}"


class EntryWriter:
    """Writes validated entries as <id>.json in the configured output dir."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, entry: Entry) -> Path:
        data = entry.model_dump(mode="json", exclude_none=False)
        validate_entry(data)
        out = self.output_dir / f"{entry.id}.json"
        with out.open("w") as f:
            json.dump(data, f, indent=2, sort_keys=False)
            f.write("\n")
        return out
