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
"""Authoritative regional NDVI analysis pipeline for Sentinel-2 satellite imagery.

This module orchestrates the complete regional satellite observation evidence and
NDVI analysis workflow defined in DEC-011.

Architectural Guarantees:
-------------------------
1. Single Authoritative Observation:
   Discovers and qualifies candidate scenes in a single pass using regional Cloud Score+
   coverage, selects collection.first() exactly once, and flows that single image proxy
   through metadata extraction, quality masking, NDVI computation, and zonal reduction.
   Never executes split-brain re-queries or secondary image selections.

2. Identical Quality Masking:
   Applies pixel-level masking (cs_cdf >= clear_threshold) identical to the candidate
   qualification condition before computing NDVI, ensuring cloudy pixels are excluded
   from zonal reduction.

3. Mathematical Invariant Verification:
   Validates min <= mean <= max and min <= median <= max within an epsilon tolerance
   (1e-6) before constructing the successful RegionalNdviAnalysis payload.

4. Evidence-Only Freshness:
   Derives observation age in days deterministically relative to the resolved reference
   date without fabricating arbitrary confidence scores or binary freshness flags.
"""

from datetime import date, datetime, timezone
import math
from typing import Union

import ee

from .geometry import DEFAULT_ANALYSIS_RADIUS_M, create_analysis_region
from .ndvi import calculate_ndvi, calculate_ndvi_statistics
from .sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    SENTINEL2_SR_HARMONIZED,
    get_sentinel2_collection,
    mask_observation_quality,
    resolve_date_range,
)
from .types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    EarthEngineResult,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    Sentinel2ImageMetadata,
)

# Epsilon tolerance for floating-point statistical envelope comparisons
STATISTICAL_INVARIANT_EPSILON: float = 1e-6


