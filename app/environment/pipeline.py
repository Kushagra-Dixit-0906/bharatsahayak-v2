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
"""Pure Python normalization and root orchestration for ERA5-Land environmental intelligence (Phase 3A, DEC-019).

This module implements Tier 2 and Tier 3 of the Phase 3A architecture:
- Tier 2 (Pure Normalization): Converts raw Earth Engine property dictionaries into normalized
  DailyEnvironmentalObservation domain models. Applies Kelvin -> Celsius, meters -> millimeters,
  and dimensionless soil water preservation. Enforces strict missing != zero semantics and rejects
  negative precipitation/runoff artifacts without clamping.
- Tier 3 (Root Orchestration): Coordinates Tier 1 Earth Engine retrieval (via app.environment.era5),
  Tier 2 normalization, dynamic publication data lag derivation, Step 2 window aggregation,
  and ERA5LandAnalysis envelope construction.
- Architectural Boundary: This module is pure Python and contains NO Earth Engine imports (ee),
  network calls, or direct getInfo() evaluations.
"""

from datetime import date, datetime, timezone
import math
from typing import Any, Union

from app.environment.aggregation import compute_environmental_window_suite
from app.environment.era5 import DEFAULT_LOOKBACK_DAYS, fetch_raw_era5_land_timeseries
from app.environment.types import (
    DailyEnvironmentalObservation,
    ERA5LandAnalysis,
)
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
)

# Default radius in meters for the circular analysis region (DEC-007 / DEC-019)
DEFAULT_ANALYSIS_RADIUS_M: float = 100.0


def _is_valid_numeric(val: Any) -> bool:
    """Checks if a value is a valid, finite float or int (and not a boolean)."""
    if val is None or isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    if math.isnan(val) or math.isinf(val):
        return False
    return True


def _parse_observation_date(record: dict[str, Any]) -> date | None:
    """Extracts and parses the observation date from a raw record dictionary.

    Supports 'observation_date' (ISO string or date object) or 'system:time_start' (UTC timestamp in ms).
    """
    raw_date = record.get("observation_date")
    if raw_date is not None:
        if isinstance(raw_date, date) and not isinstance(raw_date, datetime):
            return raw_date
        if isinstance(raw_date, datetime):
            return raw_date.date()
        if isinstance(raw_date, str):
            cleaned = raw_date.strip()
            if "T" in cleaned:
                cleaned = cleaned.split("T")[0]
            try:
                return datetime.strptime(cleaned, "%Y-%m-%d").date()
            except ValueError:
                return None

    # Fallback to system:time_start if present
    time_start = record.get("system:time_start")
    if _is_valid_numeric(time_start):
        try:
            return datetime.fromtimestamp(float(time_start) / 1000.0, tz=timezone.utc).date()
        except (ValueError, OSError):
            return None

    return None


