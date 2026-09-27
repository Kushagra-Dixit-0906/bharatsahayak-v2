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
"""Type definitions and domain contracts for the CHIRPS Regional Rainfall Backup Subsystem (Phase 3B, DEC-020)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.satellite.types import AnalysisRegionMetadata, EarthEngineError, EarthEngineStatus


class DailyRainfallObservation(BaseModel):
    """Normalized daily precipitation observation for a single calendar date (DEC-020).

    Represents physical precipitation extracted from CHIRPS v3 (UCSB-CHC/CHIRPS/V3/DAILY_SAT).
    """

    observation_date: date = Field(
        description="Observation date (UTC calendar date)"
    )
    precipitation_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Daily total accumulated precipitation in millimeters (mm/day)",
    )


class RainfallWindowStatistics(BaseModel):
    """Aggregated summary statistics for a discrete retrospective rainfall window (DEC-020)."""

    window_name: Literal["recent_7_days", "recent_30_days", "recent_90_days"] = Field(
        description="Canonical identifier of the retrospective rainfall observation window"
    )
    window_start: date = Field(
        description="Inclusive start date of the observation window"
    )
    window_end: date = Field(
        description="Inclusive end date of the observation window"
    )
    days_requested: int = Field(
        gt=0,
        description="Total count of calendar days requested for this window",
    )
    days_available: int = Field(
        ge=0,
        description="Count of calendar days with observations available in this window",
    )
    is_complete: bool = Field(
        description="True if all requested days in the window have observations (days_available == days_requested)",
    )
    total_precipitation_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Total cumulative precipitation sum across available non-null days in window (mm)",
    )
    mean_daily_precipitation_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Mean daily precipitation across available non-null days in window (mm/day)",
    )
    max_daily_precipitation_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Maximum single-day precipitation across available non-null days in window (mm/day)",
    )

    @model_validator(mode="after")
    def validate_window_invariants(self) -> "RainfallWindowStatistics":
        if self.window_start > self.window_end:
            raise ValueError(
                f"window_start ({self.window_start}) cannot be after window_end ({self.window_end})"
            )
        if self.days_available > self.days_requested:
            raise ValueError(
                f"days_available ({self.days_available}) cannot exceed days_requested ({self.days_requested})"
            )
        expected_complete = self.days_available == self.days_requested
        if self.is_complete != expected_complete:
            raise ValueError(
                f"is_complete ({self.is_complete}) does not match days_available == days_requested "
                f"({self.days_available} == {self.days_requested} -> {expected_complete})"
            )
        if self.mean_daily_precipitation_mm is not None and self.max_daily_precipitation_mm is not None:
            if self.mean_daily_precipitation_mm > self.max_daily_precipitation_mm + 1e-6:
                raise ValueError(
                    f"mean_daily_precipitation_mm ({self.mean_daily_precipitation_mm}) cannot be greater "
                    f"than max_daily_precipitation_mm ({self.max_daily_precipitation_mm})"
                )
        return self


class CHIRPSRainfallAnalysis(BaseModel):
    """Authoritative domain payload for CHIRPS daily precipitation intelligence (DEC-020)."""

    region: AnalysisRegionMetadata = Field(
        description="Spatial footprint and geographic location reference"
    )
    requested_end_date: date = Field(
        description="Reference / query end date requested by the user/caller (UTC)"
    )
    latest_available_date: date | None = Field(
        default=None,
        description="Latest calendar date with valid observations in the CHIRPS archive",
    )
    data_lag_days: int | None = Field(
        default=None,
        ge=0,
        description="Operational publication latency in days (requested_end_date - latest_available_date)",
    )
    recent_7_days: RainfallWindowStatistics | None = Field(
        default=None,
        description="Summary statistics for the 7-day retrospective rainfall window",
    )
    recent_30_days: RainfallWindowStatistics | None = Field(
        default=None,
        description="Summary statistics for the 30-day retrospective rainfall window",
    )
    recent_90_days: RainfallWindowStatistics | None = Field(
        default=None,
        description="Summary statistics for the 90-day retrospective rainfall window",
    )
    daily_observations: list[DailyRainfallObservation] = Field(
        default_factory=list,
        description="Sequence of daily normalized observations in chronological order",
    )
    dataset: str = Field(
        default="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
        description="Google Earth Engine asset identifier for the CHIRPS v3 Daily Satellite dataset",
    )
    spatial_resolution_km: float = Field(
        default=5.566,
        gt=0.0,
        description="Native spatial resolution of the CHIRPS grid in kilometers (~0.05°)",
    )
    status: EarthEngineStatus = Field(
        default="success",
        description="Operational status of the retrieval: success | no_data | error",
    )
    pipeline_version: str = Field(
        default="3.1.0",
        description="Semantic version of the CHIRPS rainfall processing pipeline",
    )
    error: EarthEngineError | None = Field(
        default=None,
        description="Structured error details if status is 'error'",
    )

    @model_validator(mode="after")
    def validate_analysis_invariants(self) -> "CHIRPSRainfallAnalysis":
        if self.status == "success":
            if self.latest_available_date is None:
                raise ValueError("status='success' requires a non-null latest_available_date")
            if self.latest_available_date > self.requested_end_date:
                raise ValueError(
                    f"latest_available_date ({self.latest_available_date}) cannot be in the future "
                    f"relative to requested_end_date ({self.requested_end_date})"
                )
            expected_lag = (self.requested_end_date - self.latest_available_date).days
            if self.data_lag_days is not None and self.data_lag_days != expected_lag:
                raise ValueError(
                    f"data_lag_days ({self.data_lag_days}) does not match difference between "
                    f"requested_end_date ({self.requested_end_date}) and "
                    f"latest_available_date ({self.latest_available_date}) = {expected_lag}"
                )
            if not self.daily_observations and (self.recent_7_days or self.recent_30_days or self.recent_90_days):
                raise ValueError("status='success' with window statistics requires non-empty daily_observations")
        elif self.status == "no_data":
            if self.daily_observations:
                raise ValueError("status='no_data' cannot contain daily_observations")
            if self.recent_7_days is not None or self.recent_30_days is not None or self.recent_90_days is not None:
                raise ValueError("status='no_data' cannot contain window statistics")
        elif self.status == "error":
            if self.error is None:
                raise ValueError("status='error' requires a populated error field")
            if self.daily_observations:
                raise ValueError("status='error' cannot contain daily_observations")

        return self
