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
"""Type definitions and domain contracts for environmental data sources (Phase 3)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.satellite.types import AnalysisRegionMetadata, EarthEngineError, EarthEngineStatus


class DailyEnvironmentalObservation(BaseModel):
    """Normalized daily meteorological and hydrological observation for a single date (DEC-018).

    Represents physical variables extracted from ERA5-Land (ECMWF/ERA5_LAND/DAILY_AGGR).
    """

    observation_date: date = Field(
        description="Observation date (UTC calendar date)"
    )
    temperature_c: float | None = Field(
        default=None,
        ge=-100.0,
        le=100.0,
        description="Daily mean 2m air temperature in degrees Celsius (°C)",
    )
    precipitation_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Daily total accumulated precipitation in millimeters (mm)",
    )
    volumetric_soil_water_layer_1: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Topsoil volumetric soil water (0–7 cm depth), dimensionless fraction (m³/m³)",
    )
    runoff_sum_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Daily total surface and subsurface runoff in millimeters (mm)",
    )

    @property
    def runoff_mm(self) -> float | None:
        """Alias for runoff_sum_mm for backward/flexible naming parity."""
        return self.runoff_sum_mm


class EnvironmentalWindowStatistics(BaseModel):
    """Aggregated summary statistics for a discrete environmental observation window (DEC-018)."""

    window_name: Literal["recent_7_days", "recent_30_days", "recent_90_days"] = Field(
        description="Canonical name of the retrospective observation window"
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
        description="Count of calendar days with valid observations available in this window",
    )
    is_complete: bool = Field(
        description="True if all requested days in the window have valid observations (days_available == days_requested)",
    )
    mean_temperature_c: float | None = Field(
        default=None,
        ge=-100.0,
        le=100.0,
        description="Mean 2m air temperature across available days in window (°C)",
    )
    min_temperature_c: float | None = Field(
        default=None,
        ge=-100.0,
        le=100.0,
        description="Minimum daily mean 2m temperature in window (°C)",
    )
    max_temperature_c: float | None = Field(
        default=None,
        ge=-100.0,
        le=100.0,
        description="Maximum daily mean 2m temperature in window (°C)",
    )
    total_precipitation_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Total cumulative precipitation sum across available days in window (mm)",
    )
    mean_soil_water_layer_1: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Mean topsoil volumetric soil water (0–7 cm) across available days in window (m³/m³)",
    )
    total_runoff_mm: float | None = Field(
        default=None,
        ge=0.0,
        description="Total cumulative runoff sum across available days in window (mm)",
    )

    @model_validator(mode="after")
    def validate_window_invariants(self) -> "EnvironmentalWindowStatistics":
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
        if self.min_temperature_c is not None and self.max_temperature_c is not None:
            if self.min_temperature_c > self.max_temperature_c + 1e-6:
                raise ValueError(
                    f"min_temperature_c ({self.min_temperature_c}) cannot be greater than max_temperature_c ({self.max_temperature_c})"
                )
        if self.min_temperature_c is not None and self.mean_temperature_c is not None:
            if self.min_temperature_c > self.mean_temperature_c + 1e-6:
                raise ValueError(
                    f"min_temperature_c ({self.min_temperature_c}) cannot be greater than mean_temperature_c ({self.mean_temperature_c})"
                )
        if self.max_temperature_c is not None and self.mean_temperature_c is not None:
            if self.mean_temperature_c > self.max_temperature_c + 1e-6:
                raise ValueError(
                    f"mean_temperature_c ({self.mean_temperature_c}) cannot be greater than max_temperature_c ({self.max_temperature_c})"
                )
        return self


class ERA5LandAnalysis(BaseModel):
    """Authoritative domain payload for ERA5-Land daily reanalysis environmental context (DEC-018)."""

    region: AnalysisRegionMetadata = Field(
        description="Spatial footprint and geographic location reference"
    )
    requested_end_date: date = Field(
        description="Reference / query end date requested by the user/caller (UTC)"
    )
    latest_available_date: date | None = Field(
        default=None,
        description="Latest calendar date with valid observations in the reanalysis archive",
    )
    data_lag_days: int | None = Field(
        default=None,
        ge=0,
        description="Operational reanalysis latency in days (requested_end_date - latest_available_date)",
    )
    recent_7_days: EnvironmentalWindowStatistics | None = Field(
        default=None,
        description="Summary statistics for the 7-day retrospective observation window",
    )
    recent_30_days: EnvironmentalWindowStatistics | None = Field(
        default=None,
        description="Summary statistics for the 30-day retrospective observation window",
    )
    recent_90_days: EnvironmentalWindowStatistics | None = Field(
        default=None,
        description="Summary statistics for the 90-day retrospective observation window",
    )
    daily_observations: list[DailyEnvironmentalObservation] = Field(
        default_factory=list,
        description="Sequence of daily normalized observations in chronological order",
    )
    dataset: str = Field(
        default="ECMWF/ERA5_LAND/DAILY_AGGR",
        description="Google Earth Engine asset identifier for the ERA5-Land Daily Aggregated dataset",
    )
    spatial_resolution_km: float = Field(
        default=11.1,
        gt=0.0,
        description="Native spatial resolution of the ERA5-Land grid in kilometers (~0.1°)",
    )
    status: EarthEngineStatus = Field(
        default="success",
        description="Operational status of the retrieval: success | no_data | error",
    )
    pipeline_version: str = Field(
        default="3.0.0",
        description="Semantic version of the environmental processing pipeline",
    )
    error: EarthEngineError | None = Field(
        default=None,
        description="Structured error details if status is 'error'",
    )

    @model_validator(mode="after")
    def validate_analysis_invariants(self) -> "ERA5LandAnalysis":
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
