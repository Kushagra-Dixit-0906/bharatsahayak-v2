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
    calculate_ndvi_statistics,
    compute_ndvi,
    compute_ndvi_statistics,
)
from .pipeline import (
    STATISTICAL_INVARIANT_EPSILON,
    analyze_regional_ndvi,
)
from .historical import (
    DEFAULT_HISTORICAL_MAX_OBSERVATIONS,
    select_historical_observations,
)
from .sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    SENTINEL2_SR_HARMONIZED,
    calculate_usable_coverage,
    get_most_recent_sentinel2_image,
    get_sentinel2_collection,
    mask_observation_quality,
    resolve_date_range,
    select_most_recent_sentinel2_image,
)
from .temporal import (
    DEFAULT_HISTORICAL_YEARS,
    DEFAULT_WINDOW_HALF_DAYS,
    calculate_historical_target_years,
    construct_historical_temporal_window,
    parse_utc_date,
)
from .types import (
    AnalysisRegionMetadata,
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    EarthEngineResult,
    EarthEngineStatus,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    SatelliteAnnualHistoricalNdviObservation,
    SatelliteError,
    SatelliteFreshness,
    SatelliteHistoricalObservationSummary,
    SatelliteImageMetadata,
    SatelliteQualityEvidence,
    SatelliteRegionMetadata,
    SatelliteRegionalAnalysis,
    SatelliteRegionalStatistics,
    SatelliteResult,
    SatelliteStatus,
    SatelliteTemporalWindow,
    Sentinel2ImageMetadata,
)

__all__ = [
    "CLOUD_SCORE_PLUS_S2_HARMONIZED",
    "DEFAULT_ANALYSIS_RADIUS_M",
    "DEFAULT_CLEAR_THRESHOLD",
    "DEFAULT_HISTORICAL_MAX_OBSERVATIONS",
    "DEFAULT_HISTORICAL_YEARS",
    "DEFAULT_LOOKBACK_DAYS",
    "DEFAULT_MAX_CLOUD_PERCENTAGE",
    "DEFAULT_MIN_USABLE_COVERAGE",
    "DEFAULT_QUALITY_BAND",
    "DEFAULT_WINDOW_HALF_DAYS",
    "NDVI_BAND_NAME",
    "NIR_BAND",
    "RED_BAND",
    "SENTINEL2_SR_HARMONIZED",
    "STATISTICAL_INVARIANT_EPSILON",
    "analyze_regional_ndvi",
    "calculate_historical_target_years",
    "calculate_ndvi",
    "calculate_ndvi_statistics",
    "calculate_usable_coverage",
    "compute_ndvi",
    "compute_ndvi_statistics",
    "construct_historical_temporal_window",
    "create_analysis_region",
    "get_most_recent_sentinel2_image",
    "get_sentinel2_collection",
    "mask_observation_quality",
    "parse_utc_date",
    "resolve_date_range",
    "select_historical_observations",
    "select_most_recent_sentinel2_image",
    "AnalysisRegionMetadata",
    "AnnualHistoricalNdviObservation",
    "EarthEngineError",
    "EarthEngineResult",
    "EarthEngineStatus",
    "HistoricalObservationSummary",
    "HistoricalTemporalWindow",
    "NdviRegionalStatistics",
    "ObservationFreshness",
    "ObservationQualityEvidence",
    "RegionalNdviAnalysis",
    "SatelliteAnnualHistoricalNdviObservation",
    "SatelliteError",
    "SatelliteFreshness",
    "SatelliteHistoricalObservationSummary",
    "SatelliteImageMetadata",
    "SatelliteQualityEvidence",
    "SatelliteRegionMetadata",
    "SatelliteRegionalAnalysis",
    "SatelliteRegionalStatistics",
    "SatelliteResult",
    "SatelliteStatus",
    "SatelliteTemporalWindow",
    "Sentinel2ImageMetadata",
]
