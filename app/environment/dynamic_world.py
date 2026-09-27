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
"""Dynamic World V1 Earth Engine data adapter and regional probability extraction pipeline (Phase 3C, DEC-021).

This module implements Tier 1 of the Phase 3C architecture:
- Directly interfaces with Google Earth Engine (GOOGLE/DYNAMICWORLD/V1).
- Queries the requested temporal window [requested_end_date - lookback_days + 1, requested_end_date + 1).
- Selects all 9 continuous land-cover probability bands (water, trees, grass, flooded_vegetation,
  crops, shrub_and_scrub, built, bare, snow_and_ice).
- Performs Option A spatial reduction: unweighted zonal mean reduction (ee.Reducer.mean())
  at native 10m nominal scale over the circular AnalysisRegion geometry.
- Enforces server-side usability filtering and selects strictly the single NEWEST USABLE observation.
- Returns standard EarthEngineResult envelopes containing raw properties.
- Architectural Boundary: This is the ONLY module in the Dynamic World subsystem that imports ee
  or calls getInfo().
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Union

import ee

from app.satellite.geometry import DEFAULT_ANALYSIS_RADIUS_M, create_analysis_region
from app.satellite.types import EarthEngineError, EarthEngineResult

# Canonical Earth Engine dataset ID for Dynamic World V1 (DEC-021)
DYNAMIC_WORLD_DATASET: str = "GOOGLE/DYNAMICWORLD/V1"

# Target 9 continuous probability bands from GOOGLE/DYNAMICWORLD/V1 (DEC-021)
DYNAMIC_WORLD_PROBABILITY_BANDS: list[str] = [
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

# Native spatial resolution in meters (matching Sentinel-2 MSI 10m grid)
DYNAMIC_WORLD_NOMINAL_SCALE_M: float = 10.0

# Default retrospective lookback window in calendar days (DEC-021)
DEFAULT_LOOKBACK_DAYS: int = 30


def _parse_date(date_val: Union[str, date, datetime]) -> date:
    """Parses a string, date, or datetime into a datetime.date object.

    Args:
        date_val: An ISO date string ("YYYY-MM-DD" or ISO 8601), datetime, or date.

    Returns:
        date: The parsed date object.

    Raises:
        ValueError: If the date format is invalid or cannot be parsed.
        TypeError: If date_val is of an unsupported type.
    """
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, str):
        cleaned = date_val.strip()
        if "T" in cleaned:
            cleaned = cleaned.split("T")[0]
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid date format '{date_val}', expected 'YYYY-MM-DD' or ISO 8601 string."
            ) from exc
    raise TypeError(f"Unsupported date type {type(date_val)!r}: {date_val!r}")


def fetch_raw_dynamic_world_record(
    region: Union[ee.Geometry, Any],
    requested_end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    dataset: str = DYNAMIC_WORLD_DATASET,
) -> EarthEngineResult:
    """Fetches the newest usable Dynamic World observation over the AnalysisRegion (DEC-021).

    Executes a bounded Earth Engine query over [requested_end_date - lookback_days + 1, requested_end_date],
    applies unweighted zonal mean spatial reduction across all 9 probability bands at native 10m scale,
    filters server-side for usable regional probability data, and selects the single newest usable observation.

    Args:
        region: ee.Geometry circular buffer or AnalysisRegionMetadata instance.
        requested_end_date: Reference/query end date. Defaults to current UTC date.
        lookback_days: Number of retrospective calendar days (default 30 days for E-29 through E).
        dataset: Asset ID of the Dynamic World collection (default 'GOOGLE/DYNAMICWORLD/V1').

    Returns:
        EarthEngineResult:
            - status="success": data contains property dict for the newest usable observation.
            - status="no_data": image_count=0, data=None.
            - status="error": Earth Engine exception occurred; error populated.

    Raises:
        TypeError: If region is not an ee.Geometry or cannot be resolved to one.
        ValueError: If lookback_days <= 0.
    """
    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or lookback_days <= 0:
        raise ValueError(
            f"lookback_days must be a strictly positive integer (> 0), got {lookback_days!r}"
        )

    # Resolve geometry from ee.Geometry or region metadata
    geometry: ee.Geometry
    if isinstance(region, ee.Geometry):
        geometry = region
    elif hasattr(region, "latitude") and hasattr(region, "longitude"):
        radius = getattr(region, "radius_m", DEFAULT_ANALYSIS_RADIUS_M)
        geometry = create_analysis_region(region.latitude, region.longitude, radius)
    else:
        raise TypeError(
            f"region must be an instance of ee.Geometry or have latitude/longitude attributes, got {type(region)!r}"
        )

    # Resolve temporal boundaries: [start_dt, end_dt] inclusive -> EE filter [start_str, end_str) half-open
    end_dt: date
    if requested_end_date is not None:
        end_dt = _parse_date(requested_end_date)
    else:
        end_dt = datetime.now(timezone.utc).date()

    start_dt = end_dt - timedelta(days=lookback_days - 1)
    filter_end = end_dt + timedelta(days=1)

    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = filter_end.strftime("%Y-%m-%d")

    try:
        # 1. Query candidate Dynamic World collection sorted descending by time
        collection = (
            ee.ImageCollection(dataset)
            .filterBounds(geometry)
            .filterDate(start_str, end_str)
            .select(DYNAMIC_WORLD_PROBABILITY_BANDS)
            .sort("system:time_start", False)
        )

        # 2. Server-side unweighted regional mean reduction of 9 probability bands
        def _reduce_and_enrich(img: ee.Image) -> ee.Feature:
            stats = img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=DYNAMIC_WORLD_NOMINAL_SCALE_M,
                maxPixels=1000000,
            )
            date_str = img.date().format("YYYY-MM-dd")
            system_time_start = img.get("system:time_start")
            sys_index = img.id()
            enriched_stats = stats.set("observation_date", date_str).set(
                "system:time_start", system_time_start
            ).set("system:index", sys_index).set("observation_id", sys_index)
            return ee.Feature(None, enriched_stats)

        reduced_fc = collection.map(_reduce_and_enrich)

        # 3. Server-side usability filter: require non-null regional probability data
        usable_fc = reduced_fc.filter(ee.Filter.notNull(DYNAMIC_WORLD_PROBABILITY_BANDS))

        # 4. Select the newest usable observation
        newest_feature = usable_fc.first()
        feat_info = newest_feature.getInfo()

        if not feat_info or not isinstance(feat_info, dict) or "properties" not in feat_info:
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=None,
                error=None,
            )

        properties = feat_info.get("properties")
        if not isinstance(properties, dict) or not properties:
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=None,
                error=None,
            )

        if "observation_id" not in properties and "id" in feat_info:
            properties["observation_id"] = feat_info["id"]

        # Verify that at least one required probability band is non-null in properties
        has_valid_prob = any(
            band in properties and properties[band] is not None
            for band in DYNAMIC_WORLD_PROBABILITY_BANDS
        )
        if not has_valid_prob:
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=None,
                error=None,
            )

        return EarthEngineResult(
            status="success",
            dataset=dataset,
            image_count=1,
            data=properties,
            error=None,
        )

    except Exception as exc:
        error_type = exc.__class__.__name__
        return EarthEngineResult(
            status="error",
            dataset=dataset,
            image_count=None,
            data=None,
            error=EarthEngineError(
                type=error_type,
                message=str(exc),
            ),
        )
