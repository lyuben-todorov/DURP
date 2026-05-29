"""Tests for the fat-image bucketing / toolchain-selection logic.

This is the load-bearing logic of the whole project: it decides which
rustc + Debian a candidate is reproduced under. If `bucket_for` is
wrong, every reproducibility number is suspect. These tests pin the
era-floor + MSRV-floor + Docker-Hub-reroute behaviour against concrete,
hand-checked cases.

Pure functions only — no Docker, no network.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

# Make the repo root + lib/ importable whether run via pytest or
# `python -m unittest discover tests`.
_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pipelines.cargo import fat_image as fi


class TestParseSemver(unittest.TestCase):
    def test_three_part(self):
        self.assertEqual(fi.parse_semver("1.56.0"), (1, 56, 0))

    def test_two_part_defaults_patch_zero(self):
        self.assertEqual(fi.parse_semver("1.56"), (1, 56, 0))

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            fi.parse_semver("stable")


class TestRoundUpToMilestone(unittest.TestCase):
    def test_exact_milestone_returns_itself(self):
        self.assertEqual(fi.round_up_to_milestone("1.56"), "1.56")

    def test_rounds_up_to_next_shipped(self):
        # 1.50 isn't shipped; next is 1.56.
        self.assertEqual(fi.round_up_to_milestone("1.50"), "1.56")

    def test_below_smallest_rounds_to_smallest(self):
        self.assertEqual(fi.round_up_to_milestone("1.20"), "1.30")

    def test_above_largest_returns_none(self):
        self.assertIsNone(fi.round_up_to_milestone("1.99"))

    def test_unparseable_returns_none(self):
        self.assertIsNone(fi.round_up_to_milestone("nightly"))


class TestEraMilestoneForCommit(unittest.TestCase):
    def test_rounds_up_to_next_shipped_milestone(self):
        # rustc 1.45 current on 2020-08-25; we don't ship 1.45, so the era
        # floor rounds UP to 1.49 (next shipped), never down to 1.39.
        # This is the documented anti-bitrot behaviour.
        self.assertEqual(
            fi.era_milestone_for_commit(dt.date(2020, 8, 25)), "1.49"
        )

    def test_commit_exactly_on_release_date_picks_that_milestone(self):
        # 1.56 released 2021-10-21; a commit that day picks 1.56 (>= holds).
        self.assertEqual(
            fi.era_milestone_for_commit(dt.date(2021, 10, 21)), "1.56"
        )

    def test_very_old_commit_picks_smallest(self):
        self.assertEqual(
            fi.era_milestone_for_commit(dt.date(2018, 1, 1)), "1.30"
        )

    def test_future_commit_picks_largest(self):
        # No upward bump available past the last milestone.
        self.assertEqual(
            fi.era_milestone_for_commit(dt.date(2030, 1, 1)),
            fi.MILESTONES[-1],
        )


class TestLatestMilestoneBefore(unittest.TestCase):
    def test_walks_back_to_current_at_commit(self):
        # 2020-08-25: latest milestone *released by then* is 1.49? No —
        # 1.49 released 2020-12-31, so the latest <= is 1.39 (2019-11-07).
        self.assertEqual(
            fi.latest_milestone_before(dt.date(2020, 8, 25)), "1.39"
        )

    def test_before_first_release_returns_smallest(self):
        self.assertEqual(
            fi.latest_milestone_before(dt.date(2017, 1, 1)), "1.30"
        )

    def test_era_floor_is_never_below_strict_era(self):
        # The era-floor (rounds up) should always be >= the strict
        # "what was current" answer (rounds down), for any date.
        for d in (dt.date(2018, 6, 1), dt.date(2020, 8, 25),
                  dt.date(2021, 3, 9), dt.date(2023, 1, 1)):
            up = fi.parse_semver(fi.era_milestone_for_commit(d))
            down = fi.parse_semver(fi.latest_milestone_before(d))
            self.assertGreaterEqual(up, down, f"era<strict at {d}")


class TestBucketFor(unittest.TestCase):
    def test_msrv_none_uses_era_floor(self):
        # No declared MSRV → milestone is the era floor for the commit.
        bk = fi.bucket_for(None, dt.date(2020, 8, 25), "buster")
        self.assertIsNotNone(bk)
        self.assertEqual(bk.milestone, "1.49")
        self.assertEqual(bk.year, 2020)
        self.assertEqual(bk.debian, "buster")

    def test_takes_max_of_msrv_floor_and_era(self):
        # MSRV 1.65 (floor 1.65) on a 2020 commit (era 1.49): max => 1.65.
        # The MSRV is the binding constraint here.
        bk = fi.bucket_for("1.65", dt.date(2020, 8, 25), "buster")
        self.assertIsNotNone(bk)
        self.assertEqual(bk.milestone, "1.65")

    def test_low_msrv_does_not_regress_below_era(self):
        # The documented regression guard: MSRV=1.31 in 2020 must NOT
        # route to 1.35 — the era floor (1.49) wins via max().
        bk = fi.bucket_for("1.31", dt.date(2020, 8, 25), "buster")
        self.assertIsNotNone(bk)
        self.assertEqual(bk.milestone, "1.49")

    def test_reroutes_upward_when_pair_unpublished(self):
        # (1.49, bullseye) is NOT a published rust base (see
        # MILESTONE_DEBIAN_SUPPORTED). bullseye's smallest supported is
        # 1.56, so an era-1.49 candidate on bullseye reroutes up to 1.56.
        self.assertNotIn(("1.49", "bullseye"), fi.MILESTONE_DEBIAN_SUPPORTED)
        bk = fi.bucket_for(None, dt.date(2020, 8, 25), "bullseye")
        self.assertIsNotNone(bk)
        self.assertEqual(bk.milestone, "1.56")
        self.assertEqual(bk.debian, "bullseye")

    def test_unparseable_msrv_falls_back_to_era(self):
        bk = fi.bucket_for("nightly", dt.date(2020, 8, 25), "buster")
        self.assertIsNotNone(bk)
        self.assertEqual(bk.milestone, "1.49")

    def test_bucket_milestone_always_supported_on_its_debian(self):
        # Whatever bucket_for returns, the (milestone, debian) must be a
        # pair Docker Hub actually publishes — otherwise the build fails.
        for debian in ("stretch", "buster", "bullseye", "bookworm", "trixie"):
            for year in range(2018, 2026):
                bk = fi.bucket_for(None, dt.date(year, 6, 1), debian)
                if bk is None:
                    continue
                self.assertIn(
                    (bk.milestone, bk.debian),
                    fi.MILESTONE_DEBIAN_SUPPORTED,
                    f"bucket_for(None, {year}-06-01, {debian}) -> "
                    f"unpublished ({bk.milestone}, {bk.debian})",
                )


class TestMilestoneInvariants(unittest.TestCase):
    def test_milestones_sorted_ascending(self):
        tuples = [fi.parse_semver(m) for m in fi.MILESTONES]
        self.assertEqual(tuples, sorted(tuples))

    def test_every_milestone_has_a_release_date(self):
        for m in fi.MILESTONES:
            self.assertIn(m, fi.MILESTONE_RELEASE_DATES)

    def test_release_dates_monotonic_with_version(self):
        # Newer milestone => later (or equal) release date.
        prev_date = None
        for m in fi.MILESTONES:
            d = fi.MILESTONE_RELEASE_DATES[m]
            if prev_date is not None:
                self.assertGreaterEqual(d, prev_date, f"{m} out of order")
            prev_date = d


if __name__ == "__main__":
    unittest.main()
