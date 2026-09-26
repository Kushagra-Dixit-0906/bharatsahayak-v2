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
"""Type definitions and result contracts for satellite and Earth Engine operations."""

from typing import Any, Literal

from pydantic import BaseModel, Field

EarthEngineStatus = Literal["success", "no_data", "error"]
SatelliteStatus = EarthEngineStatus


class EarthEngineError(BaseModel):
    """Structured error details for Earth Engine operations."""

    type: str
    message: str


SatelliteError = EarthEngineError


class Sentinel2ImageMetadata(BaseModel):
    """Structured metadata for a selected Sentinel-2 satellite observation."""

    image_id: str
    acquisition_date: str
    cloud_percentage: float = Field(ge=0.0, le=100.0)
    spacecraft_name: str | None = None
    mgrs_tile: str | None = None
    product_id: str | None = None
    system_time_start: int | None = None
    usable_coverage_percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    clear_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_band: str | None = None


SatelliteImageMetadata = Sentinel2ImageMetadata


class NdviRegionalStatistics(BaseModel):
    """Structured regional summary statistics for NDVI over an AnalysisRegion."""

    mean: float = Field(ge=-1.0, le=1.0)
    median: float = Field(ge=-1.0, le=1.0)
    min: float = Field(ge=-1.0, le=1.0)
    max: float = Field(ge=-1.0, le=1.0)
    valid_pixel_count: int | None = Field(default=None, ge=0)


SatelliteRegionalStatistics = NdviRegionalStatistics


class EarthEngineResult(BaseModel):
    """Minimal result contract for Earth Engine operations."""

    status: EarthEngineStatus
    dataset: str | None = None
    image_count: int | None = Field(default=None, ge=0)
    data: Any | None = None
    error: EarthEngineError | None = None


SatelliteResult = EarthEngineResult
