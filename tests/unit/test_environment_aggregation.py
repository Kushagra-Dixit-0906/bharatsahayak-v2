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
"""Unit tests for Phase 3A environmental window aggregation engine (DEC-018)."""

from datetime import date, timedelta
import random

import pytest

from app.environment.aggregation import (
    aggregate_window_statistics,
    compute_environmental_window_suite,
)
from app.environment.types import DailyEnvironmentalObservation
from tests.fixtures.era5_fixtures import (
    load_lagged_partial_raw,
    load_punjab_monsoon_raw,
    load_punjab_winter_dry_raw,
)


def _generate_daily_series(
    start_date: date,
    num_days: int,
    temp_base: float = 30.0,
    precip_val: float = 5.0,
    soil_val: float = 0.25,
    runoff_val: float = 1.0,
) -> list[DailyEnvironmentalObservation]:
    """Helper to generate a synthetic sequence of observations."""
    return [
        DailyEnvironmentalObservation(
            observation_date=start_date + timedelta(days=i),
            temperature_c=temp_base + (i % 5),
            precipitation_mm=precip_val,
            volumetric_soil_water_layer_1=soil_val,
            runoff_sum_mm=runoff_val,
        )
        for i in range(num_days)
    ]


# ============================================================================
# 1. WINDOW DURATION & INCLUSIVE BOUNDARY TESTS
# ============================================================================


class TestWindowBoundariesAndCompleteness:
    """Tests for temporal window spans and completeness semantics."""

    def test_standard_7_day_window(self) -> None:
        """Verifies exact inclusive 7-day span [E-6, E], completeness, and metrics."""
        end_d = date(2026, 9, 25)
        # E - 6 is 2026-09-19
        obs = _generate_daily_series(
            start_date=date(2026, 9, 19),
            num_days=7,
            temp_base=30.0,
            precip_val=10.0,
            soil_val=0.30,
            runoff_val=2.0,
        )
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )

        assert stats.window_name == "recent_7_days"
        assert stats.window_start == date(2026, 9, 19)
        assert stats.window_end == date(2026, 9, 25)
        assert stats.days_requested == 7
        assert stats.days_available == 7
        assert stats.is_complete is True
        assert stats.total_precipitation_mm == pytest.approx(70.0)
        assert stats.total_runoff_mm == pytest.approx(14.0)
        assert stats.mean_soil_water_layer_1 == pytest.approx(0.30)
        assert stats.min_temperature_c == 30.0
        assert stats.max_temperature_c == 34.0
        assert stats.mean_temperature_c == pytest.approx(221.0 / 7.0)

    def test_standard_30_day_window(self) -> None:
        """Verifies exact inclusive 30-day span [E-29, E] and completeness."""
        end_d = date(2026, 9, 25)
        start_d = end_d - timedelta(days=29)
        obs = _generate_daily_series(start_date=start_d, num_days=30)
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_30_days",
            window_end=end_d,
            window_days=30,
        )

        assert stats.window_name == "recent_30_days"
        assert stats.window_start == date(2026, 8, 27)
        assert stats.window_end == date(2026, 9, 25)
        assert stats.days_requested == 30
        assert stats.days_available == 30
        assert stats.is_complete is True

    def test_standard_90_day_window(self) -> None:
        """Verifies exact inclusive 90-day span [E-89, E] and completeness."""
        end_d = date(2026, 9, 25)
        start_d = end_d - timedelta(days=89)
        obs = _generate_daily_series(start_date=start_d, num_days=90)
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_90_days",
            window_end=end_d,
            window_days=90,
        )

        assert stats.window_name == "recent_90_days"
        assert stats.window_start == date(2026, 6, 28)
        assert stats.window_end == date(2026, 9, 25)
        assert stats.days_requested == 90
        assert stats.days_available == 90
        assert stats.is_complete is True

    def test_invalid_window_days_raises(self) -> None:
        """Verifies window_days <= 0 raises ValueError."""
        with pytest.raises(ValueError, match="window_days must be positive"):
            aggregate_window_statistics(
                observations=[],
                window_name="recent_7_days",
                window_end=date(2026, 9, 25),
                window_days=0,
            )

        with pytest.raises(ValueError, match="window_days must be positive"):
            aggregate_window_statistics(
                observations=[],
                window_name="recent_7_days",
                window_end=date(2026, 9, 25),
                window_days=-5,
            )


# ============================================================================
# 2. PARTIAL & EMPTY WINDOW TESTS
# ============================================================================


