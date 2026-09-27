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
"""Strongly-typed Pydantic domain models for Dynamic World Land-Cover Context (Phase 3C, DEC-021).

Defines canonical representations for:
- DynamicWorldLandCoverClass: 9 canonical land use / land cover classes.
- DynamicWorldClassProbabilities: Continuous regional probability distribution [0.0, 1.0].
- DynamicWorldAnalysis: Authoritative root land-cover context envelope with metadata and status.
"""

from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    EarthEngineStatus,
)

# Canonical Dynamic World land-cover class identifiers (DEC-021)
DynamicWorldLandCoverClass = Literal[
    "water",
    "trees",
    "grass",
    "flooded_vegetation",
    "crops",
    "shrub_and_scrub",
    "built",
    "bare",
    "snow_and_ice",
]

# Canonical GEE index ordering for deterministic tie-breaking (DEC-021)
CANONICAL_CLASS_PRECEDENCE: tuple[DynamicWorldLandCoverClass, ...] = (
    "water",              # 0
    "trees",              # 1
    "grass",              # 2
    "flooded_vegetation", # 3
    "crops",              # 4
    "shrub_and_scrub",    # 5
    "built",              # 6
    "bare",               # 7
    "snow_and_ice",       # 8
)


class DynamicWorldClassProbabilities(BaseModel):
    """Normalized regional mean probability distribution over the 9 Dynamic World classes (DEC-021).

    Each probability field represents the unweighted zonal mean probability of that class
    across the farmer's circular AnalysisRegion, preserved 1:1 without artificial rounding or scaling.
    """

    water: float = Field(..., ge=0.0, le=1.0, description="Probability of open surface water, rivers, lakes, canals")
    trees: float = Field(..., ge=0.0, le=1.0, description="Probability of tree canopy, agroforestry, orchards, woodlands")
    grass: float = Field(..., ge=0.0, le=1.0, description="Probability of natural grassland, pastures, rangeland, turf")
    flooded_vegetation: float = Field(..., ge=0.0, le=1.0, description="Probability of inundated vegetation, marsh, flooded paddy")
    crops: float = Field(..., ge=0.0, le=1.0, description="Probability of cultivated agricultural cropland, standing crops")
    shrub_and_scrub: float = Field(..., ge=0.0, le=1.0, description="Probability of bushes, arid scrub, sparse woody vegetation")
    built: float = Field(..., ge=0.0, le=1.0, description="Probability of human structures, roads, farm buildings, paved surfaces")
    bare: float = Field(..., ge=0.0, le=1.0, description="Probability of exposed soil, sand, dry riverbeds, bare earth")
    snow_and_ice: float = Field(..., ge=0.0, le=1.0, description="Probability of snow, ice cover, glacial terrain")

    model_config = ConfigDict(frozen=True, extra="forbid")


class DynamicWorldAnalysis(BaseModel):
    """Complete environmental land-cover context envelope over the farmer's AnalysisRegion (DEC-021).

    Represents regional land-cover context derived from the single newest usable Dynamic World
    observation within the retrospective 30-day temporal window.
    """

    region: AnalysisRegionMetadata = Field(..., description="Spatial metadata of the analyzed circular region")
    requested_end_date: date = Field(..., description="Caller reference date anchoring the 30-day lookback window")
    observation_date: date | None = Field(default=None, description="Actual acquisition date of the selected Dynamic World image")
    observation_id: str | None = Field(default=None, description="GEE system:index of the selected observation for granule lineage")
    data_lag_days: int | None = Field(default=None, ge=0, description="Publication/acquisition latency: (requested_end_date - observation_date).days")
    dominant_class: DynamicWorldLandCoverClass | None = Field(default=None, description="Land-cover class possessing the highest regional mean probability")
    dominant_probability: float | None = Field(default=None, ge=0.0, le=1.0, description="Highest regional mean probability value")
    class_probabilities: DynamicWorldClassProbabilities | None = Field(default=None, description="Complete 9-class regional probability distribution")
    dataset: str = Field(default="GOOGLE/DYNAMICWORLD/V1", description="Canonical Earth Engine asset ID")
    spatial_resolution_m: float = Field(default=10.0, description="Native spatial resolution in meters")
    status: EarthEngineStatus = Field(default="success", description="Universal Earth Engine status (success, no_data, error)")
    pipeline_version: str = Field(default="3.1.0", description="Contract schema version")
    error: EarthEngineError | None = Field(default=None, description="Structured error payload populated when status is error")

    model_config = ConfigDict(frozen=True, extra="forbid")
