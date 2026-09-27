# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Unit tests for Phase 3B CHIRPS rainfall window aggregation engine (DEC-020)."""

from datetime import date, timedelta
import random

import pytest

from app.environment.chirps_aggregation import (
    aggregate_rainfall_window_statistics,
    compute_rainfall_window_suite,
)
from app.environment.chirps_types import (
    DailyRainfallObservation,
    RainfallWindowStatistics,
)


class TestAggregateRainfallWindowStatistics:
    """Comprehensive tests for aggregate_rainfall_window_statistics."""

    def test_exact_7_day_complete_window(self) -> None:
        """Verifies exact 7-day aggregation math with complete daily observations."""
        anchor = date(2026, 9, 25)
        # 7 days: 2026-09-19 through 2026-09-25
        # Values: [0.0, 5.0, 10.0, 15.0, 20.0, 0.0, 2.0]
        precip_vals = [0.0, 5.0, 10.0, 15.0, 20.0, 0.0, 2.0]
        obs = [
            DailyRainfallObservation(
                observation_date=anchor - timedelta(days=6 - i),
                precipitation_mm=precip_vals[i],
            )
            for i in range(7)
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=anchor,
            window_days=7,
        )

        assert stats.window_name == "recent_7_days"
        assert stats.window_start == date(2026, 9, 19)
        assert stats.window_end == anchor
        assert stats.days_requested == 7
        assert stats.days_available == 7
        assert stats.is_complete is True
        assert stats.total_precipitation_mm == pytest.approx(52.0)
        assert stats.mean_daily_precipitation_mm == pytest.approx(52.0 / 7.0)
        assert stats.max_daily_precipitation_mm == pytest.approx(20.0)

    def test_exact_30_day_complete_window(self) -> None:
        """Verifies exact 30-day aggregation math with complete daily observations."""
        anchor = date(2026, 9, 25)
        start = anchor - timedelta(days=29)  # 2026-08-27
        obs = [
            DailyRainfallObservation(
                observation_date=start + timedelta(days=i),
                precipitation_mm=2.5,
            )
            for i in range(30)
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_30_days",
            window_end=anchor,
            window_days=30,
        )

        assert stats.window_name == "recent_30_days"
        assert stats.window_start == date(2026, 8, 27)
        assert stats.window_end == anchor
        assert stats.days_requested == 30
        assert stats.days_available == 30
        assert stats.is_complete is True
        assert stats.total_precipitation_mm == pytest.approx(75.0)
        assert stats.mean_daily_precipitation_mm == pytest.approx(2.5)
        assert stats.max_daily_precipitation_mm == pytest.approx(2.5)

    def test_exact_90_day_complete_window(self) -> None:
        """Verifies exact 90-day aggregation math with complete daily observations."""
        anchor = date(2026, 9, 25)
        start = anchor - timedelta(days=89)  # 2026-06-28
        obs = [
            DailyRainfallObservation(
                observation_date=start + timedelta(days=i),
                precipitation_mm=float(i % 10),
            )
            for i in range(90)
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_90_days",
            window_end=anchor,
            window_days=90,
        )

        assert stats.window_name == "recent_90_days"
        assert stats.window_start == date(2026, 6, 28)
        assert stats.window_end == anchor
        assert stats.days_requested == 90
        assert stats.days_available == 90
        assert stats.is_complete is True
        expected_total = sum(float(i % 10) for i in range(90))
        assert stats.total_precipitation_mm == pytest.approx(expected_total)
        assert stats.mean_daily_precipitation_mm == pytest.approx(expected_total / 90.0)
        assert stats.max_daily_precipitation_mm == pytest.approx(9.0)

    def test_partial_window_semantics(self) -> None:
        """Verifies partial window: metrics calculated strictly over available non-null days."""
        anchor = date(2026, 9, 25)
        # Only 3 days available in a 7-day window: 2026-09-20, 2026-09-22, 2026-09-25
        obs = [
            DailyRainfallObservation(observation_date=date(2026, 9, 20), precipitation_mm=10.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 22), precipitation_mm=20.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 25), precipitation_mm=30.0),
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=anchor,
            window_days=7,
        )

        assert stats.days_requested == 7
        assert stats.days_available == 3
        assert stats.is_complete is False
        assert stats.total_precipitation_mm == pytest.approx(60.0)
        assert stats.mean_daily_precipitation_mm == pytest.approx(20.0)  # 60.0 / 3, NOT 60.0 / 7
        assert stats.max_daily_precipitation_mm == pytest.approx(30.0)

    def test_empty_window_semantics(self) -> None:
        """Verifies empty window: days_available=0, is_complete=False, all metrics=None."""
        anchor = date(2026, 9, 25)
        obs: list[DailyRainfallObservation] = []

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=anchor,
            window_days=7,
        )

        assert stats.days_requested == 7
        assert stats.days_available == 0
        assert stats.is_complete is False
        assert stats.total_precipitation_mm is None
        assert stats.mean_daily_precipitation_mm is None
        assert stats.max_daily_precipitation_mm is None

    def test_zero_vs_missing_precipitation(self) -> None:
        """Verifies that explicit 0.0 is included in calculation while None is excluded."""
        anchor = date(2026, 9, 25)
        obs = [
            DailyRainfallObservation(observation_date=date(2026, 9, 23), precipitation_mm=10.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 24), precipitation_mm=0.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 25), precipitation_mm=None),
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=anchor,
            window_days=7,
        )

        assert stats.days_available == 3
        assert stats.is_complete is False
        # Non-null values are [10.0, 0.0] -> count = 2
        assert stats.total_precipitation_mm == pytest.approx(10.0)
        assert stats.mean_daily_precipitation_mm == pytest.approx(5.0)  # 10.0 / 2
        assert stats.max_daily_precipitation_mm == pytest.approx(10.0)

    def test_all_missing_precipitation(self) -> None:
        """Verifies that a window with only None values returns None metrics."""
        anchor = date(2026, 9, 25)
        obs = [
            DailyRainfallObservation(observation_date=date(2026, 9, 24), precipitation_mm=None),
            DailyRainfallObservation(observation_date=date(2026, 9, 25), precipitation_mm=None),
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=anchor,
            window_days=7,
        )

        assert stats.days_available == 2
        assert stats.is_complete is False
        assert stats.total_precipitation_mm is None
        assert stats.mean_daily_precipitation_mm is None
        assert stats.max_daily_precipitation_mm is None

    def test_duplicate_dates_raises_value_error(self) -> None:
        """Verifies duplicate observation dates cause a ValueError."""
        anchor = date(2026, 9, 25)
        obs = [
            DailyRainfallObservation(observation_date=date(2026, 9, 24), precipitation_mm=5.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 24), precipitation_mm=10.0),
        ]

        with pytest.raises(ValueError, match="Duplicate observation date detected"):
            aggregate_rainfall_window_statistics(
                observations=obs,
                window_name="recent_7_days",
                window_end=anchor,
                window_days=7,
            )

    def test_order_invariance(self) -> None:
        """Verifies that shuffling input sequence does not alter calculated results."""
        anchor = date(2026, 9, 25)
        start = anchor - timedelta(days=29)
        obs = [
            DailyRainfallObservation(
                observation_date=start + timedelta(days=i),
                precipitation_mm=float(i * 1.5),
            )
            for i in range(30)
        ]

        stats_ordered = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_30_days",
            window_end=anchor,
            window_days=30,
        )

        # Shuffle observations
        shuffled_obs = list(obs)
        random.seed(42)
        random.shuffle(shuffled_obs)

        stats_shuffled = aggregate_rainfall_window_statistics(
            observations=shuffled_obs,
            window_name="recent_30_days",
            window_end=anchor,
            window_days=30,
        )

        assert stats_ordered == stats_shuffled

    def test_out_of_window_observations_filtered_out(self) -> None:
        """Verifies observations outside [window_start, window_end] are ignored."""
        anchor = date(2026, 9, 25)
        obs = [
            # Before window (< 2026-09-19)
            DailyRainfallObservation(observation_date=date(2026, 9, 10), precipitation_mm=100.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 18), precipitation_mm=50.0),
            # In window
            DailyRainfallObservation(observation_date=date(2026, 9, 19), precipitation_mm=10.0),
            DailyRainfallObservation(observation_date=date(2026, 9, 25), precipitation_mm=15.0),
            # After window (> 2026-09-25)
            DailyRainfallObservation(observation_date=date(2026, 9, 26), precipitation_mm=200.0),
        ]

        stats = aggregate_rainfall_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=anchor,
            window_days=7,
        )

        assert stats.days_available == 2
        assert stats.total_precipitation_mm == pytest.approx(25.0)
        assert stats.mean_daily_precipitation_mm == pytest.approx(12.5)
        assert stats.max_daily_precipitation_mm == pytest.approx(15.0)


