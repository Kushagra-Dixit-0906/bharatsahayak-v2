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
"""Satellite and Earth Engine modules for BharatSahayak."""

from .geometry import (
    DEFAULT_ANALYSIS_RADIUS_M,
    create_analysis_region,
)
from .ndvi import (
    NDVI_BAND_NAME,
    NIR_BAND,
    RED_BAND,
    calculate_ndvi,
    compute_ndvi,
)
from .sentinel2 import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    SENTINEL2_SR_HARMONIZED,
    get_most_recent_sentinel2_image,
    get_sentinel2_collection,
    resolve_date_range,
    select_most_recent_sentinel2_image,
)
from .types import (
    EarthEngineError,
    EarthEngineResult,
    EarthEngineStatus,
    SatelliteError,
    SatelliteImageMetadata,
    SatelliteResult,
    SatelliteStatus,
    Sentinel2ImageMetadata,
)

__all__ = [
    "DEFAULT_ANALYSIS_RADIUS_M",
    "DEFAULT_LOOKBACK_DAYS",
    "DEFAULT_MAX_CLOUD_PERCENTAGE",
    "NDVI_BAND_NAME",
    "NIR_BAND",
    "RED_BAND",
    "SENTINEL2_SR_HARMONIZED",
    "calculate_ndvi",
    "compute_ndvi",
    "create_analysis_region",
    "get_most_recent_sentinel2_image",
    "get_sentinel2_collection",
    "resolve_date_range",
    "select_most_recent_sentinel2_image",
    "EarthEngineError",
    "EarthEngineResult",
    "EarthEngineStatus",
    "SatelliteError",
    "SatelliteImageMetadata",
    "SatelliteResult",
    "SatelliteStatus",
    "Sentinel2ImageMetadata",
]
