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
"""Unit tests for the regional NDVI orchestration pipeline (DEC-011, Phase 1H.4)."""

import math
from unittest.mock import MagicMock, patch

import ee
import pytest

from app.satellite.geometry import DEFAULT_ANALYSIS_RADIUS_M
from app.satellite.pipeline import (
    STATISTICAL_INVARIANT_EPSILON,
    analyze_regional_ndvi,
)
from app.satellite.sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    SENTINEL2_SR_HARMONIZED,
)
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    EarthEngineResult,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    Sentinel2ImageMetadata,
)


@pytest.fixture(autouse=True)
def init_mock_ee():
    """Ensures Earth Engine client is initialized for tests."""
    ee.Initialize(project="bharatsahayak-v2")


def _sample_image_info() -> dict:
    """Returns a realistic mock Sentinel-2 image getInfo() response."""
    return {
        "id": "COPERNICUS/S2_SR_HARMONIZED/20260816T054251_20260816T055032_T43REQ",
        "properties": {
            "system:time_start": 1786859441321,  # 2026-08-16T05:50:41.321000+00:00
            "CLOUDY_PIXEL_PERCENTAGE": 10.995,
            "SPACECRAFT_NAME": "Sentinel-2A",
            "MGRS_TILE": "43REQ",
            "PRODUCT_ID": "S2A_MSIL2A_20260816T054251_N0511_R048_T43REQ_20260816T083432",
            "USABLE_COVERAGE": 0.9450,
        },
    }


def _sample_statistics(
    mean: float = 0.554,
    median: float = 0.550,
    min_val: float = 0.210,
    max_val: float = 0.820,
    count: int = 314,
) -> NdviRegionalStatistics:
    """Returns a sample valid NdviRegionalStatistics instance."""
    return NdviRegionalStatistics(
        mean=mean,
        median=median,
        min=min_val,
        max=max_val,
        valid_pixel_count=count,
    )


# ==============================================================================
# 1. INPUT VALIDATION TESTS (Synchronous before network calls)
# ==============================================================================


