"""durp — the Cargo dependency-update reproduction CLI.

A single entrypoint over the pipeline. Researcher-facing verbs at the top
level; power-user / internal tools nested under `fat-image` and `dev`.

    durp verify    <entry.json>       re-verify one published entry (rebuild + fingerprint)
    durp reproduce --candidates ...   drive a cohort end-to-end (the main pipeline)
    durp mine      <owner/repo>       mine dependency-update PRs from one repo
    durp plan      --candidates ...   show which fat images a cohort needs (read-only)
    durp index     [rebuild|verify]   rebuild / drift-check the SQLite index
    durp fat-image <list|resolve|build|register|unregister> ...
    durp dev       <live-search|live-sample|rebatchi|...>   ingestion + cohort tooling

Every verb is a thin argv-translation over an existing module's main();
durp injects defaults from durp.toml/.env for flags you didn't pass, and
forwards everything else through unchanged. So any flag the underlying
tool accepts still works: `durp reproduce --candidates x.jsonl --parallel 5
--relax-locked` is exactly `python -m pipelines.cargo.cargo_drive ...`.

Run `durp <verb> --help` to see the underlying tool's full flag set.
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config, Config
from .dispatch import run_module_main, with_defaults


# ---- verb → (module, default-builder) ---------------------------------------
# Each handler takes (cfg, passthrough_args) and returns an exit code.

def _cmd_reproduce(cfg: Config, rest: list[str]) -> int:
    # The end-to-end driver. Inject conventional paths + host/db/max-sde
    # only when the user didn't specify them.
    defaults = {
        "--out-dir": str(cfg.cargo_entries_dir),
        "--logs-dir": str(cfg.logs_dir),
        "--db": str(cfg.db_path),
        "--host": cfg.host,
        "--max-sde-date": cfg.max_sde_date,
    }
    args = with_defaults(rest, defaults)
    return run_module_main("pipelines.cargo.cargo_drive", args)


def _cmd_verify(cfg: Config, rest: list[str]) -> int:
    # Re-verify a single entry. The entry path is positional-ish via --entry;
    # accept a bare path as a convenience and translate it.
    args = list(rest)
    if args and not args[0].startswith("-"):
        args = ["--entry", args[0], *args[1:]]
    args = with_defaults(args, {"--host": cfg.host})
    return run_module_main("pipelines.cargo.cargo_regenerate", args)


def _cmd_mine(cfg: Config, rest: list[str]) -> int:
    # Per-repo miner. owner/repo is positional; pass straight through.
    return run_module_main("pipelines.cargo.cargo_miner", rest)


def _cmd_plan(cfg: Config, rest: list[str]) -> int:
    args = with_defaults(rest, {"--max-sde-date": cfg.max_sde_date})
    return run_module_main("pipelines.cargo.cargo_plan_fat_images", args)


def _cmd_index(cfg: Config, rest: list[str]) -> int:
    # durp index rebuild | verify
    if not rest or rest[0] not in ("rebuild", "verify"):
        print("usage: durp index <rebuild|verify> [flags]", file=sys.stderr)
        return 2
    sub, tail = rest[0], rest[1:]
    module = "scripts.rebuild_index" if sub == "rebuild" else "scripts.verify_index"
    defaults = {
        "--db": str(cfg.db_path),
        "--entries-dir": str(cfg.cargo_entries_dir),
    }
    # rebuild_index also takes --fat-index; verify_index does not.
    if sub == "rebuild":
        defaults["--fat-index"] = str(cfg.fat_index)
    return run_module_main(module, with_defaults(tail, defaults))


def _cmd_fat_image(cfg: Config, rest: list[str]) -> int:
    # fat_image.py already has its own subcommands; forward verbatim.
    if not rest:
        print("usage: durp fat-image <list|resolve|build|register|unregister> [flags]",
              file=sys.stderr)
        return 2
    return run_module_main("pipelines.cargo.fat_image", rest)


# dev tools: ingestion + cohort plumbing. name → module.
_DEV_TOOLS = {
    "live-search": "scripts.cargo_live_search",
    "live-sample": "scripts.cargo_live_sample",
    "rebatchi": "scripts.rebatchi_to_candidate",
    "rebatchi-filter": "scripts.rebatchi_ds1_filter",
    "reproducer": "pipelines.cargo.cargo_reproducer",
    "classify": "pipelines.cargo.cargo_classifier",
    "assemble": "pipelines.cargo.cargo_assemble_entry",
}


def _cmd_dev(cfg: Config, rest: list[str]) -> int:
    if not rest or rest[0] not in _DEV_TOOLS:
        print(f"usage: durp dev <{'|'.join(_DEV_TOOLS)}> [flags]", file=sys.stderr)
        return 2
    return run_module_main(_DEV_TOOLS[rest[0]], rest[1:])


_VERBS = {
    "verify": _cmd_verify,
    "reproduce": _cmd_reproduce,
    "mine": _cmd_mine,
    "plan": _cmd_plan,
    "index": _cmd_index,
    "fat-image": _cmd_fat_image,
    "dev": _cmd_dev,
}


def _print_help() -> None:
    print(__doc__.strip())


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help()
        return 0
    if argv[0] in ("--version", "-V"):
        from . import __version__
        print(f"durp {__version__}")
        return 0

    verb, rest = argv[0], argv[1:]
    handler = _VERBS.get(verb)
    if handler is None:
        print(f"durp: unknown command '{verb}'. Run `durp --help`.", file=sys.stderr)
        return 2

    cfg = load_config()
    return handler(cfg, rest)


if __name__ == "__main__":
    raise SystemExit(main())
