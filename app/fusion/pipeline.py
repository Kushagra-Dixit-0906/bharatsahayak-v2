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
"""Root orchestration pipeline for multi-source evidence fusion (DEC-022).

This module coordinates the sequential execution of all remote-sensing and environmental
intelligence pipelines:
1. Sentinel-2 current regional NDVI (Phase 1)
2. Historical multi-year seasonal NDVI (Phase 2, reusing Phase 1 output without redundant queries)
3. ERA5-Land daily reanalysis (Phase 3A)
4. CHIRPS daily precipitation (Phase 3B)
5. Dynamic World 9-class land cover (Phase 3C)
6. Pure fusion assembly (Phase 4)
"""

from datetime import date, datetime, timezone
import math
from typing import Union

from app.environment.chirps_pipeline import analyze_chirps_rainfall
from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_pipeline import analyze_dynamic_world_land_cover
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.pipeline import analyze_era5_land
from app.environment.types import ERA5LandAnalysis
from app.fusion.fusion import fuse_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.geometry import DEFAULT_ANALYSIS_RADIUS_M, create_analysis_region
from app.satellite.historical import (
    DEFAULT_HISTORICAL_YEARS,
    DEFAULT_WINDOW_HALF_DAYS,
    analyze_historical_years,
)
from app.satellite.historical_analysis import build_historical_ndvi_analysis
from app.satellite.pipeline import analyze_regional_ndvi
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    HistoricalNdviAnalysis,
    HistoricalSufficiencyEvidence,
    RegionalNdviAnalysis,
)


def _resolve_reference_date(reference_date: Union[date, str, datetime, None]) -> date:
    """Resolves and validates the query reference date parameter."""
    if reference_date is None:
        return datetime.now(timezone.utc).date()
    if isinstance(reference_date, datetime):
        return reference_date.date()
    if isinstance(reference_date, date):
        return reference_date
    if isinstance(reference_date, str):
        cleaned = reference_date.strip()
        if "T" in cleaned:
            cleaned = cleaned.split("T")[0]
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid reference_date format '{reference_date}', expected 'YYYY-MM-DD' or ISO 8601 string."
            ) from exc
    raise TypeError(f"Unsupported reference_date type {type(reference_date)!r}: {reference_date!r}")


