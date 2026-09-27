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
"""Pure Python normalization and root orchestration for CHIRPS rainfall intelligence (Phase 3B, DEC-020).

This module implements Tier 2 and Tier 3 of the Phase 3B architecture:
- Tier 2 (Pure Normalization): Converts raw Earth Engine property dictionaries into normalized
  DailyRainfallObservation domain models. Preserves native mm/day values 1:1 without scaling,
  rounding, or clamping. Enforces strict missing != zero semantics and rejects negative
  precipitation artifacts without clamping.
- Tier 3 (Root Orchestration): Coordinates Tier 1 Earth Engine retrieval (via app.environment.chirps),
  Tier 2 normalization, dynamic publication data lag derivation, pure rainfall window aggregation,
  and CHIRPSRainfallAnalysis envelope construction.
- Architectural Boundary: This module contains NO direct Earth Engine imports (ee), network calls,
  or getInfo() evaluations.
"""

from datetime import date, datetime, timezone
import math
from typing import Any, Union

from app.environment.chirps import (
    CHIRPS_DATASET,
    DEFAULT_LOOKBACK_DAYS,
    fetch_raw_chirps_rainfall_timeseries,
)
from app.environment.chirps_aggregation import compute_rainfall_window_suite
from app.environment.chirps_types import (
    CHIRPSRainfallAnalysis,
    DailyRainfallObservation,
)
from app.satellite.geometry import (
    DEFAULT_ANALYSIS_RADIUS_M,
    create_analysis_region,
)
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
)


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


