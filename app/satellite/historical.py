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
"""Historical Sentinel-2 observation discovery, recency selection, and NDVI compositing.

This module implements Step 3A & Step 3B of Phase 2C Historical Satellite Intelligence
(DEC-014 / DEC-016):
- Step 3A: Discovers candidate Sentinel-2 SR scenes within a single target year's
  Phase 2B seasonal window [ee_filter_start, ee_filter_end), applies the Phase 1 quality
  gate (Cloud Score+ cs_cdf >= 0.60, scene cloud < 20%, usable coverage >= 70%), sorts
  strictly newest-first, and selects up to 3 newest usable observations.
- Step 3B: Applies pixel-level quality masking (mask_observation_quality) to each selected
  scene, computes NDVI per-scene (calculate_ndvi), composites them via pixel-wise median
  (ee.ImageCollection.median()), executes regional zonal reduction on the final composite,
  and constructs a strongly typed AnnualHistoricalNdviObservation.

Important Scope Boundaries:
---------------------------
- Does NOT orchestrate multi-year collections (Y-1, Y-2, Y-3) across years (Phase 2C Step 4).
- Does NOT calculate baseline anomalies or z-scores across historical years (Phase 2D).
- Operates strictly on a single target historical year.
"""

from datetime import datetime, timezone
import math
from typing import Union

import ee

from .ndvi import (
    calculate_ndvi,
    calculate_ndvi_statistics,
)
from .pipeline import (
    STATISTICAL_INVARIANT_EPSILON,
    _verify_statistical_invariants,
)
from .sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    SENTINEL2_SR_HARMONIZED,
    get_sentinel2_collection,
    mask_observation_quality,
)
from .types import (
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    EarthEngineResult,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
    NdviRegionalStatistics,
    SatelliteAnnualHistoricalNdviObservation,
    SatelliteHistoricalObservationSummary,
)

# Architectural maximum usable observations selected per historical year (DEC-014 / DEC-016)
DEFAULT_HISTORICAL_MAX_OBSERVATIONS: int = 3


def _validate_numeric_bound(
    name: str,
    value: Union[int, float],
    min_val: float = 0.0,
    max_val: float = 1.0,
) -> float:
    """Validates that a numeric threshold is a finite float in [min_val, max_val]."""
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or math.isnan(value)
        or math.isinf(value)
    ):
        raise ValueError(f"{name} must be a valid finite number, got {value!r}")
    val_float = float(value)
    if not (min_val <= val_float <= max_val):
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {value}")
    return val_float