def fetch_agricultural_environmental_evidence(
    latitude: float,
    longitude: float,
    reference_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    ndvi_lookback_days: int = 30,
    history_years: int = DEFAULT_HISTORICAL_YEARS,
    window_half_days: int = DEFAULT_WINDOW_HALF_DAYS,
    reanalysis_lookback_days: int = 90,
    rainfall_lookback_days: int = 90,
    land_cover_lookback_days: int = 30,
) -> AgriculturalEnvironmentalEvidence:
    """Orchestrates multi-source remote sensing and environmental evidence retrieval and fusion.

    Executes source pipelines sequentially with strict fault isolation, reuses Phase 1 current
    NDVI domain objects when invoking Phase 2 historical analysis, and produces an immutable,
    strongly typed AgriculturalEnvironmentalEvidence domain envelope (DEC-022).

    Args:
        latitude: Target center latitude coordinate [-90.0, 90.0].
        longitude: Target center longitude coordinate [-180.0, 180.0].
        reference_date: Anchor query reference date (UTC). Defaults to current UTC date.
        radius_m: Circular analysis region radius in meters (default 100.0m).
        ndvi_lookback_days: Retrospective lookback window for Sentinel-2 NDVI (default 30 days).
        history_years: Number of historical target years for seasonal NDVI baseline (default 3).
        window_half_days: Half-width of historical seasonal matching window (default 15 days).
        reanalysis_lookback_days: Retrospective window for ERA5-Land (default 90 days).
        rainfall_lookback_days: Retrospective window for CHIRPS rainfall (default 90 days).
        land_cover_lookback_days: Retrospective window for Dynamic World land cover (default 30 days).

    Returns:
        AgriculturalEnvironmentalEvidence: Unified, validated multi-source evidence payload.

    Raises:
        TypeError: If coordinates or radius are invalid types.
        ValueError: If coordinates, radius, or dates are out of physical bounds.
    """
    # 1. Parameter Validation
    if not isinstance(latitude, (int, float)) or isinstance(latitude, bool):
        raise TypeError(f"Latitude must be a valid number, got {latitude!r}")
    if math.isnan(latitude) or math.isinf(latitude) or not (-90.0 <= float(latitude) <= 90.0):
        raise ValueError(f"Latitude must be between -90 and 90 degrees, got {latitude}")

    if not isinstance(longitude, (int, float)) or isinstance(longitude, bool):
        raise TypeError(f"Longitude must be a valid number, got {longitude!r}")
    if math.isnan(longitude) or math.isinf(longitude) or not (-180.0 <= float(longitude) <= 180.0):
        raise ValueError(f"Longitude must be between -180 and 180 degrees, got {longitude}")

    if not isinstance(radius_m, (int, float)) or isinstance(radius_m, bool):
        raise TypeError(f"Radius must be a valid number, got {radius_m!r}")
    if math.isnan(radius_m) or math.isinf(radius_m) or radius_m <= 0.0:
        raise ValueError(f"Radius must be strictly positive (> 0), got {radius_m}")

    resolved_ref_date = _resolve_reference_date(reference_date)

    region_metadata = AnalysisRegionMetadata(
        latitude=float(latitude),
        longitude=float(longitude),
        radius_m=float(radius_m),
        geometry_type="PointBuffer",
        scale_m=10.0,
    )

    # 2. Sequential Pipeline Execution with Fault Isolation

    # Source 1 & 2: Vegetation (Sentinel-2 Current NDVI + Historical Baseline)
    vegetation: HistoricalNdviAnalysis
    try:
        current_res = analyze_regional_ndvi(
            latitude=float(latitude),
            longitude=float(longitude),
            radius_m=float(radius_m),
            end_date=resolved_ref_date.isoformat(),
            lookback_days=ndvi_lookback_days,
        )

        if current_res.status == "success" and isinstance(current_res.data, RegionalNdviAnalysis):
            ee_region = create_analysis_region(
                latitude=float(latitude),
                longitude=float(longitude),
                radius_m=float(radius_m),
            )
            hist_obs = analyze_historical_years(
                region=ee_region,
                reference_date=current_res.data,
                history_years=history_years,
                window_half_days=window_half_days,
            )
            vegetation = build_historical_ndvi_analysis(
                current=current_res.data,
                historical_observations=hist_obs,
                requested_years_count=history_years,
            )
        else:
            # Phase 1 failed or no data: propagate directly without executing historical queries
            vegetation = build_historical_ndvi_analysis(
                current=current_res,
                historical_observations=[],
                requested_years_count=history_years,
            )
    except Exception as exc:
        missing_years = [resolved_ref_date.year - i for i in range(1, history_years + 1)]
        vegetation = HistoricalNdviAnalysis(
            current=None,
            historical_observations=[],
            baseline=None,
            sufficiency=HistoricalSufficiencyEvidence(
                requested_years_count=history_years,
                represented_years_count=0,
                minimum_required_years=2,
                is_sufficient=False,
                represented_years=[],
                missing_years=missing_years,
            ),
            anomaly=None,
            status="error",
            pipeline_version="2.0.0",
            error=EarthEngineError(type=exc.__class__.__name__, message=str(exc)),
        )

    # Source 3: ERA5-Land Daily Reanalysis
    reanalysis: ERA5LandAnalysis
    try:
        reanalysis = analyze_era5_land(
            latitude=float(latitude),
            longitude=float(longitude),
            requested_end_date=resolved_ref_date,
            radius_m=float(radius_m),
            lookback_days=reanalysis_lookback_days,
        )
    except Exception as exc:
        reanalysis = ERA5LandAnalysis(
            region=region_metadata,
            requested_end_date=resolved_ref_date,
            dataset="ECMWF/ERA5_LAND/DAILY_AGGR",
            spatial_resolution_km=11.1,
            status="error",
            pipeline_version="3.0.0",
            error=EarthEngineError(type=exc.__class__.__name__, message=str(exc)),
        )

    # Source 4: CHIRPS Daily Precipitation
    rainfall: CHIRPSRainfallAnalysis
    try:
        rainfall = analyze_chirps_rainfall(
            latitude=float(latitude),
            longitude=float(longitude),
            requested_end_date=resolved_ref_date,
            radius_m=float(radius_m),
            lookback_days=rainfall_lookback_days,
        )
    except Exception as exc:
        rainfall = CHIRPSRainfallAnalysis(
            region=region_metadata,
            requested_end_date=resolved_ref_date,
            dataset="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
            spatial_resolution_km=5.566,
            status="error",
            pipeline_version="3.1.0",
            error=EarthEngineError(type=exc.__class__.__name__, message=str(exc)),
        )

    # Source 5: Dynamic World Land-Cover Context
    land_cover: DynamicWorldAnalysis
    try:
        land_cover = analyze_dynamic_world_land_cover(
            latitude=float(latitude),
            longitude=float(longitude),
            requested_end_date=resolved_ref_date,
            radius_m=float(radius_m),
            lookback_days=land_cover_lookback_days,
        )
    except Exception as exc:
        land_cover = DynamicWorldAnalysis(
            region=region_metadata,
            requested_end_date=resolved_ref_date,
            dataset="GOOGLE/DYNAMICWORLD/V1",
            spatial_resolution_m=10.0,
            status="error",
            pipeline_version="3.1.0",
            error=EarthEngineError(type=exc.__class__.__name__, message=str(exc)),
        )

    # 3. Pure Assembly & Status Resolution
    return fuse_agricultural_environmental_evidence(
        reference_date=resolved_ref_date,
        region=region_metadata,
        vegetation=vegetation,
        reanalysis=reanalysis,
        rainfall=rainfall,
        land_cover=land_cover,
    )