class TestPartialAndEmptyWindows:
    """Tests for missing observation days and empty windows."""

    def test_partial_window_calculates_available_metrics(self) -> None:
        """Verifies partial window calculates metrics without rejecting the window."""
        end_d = date(2026, 9, 25)
        # 85 days available out of 90 requested (starts at 2026-06-28, ends at 2026-09-20)
        obs = _generate_daily_series(
            start_date=date(2026, 6, 28),
            num_days=85,
            temp_base=30.0,
            precip_val=2.0,
            soil_val=0.20,
            runoff_val=0.5,
        )
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_90_days",
            window_end=end_d,
            window_days=90,
        )

        assert stats.days_requested == 90
        assert stats.days_available == 85
        assert stats.is_complete is False
        assert stats.total_precipitation_mm == pytest.approx(85 * 2.0)
        assert stats.total_runoff_mm == pytest.approx(85 * 0.5)
        assert stats.mean_soil_water_layer_1 == pytest.approx(0.20)
        assert stats.mean_temperature_c is not None

    def test_empty_window_all_metrics_none(self) -> None:
        """Verifies empty window produces days_available=0, is_complete=False, all metrics None."""
        end_d = date(2026, 9, 25)
        stats = aggregate_window_statistics(
            observations=[],
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )

        assert stats.days_requested == 7
        assert stats.days_available == 0
        assert stats.is_complete is False
        assert stats.mean_temperature_c is None
        assert stats.min_temperature_c is None
        assert stats.max_temperature_c is None
        assert stats.total_precipitation_mm is None
        assert stats.mean_soil_water_layer_1 is None
        assert stats.total_runoff_mm is None


# ============================================================================
# 3. METRIC-LEVEL MISSINGNESS & ZERO DISTINCTION
# ============================================================================


class TestMetricLevelMissingnessAndZeros:
    """Tests for partial variable availability and strict 0.0 vs None distinction."""

    def test_partial_variable_availability_per_day(self) -> None:
        """Verifies days_available counts observation dates while metrics aggregate non-null values."""
        end_d = date(2026, 9, 25)
        obs: list[DailyEnvironmentalObservation] = []
        for i in range(30):
            d = date(2026, 8, 27) + timedelta(days=i)
            # Temperature available on all 30
            # Precipitation available on first 25 (None on last 5)
            # Soil water available on first 29 (None on last 1)
            # Runoff available on first 24 (None on last 6)
            obs.append(
                DailyEnvironmentalObservation(
                    observation_date=d,
                    temperature_c=28.0,
                    precipitation_mm=4.0 if i < 25 else None,
                    volumetric_soil_water_layer_1=0.30 if i < 29 else None,
                    runoff_sum_mm=1.0 if i < 24 else None,
                )
            )

        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_30_days",
            window_end=end_d,
            window_days=30,
        )

        assert stats.days_available == 30
        assert stats.days_requested == 30
        assert stats.is_complete is True
        assert stats.mean_temperature_c == pytest.approx(28.0)
        assert stats.total_precipitation_mm == pytest.approx(25 * 4.0)
        assert stats.mean_soil_water_layer_1 == pytest.approx(0.30)
        assert stats.total_runoff_mm == pytest.approx(24 * 1.0)

    def test_zero_precipitation_vs_none_precipitation(self) -> None:
        """Verifies observed 0.0 mm rainfall produces total 0.0 mm, while all-None produces None."""
        end_d = date(2026, 9, 25)

        # All 0.0
        obs_zero = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 19) + timedelta(days=i),
                precipitation_mm=0.0,
            )
            for i in range(7)
        ]
        stats_zero = aggregate_window_statistics(
            observations=obs_zero,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )
        assert stats_zero.total_precipitation_mm == 0.0
        assert stats_zero.days_available == 7

        # All None
        obs_none = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 19) + timedelta(days=i),
                precipitation_mm=None,
            )
            for i in range(7)
        ]
        stats_none = aggregate_window_statistics(
            observations=obs_none,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )
        assert stats_none.total_precipitation_mm is None
        assert stats_none.days_available == 7

    def test_zero_runoff_vs_none_runoff(self) -> None:
        """Verifies observed 0.0 mm runoff produces total 0.0 mm, while all-None produces None."""
        end_d = date(2026, 9, 25)

        obs_zero = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 19) + timedelta(days=i),
                runoff_sum_mm=0.0,
            )
            for i in range(7)
        ]
        stats_zero = aggregate_window_statistics(
            observations=obs_zero,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )
        assert stats_zero.total_runoff_mm == 0.0

        obs_none = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 19) + timedelta(days=i),
                runoff_sum_mm=None,
            )
            for i in range(7)
        ]
        stats_none = aggregate_window_statistics(
            observations=obs_none,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )
        assert stats_none.total_runoff_mm is None

    def test_all_metrics_missing_preserves_calendar_availability(self) -> None:
        """Verifies observations with all metrics None count towards days_available with None metrics."""
        end_d = date(2026, 9, 25)
        obs = [
            DailyEnvironmentalObservation(observation_date=date(2026, 9, 19) + timedelta(days=i))
            for i in range(7)
        ]
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )
        assert stats.days_available == 7
        assert stats.is_complete is True
        assert stats.mean_temperature_c is None
        assert stats.min_temperature_c is None
        assert stats.max_temperature_c is None
        assert stats.total_precipitation_mm is None
        assert stats.mean_soil_water_layer_1 is None
        assert stats.total_runoff_mm is None


