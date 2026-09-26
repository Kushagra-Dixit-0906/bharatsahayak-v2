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
"""Historical Sentinel-2 observation discovery and recency selection.

This module implements Step 3A of Phase 2C Historical Satellite Intelligence
(DEC-014 / DEC-016):
- Queries Sentinel-2 Surface Reflectance imagery within a single target year's
  Phase 2B seasonal window [ee_filter_start, ee_filter_end).
- Applies the exact Phase 1 observation-quality gate (Cloud Score+ cs_cdf >= 0.60,
  scene cloud < 20%, regional usable coverage >= 70%).
- Sorts usable observations strictly by acquisition date descending (newest first).
- Selects up to 3 newest usable observations (3+ -> 3, 2 -> 2, 1 -> 1, 0 -> no_data).
- Preserves empirical available vs. selected observation counts and generates
  structured HistoricalObservationSummary records.

Important Scope Boundaries:
---------------------------
- Does NOT perform NDVI band mathematics or median compositing (Phase 2C Step 3B).
- Does NOT perform zonal statistical reductions on composites (Phase 2C Step 3B).
- Does NOT orchestrate multi-year collections (Y-1, Y-2, Y-3) (Phase 2C Step 4).
- Does NOT calculate baseline anomalies or z-scores (Phase 2A / Phase 2D).
"""

from datetime import datetime, timezone
import math
from typing import Union

import ee

from .sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    SENTINEL2_SR_HARMONIZED,
    get_sentinel2_collection,
)
from .types import (
    EarthEngineError,
    EarthEngineResult,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
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