def _validate_non_empty_string(name: str, value: str) -> str:
    """Validates that a parameter is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")
    return value.strip()


def select_historical_observations(
    temporal_window: HistoricalTemporalWindow,
    region: ee.Geometry,
    max_observations: int = DEFAULT_HISTORICAL_MAX_OBSERVATIONS,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
    quality_dataset: str = CLOUD_SCORE_PLUS_S2_HARMONIZED,
    quality_band: str = DEFAULT_QUALITY_BAND,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    min_usable_coverage: float = DEFAULT_MIN_USABLE_COVERAGE,
) -> EarthEngineResult:
    """Discovers and selects up to 3 newest usable Sentinel-2 observations for a single historical year.

    Applies the exact Phase 1 Cloud Score+ observation-quality gate to candidate scenes within
    the historical temporal window. Qualifying scenes (usable coverage >= min_usable_coverage)
    are sorted by acquisition timestamp descending and up to `max_observations` (default 3) are
    selected and converted into HistoricalObservationSummary instances (DEC-014 / DEC-016).

    Args:
        temporal_window: The target year's HistoricalTemporalWindow defining the 31-day search range.
        region: The parcel buffer spatial geometry (ee.Geometry).
        max_observations: Maximum number of newest usable observations to select (1 to 3). Defaults to 3.
        max_cloud_percentage: Coarse scene cloud threshold in percent. Defaults to 20.0%.
        dataset: Sentinel-2 Earth Engine dataset ID. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.
        quality_dataset: Cloud Score+ dataset ID. Defaults to 'GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.
        clear_threshold: Pixel clear-sky score threshold in [0.0, 1.0]. Defaults to 0.60.
        min_usable_coverage: Minimum regional usable coverage ratio in [0.0, 1.0]. Defaults to 0.70.

    Returns:
        EarthEngineResult:
            - status="success": Found >= 1 usable observation; data contains list[HistoricalObservationSummary]
              with selection_rank (1 = newest) and image_count = available_usable_scenes_count.
            - status="no_data": Zero qualifying scenes in the seasonal window; image_count = 0, data = [].
            - status="error": Earth Engine exception occurred; error contains details.

    Raises:
        TypeError: If temporal_window is not HistoricalTemporalWindow or region is not ee.Geometry.
        ValueError: If max_observations is not an integer in [1, 3] or thresholds are invalid.
    """
    if not isinstance(temporal_window, HistoricalTemporalWindow):
        raise TypeError(
            f"temporal_window must be an instance of HistoricalTemporalWindow, got {type(temporal_window)!r}"
        )
    if not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    if (
        not isinstance(max_observations, int)
        or isinstance(max_observations, bool)
        or max_observations <= 0
    ):
        raise ValueError(
            f"max_observations must be a strictly positive integer (> 0), got {max_observations!r}"
        )
    if max_observations > DEFAULT_HISTORICAL_MAX_OBSERVATIONS:
        raise ValueError(
            f"max_observations cannot exceed the architectural maximum of {DEFAULT_HISTORICAL_MAX_OBSERVATIONS} "
            f"(DEC-014 / DEC-016), got {max_observations}"
        )

    _validate_numeric_bound("max_cloud_percentage", max_cloud_percentage, 0.0, 100.0)
    _validate_numeric_bound("clear_threshold", clear_threshold, 0.0, 1.0)
    _validate_numeric_bound("min_usable_coverage", min_usable_coverage, 0.0, 1.0)
    _validate_non_empty_string("dataset", dataset)
    _validate_non_empty_string("quality_dataset", quality_dataset)
    _validate_non_empty_string("quality_band", quality_band)

    try:
        # Build quality-filtered collection for the historical temporal window
        collection = get_sentinel2_collection(
            region=region,
            start_date=temporal_window.ee_filter_start,
            end_date=temporal_window.ee_filter_end,
            max_cloud_percentage=max_cloud_percentage,
            dataset=dataset,
            quality_dataset=quality_dataset,
            quality_band=quality_band,
            clear_threshold=clear_threshold,
            min_usable_coverage=min_usable_coverage,
            apply_quality_filter=True,
        )

        # Single-call bundled metadata materialization (quota & latency discipline)
        bundle = ee.Dictionary({
            "available_count": collection.size(),
            "selected_images": collection.limit(max_observations).toList(max_observations),
        })
        info = bundle.getInfo()

        available_count = int(info.get("available_count", 0) if info else 0)
        selected_raw = info.get("selected_images", []) if info else []
        if selected_raw is None:
            selected_raw = []

        if available_count == 0 or len(selected_raw) == 0:
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=[],
                error=None,
            )

        # Guarantee deterministic newest-first ordering
        def _get_time_start(item: dict) -> int:
            props = item.get("properties", {}) or {}
            return int(props.get("system:time_start", 0) or 0)

        sorted_images = sorted(selected_raw, key=_get_time_start, reverse=True)
        selected_images = sorted_images[:max_observations]

        summaries: list[HistoricalObservationSummary] = []
        for rank_idx, img_dict in enumerate(selected_images):
            image_id = str(img_dict.get("id", ""))
            props = img_dict.get("properties", {}) or {}

            system_time_start = props.get("system:time_start")
            acquisition_date_iso = ""
            if system_time_start is not None:
                acq_dt = datetime.fromtimestamp(
                    system_time_start / 1000.0, tz=timezone.utc
                )
                acquisition_date_iso = acq_dt.isoformat()

            cloud_pct = float(props.get("CLOUDY_PIXEL_PERCENTAGE", 0.0))
            spacecraft = props.get("SPACECRAFT_NAME")
            tile = props.get("MGRS_TILE")
            product = props.get("PRODUCT_ID")

            usable_cov_ratio = props.get("USABLE_COVERAGE")
            usable_cov_pct: float | None = None
            if usable_cov_ratio is not None:
                usable_cov_pct = round(float(usable_cov_ratio) * 100.0, 2)

            summary = HistoricalObservationSummary(
                image_id=image_id,
                acquisition_date=acquisition_date_iso,
                target_year=temporal_window.target_year,
                cloud_percentage=cloud_pct,
                usable_coverage_percentage=usable_cov_pct,
                spacecraft_name=spacecraft,
                mgrs_tile=tile,
                product_id=product,
                system_time_start=system_time_start,
                selection_rank=rank_idx + 1,  # 1-based rank (1 = newest)
                clear_threshold=float(clear_threshold),
                quality_band=str(quality_band),
            )
            summaries.append(summary)

        return EarthEngineResult(
            status="success",
            dataset=dataset,
            image_count=available_count,
            data=summaries,
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


def build_historical_ndvi_composite(
    images: Union[ee.ImageCollection, list[ee.Image]],
    region: Union[ee.Geometry, None] = None,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    quality_band: str = DEFAULT_QUALITY_BAND,
) -> ee.Image:
    """Constructs a pixel-wise median NDVI composite from quality-linked Sentinel-2 images.

    For each input image:
    1. Applies Cloud Score+ pixel-level quality masking (mask_observation_quality).
    2. Calculates Normalized Difference Vegetation Index (calculate_ndvi).
    3. Stacks the masked NDVI rasters into an ee.ImageCollection.
    4. Computes the pixel-wise median across unmasked pixels (ee.ImageCollection.median()).

    Invariants:
    - Median is calculated independently per-pixel across the stack of NDVI images (DEC-016).
    - Masked pixels do not contribute to the median at that pixel.
    - If all scenes are masked at a pixel, that pixel remains masked in the composite.
    - Masked pixels are NEVER replaced with artificial zeros (NULL != 0.0).

    Args:
        images: An ee.ImageCollection or list of ee.Image objects with Cloud Score+ linked.
        region: Optional spatial analysis geometry (ee.Geometry) to clip rasters.
        clear_threshold: Clear-sky threshold for pixel usability in [0.0, 1.0]. Defaults to 0.60.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.

    Returns:
        ee.Image: Earth Engine image proxy containing the single composite 'NDVI' band.

    Raises:
        TypeError: If images is not an ee.ImageCollection or list of ee.Image, or region is invalid.
        ValueError: If images is an empty list, or thresholds are invalid.
    """
    if region is not None and not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    _validate_numeric_bound("clear_threshold", clear_threshold, 0.0, 1.0)
    _validate_non_empty_string("quality_band", quality_band)

    if isinstance(images, list):
        if len(images) == 0:
            raise ValueError("images list cannot be empty")
        for i, img in enumerate(images):
            if not isinstance(img, ee.Image):
                raise TypeError(
                    f"images[{i}] must be an instance of ee.Image, got {type(img)!r}"
                )

        ndvi_images = [
            calculate_ndvi(
                mask_observation_quality(
                    img,
                    clear_threshold=clear_threshold,
                    quality_band=quality_band,
                ),
                region=region,
            )
            for img in images
        ]
        ndvi_collection = ee.ImageCollection(ndvi_images)
        return ndvi_collection.median()

    elif isinstance(images, ee.ImageCollection):
        def _process_image(img: ee.Image) -> ee.Image:
            masked = mask_observation_quality(
                img,
                clear_threshold=clear_threshold,
                quality_band=quality_band,
            )
            return calculate_ndvi(masked, region=region)

        ndvi_collection = images.map(_process_image)
        return ndvi_collection.median()

    else:
        raise TypeError(
            f"images must be an instance of ee.ImageCollection or list[ee.Image], got {type(images)!r}"
        )


def compute_annual_historical_ndvi(
    temporal_window: HistoricalTemporalWindow,
    region: ee.Geometry,
    max_observations: int = DEFAULT_HISTORICAL_MAX_OBSERVATIONS,
    scale_m: Union[int, float] = 10.0,
    max_cloud_percentage: float = DEFAULT_MAX_CLOUD_PERCENTAGE,
    dataset: str = SENTINEL2_SR_HARMONIZED,
    quality_dataset: str = CLOUD_SCORE_PLUS_S2_HARMONIZED,
    quality_band: str = DEFAULT_QUALITY_BAND,
    clear_threshold: float = DEFAULT_CLEAR_THRESHOLD,
    min_usable_coverage: float = DEFAULT_MIN_USABLE_COVERAGE,
) -> EarthEngineResult:
    """Orchestrates single-target-year historical observation discovery, compositing, and statistics.

    Workflow (Phase 2C Step 3A & Step 3B):
    1. Discovers and selects up to `max_observations` (default 3) newest usable observations
       within the target year's 31-day seasonal window.
    2. Constructs the server-side pixel-wise median NDVI composite across selected scenes.
    3. Calculates regional zonal NDVI summary statistics over the composite raster.
    4. Verifies mathematical envelope invariants (min <= median <= max, min <= mean <= max).
    5. Returns an EarthEngineResult containing an AnnualHistoricalNdviObservation.

    Args:
        temporal_window: Target year's HistoricalTemporalWindow defining the 31-day search range.
        region: Parcel buffer spatial geometry (ee.Geometry).
        max_observations: Maximum newest usable observations to select (1 to 3). Defaults to 3.
        scale_m: Spatial reduction scale in meters (> 0). Defaults to 10.0.
        max_cloud_percentage: Coarse scene cloud threshold in percent. Defaults to 20.0%.
        dataset: Sentinel-2 Earth Engine dataset ID. Defaults to 'COPERNICUS/S2_SR_HARMONIZED'.
        quality_dataset: Cloud Score+ dataset ID. Defaults to 'GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED'.
        quality_band: Quality band identifier. Defaults to 'cs_cdf'.
        clear_threshold: Pixel clear-sky score threshold in [0.0, 1.0]. Defaults to 0.60.
        min_usable_coverage: Minimum regional usable coverage ratio in [0.0, 1.0]. Defaults to 0.70.

    Returns:
        EarthEngineResult:
            - status="success": Found usable observations and computed valid composite statistics;
              data contains an AnnualHistoricalNdviObservation instance.
            - status="no_data": Zero usable observations found, or reduction had zero valid pixels;
              data contains an AnnualHistoricalNdviObservation with status="no_data".
            - status="error": Remote Earth Engine exception or statistical invariant failure;
              data contains an AnnualHistoricalNdviObservation with status="error" or None.

    Raises:
        TypeError: If temporal_window is not HistoricalTemporalWindow or region is not ee.Geometry.
        ValueError: If max_observations, scale_m, or thresholds are out of valid bounds.
    """
    if not isinstance(temporal_window, HistoricalTemporalWindow):
        raise TypeError(
            f"temporal_window must be an instance of HistoricalTemporalWindow, got {type(temporal_window)!r}"
        )
    if not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    if (
        not isinstance(max_observations, int)
        or isinstance(max_observations, bool)
        or max_observations <= 0
    ):
        raise ValueError(
            f"max_observations must be a strictly positive integer (> 0), got {max_observations!r}"
        )
    if max_observations > DEFAULT_HISTORICAL_MAX_OBSERVATIONS:
        raise ValueError(
            f"max_observations cannot exceed the architectural maximum of {DEFAULT_HISTORICAL_MAX_OBSERVATIONS} "
            f"(DEC-014 / DEC-016), got {max_observations}"
        )

    if (
        not isinstance(scale_m, (int, float))
        or isinstance(scale_m, bool)
        or math.isnan(scale_m)
        or math.isinf(scale_m)
        or float(scale_m) <= 0.0
    ):
        raise ValueError(f"scale_m must be a strictly positive number (> 0), got {scale_m!r}")
    scale_val = float(scale_m)

    _validate_numeric_bound("max_cloud_percentage", max_cloud_percentage, 0.0, 100.0)
    _validate_numeric_bound("clear_threshold", clear_threshold, 0.0, 1.0)
    _validate_numeric_bound("min_usable_coverage", min_usable_coverage, 0.0, 1.0)
    _validate_non_empty_string("dataset", dataset)
    _validate_non_empty_string("quality_dataset", quality_dataset)
    _validate_non_empty_string("quality_band", quality_band)

    try:
        # Step 1: Discover and select candidate observations (Step 3A)
        selection_result = select_historical_observations(
            temporal_window=temporal_window,
            region=region,
            max_observations=max_observations,
            max_cloud_percentage=max_cloud_percentage,
            dataset=dataset,
            quality_dataset=quality_dataset,
            quality_band=quality_band,
            clear_threshold=clear_threshold,
            min_usable_coverage=min_usable_coverage,
        )

        if selection_result.status == "error":
            obs_err = AnnualHistoricalNdviObservation(
                target_year=temporal_window.target_year,
                temporal_window=temporal_window,
                available_usable_scenes_count=0,
                selected_scenes_count=0,
                selected_observations=[],
                statistics=None,
                status="error",
                composite_method="none",
                pipeline_version="1.0.0",
                error=selection_result.error,
            )
            return EarthEngineResult(
                status="error",
                dataset=dataset,
                image_count=None,
                data=obs_err,
                error=selection_result.error,
            )

        if selection_result.status == "no_data" or not selection_result.data or selection_result.image_count == 0:
            observation_nodata = AnnualHistoricalNdviObservation(
                target_year=temporal_window.target_year,
                temporal_window=temporal_window,
                available_usable_scenes_count=0,
                selected_scenes_count=0,
                selected_observations=[],
                statistics=None,
                status="no_data",
                composite_method="none",
                pipeline_version="1.0.0",
                error=None,
            )
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=0,
                data=observation_nodata,
                error=None,
            )

        available_count: int = selection_result.image_count or 0
        selected_summaries: list[HistoricalObservationSummary] = selection_result.data
        selected_count: int = len(selected_summaries)

        # Step 2: Build server-side quality-linked collection of selected images
        collection = get_sentinel2_collection(
            region=region,
            start_date=temporal_window.ee_filter_start,
            end_date=temporal_window.ee_filter_end,
            max_cloud_percentage=max_cloud_percentage,
            dataset=dataset,
            quality_dataset=quality_dataset,
            quality_band=quality_band,
            clear_threshold=clear_threshold,
            min_usable_coverage=min_usable_coverage,
            apply_quality_filter=True,
        )
        selected_collection = collection.limit(selected_count)

        # Step 3: Build pixel-wise median NDVI composite (Step 3B)
        composite_ndvi = build_historical_ndvi_composite(
            images=selected_collection,
            region=region,
            clear_threshold=clear_threshold,
            quality_band=quality_band,
        )

        composite_method = "pixel_median" if selected_count >= 2 else "identity"

        # Step 4: Regional Zonal Reduction on the Final Composite
        stats_result = calculate_ndvi_statistics(
            ndvi_image=composite_ndvi,
            region=region,
            scale=scale_val,
        )

        if stats_result.status == "no_data":
            obs_nodata = AnnualHistoricalNdviObservation(
                target_year=temporal_window.target_year,
                temporal_window=temporal_window,
                available_usable_scenes_count=available_count,
                selected_scenes_count=0,
                selected_observations=[],
                statistics=None,
                status="no_data",
                composite_method=composite_method,
                pipeline_version="1.0.0",
                error=None,
            )
            return EarthEngineResult(
                status="no_data",
                dataset=dataset,
                image_count=available_count,
                data=obs_nodata,
                error=None,
            )

        if stats_result.status == "error":
            obs_err = AnnualHistoricalNdviObservation(
                target_year=temporal_window.target_year,
                temporal_window=temporal_window,
                available_usable_scenes_count=available_count,
                selected_scenes_count=selected_count,
                selected_observations=selected_summaries,
                statistics=None,
                status="error",
                composite_method=composite_method,
                pipeline_version="1.0.0",
                error=stats_result.error,
            )
            return EarthEngineResult(
                status="error",
                dataset=dataset,
                image_count=available_count,
                data=obs_err,
                error=stats_result.error,
            )

        statistics: NdviRegionalStatistics = stats_result.data

        # Step 5: Statistical Invariant Verification
        try:
            _verify_statistical_invariants(statistics)
        except ValueError as inv_exc:
            err = EarthEngineError(
                type="StatisticalInvariantError",
                message=str(inv_exc),
            )
            obs_inv_err = AnnualHistoricalNdviObservation(
                target_year=temporal_window.target_year,
                temporal_window=temporal_window,
                available_usable_scenes_count=available_count,
                selected_scenes_count=selected_count,
                selected_observations=selected_summaries,
                statistics=None,
                status="error",
                composite_method=composite_method,
                pipeline_version="1.0.0",
                error=err,
            )
            return EarthEngineResult(
                status="error",
                dataset=dataset,
                image_count=available_count,
                data=obs_inv_err,
                error=err,
            )

        # Step 6: Construct Successful Annual Historical Observation
        annual_observation = AnnualHistoricalNdviObservation(
            target_year=temporal_window.target_year,
            temporal_window=temporal_window,
            available_usable_scenes_count=available_count,
            selected_scenes_count=selected_count,
            selected_observations=selected_summaries,
            statistics=statistics,
            status="success",
            composite_method=composite_method,
            pipeline_version="1.0.0",
            error=None,
        )

        return EarthEngineResult(
            status="success",
            dataset=dataset,
            image_count=available_count,
            data=annual_observation,
            error=None,
        )

    except Exception as exc:
        error_type = exc.__class__.__name__
        err = EarthEngineError(
            type=error_type,
            message=str(exc),
        )
        return EarthEngineResult(
            status="error",
            dataset=dataset,
            image_count=None,
            data=None,
            error=err,
        )


# Semantic aliases for discoverability and backward/forward compatibility
build_annual_historical_composite = compute_annual_historical_ndvi
build_annual_historical_ndvi_observation = compute_annual_historical_ndvi
