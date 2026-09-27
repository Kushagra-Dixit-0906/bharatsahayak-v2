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
"""Pure mathematical and window aggregation engine for environmental observations (Phase 3A)."""

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from app.environment.types import (
    DailyEnvironmentalObservation,
    EnvironmentalWindowStatistics,
)


def aggregate_window_statistics(
    observations: Sequence[DailyEnvironmentalObservation],
    window_name: Literal["recent_7_days", "recent_30_days", "recent_90_days"],
    window_end: date,
    window_days: int,
) -> EnvironmentalWindowStatistics:
    """Aggregate daily environmental observations over an inclusive retrospective temporal window (DEC-018).

    Calculates deterministic summary metrics (temperature mean/min/max, precipitation sum,
    soil water mean, runoff sum) and temporal completeness metadata for an inclusive
    calendar date span: [window_end - timedelta(days=window_days - 1), window_end].

    Args:
        observations: Sequence of normalized daily observations in arbitrary order.
        window_name: Canonical window identifier ('recent_7_days', 'recent_30_days', 'recent_90_days').
        window_end: Inclusive anchor end date of the retrospective window.
        window_days: Total count of calendar days requested for this window (e.g. 7, 30, 90).

    Returns:
        EnvironmentalWindowStatistics containing aggregated metrics and completeness flags.

    Raises:
        ValueError: If window_days <= 0, or if duplicate observation dates exist in the input sequence.
    """
    if window_days <= 0:
        raise ValueError(f"window_days must be positive, got {window_days}")

    window_start = window_end - timedelta(days=window_days - 1)

    # Check for duplicate observation dates across the input sequence
    seen_dates: set[date] = set()
    for obs in observations:
        if obs.observation_date in seen_dates:
            raise ValueError(f"Duplicate observation date detected: {obs.observation_date}")
        seen_dates.add(obs.observation_date)

    # Filter observations falling strictly within [window_start, window_end]
    window_obs = [
        obs for obs in observations
        if window_start <= obs.observation_date <= window_end
    ]

    days_requested = window_days
    days_available = len(window_obs)
    is_complete = days_available == days_requested

    # Extract physical variable sequences excluding None
    temps = [obs.temperature_c for obs in window_obs if obs.temperature_c is not None]
    precips = [obs.precipitation_mm for obs in window_obs if obs.precipitation_mm is not None]
    soils = [
        obs.volumetric_soil_water_layer_1
        for obs in window_obs
        if obs.volumetric_soil_water_layer_1 is not None
    ]
    runoffs = [obs.runoff_sum_mm for obs in window_obs if obs.runoff_sum_mm is not None]

    # Temperature statistics
    mean_temp = sum(temps) / len(temps) if temps else None
    min_temp = min(temps) if temps else None
    max_temp = max(temps) if temps else None

    # Precipitation sum
    total_precip = sum(precips) if precips else None

    # Soil water mean
    mean_soil = sum(soils) / len(soils) if soils else None

    # Runoff sum
    total_runoff = sum(runoffs) if runoffs else None

    return EnvironmentalWindowStatistics(
        window_name=window_name,
        window_start=window_start,
        window_end=window_end,
        days_requested=days_requested,
        days_available=days_available,
        is_complete=is_complete,
        mean_temperature_c=mean_temp,
        min_temperature_c=min_temp,
        max_temperature_c=max_temp,
        total_precipitation_mm=total_precip,
        mean_soil_water_layer_1=mean_soil,
        total_runoff_mm=total_runoff,
    )


def compute_environmental_window_suite(
    observations: Sequence[DailyEnvironmentalObservation],
    end_date: date,
) -> tuple[
    EnvironmentalWindowStatistics,
    EnvironmentalWindowStatistics,
    EnvironmentalWindowStatistics,
]:
    """Compute the standardized 7-day, 30-day, and 90-day environmental window statistics suite.

    Delegates directly to aggregate_window_statistics for each discrete window.

    Args:
        observations: Sequence of normalized daily observations.
        end_date: Inclusive anchor date for all windows.

    Returns:
        Tuple of (recent_7_days, recent_30_days, recent_90_days) EnvironmentalWindowStatistics.
    """
    recent_7 = aggregate_window_statistics(
        observations=observations,
        window_name="recent_7_days",
        window_end=end_date,
        window_days=7,
    )
    recent_30 = aggregate_window_statistics(
        observations=observations,
        window_name="recent_30_days",
        window_end=end_date,
        window_days=30,
    )
    recent_90 = aggregate_window_statistics(
        observations=observations,
        window_name="recent_90_days",
        window_end=end_date,
        window_days=90,
    )
    return (recent_7, recent_30, recent_90)
