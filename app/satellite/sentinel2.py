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
"""Sentinel-2 Surface Reflectance imagery selection and ingestion pipeline.

This module implements the Sentinel-2 imagery data pipeline defined in DEC-008
(Phase 1E — Sentinel-2 Data Pipeline).

Architectural Responsibilities:
-------------------------------
1. Ingests Copernicus Sentinel-2 Level-2A (Harmonized Surface Reflectance) collections.
2. Applies spatial bounding via an AnalysisRegion (ee.Geometry).
3. Applies temporal filtering with configurable lookback windows (default 30 days).
4. Applies scene-level cloud filtering (CLOUDY_PIXEL_PERCENTAGE < 20%).
5. Orders candidate scenes descending by acquisition timestamp (newest-first).
6. Selects the most recent usable image (never termed 'best image') for downstream processing.
7. Extracts structured observation metadata (acquisition date, cloud percentage, etc.)
   and returns standard EarthEngineResult envelopes (success, no_data, error).

Important Scope Boundaries:
---------------------------
- Pixel-level cloud masking (QA60 / SCL masking) is deferred to subsequent computation phases.
- NDVI calculation and band math are NOT implemented here (Phase 1F).
- Zonal statistical reductions (mean, median, min, max) are NOT implemented here (Phase 1G).
- Multi-temporal time-series and historical baseline anomaly detection are NOT implemented here.
"""

import math
from datetime import date, datetime, timedelta, timezone
from typing import Union

import ee

from .types import EarthEngineError, EarthEngineResult, Sentinel2ImageMetadata

# Canonical Earth Engine dataset ID for Sentinel-2 Level-2A Harmonized Surface Reflectance
SENTINEL2_SR_HARMONIZED: str = "COPERNICUS/S2_SR_HARMONIZED"

# Default lookback window in days for discovering recent satellite observations (DEC-008)
DEFAULT_LOOKBACK_DAYS: int = 30

# Default maximum scene cloudy pixel percentage threshold (DEC-008)
DEFAULT_MAX_CLOUD_PERCENTAGE: float = 20.0


