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

# Canonical Earth Engine dataset ID for Cloud Score+ Sentinel-2 Harmonized (DEC-010)
CLOUD_SCORE_PLUS_S2_HARMONIZED: str = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"

# Canonical quality band for Cloud Score+ (cumulative distribution function clear-sky score)
DEFAULT_QUALITY_BAND: str = "cs_cdf"

# Default minimum clear-sky quality score threshold (DEC-010)
DEFAULT_CLEAR_THRESHOLD: float = 0.60

# Default minimum usable regional pixel coverage ratio (DEC-010)
DEFAULT_MIN_USABLE_COVERAGE: float = 0.70

# Default lookback window in days for discovering recent satellite observations (DEC-008)
DEFAULT_LOOKBACK_DAYS: int = 30

# Default maximum scene cloudy pixel percentage threshold (DEC-008 coarse catalog pre-filter)
DEFAULT_MAX_CLOUD_PERCENTAGE: float = 60.0


def _validate_threshold(
    name: str,
    value: Union[int, float],
    min_val: float = 0.0,
    max_val: float = 1.0,
) -> float:
    """Validates that a numeric threshold is a finite float in [min_val, max_val].

    Args:
        name: Parameter name for descriptive error messaging.
        value: The numeric value to validate.
        min_val: Minimum acceptable value (inclusive).
        max_val: Maximum acceptable value (inclusive).

    Returns:
        float: The validated float value.

    Raises:
        ValueError: If value is non-numeric, boolean, NaN, infinite, or out of range.
    """
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or math.isnan(value)
        or math.isinf(value)
    ):
        raise ValueError(f"{name} must be a valid finite number, got {value!r}")
    val_float = float(value)
    if not (min_val <= val_float <= max_val):
        raise ValueError(
            f"{name} must be between {min_val} and {max_val}, got {value}"
        )
    return val_float