def _validate_numeric(
    name: str,
    value: Union[int, float],
    min_val: float | None = None,
    max_val: float | None = None,
    strictly_positive: bool = False,
) -> float:
    """Validates that a numeric argument is a finite float within specified bounds.

    Args:
        name: Parameter name for error messages.
        value: The numeric value to validate.
        min_val: Optional minimum acceptable value (inclusive).
        max_val: Optional maximum acceptable value (inclusive).
        strictly_positive: If True, value must be strictly > 0.

    Returns:
        float: The validated float value.

    Raises:
        TypeError: If value is non-numeric or a boolean.
        ValueError: If value is NaN, infinite, or out of bounds.
    """
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(
            f"{name} must be a numeric value, got {type(value).__name__}: {value!r}"
        )
    if math.isnan(value) or math.isinf(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    val_float = float(value)
    if strictly_positive and val_float <= 0.0:
        raise ValueError(f"{name} must be strictly positive (> 0), got {value}")
    if min_val is not None and val_float < min_val:
        raise ValueError(f"{name} must be >= {min_val}, got {value}")
    if max_val is not None and val_float > max_val:
        raise ValueError(f"{name} must be <= {max_val}, got {value}")
    return val_float


def _validate_string(name: str, value: str) -> str:
    """Validates that a parameter is a non-empty string."""
    if not isinstance(value, str):
        raise TypeError(
            f"{name} must be a string, got {type(value).__name__}: {value!r}"
        )
    if not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value.strip()


def _verify_statistical_invariants(stats: NdviRegionalStatistics) -> None:
    """Verifies that regional summary statistics adhere to mathematical envelope invariants.

    Raises:
        ValueError: If min > median, min > mean, mean > max, or median > max beyond tolerance.
    """
    eps = STATISTICAL_INVARIANT_EPSILON
    if not (
        (stats.min - eps <= stats.median <= stats.max + eps)
        and (stats.min - eps <= stats.mean <= stats.max + eps)
    ):
        raise ValueError(
            f"Statistical invariant violation: min={stats.min}, median={stats.median}, "
            f"mean={stats.mean}, max={stats.max} exceeds tolerance ({eps})."
        )


def analyze_regional_ndvi(
    latitude: Union[int, float],
    longitude: Union[int, float],
    radius_m: Union[int, float] = DEFAULT_ANALYSIS_RADIUS_M,
    start_date: Union[str, date, datetime, None] = None,
    end_date: Union[str, date, datetime, None] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    min_usable_coverage: float = DEFAULT_MIN_USABLE_COVERAGE,
    scale_m: Union[int, float] = 10.0,
    dataset: str = SENTINEL2_SR_HARMONIZED,
    quality_dataset: str = CLOUD_SCORE_PLUS_S2_HARMONIZED,
    quality_band: str = DEFAULT_QUALITY_BAND,
) -> EarthEngineResult:
    """Orchestrates the authoritative regional Sentinel-2 NDVI analysis pipeline.

    Discovers candidate satellite scenes, evaluates regional Cloud Score+ optical usability,
    selects the newest qualifying observation, computes quality-masked NDVI, executes zonal
    statistical reductions, and returns an EarthEngineResult containing a strongly typed
    RegionalNdviAnalysis domain payload (DEC-011).

    Args:
        latitude: Center latitude coordinate in decimal degrees in [-90, 90].
        longitude: Center longitude coordinate in decimal degrees in [-180, 180].
        radius_m: Buffer radius in meters (> 0). Defaults to 100.0 meters.
        start_date: Optional start date for search window.
        end_date: Optional end date / reference date for search window. Defaults to current UTC date.
        lookback_days: Lookback window in days if start_date omitted (> 0). Defaults to 30.
        max_cloud_percentage: Max scene cloud cover threshold in percent in [0, 100]. Defaults to 20.0.
        clear_threshold: Clear-sky threshold for pixel usability in [0, 1]. Defaults to 0.60.
        min_usable_coverage: Minimum regional usable pixel coverage ratio in [0, 1]. Defaults to 0.70.
        scale_m: Spatial reduction scale in meters (> 0). Defaults to 10.0.
        dataset: Sentinel-2 Earth Engine dataset ID. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.
        quality_dataset: Cloud Score+ dataset ID. Defaults to 'GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'.
        quality_band: Quality band name. Defaults to 'cs_cdf'.

    Returns:
        EarthEngineResult:
            - status="success": Found qualifying scene and computed valid statistics; data contains
              a RegionalNdviAnalysis instance.
            - status="no_data": Zero qualifying scenes found or zero valid unmasked pixels in reduction.
            - status="error": Remote Earth Engine error, malformed metadata, or invariant violation.

    Raises:
        TypeError: If input types are incorrect.
        ValueError: If input values are out of valid bounds.
    """
    # 1. Synchronous Input Validation
    lat_val = _validate_numeric("latitude", latitude, min_val=-90.0, max_val=90.0)
    lon_val = _validate_numeric("longitude", longitude, min_val=-180.0, max_val=180.0)
    rad_val = _validate_numeric("radius_m", radius_m, strictly_positive=True)
    scale_val = _validate_numeric("scale_m", scale_m, strictly_positive=True)
    max_cloud_val = _validate_numeric(
        "max_cloud_percentage", max_cloud_percentage, min_val=0.0, max_val=100.0
    )
    clear_thresh_val = _validate_numeric(
        "clear_threshold", clear_threshold, min_val=0.0, max_val=1.0
    )
    min_cov_val = _validate_numeric(
        "min_usable_coverage", min_usable_coverage, min_val=0.0, max_val=1.0
    )

    if (
        not isinstance(lookback_days, int)
        or isinstance(lookback_days, bool)
        or lookback_days <= 0
    ):
        raise ValueError(
            f"lookback_days must be a strictly positive integer (> 0), got {lookback_days!r}"
        )

    ds_str = _validate_string("dataset", dataset)
    q_ds_str = _validate_string("quality_dataset", quality_dataset)
    q_band_str = _validate_string("quality_band", quality_band)

    # 2. Date Resolution
    start_str, end_str = resolve_date_range(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )

    try:
        # 3. Spatial Geometry Creation (client-side proxy)
        region = create_analysis_region(
            latitude=lat_val,
            longitude=lon_val,
            radius_m=rad_val,
        )

        # 4. Qualified Sentinel-2 Collection Construction (client-side proxy)
        collection = get_sentinel2_collection(
            region=region,
            start_date=start_str,
            end_date=end_str,
            lookback_days=lookback_days,
            max_cloud_percentage=max_cloud_val,
            dataset=ds_str,
            quality_dataset=q_ds_str,
            quality_band=q_band_str,
            clear_threshold=clear_thresh_val,
            min_usable_coverage=min_cov_val,
            apply_quality_filter=True,
        )

        # 5. Candidate Count Materialization (Materialization Call 1)
        image_count = int(collection.size().getInfo())
        if image_count == 0:
            return EarthEngineResult(
                status="no_data",
                dataset=ds_str,
                image_count=0,
                data=None,
                error=None,
            )

        # 6. Authoritative Image Selection (Exactly ONE image proxy)
        authoritative_image = collection.first()

        # 7. Metadata Materialization (Materialization Call 2)
        image_info = authoritative_image.getInfo()
        if not isinstance(image_info, dict) or not image_info:
            return EarthEngineResult(
                status="error",
                dataset=ds_str,
                image_count=image_count,
                data=None,
                error=EarthEngineError(
                    type="MetadataExtractionError",
                    message="Failed to retrieve properties from authoritative Sentinel-2 image.",
                ),
            )

        image_id = image_info.get("id", "")
        properties = image_info.get("properties", {})

        system_time_start = properties.get("system:time_start")
        if system_time_start is None:
            return EarthEngineResult(
                status="error",
                dataset=ds_str,
                image_count=image_count,
                data=None,
                error=EarthEngineError(
                    type="MetadataExtractionError",
                    message="Authoritative image missing required system:time_start property.",
                ),
            )

        acquisition_dt = datetime.fromtimestamp(
            system_time_start / 1000.0, tz=timezone.utc
        )
        acquisition_date_iso = acquisition_dt.isoformat()
        acquisition_calendar_date = acquisition_date_iso[:10]

        cloud_percentage = float(properties.get("CLOUDY_PIXEL_PERCENTAGE", 0.0))
        spacecraft_name = properties.get("SPACECRAFT_NAME")
        mgrs_tile = properties.get("MGRS_TILE")
        product_id = properties.get("PRODUCT_ID")

        usable_coverage_ratio = properties.get("USABLE_COVERAGE")
        usable_coverage_pct: float | None = None
        if usable_coverage_ratio is not None:
            usable_coverage_pct = round(float(usable_coverage_ratio) * 100.0, 2)

        observation_metadata = Sentinel2ImageMetadata(
            image_id=image_id,
            acquisition_date=acquisition_date_iso,
            cloud_percentage=cloud_percentage,
            spacecraft_name=spacecraft_name,
            mgrs_tile=mgrs_tile,
            product_id=product_id,
            system_time_start=system_time_start,
            usable_coverage_percentage=usable_coverage_pct,
            clear_threshold=clear_thresh_val,
            quality_band=q_band_str,
        )

        # 8. Consistent Quality Masking on Authoritative Image
        masked_image = mask_observation_quality(
            authoritative_image,
            clear_threshold=clear_thresh_val,
            quality_band=q_band_str,
        )

        # 9. NDVI Calculation on Masked Raster (client-side proxy)
        ndvi_image = calculate_ndvi(
            image=masked_image,
            region=region,
        )

        # 10. Regional Zonal Reduction (Materialization Call 3 inside helper)
        stats_result = calculate_ndvi_statistics(
            ndvi_image=ndvi_image,
            region=region,
            scale=scale_val,
        )

        if stats_result.status == "no_data":
            return EarthEngineResult(
                status="no_data",
                dataset=ds_str,
                image_count=image_count,
                data=None,
                error=None,
            )

        if stats_result.status == "error":
            return stats_result

        statistics: NdviRegionalStatistics = stats_result.data

        # 11. Statistical Invariant Verification
        try:
            _verify_statistical_invariants(statistics)
        except ValueError as inv_exc:
            return EarthEngineResult(
                status="error",
                dataset=ds_str,
                image_count=image_count,
                data=None,
                error=EarthEngineError(
                    type="StatisticalInvariantError",
                    message=str(inv_exc),
                ),
            )

        # 12. Freshness Derivation
        ref_dt = datetime.strptime(end_str, "%Y-%m-%d").date()
        acq_dt = datetime.strptime(acquisition_calendar_date, "%Y-%m-%d").date()
        age_days = max(0, (ref_dt - acq_dt).days)

        freshness_evidence = ObservationFreshness(
            reference_date=end_str,
            observation_age_days=age_days,
            lookback_window_days=lookback_days,
        )

        # 13. Quality Evidence Assembly
        quality_evidence = ObservationQualityEvidence(
            quality_dataset=q_ds_str,
            min_usable_coverage_threshold=min_cov_val,
            max_scene_cloud_threshold=max_cloud_val,
            quality_mask_applied=True,
            is_usable=True,
        )

        # 14. Analysis Region Metadata Assembly
        region_metadata = AnalysisRegionMetadata(
            latitude=lat_val,
            longitude=lon_val,
            radius_m=rad_val,
            geometry_type="PointBuffer",
            scale_m=scale_val,
        )

        # 15. Root Domain Analysis Construction
        analysis = RegionalNdviAnalysis(
            observation=observation_metadata,
            quality=quality_evidence,
            freshness=freshness_evidence,
            region=region_metadata,
            statistics=statistics,
            pipeline_version="1.0.0",
        )

        return EarthEngineResult(
            status="success",
            dataset=ds_str,
            image_count=image_count,
            data=analysis,
            error=None,
        )

    except Exception as exc:
        error_type = exc.__class__.__name__
        return EarthEngineResult(
            status="error",
            dataset=ds_str,
            image_count=None,
            data=None,
            error=EarthEngineError(
                type=error_type,
                message=str(exc),
            ),
        )