@pytest.mark.parametrize(
    ("bad_lat", "exc_type"),
    [
        (-90.1, ValueError),
        (90.1, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        (-math.inf, ValueError),
        ("30.9157", TypeError),
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
        ([], TypeError),
        ({}, TypeError),
    ],
)
def test_invalid_latitude_rejected(bad_lat, exc_type) -> None:
    """Verifies that invalid latitude raises ValueError or TypeError synchronously."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(latitude=bad_lat, longitude=75.7196)


@pytest.mark.parametrize(
    ("bad_lon", "exc_type"),
    [
        (-180.1, ValueError),
        (180.1, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        (-math.inf, ValueError),
        ("75.7196", TypeError),
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
        ([], TypeError),
        ({}, TypeError),
    ],
)
def test_invalid_longitude_rejected(bad_lon, exc_type) -> None:
    """Verifies that invalid longitude raises ValueError or TypeError synchronously."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(latitude=30.9157, longitude=bad_lon)


@pytest.mark.parametrize(
    ("bad_radius", "exc_type"),
    [
        (0, ValueError),
        (0.0, ValueError),
        (-1.0, ValueError),
        (-100.0, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        ("100", TypeError),
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
        ([], TypeError),
    ],
)
def test_invalid_radius_rejected(bad_radius, exc_type) -> None:
    """Verifies that non-positive, non-numeric, or infinite radius raises error synchronously."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(latitude=30.9157, longitude=75.7196, radius_m=bad_radius)


@pytest.mark.parametrize(
    "bad_lookback",
    [
        0,
        -1,
        -30,
        30.5,
        "30",
        None,
        True,
        False,
        [],
        {},
    ],
)
def test_invalid_lookback_days_rejected(bad_lookback) -> None:
    """Verifies that non-positive, boolean, non-integer lookback_days raises ValueError."""
    with pytest.raises(ValueError):
        analyze_regional_ndvi(
            latitude=30.9157, longitude=75.7196, lookback_days=bad_lookback
        )


@pytest.mark.parametrize(
    ("bad_cloud", "exc_type"),
    [
        (-0.1, ValueError),
        (100.1, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        ("20.0", TypeError),
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
    ],
)
def test_invalid_cloud_threshold_rejected(bad_cloud, exc_type) -> None:
    """Verifies that out-of-bound or non-numeric max_cloud_percentage raises error."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(
            latitude=30.9157, longitude=75.7196, max_cloud_percentage=bad_cloud
        )


@pytest.mark.parametrize(
    ("bad_clear", "exc_type"),
    [
        (-0.01, ValueError),
        (1.01, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        ("0.60", TypeError),
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
    ],
)
def test_invalid_clear_threshold_rejected(bad_clear, exc_type) -> None:
    """Verifies that clear_threshold outside [0, 1] or non-numeric raises error."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(
            latitude=30.9157, longitude=75.7196, clear_threshold=bad_clear
        )


@pytest.mark.parametrize(
    ("bad_coverage", "exc_type"),
    [
        (-0.01, ValueError),
        (1.01, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        ("0.70", TypeError),
        (None, TypeError),
        (True, TypeError),
        (False, TypeError),
    ],
)
def test_invalid_usable_coverage_rejected(bad_coverage, exc_type) -> None:
    """Verifies that min_usable_coverage outside [0, 1] or non-numeric raises error."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(
            latitude=30.9157, longitude=75.7196, min_usable_coverage=bad_coverage
        )


@pytest.mark.parametrize(
    ("bad_scale", "exc_type"),
    [
        (0, ValueError),
        (0.0, ValueError),
        (-10.0, ValueError),
        (math.nan, ValueError),
        (math.inf, ValueError),
        ("10", TypeError),
        (None, TypeError),
        (True, TypeError),
    ],
)
def test_invalid_scale_rejected(bad_scale, exc_type) -> None:
    """Verifies that non-positive, boolean, or non-numeric scale_m raises error."""
    with pytest.raises(exc_type):
        analyze_regional_ndvi(
            latitude=30.9157, longitude=75.7196, scale_m=bad_scale
        )


@pytest.mark.parametrize(
    ("param_name", "bad_str", "exc_type"),
    [
        ("dataset", "", ValueError),
        ("dataset", "   ", ValueError),
        ("dataset", None, TypeError),
        ("dataset", 123, TypeError),
        ("quality_dataset", "", ValueError),
        ("quality_dataset", "   ", ValueError),
        ("quality_dataset", None, TypeError),
        ("quality_band", "", ValueError),
        ("quality_band", "   ", ValueError),
        ("quality_band", None, TypeError),
    ],
)
def test_empty_or_invalid_dataset_strings_rejected(param_name, bad_str, exc_type) -> None:
    """Verifies that empty, whitespace, or non-string dataset parameters raise error."""
    kwargs = {
        "latitude": 30.9157,
        "longitude": 75.7196,
        param_name: bad_str,
    }
    with pytest.raises(exc_type):
        analyze_regional_ndvi(**kwargs)


# ==============================================================================
# 2. SUCCESSFUL ORCHESTRATION & PAYLOAD ASSEMBLY
# ==============================================================================


@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_valid_success_assembly(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
) -> None:
    """Verifies full end-to-end assembly of a valid RegionalNdviAnalysis payload."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 3
    mock_image = MagicMock()
    mock_image.getInfo.return_value = _sample_image_info()
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    mock_masked_img = MagicMock()
    mock_mask.return_value = mock_masked_img

    mock_ndvi_img = MagicMock()
    mock_calc_ndvi.return_value = mock_ndvi_img

    stats = _sample_statistics(mean=0.554, median=0.550, min_val=0.210, max_val=0.820, count=314)
    mock_calc_stats.return_value = EarthEngineResult(
        status="success",
        dataset=SENTINEL2_SR_HARMONIZED,
        image_count=1,
        data=stats,
    )

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        radius_m=100.0,
        start_date="2026-08-01",
        end_date="2026-08-31",
        lookback_days=30,
    )

    assert isinstance(result, EarthEngineResult)
    assert result.status == "success"
    assert result.dataset == SENTINEL2_SR_HARMONIZED
    assert result.image_count == 3
    assert result.error is None

    analysis = result.data
    assert isinstance(analysis, RegionalNdviAnalysis)
    assert analysis.pipeline_version == "1.0.0"

    # Observation metadata
    obs = analysis.observation
    assert isinstance(obs, Sentinel2ImageMetadata)
    assert obs.image_id == "COPERNICUS/S2_SR_HARMONIZED/20260816T054251_20260816T055032_T43REQ"
    assert obs.acquisition_date == "2026-08-16T05:50:41.321000+00:00"
    assert obs.cloud_percentage == 10.995
    assert obs.spacecraft_name == "Sentinel-2A"
    assert obs.mgrs_tile == "43REQ"
    assert obs.product_id == "S2A_MSIL2A_20260816T054251_N0511_R048_T43REQ_20260816T083432"
    assert obs.system_time_start == 1786859441321
    assert obs.usable_coverage_percentage == 94.50
    assert obs.clear_threshold == DEFAULT_CLEAR_THRESHOLD
    assert obs.quality_band == DEFAULT_QUALITY_BAND

    # Quality evidence
    qual = analysis.quality
    assert isinstance(qual, ObservationQualityEvidence)
    assert qual.quality_dataset == CLOUD_SCORE_PLUS_S2_HARMONIZED
    assert qual.min_usable_coverage_threshold == DEFAULT_MIN_USABLE_COVERAGE
    assert qual.max_scene_cloud_threshold == DEFAULT_MAX_CLOUD_PERCENTAGE
    assert qual.quality_mask_applied is True
    assert qual.is_usable is True

    # Freshness
    fresh = analysis.freshness
    assert isinstance(fresh, ObservationFreshness)
    assert fresh.reference_date == "2026-08-31"
    assert fresh.observation_age_days == 15  # 2026-08-31 minus 2026-08-16
    assert fresh.lookback_window_days == 30

    # Region metadata
    reg = analysis.region
    assert isinstance(reg, AnalysisRegionMetadata)
    assert reg.latitude == 30.9157
    assert reg.longitude == 75.7196
    assert reg.radius_m == 100.0
    assert reg.geometry_type == "PointBuffer"
    assert reg.scale_m == 10.0

    # Statistics
    s = analysis.statistics
    assert isinstance(s, NdviRegionalStatistics)
    assert s.mean == 0.554
    assert s.median == 0.550
    assert s.min == 0.210
    assert s.max == 0.820
    assert s.valid_pixel_count == 314


# ==============================================================================
# 3. SINGLE AUTHORITATIVE OBSERVATION & NO SECONDARY SELECTION
# ==============================================================================


@patch("app.satellite.sentinel2.get_most_recent_sentinel2_image")
@patch("app.satellite.sentinel2.select_most_recent_sentinel2_image")
@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_single_authoritative_image_selection_and_no_secondary_selection(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
    mock_select_recent,
    mock_get_recent,
) -> None:
    """Verifies that collection.first() is called exactly once and lower-level discovery functions are NOT called."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 2
    mock_image = MagicMock()
    mock_image.getInfo.return_value = _sample_image_info()
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    stats = _sample_statistics()
    mock_calc_stats.return_value = EarthEngineResult(status="success", data=stats)

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "success"

    # Verify collection.first() was called exactly once
    assert mock_coll.first.call_count == 1

    # Verify mask_observation_quality was invoked with the exact same authoritative image proxy
    mock_mask.assert_called_once_with(
        mock_image,
        clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        quality_band=DEFAULT_QUALITY_BAND,
    )

    # Verify secondary image discovery/selection helpers were NEVER called
    mock_select_recent.assert_not_called()
    mock_get_recent.assert_not_called()


# ==============================================================================
# 4. ZERO CANDIDATE SHORT-CIRCUIT & ZERO VALID PIXELS (NO_DATA)
# ==============================================================================


@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_zero_candidate_short_circuit_no_data(mock_get_coll) -> None:
    """Verifies that candidate count == 0 short-circuits immediately to status='no_data'."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 0
    mock_get_coll.return_value = mock_coll

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="1990-01-01",
        end_date="1990-01-31",
    )

    assert isinstance(result, EarthEngineResult)
    assert result.status == "no_data"
    assert result.dataset == SENTINEL2_SR_HARMONIZED
    assert result.image_count == 0
    assert result.data is None
    assert result.error is None

    # Verify collection.first() was never called
    mock_coll.first.assert_not_called()


@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_zero_valid_pixels_returns_no_data(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
) -> None:
    """Verifies that if zonal reduction returns no_data (all pixels masked), pipeline returns no_data."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    mock_image.getInfo.return_value = _sample_image_info()
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    mock_calc_stats.return_value = EarthEngineResult(
        status="no_data",
        dataset=SENTINEL2_SR_HARMONIZED,
        image_count=0,
        data=None,
        error=None,
    )

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "no_data"
    assert result.dataset == SENTINEL2_SR_HARMONIZED
    assert result.image_count == 1
    assert result.data is None
    assert result.error is None


# ==============================================================================
# 5. STATISTICAL INVARIANT VERIFICATION
# ==============================================================================


@pytest.mark.parametrize(
    ("mean", "median", "min_val", "max_val"),
    [
        (0.50, 0.50, 0.50, 0.50),  # Flat / homogeneous region
        (0.50, 0.45, 0.10, 0.90),  # Standard distribution
        (0.1000001, 0.10, 0.10, 0.90),  # Invariant within epsilon
        (0.8999999, 0.90, 0.10, 0.90),  # Invariant within epsilon
    ],
)
@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_statistics_invariant_success(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
    mean: float,
    median: float,
    min_val: float,
    max_val: float,
) -> None:
    """Verifies that valid statistical envelopes pass invariant checks."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    mock_image.getInfo.return_value = _sample_image_info()
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    stats = _sample_statistics(mean=mean, median=median, min_val=min_val, max_val=max_val)
    mock_calc_stats.return_value = EarthEngineResult(status="success", data=stats)

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "success"
    assert result.data.statistics.mean == mean


@pytest.mark.parametrize(
    ("mean", "median", "min_val", "max_val", "violation_desc"),
    [
        (0.95, 0.50, 0.10, 0.90, "mean > max"),
        (0.05, 0.50, 0.10, 0.90, "mean < min"),
        (0.50, 0.95, 0.10, 0.90, "median > max"),
        (0.50, 0.05, 0.10, 0.90, "median < min"),
    ],
)
@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_statistics_invariant_failure_returns_error(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
    mean: float,
    median: float,
    min_val: float,
    max_val: float,
    violation_desc: str,
) -> None:
    """Verifies that statistical invariant violations return status='error' with StatisticalInvariantError."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    mock_image.getInfo.return_value = _sample_image_info()
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    stats = _sample_statistics(mean=mean, median=median, min_val=min_val, max_val=max_val)
    mock_calc_stats.return_value = EarthEngineResult(status="success", data=stats)

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert isinstance(result, EarthEngineResult)
    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert result.error.type == "StatisticalInvariantError"
    assert "Statistical invariant violation" in result.error.message


# ==============================================================================
# 6. METADATA EXTRACTION & ERROR HANDLING
# ==============================================================================


@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_malformed_image_metadata_returns_error(mock_get_coll) -> None:
    """Verifies that empty or non-dict getInfo() returns structured error."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    mock_image.getInfo.return_value = {}  # Empty dict
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "MetadataExtractionError"
    assert "Failed to retrieve properties" in result.error.message


@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_missing_system_time_start_returns_error(mock_get_coll) -> None:
    """Verifies that missing system:time_start returns structured error."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    mock_image.getInfo.return_value = {
        "id": "COPERNICUS/S2_SR_HARMONIZED/test",
        "properties": {
            "CLOUDY_PIXEL_PERCENTAGE": 10.0,
            # system:time_start missing!
        },
    }
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "MetadataExtractionError"
    assert "system:time_start" in result.error.message


