"""Tests for the durp CLI's pure logic: config layering + argv injection.

The dispatch itself (importing a module, calling main()) is covered by
the integration smoke in CI; here we pin the deterministic helpers that
decide *what* gets run — config resolution and the flag-injection rule
(explicit CLI flags must always beat config defaults).
"""

import os
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from durp.dispatch import with_defaults
from durp import config as durp_config


class TestWithDefaults(unittest.TestCase):
    def test_fills_missing_flag(self):
        out = with_defaults(["--candidates", "x"], {"--db": "/d.db"})
        self.assertEqual(out, ["--candidates", "x", "--db", "/d.db"])

    def test_user_flag_wins(self):
        # User passed --db; config must NOT override it.
        out = with_defaults(["--db", "/mine.db"], {"--db": "/config.db"})
        self.assertEqual(out, ["--db", "/mine.db"])

    def test_none_default_skipped(self):
        out = with_defaults(["--candidates", "x"], {"--host": None})
        self.assertEqual(out, ["--candidates", "x"])

    def test_empty_string_default_is_passed(self):
        # "" is meaningful for some flags (e.g. --cargo-cache disables).
        out = with_defaults(["--candidates", "x"], {"--cargo-cache": ""})
        self.assertEqual(out, ["--candidates", "x", "--cargo-cache", ""])

    def test_preserves_explicit_order_and_extras(self):
        out = with_defaults(
            ["--candidates", "x", "--parallel", "5"],
            {"--db": "/d.db", "--host": "h"},
        )
        # originals first, in order; injected defaults appended
        self.assertEqual(out[:4], ["--candidates", "x", "--parallel", "5"])
        self.assertIn("--db", out)
        self.assertIn("--host", out)


class TestFindRepoRoot(unittest.TestCase):
    def test_finds_root_with_pyproject(self):
        # From this test file, the root is the repo (has pyproject.toml).
        root = durp_config.find_repo_root(Path(__file__).parent)
        self.assertTrue((root / "pyproject.toml").is_file())


class TestDotenvLoader(unittest.TestCase):
    def setUp(self):
        self._saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def _write(self, body: str) -> Path:
        import tempfile
        d = Path(tempfile.mkdtemp())
        p = d / ".env"
        p.write_text(body)
        return p

    def test_loads_plain_and_export_and_quotes(self):
        os.environ.pop("DURP_TEST_A", None)
        os.environ.pop("DURP_TEST_B", None)
        os.environ.pop("DURP_TEST_C", None)
        p = self._write(
            "# a comment\n"
            "DURP_TEST_A=plain\n"
            "export DURP_TEST_B=exported\n"
            'DURP_TEST_C="quoted value"\n'
            "\n"
        )
        n = durp_config._load_dotenv(p)
        self.assertEqual(n, 3)
        self.assertEqual(os.environ["DURP_TEST_A"], "plain")
        self.assertEqual(os.environ["DURP_TEST_B"], "exported")
        self.assertEqual(os.environ["DURP_TEST_C"], "quoted value")

    def test_does_not_clobber_existing(self):
        os.environ["DURP_TEST_X"] = "already"
        p = self._write("DURP_TEST_X=fromfile\n")
        durp_config._load_dotenv(p)
        self.assertEqual(os.environ["DURP_TEST_X"], "already")

    def test_missing_file_is_zero(self):
        self.assertEqual(durp_config._load_dotenv(Path("/no/such/.env")), 0)


class TestConfigPaths(unittest.TestCase):
    def test_paths_are_absolute_under_root(self):
        cfg = durp_config.load_config(Path(__file__).parent)
        self.assertTrue(cfg.db_path.is_absolute())
        self.assertTrue(str(cfg.cargo_entries_dir).startswith(str(cfg.repo_root)))
        # default layout
        self.assertEqual(cfg.cargo_entries_dir, cfg.repo_root / "data" / "cargo")


if __name__ == "__main__":
    unittest.main()
