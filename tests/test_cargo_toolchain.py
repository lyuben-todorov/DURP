"""Tests for MSRV / toolchain parsing in cargo_toolchain.

Covers the pure byte-level parsers (no GitHub API). The
workspace-inheritance case is a regression test for the live-mine
crash on 2026-05-28: modern Cargo.toml writes `rust-version.workspace
= true`, which tomllib parses as a dict, and the old code crashed in
`_normalize_channel` calling `.strip()` on it.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipelines.cargo import cargo_toolchain as ct


class TestNormalizeChannel(unittest.TestCase):
    def test_concrete_version_to_major_minor(self):
        self.assertEqual(ct._normalize_channel("1.70.0"), "1.70")

    def test_two_part_version(self):
        self.assertEqual(ct._normalize_channel("1.65"), "1.65")

    def test_strips_quotes_and_space(self):
        self.assertEqual(ct._normalize_channel('  "1.56" '), "1.56")

    def test_channel_tags_pass_through(self):
        for tag in ("stable", "beta", "nightly"):
            self.assertEqual(ct._normalize_channel(tag), tag)

    def test_empty_is_none(self):
        self.assertIsNone(ct._normalize_channel(""))

    def test_garbage_is_none(self):
        self.assertIsNone(ct._normalize_channel("not-a-version"))

    # --- regression: non-string inputs must not crash ---
    def test_dict_input_returns_none(self):
        # `rust-version.workspace = true` parses to {"workspace": True}.
        self.assertIsNone(ct._normalize_channel({"workspace": True}))

    def test_none_input_returns_none(self):
        self.assertIsNone(ct._normalize_channel(None))

    def test_bool_input_returns_none(self):
        self.assertIsNone(ct._normalize_channel(True))


class TestChannelFromCargoToml(unittest.TestCase):
    def _b(self, s: str) -> bytes:
        return s.encode("utf-8")

    def test_simple_package_rust_version(self):
        toml = self._b('[package]\nname = "x"\nrust-version = "1.65"\n')
        self.assertEqual(ct._channel_from_cargo_toml_bytes(toml), "1.65")

    def test_workspace_inheritance_falls_through(self):
        # The regression: [package] inherits, real value in [workspace.package].
        toml = self._b(
            '[workspace.package]\nrust-version = "1.75"\n'
            '[package]\nname = "x"\nrust-version.workspace = true\n'
        )
        self.assertEqual(ct._channel_from_cargo_toml_bytes(toml), "1.75")

    def test_workspace_inheritance_without_workspace_block_is_none(self):
        # Inherits, but this file is the member (no [workspace.package]
        # here). No crash, returns None — caller falls back to era floor.
        toml = self._b(
            '[package]\nname = "x"\nrust-version.workspace = true\n'
        )
        self.assertIsNone(ct._channel_from_cargo_toml_bytes(toml))

    def test_no_rust_version_is_none(self):
        toml = self._b('[package]\nname = "x"\nversion = "0.1.0"\n')
        self.assertIsNone(ct._channel_from_cargo_toml_bytes(toml))

    def test_workspace_package_only(self):
        toml = self._b('[workspace.package]\nrust-version = "1.56"\n')
        self.assertEqual(ct._channel_from_cargo_toml_bytes(toml), "1.56")

    def test_malformed_toml_is_none(self):
        self.assertIsNone(ct._channel_from_cargo_toml_bytes(b"this is not = toml ["))


class TestChannelFromRustToolchain(unittest.TestCase):
    def test_toml_form(self):
        toml = b'[toolchain]\nchannel = "1.72.0"\n'
        self.assertEqual(ct._channel_from_rust_toolchain_toml_bytes(toml), "1.72")

    def test_toml_channel_tag(self):
        toml = b'[toolchain]\nchannel = "stable"\n'
        self.assertEqual(ct._channel_from_rust_toolchain_toml_bytes(toml), "stable")

    def test_raw_form(self):
        self.assertEqual(ct._channel_from_rust_toolchain_bytes(b"1.68.0\n"), "1.68")


class TestDebianReleaseFor(unittest.TestCase):
    def test_pre_buster_is_stretch(self):
        self.assertEqual(ct.debian_release_for(dt.date(2019, 1, 1)), "stretch")

    def test_2020_is_buster(self):
        self.assertEqual(ct.debian_release_for(dt.date(2020, 6, 1)), "buster")

    def test_2022_is_bullseye(self):
        self.assertEqual(ct.debian_release_for(dt.date(2022, 6, 1)), "bullseye")

    def test_2024_is_bookworm(self):
        self.assertEqual(ct.debian_release_for(dt.date(2024, 6, 1)), "bookworm")

    def test_far_future_is_trixie(self):
        self.assertEqual(ct.debian_release_for(dt.date(2030, 1, 1)), "trixie")

    def test_cutovers_are_monotonic(self):
        # The release returned should never go "backward" as date advances.
        order = ["stretch", "buster", "bullseye", "bookworm", "trixie"]
        last_idx = -1
        d = dt.date(2018, 1, 1)
        while d < dt.date(2027, 1, 1):
            idx = order.index(ct.debian_release_for(d))
            self.assertGreaterEqual(idx, last_idx, f"regressed at {d}")
            last_idx = idx
            d += dt.timedelta(days=30)


if __name__ == "__main__":
    unittest.main()
