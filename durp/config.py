"""Configuration for the durp CLI.

Layered config, last wins:
  1. built-in defaults (the repo's conventional layout)
  2. durp.toml at the repo root (if present)
  3. .env at the repo root (auto-loaded into os.environ; GITHUB_TOKEN etc.)
  4. explicit CLI flags (handled by the dispatcher, not here)

The whole point is to kill the `set -a; . .env` papercut and the
scattered `data/...` argparse defaults: a fresh checkout gets sensible
paths, and a user can point durp at a different data dir / db / host in
one durp.toml instead of remembering per-command flags.

No third-party deps — tomllib is stdlib on 3.11+, and we parse .env with
a tiny hand-rolled reader rather than pulling in python-dotenv.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Walk up from `start` (or cwd) to the directory containing pyproject.toml.

    Falls back to cwd if no marker is found, so durp still runs (with
    built-in path defaults) from an unusual working directory.
    """
    cur = (start or Path.cwd()).resolve()
    for d in (cur, *cur.parents):
        if (d / "pyproject.toml").is_file():
            return d
    return cur


def _load_dotenv(path: Path) -> int:
    """Load KEY=VALUE lines from `path` into os.environ (without clobbering
    already-set vars). Returns the count of keys loaded. Tolerant of
    `export KEY=val`, quotes, blank lines, and # comments.
    """
    if not path.is_file():
        return 0
    loaded = 0
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val
            loaded += 1
    return loaded


@dataclass
class Config:
    """Resolved durp configuration. Paths are absolute (rooted at repo_root)."""

    repo_root: Path
    data_dir: Path                 # data/
    cargo_entries_dir: Path        # data/cargo/  (the submodule, Layer 1)
    logs_dir: Path                 # data/cargo-logs/
    rebatchi_dir: Path             # data/rebatchi/
    live_mine_dir: Path            # data/live-mine/
    db_path: Path                  # data/pipeline.sqlite
    fat_index: Path                # docker/cargo-fat/index.json
    host: str | None               # default --host label
    max_sde_date: str | None       # default --max-sde-date (YYYY-MM-DD)
    raw: dict = field(default_factory=dict)  # the parsed durp.toml, for extras

    def has_github_token(self) -> bool:
        return bool(os.environ.get("GITHUB_TOKEN"))


def _abs(root: Path, value: str) -> Path:
    """Resolve a config path: absolute stays, relative is rooted at repo_root."""
    p = Path(value)
    return p if p.is_absolute() else (root / p)


def load_config(start: Path | None = None) -> Config:
    """Resolve config from repo root + durp.toml + .env.

    durp.toml shape (all keys optional):

        host = "crack"
        max_sde_date = "2023-12-31"

        [paths]
        data_dir = "data"
        cargo_entries_dir = "data/cargo"
        logs_dir = "data/cargo-logs"
        rebatchi_dir = "data/rebatchi"
        live_mine_dir = "data/live-mine"
        db = "data/pipeline.sqlite"
        fat_index = "docker/cargo-fat/index.json"
    """
    root = find_repo_root(start)

    # .env first so GITHUB_TOKEN is available to every downstream module.
    _load_dotenv(root / ".env")

    toml: dict = {}
    toml_path = root / "durp.toml"
    if toml_path.is_file():
        with toml_path.open("rb") as f:
            toml = tomllib.load(f)

    paths = toml.get("paths", {})

    def p(key: str, default: str) -> Path:
        return _abs(root, paths.get(key, default))

    return Config(
        repo_root=root,
        data_dir=p("data_dir", "data"),
        cargo_entries_dir=p("cargo_entries_dir", "data/cargo"),
        logs_dir=p("logs_dir", "data/cargo-logs"),
        rebatchi_dir=p("rebatchi_dir", "data/rebatchi"),
        live_mine_dir=p("live_mine_dir", "data/live-mine"),
        db_path=p("db", "data/pipeline.sqlite"),
        fat_index=p("fat_index", "docker/cargo-fat/index.json"),
        host=toml.get("host"),
        max_sde_date=toml.get("max_sde_date"),
        raw=toml,
    )