class TestComputeRainfallWindowSuite:
    """Tests for compute_rainfall_window_suite."""

    def test_standard_suite_generation(self) -> None:
        """Verifies simultaneous generation of 7-day, 30-day, and 90-day window statistics."""
        anchor = date(2026, 9, 25)
        start = anchor - timedelta(days=89)
        obs = [
            DailyRainfallObservation(
                observation_date=start + timedelta(days=i),
                precipitation_mm=5.0,
            )
            for i in range(90)
        ]

        r7, r30, r90 = compute_rainfall_window_suite(obs, anchor)

        assert r7.window_name == "recent_7_days"
        assert r7.window_start == date(2026, 9, 19)
        assert r7.days_available == 7
        assert r7.is_complete is True
        assert r7.total_precipitation_mm == pytest.approx(35.0)

        assert r30.window_name == "recent_30_days"
        assert r30.window_start == date(2026, 8, 27)
        assert r30.days_available == 30
        assert r30.is_complete is True
        assert r30.total_precipitation_mm == pytest.approx(150.0)

        assert r90.window_name == "recent_90_days"
        assert r90.window_start == date(2026, 6, 28)
        assert r90.days_available == 90
        assert r90.is_complete is True
        assert r90.total_precipitation_mm == pytest.approx(450.0)
