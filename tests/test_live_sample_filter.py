"""Tests for the live-mine sampler's title filter.

The sampler (`scripts/cargo_live_sample.py`) drops non-Cargo bumps
before sampling by requiring the title to parse as a Dependabot-style
`Bump X from A to B` with a non-slashed dependency name. This is what
keeps GitHub Actions bumps (`actions/checkout`, `cachix/*`) — which
ride along in `language:Rust` repos — out of the recent cohort.

`scripts/` modules aren't a package, so we load the file by path.
"""

import importlib.util
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / relpath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_sample = _load("cargo_live_sample_under_test", "scripts/cargo_live_sample.py")
BUMP_RE = _sample.BUMP_RE


def _keep(title: str) -> bool:
    """Reproduce the sampler's keep predicate: parses as a bump AND the
    dep name has no slash."""
    m = BUMP_RE.search(title)
    return bool(m) and "/" not in m.group(1)


class TestBumpTitleFilter(unittest.TestCase):
    def test_keeps_cargo_crate_bump(self):
        self.assertTrue(_keep("Bump serde from 1.0.1 to 1.0.2"))

    def test_keeps_crate_with_underscores_and_dashes(self):
        self.assertTrue(_keep("Bump tokio-util from 0.7.8 to 0.7.10"))
        self.assertTrue(_keep("Bump serde_json from 1.0.108 to 1.0.110"))

    def test_drops_github_action_bump(self):
        # The slash in actions/checkout fails the dep-name char class.
        self.assertFalse(_keep("Bump actions/checkout from 3 to 4"))

    def test_drops_nix_action_bump(self):
        self.assertFalse(_keep("Bump cachix/install-nix-action from 23 to 25"))

    def test_drops_build_deps_prefixed_action(self):
        # The "build(deps):" prefix variant still carries the slash.
        self.assertFalse(_keep("build(deps): Bump actions/checkout from 3 to 4"))

    def test_drops_non_bump_title(self):
        self.assertFalse(_keep("chore: update dependencies"))
        self.assertFalse(_keep("Fix flaky test in CI"))

    def test_extracts_three_groups(self):
        m = BUMP_RE.search("Bump clap from 4.4.15 to 4.4.16")
        self.assertEqual(m.group(1), "clap")
        self.assertEqual(m.group(2), "4.4.15")
        self.assertEqual(m.group(3), "4.4.16")


if __name__ == "__main__":
    unittest.main()