@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_remote_earth_engine_exception_propagated(mock_get_coll) -> None:
    """Verifies that remote Earth Engine exceptions are caught and wrapped into EarthEngineResult error."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.side_effect = ee.EEException("User memory limit exceeded.")
    mock_get_coll.return_value = mock_coll

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert isinstance(result, EarthEngineResult)
    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert result.error.type == "EEException"
    assert "User memory limit exceeded" in result.error.message


@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_stats_error_propagated(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
) -> None:
    """Verifies that if calculate_ndvi_statistics returns an error result, it is propagated directly."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    mock_image.getInfo.return_value = _sample_image_info()
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    mock_calc_stats.return_value = EarthEngineResult(
        status="error",
        error=EarthEngineError(
            type="EEComputationError",
            message="Server compute failed during zonal reduction.",
        ),
    )

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "EEComputationError"
    assert "Server compute failed" in result.error.message


# ==============================================================================
# 7. FRESHNESS CALCULATION EDGE CASES
# ==============================================================================


@patch("app.satellite.pipeline.calculate_ndvi_statistics")
@patch("app.satellite.pipeline.calculate_ndvi")
@patch("app.satellite.pipeline.mask_observation_quality")
@patch("app.satellite.pipeline.get_sentinel2_collection")
def test_freshness_zero_days_when_same_day(
    mock_get_coll,
    mock_mask,
    mock_calc_ndvi,
    mock_calc_stats,
) -> None:
    """Verifies that an image acquired on the reference date yields observation_age_days = 0."""
    mock_coll = MagicMock()
    mock_coll.size().getInfo.return_value = 1
    mock_image = MagicMock()
    # 2026-08-31T05:50:41.000Z -> timestamp 1788155441000
    mock_image.getInfo.return_value = {
        "id": "test_same_day",
        "properties": {
            "system:time_start": 1788155441000,
            "CLOUDY_PIXEL_PERCENTAGE": 5.0,
            "USABLE_COVERAGE": 0.99,
        },
    }
    mock_coll.first.return_value = mock_image
    mock_get_coll.return_value = mock_coll

    stats = _sample_statistics()
    mock_calc_stats.return_value = EarthEngineResult(status="success", data=stats)

    result = analyze_regional_ndvi(
        latitude=30.9157,
        longitude=75.7196,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "success"
    assert result.data.freshness.observation_age_days == 0
    assert result.data.freshness.reference_date == "2026-08-31"
