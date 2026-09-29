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
"""ERA5-Land Earth Engine data adapter and spatial reduction pipeline (Phase 3A, DEC-019).

This module implements Tier 1 of the Phase 3A architecture:
- Directly interfaces with Google Earth Engine (ECMWF/ERA5_LAND/DAILY_AGGR).
- Queries the requested temporal window [requested_end_date - lookback_days + 1, requested_end_date + 1).
- Selects the 4 target reanalysis bands:
    1. temperature_2m
    2. total_precipitation_sum
    3. volumetric_soil_water_layer_1
    4. runoff_sum
- Performs Option A spatial reduction: unweighted zonal mean reduction (ee.Reducer.mean())
  at native ERA5-Land nominal scale (~11132 m) over the circular AnalysisRegion geometry.
- Enforces the strict scientific boundary: ERA5-Land provides coarse regional environmental
  context (~11.1 km), NOT 100m parcel-scale microclimate. No synthetic downscaling or
  sub-pixel weighting is performed.
- Returns standard EarthEngineResult envelopes containing raw properties.
"""

from datetime import date, datetime, timedelta, timezone
import math
from typing import Any, Union

import ee

from app.satellite.geometry import DEFAULT_ANALYSIS_RADIUS_M, create_analysis_region
from app.satellite.types import EarthEngineError, EarthEngineResult

# Canonical Earth Engine dataset ID for ERA5-Land Daily Aggregated (DEC-018 / DEC-019)
ERA5_LAND_DATASET: str = "ECMWF/ERA5_LAND/DAILY_AGGR"

# Target physical variable bands from ECMWF ERA5-Land Daily Aggregated
ERA5_LAND_BANDS: list[str] = [
    "temperature_2m",
    "total_precipitation_sum",
    "volumetric_soil_water_layer_1",
    "runoff_sum",
]

# Nominal spatial resolution in meters (~0.1° at the equator, ~11132 m)
ERA5_LAND_NOMINAL_SCALE_M: float = 11132.0

# Sampling scale in meters for regional reduction over parcel geometry (1000.0m)
ERA5_LAND_REDUCTION_SCALE_M: float = 1000.0

# Default retrospective lookback window in calendar days (DEC-018)
DEFAULT_LOOKBACK_DAYS: int = 90


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


def fetch_raw_era5_land_timeseries(
    region: Union[ee.Geometry, Any],
    requested_end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    dataset: str = ERA5_LAND_DATASET,
) -> EarthEngineResult:
    """Fetches raw daily ERA5-Land reanalysis observations over the AnalysisRegion (DEC-019).

    Executes a bounded Earth Engine query over [requested_end_date - lookback_days + 1, requested_end_date]
    and applies Option A spatial reduction (zonal mean at ~11.1 km nominal scale).

    Args:
        region: ee.Geometry circular buffer or AnalysisRegionMetadata instance.
        requested_end_date: Reference/query end date. Defaults to current UTC date.
        lookback_days: Number of retrospective calendar days (default 90 days for E-89 through E).
        dataset: Asset ID of the ERA5-Land collection (default 'ECMWF/ERA5_LAND/DAILY_AGGR').

    Returns:
        EarthEngineResult:
            - status="success": data contains list of raw property dicts per available day.
            - status="no_data": image_count=0, data=[].
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
        collection = (
            ee.ImageCollection(dataset)
            .filterBounds(geometry)
            .filterDate(start_str, end_str)
            .select(ERA5_LAND_BANDS)
            .sort("system:time_start", True)
        )

        def _reduce_image(img: ee.Image) -> ee.Feature:
            stats = img.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=ERA5_LAND_REDUCTION_SCALE_M,
                maxPixels=1000000,
            )
            date_str = img.date().format("YYYY-MM-dd")
            system_time_start = img.get("system:time_start")
            enriched_stats = stats.set("observation_date", date_str).set(
                "system:time_start", system_time_start
            )
            return ee.Feature(None, enriched_stats)

        reduced_fc = collection.map(_reduce_image)
        fc_info = reduced_fc.getInfo()

        features = fc_info.get("features", []) if isinstance(fc_info, dict) else []
        image_count = len(features)

        if image_count == 0:
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=[],
                error=None,
            )

        raw_records: list[dict[str, Any]] = []
        for feat in features:
            if isinstance(feat, dict) and "properties" in feat:
                raw_records.append(feat["properties"])

        return EarthEngineResult(
            status="success",
            dataset=dataset,
            image_count=image_count,
            data=raw_records,
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