def normalize_raw_era5_record(record: dict[str, Any]) -> DailyEnvironmentalObservation | None:
    """Normalizes a raw ERA5-Land property dictionary into a DailyEnvironmentalObservation (DEC-019).

    Unit conversions:
        - Temperature: Kelvin (temperature_2m) - 273.15 -> Celsius (°C)
        - Precipitation: meters (total_precipitation_sum) * 1000.0 -> millimeters (mm)
        - Runoff: meters (runoff_sum) * 1000.0 -> millimeters (mm)
        - Soil Water: volumetric_soil_water_layer_1 (m³/m³) unchanged

    Semantic invariants:
        - Strict missing != zero: Missing/null variables remain None.
        - Negative values for precipitation and runoff are invalid artifacts and are rejected (set to None),
          never clamped to 0.0.
        - Soil water must be in [0.0, 1.0]; values outside this range are rejected (set to None).
        - Temperature must be in [-100.0, 100.0] °C; values outside this range are rejected (set to None).

    Args:
        record: Raw property dictionary from Earth Engine reduction or offline fixture.

    Returns:
        DailyEnvironmentalObservation if observation_date is valid, otherwise None.
    """
    if not isinstance(record, dict):
        return None

    obs_date = _parse_observation_date(record)
    if obs_date is None:
        return None

    # 1. Temperature conversion (K -> °C)
    temp_c: float | None = None
    if "temperature_2m" in record and _is_valid_numeric(record["temperature_2m"]):
        converted = float(record["temperature_2m"]) - 273.15
        if -100.0 <= converted <= 100.0:
            temp_c = converted
    elif "temperature_c" in record and _is_valid_numeric(record["temperature_c"]):
        val = float(record["temperature_c"])
        if -100.0 <= val <= 100.0:
            temp_c = val

    # 2. Precipitation conversion (m -> mm)
    precip_mm: float | None = None
    if "total_precipitation_sum" in record and _is_valid_numeric(record["total_precipitation_sum"]):
        val_m = float(record["total_precipitation_sum"])
        if val_m >= 0.0:
            precip_mm = val_m * 1000.0
        # Negative values are invalid artifacts; do NOT clamp to 0.0, remain None.
    elif "precipitation_mm" in record and _is_valid_numeric(record["precipitation_mm"]):
        val = float(record["precipitation_mm"])
        if val >= 0.0:
            precip_mm = val

    # 3. Volumetric soil water layer 1 (m³/m³)
    soil_water: float | None = None
    if "volumetric_soil_water_layer_1" in record and _is_valid_numeric(record["volumetric_soil_water_layer_1"]):
        val_sw = float(record["volumetric_soil_water_layer_1"])
        if 0.0 <= val_sw <= 1.0:
            soil_water = val_sw

    # 4. Runoff conversion (m -> mm)
    runoff_mm: float | None = None
    if "runoff_sum" in record and _is_valid_numeric(record["runoff_sum"]):
        val_rm = float(record["runoff_sum"])
        if val_rm >= 0.0:
            runoff_mm = val_rm * 1000.0
        # Negative values are invalid artifacts; do NOT clamp to 0.0, remain None.
    elif "runoff_sum_mm" in record and _is_valid_numeric(record["runoff_sum_mm"]):
        val = float(record["runoff_sum_mm"])
        if val >= 0.0:
            runoff_mm = val
    elif "runoff_mm" in record and _is_valid_numeric(record["runoff_mm"]):
        val = float(record["runoff_mm"])
        if val >= 0.0:
            runoff_mm = val


    return DailyEnvironmentalObservation(
        observation_date=obs_date,
        temperature_c=temp_c,
        precipitation_mm=precip_mm,
        volumetric_soil_water_layer_1=soil_water,
        runoff_sum_mm=runoff_mm,
    )


def _resolve_requested_date(requested_end_date: Union[date, str, datetime, None]) -> date:
    """Resolves and validates the requested end date parameter."""
    if requested_end_date is None:
        return datetime.now(timezone.utc).date()
    if isinstance(requested_end_date, datetime):
        return requested_end_date.date()
    if isinstance(requested_end_date, date):
        return requested_end_date
    if isinstance(requested_end_date, str):
        cleaned = requested_end_date.strip()
        if "T" in cleaned:
            cleaned = cleaned.split("T")[0]
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid requested_end_date format '{requested_end_date}', expected 'YYYY-MM-DD' or ISO 8601 string."
            ) from exc
    raise TypeError(f"Unsupported requested_end_date type {type(requested_end_date)!r}: {requested_end_date!r}")