def normalize_raw_chirps_record(record: dict[str, Any]) -> DailyRainfallObservation | None:
    """Normalizes a raw CHIRPS property dictionary into a DailyRainfallObservation (DEC-020).

    Unit preservation:
        - Precipitation: CHIRPS precipitation is already in mm/day.
        - Preserved 1:1 without scaling, rounding, or clamping.

    Semantic invariants:
        - Strict missing != zero: Missing/null precipitation remains None.
        - Negative values (< 0.0 mm) from GEE packing artifacts are rejected (set to None),
          never clamped to 0.0.
        - Explicit 0.0 remains 0.0.

    Args:
        record: Raw property dictionary from Earth Engine reduction or offline fixture.

    Returns:
        DailyRainfallObservation if observation_date is valid, otherwise None.
    """
    if not isinstance(record, dict):
        return None

    obs_date = _parse_observation_date(record)
    if obs_date is None:
        return None

    precip_mm: float | None = None
    if "precipitation" in record and _is_valid_numeric(record["precipitation"]):
        val = float(record["precipitation"])
        if val >= 0.0:
            precip_mm = val
        else:
            # Negative packing artifact rejected to None without clamping
            precip_mm = None
    elif "precipitation_mm" in record and _is_valid_numeric(record["precipitation_mm"]):
        val = float(record["precipitation_mm"])
        if val >= 0.0:
            precip_mm = val
        else:
            precip_mm = None

    return DailyRainfallObservation(
        observation_date=obs_date,
        precipitation_mm=precip_mm,
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


def analyze_chirps_rainfall(
    latitude: float,
    longitude: float,
    requested_end_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    dataset: str = CHIRPS_DATASET,
) -> CHIRPSRainfallAnalysis:
    """Orchestrates CHIRPS daily precipitation intelligence over the farmer's AnalysisRegion (DEC-020).

    Coordinates:
        1. Spatial region and temporal boundary validation.
        2. Tier 1 Earth Engine timeseries retrieval (via app.environment.chirps).
        3. Tier 2 pure normalization & missing/negative artifact filtering.
        4. Dynamic derivation of latest_available_date and data_lag_days.
        5. Pure rolling window aggregation across 7-day, 30-day, and 90-day envelopes.
        6. Domain payload assembly with status resolution (success | no_data | error).

    Args:
        latitude: Geographic latitude in decimal degrees [-90.0, 90.0].
        longitude: Geographic longitude in decimal degrees [-180.0, 180.0].
        requested_end_date: Reference/anchor date (UTC). Defaults to current UTC date.
        radius_m: Analysis buffer radius in meters (default 100.0m).
        lookback_days: Retrospective lookback window in days (default 90).
        dataset: GEE dataset asset ID (default 'UCSB-CHC/CHIRPS/V3/DAILY_SAT').

    Returns:
        CHIRPSRainfallAnalysis containing normalized daily observations and 7/30/90-day window statistics.

    Raises:
        TypeError: If latitude, longitude, or radius_m are not valid finite numbers.
        ValueError: If coordinates, radius, or dates are invalid or out of bounds.
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

    region_meta = AnalysisRegionMetadata(
        latitude=float(latitude),
        longitude=float(longitude),
        radius_m=float(radius_m),
        geometry_type="PointBuffer",
        scale_m=10.0,
    )

    # 2. Tier 1 Earth Engine Retrieval
    ee_result = fetch_raw_chirps_rainfall_timeseries(
        region=region_meta,
        requested_end_date=resolved_end_date,
        lookback_days=lookback_days,
        dataset=dataset,
    )

    # 4. Handle Earth Engine error status
    if ee_result.status == "error":
        return CHIRPSRainfallAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            status="error",
            error=ee_result.error or EarthEngineError(type="EEException", message="Unknown GEE error"),
        )

    # 5. Handle empty / no_data response
    if ee_result.status == "no_data" or not ee_result.data:
        return CHIRPSRainfallAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            status="no_data",
            latest_available_date=None,
            data_lag_days=None,
            recent_7_days=None,
            recent_30_days=None,
            recent_90_days=None,
            daily_observations=[],
        )

    # 6. Normalize records through Tier 2
    raw_list = ee_result.data if isinstance(ee_result.data, list) else []
    daily_obs_map: dict[date, DailyRainfallObservation] = {}

    for item in raw_list:
        if isinstance(item, dict):
            normalized = normalize_raw_chirps_record(item)
            if normalized is not None:
                # Deduplicate by observation_date (latest record wins if duplicates in raw response)
                daily_obs_map[normalized.observation_date] = normalized

    if not daily_obs_map:
        return CHIRPSRainfallAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            status="no_data",
            latest_available_date=None,
            data_lag_days=None,
            recent_7_days=None,
            recent_30_days=None,
            recent_90_days=None,
            daily_observations=[],
        )

    # Sort chronological ascending
    sorted_obs = sorted(daily_obs_map.values(), key=lambda o: o.observation_date)

    # 7. Dynamically derive latest_available_date and publication data lag
    valid_obs_with_data = [obs for obs in sorted_obs if obs.precipitation_mm is not None]
    if valid_obs_with_data:
        latest_date = max(obs.observation_date for obs in valid_obs_with_data)
    else:
        latest_date = max(obs.observation_date for obs in sorted_obs)

    # Guard against future dates relative to requested_end_date
    if latest_date > resolved_end_date:
        return CHIRPSRainfallAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            status="error",
            error=EarthEngineError(
                type="DataIntegrityError",
                message=f"latest_available_date ({latest_date}) is in the future relative to requested_end_date ({resolved_end_date})",
            ),
        )

    data_lag = (resolved_end_date - latest_date).days

    # 8. Compute rolling rainfall window statistics
    try:
        r7, r30, r90 = compute_rainfall_window_suite(sorted_obs, resolved_end_date)
    except Exception as exc:
        return CHIRPSRainfallAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            status="error",
            error=EarthEngineError(
                type=exc.__class__.__name__,
                message=f"Failed to compute rainfall window statistics: {exc}",
            ),
        )

    return CHIRPSRainfallAnalysis(
        region=region_meta,
        requested_end_date=resolved_end_date,
        latest_available_date=latest_date,
        data_lag_days=data_lag,
        recent_7_days=r7,
        recent_30_days=r30,
        recent_90_days=r90,
        daily_observations=sorted_obs,
        dataset=dataset,
        spatial_resolution_km=5.566,
        status="success",
        pipeline_version="3.1.0",
        error=None,
    )
