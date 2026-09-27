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
"""Type definitions and domain contract for Phase 4 Multi-Source Evidence Fusion (DEC-022)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    HistoricalNdviAnalysis,
    RegionalNdviAnalysis,
)

FusionStatus = Literal["success", "partial", "no_data", "error"]


class AgriculturalEnvironmentalEvidence(BaseModel):
    """Authoritative multi-source agricultural and environmental evidence envelope (DEC-022).

    Synthesizes current vegetation vigor, 3-year historical NDVI departures, ERA5-Land reanalysis,
    CHIRPS precipitation, and Dynamic World land-cover context over the farmer's AnalysisRegion.
    """

    region: AnalysisRegionMetadata = Field(
        description="Shared geographic footprint and circular parcel buffer metadata"
    )
    reference_date: date = Field(
        description="Authoritative reference / query anchor date (UTC)"
    )
    vegetation: HistoricalNdviAnalysis = Field(
        description="Current Sentinel-2 vegetation vigor, historical baseline, and anomaly evidence"
    )
    reanalysis: ERA5LandAnalysis = Field(
        description="ERA5-Land daily reanalysis (temperature, topsoil moisture, runoff, precipitation)"
    )
    rainfall: CHIRPSRainfallAnalysis = Field(
        description="CHIRPS daily precipitation distribution and retrospective rainfall windows"
    )
    land_cover: DynamicWorldAnalysis = Field(
        description="Dynamic World 9-class land-cover probability distribution and dominant class"
    )
    status: FusionStatus = Field(
        description="Unified operational status across all evidence sources: success | partial | no_data | error"
    )
    sources_requested_count: int = Field(
        default=4,
        description="Total distinct evidence subsystems evaluated (Vegetation, Reanalysis, Rainfall, Land Cover)",
    )
    sources_available_count: int = Field(
        ge=0,
        le=4,
        description="Count of distinct evidence subsystems providing usable evidence (full or partial)",
    )
    sources_fully_available_count: int = Field(
        ge=0,
        le=4,
        description="Count of distinct evidence subsystems returning status='success'",
    )
    is_fully_available: bool = Field(
        description="True if all 4 requested sources are fully available (sources_fully_available_count == 4)"
    )
    pipeline_version: str = Field(
        default="4.0.0",
        description="Semantic version of the multi-source evidence fusion pipeline",
    )
    error: EarthEngineError | None = Field(
        default=None,
        description="Structured error details if an unhandled top-level fusion error occurred",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    @property
    def current_vegetation(self) -> RegionalNdviAnalysis | None:
        """Convenience property accessing the current Phase 1 Sentinel-2 observation."""
        return self.vegetation.current

    @model_validator(mode="after")
    def validate_fusion_invariants(self) -> "AgriculturalEnvironmentalEvidence":
        """Validates count bounds, availability flag, and status consistency."""
        if not (0 <= self.sources_fully_available_count <= self.sources_available_count <= self.sources_requested_count):
            raise ValueError(
                f"Count invariant violation: sources_fully_available_count ({self.sources_fully_available_count}) "
                f"<= sources_available_count ({self.sources_available_count}) "
                f"<= sources_requested_count ({self.sources_requested_count})"
            )

        expected_fully_available = (self.sources_fully_available_count == self.sources_requested_count)
        if self.is_fully_available != expected_fully_available:
            raise ValueError(
                f"is_fully_available ({self.is_fully_available}) must be {expected_fully_available} "
                f"when sources_fully_available_count={self.sources_fully_available_count} "
                f"and sources_requested_count={self.sources_requested_count}"
            )

        if self.status == "success":
            if self.sources_fully_available_count != self.sources_requested_count:
                raise ValueError(
                    f"status='success' requires sources_fully_available_count == {self.sources_requested_count}, "
                    f"got {self.sources_fully_available_count}"
                )
            if self.error is not None:
                raise ValueError("status='success' cannot contain a top-level error")
        elif self.status == "partial":
            if self.sources_available_count < 1:
                raise ValueError(
                    f"status='partial' requires at least 1 usable source, got sources_available_count={self.sources_available_count}"
                )
            if self.sources_fully_available_count == self.sources_requested_count:
                raise ValueError(
                    f"status='partial' cannot have all sources fully available (count={self.sources_fully_available_count})"
                )
        elif self.status == "no_data":
            if self.sources_available_count != 0:
                raise ValueError(
                    f"status='no_data' requires sources_available_count == 0, got {self.sources_available_count}"
                )
            if self.sources_fully_available_count != 0:
                raise ValueError(
                    f"status='no_data' requires sources_fully_available_count == 0, got {self.sources_fully_available_count}"
                )
            if self.error is not None:
                raise ValueError("status='no_data' cannot contain a top-level error")
        elif self.status == "error":
            if self.sources_available_count != 0:
                raise ValueError(
                    f"status='error' requires sources_available_count == 0, got {self.sources_available_count}"
                )
            if self.sources_fully_available_count != 0:
                raise ValueError(
                    f"status='error' requires sources_fully_available_count == 0, got {self.sources_fully_available_count}"
                )

        if self.error is not None and self.status != "error":
            raise ValueError(f"Top-level error requires status='error', got status='{self.status}'")

        return self