def analyze_era5_land(
    latitude: float,
    longitude: float,
    requested_end_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> ERA5LandAnalysis:
    """Executes the complete ERA5-Land environmental analysis pipeline (Phase 3A, DEC-019).

    Coordinates:
        1. Spatial region and temporal boundary validation.
        2. Tier 1 Earth Engine reanalysis data retrieval over [requested_end_date - 89d, requested_end_date].
        3. Tier 2 pure unit normalization and missing-value handling.
        4. Dynamic publication data lag calculation from empirical observations.
        5. Step 2 multi-window statistical aggregation (7-day, 30-day, 90-day).
        6. Packaging of authoritative ERA5LandAnalysis domain payload.

    Args:
        latitude: Latitude coordinate in decimal degrees [-90.0, 90.0].
        longitude: Longitude coordinate in decimal degrees [-180.0, 180.0].
        requested_end_date: Anchor query end date (default current UTC date).
        radius_m: Circular buffer radius in meters (default 100.0 m).
        lookback_days: Total retrospective calendar days to query (default 90 days).

    Returns:
        ERA5LandAnalysis containing normalized observations, window statistics, and metadata.

    Raises:
        TypeError: If latitude, longitude, or radius_m are not valid finite numbers.
        ValueError: If coordinates or radius are out of bounds.
    """
    # 1. Spatial and parameter validation
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
    if math.isnan(radius_m) or math.isinf(radius_m) or float(radius_m) <= 0.0:
        raise ValueError(f"Radius must be strictly positive (> 0), got {radius_m}")

    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or lookback_days <= 0:
        raise ValueError(f"lookback_days must be a strictly positive integer (> 0), got {lookback_days!r}")

    resolved_end_date = _resolve_requested_date(requested_end_date)

    region_metadata = AnalysisRegionMetadata(
        latitude=float(latitude),
        longitude=float(longitude),
        radius_m=float(radius_m),
        geometry_type="PointBuffer",
        scale_m=10.0,
    )

    # 2. Tier 1 Earth Engine Retrieval
    ee_result = fetch_raw_era5_land_timeseries(
        region=region_metadata,
        requested_end_date=resolved_end_date,
        lookback_days=lookback_days,
    )

    # 3. Handle Error and No-Data status states
    if ee_result.status == "error":
        return ERA5LandAnalysis(
            region=region_metadata,
            requested_end_date=resolved_end_date,
            latest_available_date=None,
            data_lag_days=None,
            recent_7_days=None,
            recent_30_days=None,
            recent_90_days=None,
            daily_observations=[],
            dataset="ECMWF/ERA5_LAND/DAILY_AGGR",
            spatial_resolution_km=11.1,
            status="error",
            pipeline_version="3.0.0",
            error=ee_result.error or EarthEngineError(type="UnknownError", message="Earth Engine retrieval failed"),
        )

    if ee_result.status == "no_data" or not ee_result.data:
        return ERA5LandAnalysis(
            region=region_metadata,
            requested_end_date=resolved_end_date,
            latest_available_date=None,
            data_lag_days=None,
            recent_7_days=None,
            recent_30_days=None,
            recent_90_days=None,
            daily_observations=[],
            dataset="ECMWF/ERA5_LAND/DAILY_AGGR",
            spatial_resolution_km=11.1,
            status="no_data",
            pipeline_version="3.0.0",
            error=None,
        )

    # 4. Tier 2 Normalization
    normalized_observations: list[DailyEnvironmentalObservation] = []
    for raw_record in ee_result.data:
        obs = normalize_raw_era5_record(raw_record)
        if obs is not None:
            normalized_observations.append(obs)

    if not normalized_observations:
        return ERA5LandAnalysis(
            region=region_metadata,
            requested_end_date=resolved_end_date,
            latest_available_date=None,
            data_lag_days=None,
            recent_7_days=None,
            recent_30_days=None,
            recent_90_days=None,
            daily_observations=[],
            dataset="ECMWF/ERA5_LAND/DAILY_AGGR",
            spatial_resolution_km=11.1,
            status="no_data",
            pipeline_version="3.0.0",
            error=None,
        )

    # Chronological sort
    normalized_observations.sort(key=lambda x: x.observation_date)

    # 5. Dynamic Publication Data Lag
    latest_available_date = max(obs.observation_date for obs in normalized_observations)
    data_lag_days = max(0, (resolved_end_date - latest_available_date).days)

    # 6. Step 2 Multi-Window Aggregation
    recent_7, recent_30, recent_90 = compute_environmental_window_suite(
        observations=normalized_observations,
        end_date=resolved_end_date,
    )

    # 7. Construct Authoritative Payload
    return ERA5LandAnalysis(
        region=region_metadata,
        requested_end_date=resolved_end_date,
        latest_available_date=latest_available_date,
        data_lag_days=data_lag_days,
        recent_7_days=recent_7,
        recent_30_days=recent_30,
        recent_90_days=recent_90,
        daily_observations=normalized_observations,
        dataset="ECMWF/ERA5_LAND/DAILY_AGGR",
        spatial_resolution_km=11.1,
        status="success",
        pipeline_version="3.0.0",
        error=None,
    )
