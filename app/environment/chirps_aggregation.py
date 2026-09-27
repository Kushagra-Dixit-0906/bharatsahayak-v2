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
"""Pure mathematical and window aggregation engine for CHIRPS rainfall observations (Phase 3B, DEC-020)."""

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

from app.environment.chirps_types import (
    DailyRainfallObservation,
    RainfallWindowStatistics,
)


def aggregate_rainfall_window_statistics(
    observations: Sequence[DailyRainfallObservation],
    window_name: Literal["recent_7_days", "recent_30_days", "recent_90_days"],
    window_end: date,
    window_days: int,
) -> RainfallWindowStatistics:
    """Aggregate daily rainfall observations over an inclusive retrospective temporal window (DEC-020).

    Calculates deterministic summary metrics (precipitation total, daily mean, daily maximum)
    and temporal completeness metadata for an inclusive calendar date span:
    [window_end - timedelta(days=window_days - 1), window_end].

    Semantics:
        - Partial windows (is_complete=False): metrics calculate strictly over available non-null observations.
          total_precipitation_mm represents observed precipitation sum over available days, NOT a complete-window total.
          mean_daily_precipitation_mm represents mean over available days, NOT a mean over missing days treated as zero.
        - Empty windows (days_available=0): is_complete=False, and all metric values are None.
        - Missing dates are NOT fabricated. Missing precipitation values are NOT converted to zero.
        - Duplicate observation dates raise ValueError.
        - Order-invariant: input sequence ordering does not affect computed statistics.

    Args:
        observations: Sequence of normalized daily observations in arbitrary order.
        window_name: Canonical window identifier ('recent_7_days', 'recent_30_days', 'recent_90_days').
        window_end: Inclusive anchor end date of the retrospective window.
        window_days: Total count of calendar days requested for this window (e.g. 7, 30, 90).

    Returns:
        RainfallWindowStatistics containing aggregated metrics and completeness flags.

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

    # Extract non-null precipitation values
    precips = [obs.precipitation_mm for obs in window_obs if obs.precipitation_mm is not None]

    # Compute metrics over available non-null observations
    total_precip = sum(precips) if precips else None
    mean_precip = sum(precips) / len(precips) if precips else None
    max_precip = max(precips) if precips else None

    return RainfallWindowStatistics(
        window_name=window_name,
        window_start=window_start,
        window_end=window_end,
        days_requested=days_requested,
        days_available=days_available,
        is_complete=is_complete,
        total_precipitation_mm=total_precip,
        mean_daily_precipitation_mm=mean_precip,
        max_daily_precipitation_mm=max_precip,
    )


def compute_rainfall_window_suite(
    observations: Sequence[DailyRainfallObservation],
    requested_end_date: date,
) -> tuple[
    RainfallWindowStatistics,
    RainfallWindowStatistics,
    RainfallWindowStatistics,
]:
    """Computes the standard 3-window suite (7-day, 30-day, 90-day) for CHIRPS rainfall observations.

    Args:
        observations: Sequence of normalized daily rainfall observations.
        requested_end_date: Inclusive anchor date for all three windows.

    Returns:
        tuple of (recent_7_days, recent_30_days, recent_90_days) RainfallWindowStatistics.

    Raises:
        ValueError: If duplicate dates exist in observations.
    """
    recent_7 = aggregate_rainfall_window_statistics(
        observations=observations,
        window_name="recent_7_days",
        window_end=requested_end_date,
        window_days=7,
    )
    recent_30 = aggregate_rainfall_window_statistics(
        observations=observations,
        window_name="recent_30_days",
        window_end=requested_end_date,
        window_days=30,
    )
    recent_90 = aggregate_rainfall_window_statistics(
        observations=observations,
        window_name="recent_90_days",
        window_end=requested_end_date,
        window_days=90,
    )
    return recent_7, recent_30, recent_90
