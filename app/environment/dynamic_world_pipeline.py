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
"""Pure Python normalization and root orchestration for Dynamic World Land-Cover Context (Phase 3C, DEC-021).

This module implements Tier 2 and Tier 3 of the Phase 3C architecture:
- Tier 2 (Pure Normalization & Dominant Derivation):
  - Converts raw Earth Engine property dictionaries into normalized DynamicWorldClassProbabilities.
  - Preserves native continuous float probabilities 1:1 without scaling, rounding, clipping, or thresholds.
  - Computes the dominant land-cover class and dominant probability using deterministic canonical tie-breaking.
- Tier 3 (Root Orchestration):
  - Coordinates Tier 1 Earth Engine retrieval (via app.environment.dynamic_world), Tier 2 normalization,
    dynamic publication data lag derivation, and DynamicWorldAnalysis envelope assembly.
- Architectural Boundary: This module contains NO direct Earth Engine imports (ee), network calls,
  or getInfo() evaluations.
"""

from datetime import date, datetime, timezone
import math
from typing import Any, Union

from app.environment.dynamic_world import (
    DEFAULT_LOOKBACK_DAYS,
    DYNAMIC_WORLD_DATASET,
    DYNAMIC_WORLD_NOMINAL_SCALE_M,
    DYNAMIC_WORLD_PROBABILITY_BANDS,
    fetch_raw_dynamic_world_record,
)
from app.environment.dynamic_world_types import (
    CANONICAL_CLASS_PRECEDENCE,
    DynamicWorldAnalysis,
    DynamicWorldClassProbabilities,
    DynamicWorldLandCoverClass,
)
from app.satellite.geometry import (
    DEFAULT_ANALYSIS_RADIUS_M,
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


def _parse_observation_id(record: dict[str, Any]) -> str | None:
    """Extracts the observation ID / system:index string from the record if present."""
    obs_id = record.get("observation_id") or record.get("system:index") or record.get("id")
    if obs_id is not None and isinstance(obs_id, str) and obs_id.strip():
        return obs_id.strip()
    return None


def normalize_raw_dynamic_world_record(
    record: dict[str, Any],
) -> tuple[date, str | None, DynamicWorldClassProbabilities] | None:
    """Normalizes a raw Dynamic World property dictionary into domain models (DEC-021).

    Validation & Preservation Rules:
        - All 9 canonical probability bands must be present and finite floats in [0.0, 1.0].
        - Values are preserved 1:1 without artificial rounding, scaling, clipping, or thresholding.
        - Negative values or values > 1.0 are rejected (returns None).
        - Missing or non-numeric probability bands cause rejection (returns None).

    Args:
        record: Raw property dictionary from Earth Engine reduction or offline fixture.

    Returns:
        tuple of (observation_date, observation_id, DynamicWorldClassProbabilities) if valid,
        otherwise None.
    """
    if not isinstance(record, dict):
        return None

    obs_date = _parse_observation_date(record)
    if obs_date is None:
        return None

    obs_id = _parse_observation_id(record)

    prob_values: dict[str, float] = {}
    for band in DYNAMIC_WORLD_PROBABILITY_BANDS:
        if band not in record or not _is_valid_numeric(record[band]):
            return None
        val = float(record[band])
        if not (0.0 <= val <= 1.0):
            return None
        prob_values[band] = val

    try:
        class_probs = DynamicWorldClassProbabilities(
            water=prob_values["water"],
            trees=prob_values["trees"],
            grass=prob_values["grass"],
            flooded_vegetation=prob_values["flooded_vegetation"],
            crops=prob_values["crops"],
            shrub_and_scrub=prob_values["shrub_and_scrub"],
            built=prob_values["built"],
            bare=prob_values["bare"],
            snow_and_ice=prob_values["snow_and_ice"],
        )
        return obs_date, obs_id, class_probs
    except Exception:
        return None


def derive_dominant_land_cover(
    probs: DynamicWorldClassProbabilities,
) -> tuple[DynamicWorldLandCoverClass, float]:
    """Derives the dominant land-cover class and its probability using deterministic tie-breaking (DEC-021).

    The dominant class is the class possessing the maximum regional mean probability.
    Ties are broken deterministically using canonical GEE index ordering:
    water (0) > trees (1) > grass (2) > flooded_vegetation (3) > crops (4) >
    shrub_and_scrub (5) > built (6) > bare (7) > snow_and_ice (8).

    Args:
        probs: Validated 9-class regional probability distribution.

    Returns:
        tuple of (dominant_class, dominant_probability).
    """
    max_prob = -1.0
    dominant_class: DynamicWorldLandCoverClass = CANONICAL_CLASS_PRECEDENCE[0]

    for cls_name in CANONICAL_CLASS_PRECEDENCE:
        prob = getattr(probs, cls_name)
        if prob > max_prob:
            max_prob = prob
            dominant_class = cls_name

    return dominant_class, max_prob


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


def analyze_dynamic_world_land_cover(
    latitude: float,
    longitude: float,
    requested_end_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    dataset: str = DYNAMIC_WORLD_DATASET,
) -> DynamicWorldAnalysis:
    """Orchestrates Dynamic World land-cover context intelligence over the farmer's AnalysisRegion (DEC-021).

    Workflow:
        1. Validate coordinates, radius, lookback days, and requested end date.
        2. Tier 1: Query GEE collection, reduce 9 probability bands, filter usability server-side,
           and select the newest usable observation.
        3. Tier 2: Normalize probability values 1:1, validate bounds, derive dominant land cover,
           and compute publication latency dynamically.
        4. Assemble immutable DynamicWorldAnalysis envelope with preserved context metadata.

    Args:
        latitude: Target latitude in decimal degrees [-90.0, 90.0].
        longitude: Target longitude in decimal degrees [-180.0, 180.0].
        requested_end_date: Reference end date anchoring the 30-day retrospective window.
        radius_m: Circular buffer radius in meters (default 100.0m).
        lookback_days: Retrospective lookback window in calendar days (default 30 days).
        dataset: GEE dataset asset identifier (default 'GOOGLE/DYNAMICWORLD/V1').

    Returns:
        DynamicWorldAnalysis containing regional land-cover context, metadata, and status.

    Raises:
        TypeError: If coordinates or radius are invalid types.
        ValueError: If coordinates or radius are outside physical bounds.
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
        scale_m=DYNAMIC_WORLD_NOMINAL_SCALE_M,
    )

    # 2. Tier 1 Earth Engine Retrieval
    ee_result = fetch_raw_dynamic_world_record(
        region=region_meta,
        requested_end_date=resolved_end_date,
        lookback_days=lookback_days,
        dataset=dataset,
    )

    # 3. Handle Earth Engine error status
    if ee_result.status == "error":
        return DynamicWorldAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            spatial_resolution_m=DYNAMIC_WORLD_NOMINAL_SCALE_M,
            status="error",
            pipeline_version="3.1.0",
            error=ee_result.error or EarthEngineError(type="EEException", message="Unknown GEE error"),
        )

    # 4. Handle empty / no_data response
    if ee_result.status == "no_data" or not ee_result.data or not isinstance(ee_result.data, dict):
        return DynamicWorldAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            spatial_resolution_m=DYNAMIC_WORLD_NOMINAL_SCALE_M,
            status="no_data",
            pipeline_version="3.1.0",
            observation_date=None,
            observation_id=None,
            data_lag_days=None,
            dominant_class=None,
            dominant_probability=None,
            class_probabilities=None,
            error=None,
        )

    # 5. Normalize record through Tier 2
    normalized = normalize_raw_dynamic_world_record(ee_result.data)
    if normalized is None:
        return DynamicWorldAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            spatial_resolution_m=DYNAMIC_WORLD_NOMINAL_SCALE_M,
            status="no_data",
            pipeline_version="3.1.0",
            observation_date=None,
            observation_id=None,
            data_lag_days=None,
            dominant_class=None,
            dominant_probability=None,
            class_probabilities=None,
            error=None,
        )

    obs_date, obs_id, class_probs = normalized

    # Guard against future dates relative to requested_end_date
    if obs_date > resolved_end_date:
        return DynamicWorldAnalysis(
            region=region_meta,
            requested_end_date=resolved_end_date,
            dataset=dataset,
            spatial_resolution_m=DYNAMIC_WORLD_NOMINAL_SCALE_M,
            status="error",
            pipeline_version="3.1.0",
            error=EarthEngineError(
                type="DataIntegrityError",
                message=f"observation_date ({obs_date}) is in the future relative to requested_end_date ({resolved_end_date})",
            ),
        )

    data_lag = (resolved_end_date - obs_date).days
    dom_class, dom_prob = derive_dominant_land_cover(class_probs)

    return DynamicWorldAnalysis(
        region=region_meta,
        requested_end_date=resolved_end_date,
        observation_date=obs_date,
        observation_id=obs_id,
        data_lag_days=data_lag,
        dominant_class=dom_class,
        dominant_probability=dom_prob,
        class_probabilities=class_probs,
        dataset=dataset,
        spatial_resolution_m=DYNAMIC_WORLD_NOMINAL_SCALE_M,
        status="success",
        pipeline_version="3.1.0",
        error=None,
    )