# ============================================================================
# 4. MATHEMATICAL & PHYSICAL INVARIANTS
# ============================================================================


class TestMathematicalAndPhysicalInvariants:
    """Tests for physical metric computations and validation constraints."""

    def test_temperature_subzero_and_invariants(self) -> None:
        """Verifies correct min <= mean <= max calculation for winter subzero temperatures."""
        end_d = date(2026, 1, 15)
        temps = [-10.5, -5.0, 0.0, 2.5, 5.0, 8.0, 10.0]
        obs = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 1, 9) + timedelta(days=i),
                temperature_c=temps[i],
            )
            for i in range(7)
        ]
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )

        assert stats.min_temperature_c == -10.5
        assert stats.max_temperature_c == 10.0
        expected_mean = sum(temps) / len(temps)
        assert stats.mean_temperature_c == pytest.approx(expected_mean)
        assert stats.min_temperature_c <= stats.mean_temperature_c <= stats.max_temperature_c

    def test_soil_water_mean_calculation(self) -> None:
        """Verifies arithmetic mean of topsoil moisture fractions."""
        end_d = date(2026, 9, 25)
        soils = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]
        obs = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 19) + timedelta(days=i),
                volumetric_soil_water_layer_1=soils[i],
            )
            for i in range(7)
        ]
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )
        assert stats.mean_soil_water_layer_1 == pytest.approx(sum(soils) / len(soils))


# ============================================================================
# 5. DEFENSIVE VALIDATION & ORDERING TESTS
# ============================================================================


class TestDefensiveValidationAndOrdering:
    """Tests for duplicate-date rejection, out-of-window filtering, and input order invariance."""

    def test_duplicate_dates_rejected(self) -> None:
        """Verifies duplicate observation_date in input sequence explicitly raises ValueError."""
        obs = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 20),
                temperature_c=30.0,
            ),
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 20),  # Duplicate
                temperature_c=31.0,
            ),
        ]
        with pytest.raises(ValueError, match="Duplicate observation date detected: 2026-09-20"):
            aggregate_window_statistics(
                observations=obs,
                window_name="recent_7_days",
                window_end=date(2026, 9, 25),
                window_days=7,
            )

    def test_out_of_window_filtering(self) -> None:
        """Verifies observations outside [window_start, window_end] are excluded."""
        end_d = date(2026, 9, 25)
        # Window is [2026-09-19, 2026-09-25]
        obs = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 18),  # Before start
                temperature_c=20.0,
                precipitation_mm=50.0,
            ),
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 20),  # In window
                temperature_c=30.0,
                precipitation_mm=10.0,
            ),
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 26),  # After end
                temperature_c=40.0,
                precipitation_mm=50.0,
            ),
        ]
        stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_7_days",
            window_end=end_d,
            window_days=7,
        )

        assert stats.days_available == 1
        assert stats.is_complete is False
        assert stats.total_precipitation_mm == 10.0
        assert stats.mean_temperature_c == 30.0

    def test_input_order_invariance(self) -> None:
        """Verifies reverse or randomly shuffled input order yields identical aggregation results."""
        end_d = date(2026, 9, 25)
        obs = _generate_daily_series(
            start_date=date(2026, 8, 27),
            num_days=30,
            temp_base=25.0,
            precip_val=3.5,
        )

        sorted_stats = aggregate_window_statistics(
            observations=obs,
            window_name="recent_30_days",
            window_end=end_d,
            window_days=30,
        )

        reversed_obs = list(reversed(obs))
        reversed_stats = aggregate_window_statistics(
            observations=reversed_obs,
            window_name="recent_30_days",
            window_end=end_d,
            window_days=30,
        )

        shuffled_obs = list(obs)
        random.seed(42)
        random.shuffle(shuffled_obs)
        shuffled_stats = aggregate_window_statistics(
            observations=shuffled_obs,
            window_name="recent_30_days",
            window_end=end_d,
            window_days=30,
        )

        assert sorted_stats == reversed_stats
        assert sorted_stats == shuffled_stats