def _validate_string(name: str, value: str) -> str:
    """Validates that a parameter is a non-empty string.

    Args:
        name: Parameter name for descriptive error messaging.
        value: The string to validate.

    Returns:
        str: The stripped valid string.

    Raises:
        ValueError: If value is not a string or is empty/whitespace.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value.strip()


def mask_observation_quality(
    image: ee.Image,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    quality_band: str = DEFAULT_QUALITY_BAND,
) -> ee.Image:
    """Applies Cloud Score+ pixel-level quality masking to a Sentinel-2 image.

    Masks out pixels where the quality band value is strictly less than the clear threshold.
    Masked pixels are preserved as invalid and will not contribute to downstream band
    mathematics or statistical reductions (DEC-010).

    Args:
        image: Earth Engine image containing the quality band.
        clear_threshold: Minimum clear-sky score threshold in [0.0, 1.0]. Defaults to 0.60.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.

    Returns:
        ee.Image: The input image with unusable/cloudy pixels masked out.

    Raises:
        TypeError: If image is not an instance of ee.Image.
        ValueError: If clear_threshold or quality_band are invalid.
    """
    if not isinstance(image, ee.Image):
        raise TypeError(
            f"image must be an instance of ee.Image, got {type(image)!r}"
        )

    thresh = _validate_threshold("clear_threshold", clear_threshold, 0.0, 1.0)
    band = _validate_string("quality_band", quality_band)

    quality_mask = image.select(band).gte(thresh)
    return image.updateMask(quality_mask)


def calculate_usable_coverage(
    image: ee.Image,
    region: ee.Geometry,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    quality_band: str = DEFAULT_QUALITY_BAND,
) -> ee.Number:
    """Calculates the usable pixel coverage ratio inside an analysis region.

    Computes the fraction of pixels within the analysis region satisfying the
    observation quality threshold (quality_band >= clear_threshold) using an
    Earth Engine mean reducer over a binary mask (DEC-010).

    Args:
        image: Earth Engine image containing the quality band.
        region: Analysis region geometry (ee.Geometry).
        clear_threshold: Minimum clear-sky score threshold in [0.0, 1.0]. Defaults to 0.60.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.

    Returns:
        ee.Number: Usable coverage ratio in [0.0, 1.0] (or 0.0 if unmeasurable/missing).

    Raises:
        TypeError: If image is not an ee.Image or region is not an ee.Geometry.
        ValueError: If clear_threshold or quality_band are invalid.
    """
    if not isinstance(image, ee.Image):
        raise TypeError(
            f"image must be an instance of ee.Image, got {type(image)!r}"
        )
    if not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    thresh = _validate_threshold("clear_threshold", clear_threshold, 0.0, 1.0)
    band = _validate_string("quality_band", quality_band)

    mask = image.select(band).gte(thresh)
    mean_dict = mask.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=region,
        scale=10,
        maxPixels=1e6,
    )
    return ee.Number(
        ee.Algorithms.If(
            mean_dict.contains(band),
            mean_dict.get(band),
            0.0,
        )
    )


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
    quality_dataset: str = CLOUD_SCORE_PLUS_S2_HARMONIZED,
    quality_band: str = DEFAULT_QUALITY_BAND,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    min_usable_coverage: float = DEFAULT_MIN_USABLE_COVERAGE,
    apply_quality_filter: bool = True,
) -> ee.ImageCollection:
    """Builds a spatially and temporally bounded, cloud-filtered, quality-linked Sentinel-2 collection.

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
        dataset: Sentinel-2 Earth Engine dataset identifier. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.
        quality_dataset: Cloud Score+ dataset identifier. Defaults to 'GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.
        clear_threshold: Clear-sky threshold for pixel usability in [0.0, 1.0]. Defaults to 0.60.
        min_usable_coverage: Minimum regional coverage ratio in [0.0, 1.0]. Defaults to 0.70.
        apply_quality_filter: Whether to link Cloud Score+ and filter candidates by regional usable
            coverage. Defaults to True.

    Returns:
        ee.ImageCollection: Earth Engine collection filtered by bounds, date range, cloud threshold,
            and regional quality coverage, sorted descending by acquisition time (system:time_start).

    Raises:
        TypeError: If region is not an instance of ee.Geometry.
        ValueError: If max_cloud_percentage, clear_threshold, min_usable_coverage, or date parameters are invalid.
    """
    if not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    _validate_threshold("max_cloud_percentage", max_cloud_percentage, 0.0, 100.0)
    _validate_threshold("clear_threshold", clear_threshold, 0.0, 1.0)
    _validate_threshold("min_usable_coverage", min_usable_coverage, 0.0, 1.0)
    _validate_string("quality_band", quality_band)
    _validate_string("dataset", dataset)
    _validate_string("quality_dataset", quality_dataset)

    start_str, end_str = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )

    s2_collection = (
        ee.ImageCollection(dataset)
        .filterBounds(region)
        .filterDate(start_str, end_str)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", float(max_cloud_percentage)))
        .sort("system:time_start", False)
    )

    if not apply_quality_filter:
        return s2_collection

    cs_plus = ee.ImageCollection(quality_dataset)
    linked = s2_collection.linkCollection(cs_plus, [quality_band])

    def _score_usable_coverage(img: ee.Image) -> ee.Image:
        mask = img.select(quality_band).gte(float(clear_threshold))
        mean_dict = mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=region,
            scale=10,
            maxPixels=1e6,
        )
        coverage = ee.Number(
            ee.Algorithms.If(
                mean_dict.contains(quality_band),
                mean_dict.get(quality_band),
                0.0,
            )
        )
        return img.set("USABLE_COVERAGE", coverage)

    scored = linked.map(_score_usable_coverage)
    qualified = scored.filter(
        ee.Filter.gte("USABLE_COVERAGE", float(min_usable_coverage))
    )

    return qualified


def get_most_recent_sentinel2_image(
    region: ee.Geometry,
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
    quality_dataset: str = CLOUD_SCORE_PLUS_S2_HARMONIZED,
    quality_band: str = DEFAULT_QUALITY_BAND,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    min_usable_coverage: float = DEFAULT_MIN_USABLE_COVERAGE,
    apply_quality_mask: bool = True,
) -> ee.Image:
    """Returns the un-evaluated ee.Image proxy for the most recent usable Sentinel-2 observation.

    Discovers the newest candidate meeting the regional usable coverage threshold (DEC-010)
    and applies pixel-level quality masking so unusable pixels do not corrupt downstream
    computations (such as NDVI calculation in Phase 1F).

    Args:
        region: The analysis region geometry (ee.Geometry).
        start_date: Optional search window start date.
        end_date: Optional search window end date.
        lookback_days: Lookback window in days if start_date is omitted.
        max_cloud_percentage: Maximum scene cloud cover threshold in percent.
        dataset: Sentinel-2 Earth Engine dataset identifier.
        quality_dataset: Cloud Score+ dataset identifier.
        quality_band: Quality band identifier.
        clear_threshold: Clear-sky threshold for pixel usability in [0.0, 1.0].
        min_usable_coverage: Minimum regional coverage ratio in [0.0, 1.0].
        apply_quality_mask: Whether to apply updateMask(cs_cdf >= clear_threshold). Defaults to True.

    Returns:
        ee.Image: The newest qualified candidate image from the filtered collection (.first()),
            with quality mask optionally applied.
    """
    collection = get_sentinel2_collection(
        region=region,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
        max_cloud_percentage=max_cloud_percentage,
        dataset=dataset,
        quality_dataset=quality_dataset,
        quality_band=quality_band,
        clear_threshold=clear_threshold,
        min_usable_coverage=min_usable_coverage,
        apply_quality_filter=True,
    )
    raw_image = collection.first()
    if apply_quality_mask:
        return mask_observation_quality(
            raw_image,
            clear_threshold=clear_threshold,
            quality_band=quality_band,
        )
    return raw_image


def select_most_recent_sentinel2_image(
    region: ee.Geometry,
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
    quality_dataset: str = CLOUD_SCORE_PLUS_S2_HARMONIZED,
    quality_band: str = DEFAULT_QUALITY_BAND,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    min_usable_coverage: float = DEFAULT_MIN_USABLE_COVERAGE,
) -> EarthEngineResult:
    """Discovers and selects the most recent usable Sentinel-2 image, returning a structured result.

    Evaluates candidate scenes against Cloud Score+ observation quality inside the AnalysisRegion.
    Selects the newest candidate satisfying the minimum usable regional coverage (DEC-010).

    Args:
        region: The analysis region geometry (ee.Geometry).
        start_date: Optional search window start date.
        end_date: Optional search window end date.
        lookback_days: Lookback window in days if start_date is omitted. Defaults to 30.
        max_cloud_percentage: Maximum scene cloud cover threshold in percent. Defaults to 20.0%.
        dataset: Sentinel-2 Earth Engine dataset identifier. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.
        quality_dataset: Cloud Score+ dataset identifier. Defaults to 'GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.
        clear_threshold: Clear-sky threshold for pixel usability in [0.0, 1.0]. Defaults to 0.60.
        min_usable_coverage: Minimum regional coverage ratio in [0.0, 1.0]. Defaults to 0.70.

    Returns:
        EarthEngineResult:
            - status="success": Found qualifying candidates; data contains Sentinel2ImageMetadata with
              usable_coverage_percentage populated.
            - status="no_data": Zero qualifying scenes found in the search window; image_count=0.
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
            quality_dataset=quality_dataset,
            quality_band=quality_band,
            clear_threshold=clear_threshold,
            min_usable_coverage=min_usable_coverage,
            apply_quality_filter=True,
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

        usable_coverage_ratio = properties.get("USABLE_COVERAGE")
        usable_coverage_pct: float | None = None
        if usable_coverage_ratio is not None:
            usable_coverage_pct = round(float(usable_coverage_ratio) * 100.0, 2)

        metadata = Sentinel2ImageMetadata(
            image_id=image_id,
            acquisition_date=acquisition_date_iso,
            cloud_percentage=cloud_percentage,
            spacecraft_name=spacecraft_name,
            mgrs_tile=mgrs_tile,
            product_id=product_id,
            system_time_start=system_time_start,
            usable_coverage_percentage=usable_coverage_pct,
            clear_threshold=float(clear_threshold),
            quality_band=str(quality_band),
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