def _parse_date(date_val: Union[str, date, datetime]) -> date:
    """Parses a string, date, or datetime into a datetime.date object.

    Args:
        date_val: An ISO date string ("YYYY-MM-DD" or ISO 8601), datetime, or date.

    Returns:
        date: The parsed date object.

    Raises:
        ValueError: If the date format is invalid or cannot be parsed.
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
    raise ValueError(f"Unsupported date type {type(date_val)!r}: {date_val!r}")


def resolve_date_range(
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> tuple[str, str]:
    """Resolves and validates start and end dates for temporal imagery filtering.

    Args:
        start_date: Optional start date for the search window.
        end_date: Optional end date for the search window. Defaults to current UTC date.
        lookback_days: Number of days to look back from end_date if start_date is not specified.
            Must be strictly positive (> 0). Defaults to 30 days.

    Returns:
        tuple[str, str]: A tuple of ISO date strings (start_date_str, end_date_str) in 'YYYY-MM-DD' format.

    Raises:
        ValueError: If lookback_days is not a positive integer, or if start_date is after end_date.
    """
    if (
        not isinstance(lookback_days, int)
        or isinstance(lookback_days, bool)
        or lookback_days <= 0
    ):
        raise ValueError(
            f"lookback_days must be a strictly positive integer (> 0), got {lookback_days!r}"
        )

    resolved_end: date
    if end_date is not None:
        resolved_end = _parse_date(end_date)
    else:
        resolved_end = datetime.now(timezone.utc).date()

    resolved_start: date
    if start_date is not None:
        resolved_start = _parse_date(start_date)
    else:
        resolved_start = resolved_end - timedelta(days=lookback_days)

    if resolved_start > resolved_end:
        raise ValueError(
            f"start_date ({resolved_start.isoformat()}) cannot be after end_date ({resolved_end.isoformat()})."
        )

    return resolved_start.strftime("%Y-%m-%d"), resolved_end.strftime("%Y-%m-%d")


def get_sentinel2_collection(
    region: ee.Geometry,
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
) -> ee.ImageCollection:
    """Builds a spatially and temporally bounded, cloud-filtered, newest-first Sentinel-2 collection.

    This function constructs the client-side Earth Engine ImageCollection proxy without
    performing server-side network evaluation (.getInfo()).

    Args:
        region: The analysis region geometry (ee.Geometry) to filter spatial bounds.
        start_date: Optional search window start date.
        end_date: Optional search window end date. Defaults to current date.
        lookback_days: Number of days to look back from end_date if start_date is omitted.
            Defaults to 30 days.
        max_cloud_percentage: Maximum scene cloud cover threshold in percent (0.0 to 100.0).
            Defaults to 20.0%.
        dataset: Earth Engine dataset identifier. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.

    Returns:
        ee.ImageCollection: Earth Engine collection filtered by bounds, date range, and cloud
            threshold, sorted descending by acquisition time (system:time_start).

    Raises:
        TypeError: If region is not an instance of ee.Geometry.
        ValueError: If max_cloud_percentage or date parameters are invalid.
    """
    if not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    if (
        not isinstance(max_cloud_percentage, (int, float))
        or isinstance(max_cloud_percentage, bool)
        or math.isnan(max_cloud_percentage)
        or math.isinf(max_cloud_percentage)
    ):
        raise ValueError(
            f"max_cloud_percentage must be a valid finite number, got {max_cloud_percentage!r}"
        )

    if not (0.0 <= float(max_cloud_percentage) <= 100.0):
        raise ValueError(
            f"max_cloud_percentage must be between 0.0 and 100.0, got {max_cloud_percentage}"
        )

    start_str, end_str = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )

    collection = (
        ee.ImageCollection(dataset)
        .filterBounds(region)
        .filterDate(start_str, end_str)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", float(max_cloud_percentage)))
        .sort("system:time_start", False)
    )

    return collection


def get_most_recent_sentinel2_image(
    region: ee.Geometry,
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
) -> ee.Image:
    """Returns the un-evaluated ee.Image proxy for the most recent usable Sentinel-2 observation.

    This helper provides the raw ee.Image object needed for downstream band mathematics
    (such as NDVI calculation in Phase 1F) without executing immediate server-side evaluation.

    Args:
        region: The analysis region geometry (ee.Geometry).
        start_date: Optional search window start date.
        end_date: Optional search window end date.
        lookback_days: Lookback window in days if start_date is omitted.
        max_cloud_percentage: Maximum scene cloud cover threshold in percent.
        dataset: Earth Engine dataset identifier.

    Returns:
        ee.Image: The newest candidate image from the filtered collection (.first()).
    """
    collection = get_sentinel2_collection(
        region=region,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
        max_cloud_percentage=max_cloud_percentage,
        dataset=dataset,
    )
    return collection.first()


def select_most_recent_sentinel2_image(
    region: ee.Geometry,
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
) -> EarthEngineResult:
    """Discovers and selects the most recent usable Sentinel-2 image, returning a structured result.

    Evaluates the filtered collection against Earth Engine servers, handles errors and
    zero-data states gracefully, and extracts observation metadata for downstream processing.

    Args:
        region: The analysis region geometry (ee.Geometry).
        start_date: Optional search window start date.
        end_date: Optional search window end date.
        lookback_days: Lookback window in days if start_date is omitted. Defaults to 30.
        max_cloud_percentage: Maximum scene cloud cover threshold in percent. Defaults to 20.0%.
        dataset: Earth Engine dataset identifier. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.

    Returns:
        EarthEngineResult:
            - status="success": Found usable candidates; data contains Sentinel2ImageMetadata.
            - status="no_data": Zero usable scenes found in the search window; image_count=0.
            - status="error": Earth Engine exception occurred; error contains details.
    """
    try:
        collection = get_sentinel2_collection(
            region=region,
            start_date=start_date,
            end_date=end_date,
            lookback_days=lookback_days,
            max_cloud_percentage=max_cloud_percentage,
            dataset=dataset,
        )

        image_count = int(collection.size().getInfo())

        if image_count == 0:
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=None,
                error=None,
            )

        most_recent_image = collection.first()
        image_info = most_recent_image.getInfo()

        image_id = image_info.get("id", "")
        properties = image_info.get("properties", {})

        system_time_start = properties.get("system:time_start")
        acquisition_date_iso = ""
        if system_time_start is not None:
            acquisition_dt = datetime.fromtimestamp(
                system_time_start / 1000.0, tz=timezone.utc
            )
            acquisition_date_iso = acquisition_dt.isoformat()

        cloud_percentage = float(
            properties.get("CLOUDY_PIXEL_PERCENTAGE", 0.0)
        )
        spacecraft_name = properties.get("SPACECRAFT_NAME")
        mgrs_tile = properties.get("MGRS_TILE")
        product_id = properties.get("PRODUCT_ID")

        metadata = Sentinel2ImageMetadata(
            image_id=image_id,
            acquisition_date=acquisition_date_iso,
            cloud_percentage=cloud_percentage,
            spacecraft_name=spacecraft_name,
            mgrs_tile=mgrs_tile,
            product_id=product_id,
            system_time_start=system_time_start,
        )

        return EarthEngineResult(
            status="success",
            dataset=dataset,
            image_count=image_count,
            data=metadata,
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