# ============================================================================
# 6. WINDOW SUITE ORCHESTRATION TESTS
# ============================================================================


class TestEnvironmentalWindowSuite:
    """Tests for compute_environmental_window_suite orchestrator."""

    def test_window_suite_produces_7_30_90_windows(self) -> None:
        """Verifies compute_environmental_window_suite returns 7, 30, and 90 day windows."""
        end_d = date(2026, 9, 25)
        obs = _generate_daily_series(
            start_date=date(2026, 6, 28),
            num_days=90,
            temp_base=30.0,
            precip_val=5.0,
        )

        w7, w30, w90 = compute_environmental_window_suite(observations=obs, end_date=end_d)

        assert w7.window_name == "recent_7_days"
        assert w7.days_requested == 7
        assert w7.days_available == 7
        assert w7.is_complete is True
        assert w7.window_start == date(2026, 9, 19)
        assert w7.window_end == end_d

        assert w30.window_name == "recent_30_days"
        assert w30.days_requested == 30
        assert w30.days_available == 30
        assert w30.is_complete is True
        assert w30.window_start == date(2026, 8, 27)
        assert w30.window_end == end_d

        assert w90.window_name == "recent_90_days"
        assert w90.days_requested == 90
        assert w90.days_available == 90
        assert w90.is_complete is True
        assert w90.window_start == date(2026, 6, 28)
        assert w90.window_end == end_d


# ============================================================================
# 7. DETERMINISTIC FIXTURE VALIDATION TESTS
# ============================================================================


class TestFixtureAggregation:
    """Tests aggregating real deterministic test fixtures."""

    def test_aggregate_punjab_monsoon_fixture(self) -> None:
        """Verifies deterministic aggregation over 90-day Punjab monsoon fixture."""
        raw = load_punjab_monsoon_raw()
        obs = [DailyEnvironmentalObservation(**item) for item in raw["daily_observations"]]
        end_d = date(2026, 9, 25)

        w7, w30, w90 = compute_environmental_window_suite(observations=obs, end_date=end_d)

        assert w7.is_complete is True
        assert w30.is_complete is True
        assert w90.is_complete is True

        assert w90.days_available == 90
        assert w90.total_precipitation_mm is not None
        assert w90.total_precipitation_mm > 500.0  # Monsoon cumulative precipitation
        assert w90.total_runoff_mm is not None
        assert w90.total_runoff_mm > 50.0

    def test_aggregate_punjab_winter_dry_fixture(self) -> None:
        """Verifies deterministic aggregation over 90-day Punjab winter dry fixture."""
        raw = load_punjab_winter_dry_raw()
        obs = [DailyEnvironmentalObservation(**item) for item in raw["daily_observations"]]
        end_d = date(2026, 1, 29)

        w7, w30, w90 = compute_environmental_window_suite(observations=obs, end_date=end_d)

        assert w7.is_complete is True
        assert w30.is_complete is True
        assert w90.is_complete is True

        assert w90.days_available == 90
        assert w90.mean_temperature_c is not None
        assert w90.mean_temperature_c < 22.0  # Cool winter temperatures
        assert w90.total_precipitation_mm is not None
        assert w90.total_precipitation_mm < 100.0  # Dry season low precipitation

    def test_aggregate_lagged_partial_fixture(self) -> None:
        """Verifies deterministic aggregation over lagged partial fixture (85 days available)."""
        raw = load_lagged_partial_raw()
        obs = [DailyEnvironmentalObservation(**item) for item in raw["daily_observations"]]
        # requested_end_date is 2026-09-25, latest observation is 2026-09-20
        end_d = date(2026, 9, 25)

        w7, w30, w90 = compute_environmental_window_suite(observations=obs, end_date=end_d)

        # 7-day window [2026-09-19, 2026-09-25]: 2026-09-19 and 2026-09-20 exist (2 days available)
        assert w7.days_requested == 7
        assert w7.days_available == 2
        assert w7.is_complete is False

        # 30-day window: 25 days available out of 30 requested
        assert w30.days_requested == 30
        assert w30.days_available == 25
        assert w30.is_complete is False

        # 90-day window: 85 days available out of 90 requested
        assert w90.days_requested == 90
        assert w90.days_available == 85
        assert w90.is_complete is False
        assert w90.total_precipitation_mm is not None
