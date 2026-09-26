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
"""Integration tests validating EarthEngineResult contracts against live Earth Engine behavior."""

import os

import ee
import pytest

from app.satellite.geometry import create_analysis_region
from app.satellite.ndvi import (
    NDVI_BAND_NAME,
    NIR_BAND,
    RED_BAND,
    calculate_ndvi,
    calculate_ndvi_statistics,
    compute_ndvi_statistics,
)
from app.satellite.sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    calculate_usable_coverage,
    get_most_recent_sentinel2_image,
    get_sentinel2_collection,
    mask_observation_quality,
    select_most_recent_sentinel2_image,
)
from app.satellite.pipeline import analyze_regional_ndvi
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    EarthEngineResult,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    SatelliteRegionalStatistics,
    Sentinel2ImageMetadata,
)


TEST_POINT = [75.7196, 30.9157]  # [longitude, latitude] near Ludhiana, Punjab
PUNJAB_LATITUDE = 30.9157
PUNJAB_LONGITUDE = 75.7196
TEST_DATASET = "COPERNICUS/S2_SR_HARMONIZED"



@pytest.fixture(scope="module")
def ee_session() -> str:
    """Initializes Earth Engine for the integration test module or skips if credentials unavailable."""
    project_id = os.environ.get("EE_PROJECT_ID", "bharatsahayak-v2")
    try:
        ee.Initialize(project=project_id)
    except Exception as exc:
        pytest.skip(
            f"Earth Engine authentication not available or initialization failed: {exc}"
        )
    return project_id


def test_earth_engine_connectivity_success(ee_session: str) -> None:
    """Test 1 (SUCCESS): Bounded query returning images mapped to EarthEngineResult(status='success')."""
    point = ee.Geometry.Point(TEST_POINT)
    collection = (
        ee.ImageCollection(TEST_DATASET)
        .filterBounds(point)
        .filterDate("2026-08-01", "2026-08-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    image_count = int(collection.size().getInfo())
    assert image_count > 0, "Expected at least 1 image for the test fixture query"

    result = EarthEngineResult(
        status="success",
        dataset=TEST_DATASET,
        image_count=image_count,
    )

    assert result.status == "success"
    assert result.dataset == TEST_DATASET
    assert result.image_count == image_count
    assert result.image_count > 0
    assert result.error is None


def test_earth_engine_connectivity_no_data(ee_session: str) -> None:
    """Test 2 (NO DATA): Valid query with zero matching images mapped to EarthEngineResult(status='no_data')."""
    point = ee.Geometry.Point(TEST_POINT)
    # Date range prior to Sentinel-2 deployment guaranteed to yield zero scenes
    collection = (
        ee.ImageCollection(TEST_DATASET)
        .filterBounds(point)
        .filterDate("1990-01-01", "1990-01-02")
    )

    image_count = int(collection.size().getInfo())
    assert (
        image_count == 0
    ), "Expected exactly 0 images for pre-Sentinel-2 date range"

    result = EarthEngineResult(
        status="no_data",
        dataset=TEST_DATASET,
        image_count=0,
        error=None,
    )

    assert result.status == "no_data"
    assert result.dataset == TEST_DATASET
    assert result.image_count == 0
    assert result.error is None


def test_earth_engine_connectivity_error(ee_session: str) -> None:
    """Test 3 (ERROR): Query for an invalid asset produces ee.EEException mapped to EarthEngineResult(status='error')."""
    invalid_asset_id = "NON_EXISTENT/INVALID_ASSET_12345"

    with pytest.raises(ee.EEException) as exc_info:
        ee.ImageCollection(invalid_asset_id).size().getInfo()

    error = EarthEngineError(
        type="EEException",
        message=str(exc_info.value),
    )

    result = EarthEngineResult(
        status="error",
        error=error,
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "EEException"
    assert len(result.error.message) > 0
    assert result.dataset is None
    assert result.image_count is None


def test_earth_engine_region_query_success(ee_session: str) -> None:
    """Test 4 (REGION SUCCESS): Bounded query using create_analysis_region() returns Sentinel-2 images."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    collection = (
        ee.ImageCollection(TEST_DATASET)
        .filterBounds(region)
        .filterDate("2026-08-01", "2026-08-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    image_count = int(collection.size().getInfo())
    assert image_count > 0, "Expected at least 1 image for the analysis region query"

    result = EarthEngineResult(
        status="success",
        dataset=TEST_DATASET,
        image_count=image_count,
    )

    assert result.status == "success"
    assert result.dataset == TEST_DATASET
    assert result.image_count == image_count
    assert result.image_count > 0
    assert result.error is None


def test_earth_engine_region_query_no_data(ee_session: str) -> None:
    """Test 5 (REGION NO DATA): Valid region query over pre-Sentinel-2 dates returns image_count=0."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    collection = (
        ee.ImageCollection(TEST_DATASET)
        .filterBounds(region)
        .filterDate("1990-01-01", "1990-01-02")
    )

    image_count = int(collection.size().getInfo())
    assert image_count == 0, "Expected exactly 0 images for pre-Sentinel-2 date range"

    result = EarthEngineResult(
        status="no_data",
        dataset=TEST_DATASET,
        image_count=0,
        error=None,
    )

    assert result.status == "no_data"
    assert result.dataset == TEST_DATASET
    assert result.image_count == 0
    assert result.error is None


def test_select_most_recent_sentinel2_image_success(ee_session: str) -> None:
    """Test 6 (PIPELINE SUCCESS): select_most_recent_sentinel2_image selects newest usable image and metadata."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    result = select_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
    )

    assert result.status == "success"
    assert result.dataset == TEST_DATASET
    assert result.image_count == 1
    assert result.error is None
    assert result.data is not None

    metadata = result.data
    assert isinstance(metadata, Sentinel2ImageMetadata)
    assert metadata.image_id.startswith("COPERNICUS/S2_SR_HARMONIZED/")
    assert "2026-08-16" in metadata.acquisition_date
    assert 0.0 <= metadata.cloud_percentage < 20.0
    assert metadata.spacecraft_name == "Sentinel-2A"
    assert metadata.system_time_start is not None


def test_select_most_recent_sentinel2_image_no_data(ee_session: str) -> None:
    """Test 7 (PIPELINE NO DATA): pre-Sentinel-2 query returns status='no_data' with zero images without exception."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    result = select_most_recent_sentinel2_image(
        region=region,
        start_date="1990-01-01",
        end_date="1990-01-02",
        max_cloud_percentage=20.0,
    )

    assert result.status == "no_data"
    assert result.dataset == TEST_DATASET
    assert result.image_count == 0
    assert result.data is None
    assert result.error is None


def test_sentinel2_candidate_ordering_and_most_recent_selection(
    ee_session: str,
) -> None:
    """Test 8 (ORDERING & SELECTION): Candidate images are ordered newest-first and select_most_recent selects the newest."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Search over 2 months with cloud < 50% to obtain multiple candidate scenes
    start_date = "2026-07-01"
    end_date = "2026-08-31"
    max_cloud = 50.0

    collection = get_sentinel2_collection(
        region=region,
        start_date=start_date,
        end_date=end_date,
        max_cloud_percentage=max_cloud,
    )

    candidate_count = int(collection.size().getInfo())
    assert candidate_count >= 2, f"Expected multiple candidate scenes, got {candidate_count}"

    timestamps = collection.aggregate_array("system:time_start").getInfo()
    assert len(timestamps) == candidate_count

    # Verify candidate images are strictly ordered descending (newest-first)
    for i in range(len(timestamps) - 1):
        assert timestamps[i] >= timestamps[i + 1], (
            f"Candidate timestamps are not ordered descending: {timestamps[i]} < {timestamps[i + 1]}"
        )

    # Call selection pipeline
    result = select_most_recent_sentinel2_image(
        region=region,
        start_date=start_date,
        end_date=end_date,
        max_cloud_percentage=max_cloud,
    )

    assert result.status == "success"
    assert result.image_count == candidate_count
    assert result.data is not None
    # Verify the selected image corresponds to the newest candidate
    assert result.data.system_time_start == timestamps[0]


def test_select_most_recent_sentinel2_image_error(ee_session: str) -> None:
    """Test 9 (PIPELINE ERROR): Invalid dataset ID produces EarthEngineResult(status='error')."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    result = select_most_recent_sentinel2_image(
        region=region,
        dataset="NON_EXISTENT/INVALID_DATASET_12345",
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "EEException"
    assert len(result.error.message) > 0
    assert result.data is None


def test_calculate_ndvi_live_evaluation(ee_session: str) -> None:
    """Test 10 (LIVE NDVI SUCCESS): calculate_ndvi consumes real Sentinel-2 image, produces valid NDVI band clipped to region."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Select most recent real Sentinel-2 image via Phase 1E pipeline
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
    )
    assert isinstance(image, ee.Image)

    # Compute NDVI clipped to region
    ndvi_image = calculate_ndvi(image=image, region=region)
    assert isinstance(ndvi_image, ee.Image)

    # Server-side verify band name
    band_names = ndvi_image.bandNames().getInfo()
    assert band_names == [NDVI_BAND_NAME]

    # Server-side sample valid pixels within the 100m analysis region
    sampled = (
        ndvi_image.sample(region=region, scale=10, numPixels=50)
        .aggregate_array(NDVI_BAND_NAME)
        .getInfo()
    )
    valid_pixels = [float(v) for v in sampled if v is not None]
    assert len(valid_pixels) > 0, "Expected at least 1 valid sampled NDVI pixel inside the analysis region"

    # Verify all valid NDVI pixel values are within the strict theoretical range [-1.0, 1.0]
    for pixel_val in valid_pixels:
        assert -1.0 <= pixel_val <= 1.0, f"NDVI value {pixel_val} outside expected range [-1.0, 1.0]"


def test_calculate_ndvi_no_data_path(ee_session: str) -> None:
    """Test 11 (LIVE NDVI NO DATA): Pre-Sentinel-2 query returns status='no_data' and NDVI is not fabricated."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Run Phase 1E selection pipeline over pre-Sentinel-2 dates
    selection_result = select_most_recent_sentinel2_image(
        region=region,
        start_date="1990-01-01",
        end_date="1990-01-02",
        max_cloud_percentage=20.0,
    )

    assert selection_result.status == "no_data"
    assert selection_result.image_count == 0
    assert selection_result.data is None
    assert selection_result.error is None


def test_calculate_ndvi_invalid_bands_error(ee_session: str) -> None:
    """Test 12 (LIVE NDVI INVALID BANDS): Requesting non-existent bands fails during server-side evaluation with EEException."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
    )

    # Request invalid band names
    bad_ndvi = calculate_ndvi(
        image=image,
        region=region,
        nir_band="NON_EXISTENT_NIR_BAND",
        red_band="NON_EXISTENT_RED_BAND",
    )

    with pytest.raises(ee.EEException):
        bad_ndvi.bandNames().getInfo()


def test_cloud_score_plus_linkage_and_band_association(ee_session: str) -> None:
    """Test 13 (LIVE CLOUD SCORE+ LINKAGE): Verifies Cloud Score+ cs_cdf band is linked to Sentinel-2 observation."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Retrieve raw unmasked candidate image with linked Cloud Score+
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
        apply_quality_mask=False,
    )
    assert isinstance(image, ee.Image)

    band_names = image.bandNames().getInfo()
    # Definitive association proof: contains Sentinel-2 optical bands and Cloud Score+ quality band
    assert NIR_BAND in band_names, f"Expected {NIR_BAND} in band names: {band_names}"
    assert RED_BAND in band_names, f"Expected {RED_BAND} in band names: {band_names}"
    assert DEFAULT_QUALITY_BAND in band_names, (
        f"Expected {DEFAULT_QUALITY_BAND} in band names: {band_names}"
    )

    # Server-side sample cs_cdf values inside the analysis region
    sampled_scores = (
        image.select(DEFAULT_QUALITY_BAND)
        .sample(region=region, scale=10, numPixels=30)
        .aggregate_array(DEFAULT_QUALITY_BAND)
        .getInfo()
    )
    valid_scores = [float(v) for v in sampled_scores if v is not None]
    assert len(valid_scores) > 0, "Expected at least 1 valid sampled cs_cdf score"
    for score in valid_scores:
        assert 0.0 <= score <= 1.0, f"cs_cdf score {score} outside valid range [0.0, 1.0]"


def test_observation_quality_selection_success(ee_session: str) -> None:
    """Test 14 (LIVE QUALITY SELECTION SUCCESS): select_most_recent_sentinel2_image satisfies usable coverage threshold."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    result = select_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
        clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        min_usable_coverage=DEFAULT_MIN_USABLE_COVERAGE,
    )

    assert result.status == "success"
    assert result.dataset == TEST_DATASET
    assert result.image_count is not None and result.image_count >= 1
    assert result.error is None
    assert result.data is not None

    metadata = result.data
    assert isinstance(metadata, Sentinel2ImageMetadata)
    assert metadata.image_id.startswith("COPERNICUS/S2_SR_HARMONIZED/")
    assert "2026-08-16" in metadata.acquisition_date
    assert metadata.clear_threshold == DEFAULT_CLEAR_THRESHOLD
    assert metadata.quality_band == DEFAULT_QUALITY_BAND
    assert metadata.usable_coverage_percentage is not None
    assert metadata.usable_coverage_percentage >= DEFAULT_MIN_USABLE_COVERAGE * 100.0


def test_observation_quality_masked_ndvi_evaluation(ee_session: str) -> None:
    """Test 15 (LIVE QUALITY-MASKED NDVI): calculate_ndvi executes on quality-masked image and preserves valid range."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Obtain quality-masked image
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
        clear_threshold=0.60,
        min_usable_coverage=0.70,
        apply_quality_mask=True,
    )
    assert isinstance(image, ee.Image)

    # Compute NDVI over quality-masked image
    ndvi_image = calculate_ndvi(image=image, region=region)
    assert isinstance(ndvi_image, ee.Image)

    # Sample valid NDVI pixels
    sampled_ndvi = (
        ndvi_image.sample(region=region, scale=10, numPixels=50)
        .aggregate_array(NDVI_BAND_NAME)
        .getInfo()
    )
    valid_ndvi = [float(v) for v in sampled_ndvi if v is not None]
    assert len(valid_ndvi) > 0, "Expected valid NDVI pixels from quality-masked image"
    for ndvi_val in valid_ndvi:
        assert -1.0 <= ndvi_val <= 1.0, f"NDVI value {ndvi_val} outside [-1.0, 1.0]"


def test_observation_quality_strict_threshold_rejection(ee_session: str) -> None:
    """Test 16 (LIVE STRICT THRESHOLD REJECTION): Overly strict quality requirements result in clean status='no_data'."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Pre-Sentinel-2 date window guaranteed zero candidates
    pre_result = select_most_recent_sentinel2_image(
        region=region,
        start_date="1990-01-01",
        end_date="1990-01-02",
        clear_threshold=0.60,
        min_usable_coverage=0.70,
    )
    assert pre_result.status == "no_data"
    assert pre_result.image_count == 0
    assert pre_result.data is None


def test_calculate_ndvi_statistics_live_evaluation(ee_session: str) -> None:
    """Test 17 (LIVE NDVI REGIONAL STATISTICS SUCCESS): Full pipeline from quality-filtered S2 to regional statistics."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # 1. Select most recent usable Sentinel-2 image
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
        clear_threshold=DEFAULT_CLEAR_THRESHOLD,
        min_usable_coverage=DEFAULT_MIN_USABLE_COVERAGE,
        apply_quality_mask=True,
    )
    assert isinstance(image, ee.Image)

    # 2. Calculate NDVI
    ndvi_image = calculate_ndvi(image=image, region=region)
    assert isinstance(ndvi_image, ee.Image)

    # 3. Calculate regional statistics
    result = calculate_ndvi_statistics(
        ndvi_image=ndvi_image,
        region=region,
        scale=10.0,
        band_name=NDVI_BAND_NAME,
    )

    # 4. Verify EarthEngineResult contract
    assert result.status == "success"
    assert result.error is None
    assert result.data is not None
    assert isinstance(result.data, NdviRegionalStatistics)

    stats = result.data
    # Assert values are within theoretical bounds [-1.0, 1.0]
    assert -1.0 <= stats.mean <= 1.0, f"Mean {stats.mean} outside [-1.0, 1.0]"
    assert -1.0 <= stats.median <= 1.0, f"Median {stats.median} outside [-1.0, 1.0]"
    assert -1.0 <= stats.min <= 1.0, f"Min {stats.min} outside [-1.0, 1.0]"
    assert -1.0 <= stats.max <= 1.0, f"Max {stats.max} outside [-1.0, 1.0]"

    # Assert pixel count
    assert stats.valid_pixel_count is not None
    assert stats.valid_pixel_count >= 1, f"Expected >= 1 valid pixels, got {stats.valid_pixel_count}"

    # Mathematical consistency
    assert stats.min <= stats.mean <= stats.max, (
        f"Inconsistent: min ({stats.min}) <= mean ({stats.mean}) <= max ({stats.max})"
    )
    assert stats.min <= stats.median <= stats.max, (
        f"Inconsistent: min ({stats.min}) <= median ({stats.median}) <= max ({stats.max})"
    )

    # Verify alias compute_ndvi_statistics produces identical results
    alias_result = compute_ndvi_statistics(
        ndvi_image=ndvi_image,
        region=region,
        scale=10.0,
    )
    assert alias_result.status == "success"
    assert alias_result.data == stats


def test_calculate_ndvi_statistics_all_masked_no_data(ee_session: str) -> None:
    """Test 18 (LIVE NDVI STATISTICS NO DATA): Fully-masked raster produces status='no_data' with None data/error."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Directly construct all-masked NDVI image
    masked_ndvi = (
        ee.Image.constant(0.5)
        .rename(NDVI_BAND_NAME)
        .updateMask(ee.Image.constant(0))
    )

    result = calculate_ndvi_statistics(
        ndvi_image=masked_ndvi,
        region=region,
        scale=10.0,
    )

    assert result.status == "no_data"
    assert result.data is None
    assert result.error is None


def test_calculate_ndvi_statistics_invalid_band_error(ee_session: str) -> None:
    """Test 19 (LIVE NDVI STATISTICS REMOTE ERROR): Non-existent band on real ee.Image produces status='error'."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
    )
    # Create image without NDVI band
    image_without_ndvi = ee.Image.constant(42.0).rename("B4")

    result = calculate_ndvi_statistics(
        ndvi_image=image_without_ndvi,
        region=region,
        scale=10.0,
        band_name="NON_EXISTENT_NDVI_BAND",
    )

    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert result.error.type in ("EEException", "Exception")
    assert len(result.error.message) > 0


def test_analyze_regional_ndvi_live_success(ee_session: str) -> None:
    """Test 20 (LIVE PIPELINE SUCCESS): analyze_regional_ndvi over Punjab fixture returns valid RegionalNdviAnalysis."""
    result = analyze_regional_ndvi(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
        start_date="2026-08-01",
        end_date="2026-08-31",
        lookback_days=30,
    )

    assert result.status == "success"
    assert result.dataset == TEST_DATASET
    assert result.image_count is not None and result.image_count >= 1
    assert result.error is None
    assert result.data is not None

    analysis = result.data
    assert isinstance(analysis, RegionalNdviAnalysis)
    assert analysis.pipeline_version == "1.0.0"

    # Observation metadata
    obs = analysis.observation
    assert isinstance(obs, Sentinel2ImageMetadata)
    assert obs.image_id.startswith("COPERNICUS/S2_SR_HARMONIZED/")
    assert "2026-08-16" in obs.acquisition_date
    assert obs.spacecraft_name == "Sentinel-2A"
    assert obs.clear_threshold == DEFAULT_CLEAR_THRESHOLD
    assert obs.quality_band == DEFAULT_QUALITY_BAND
    assert obs.usable_coverage_percentage is not None
    assert obs.usable_coverage_percentage >= DEFAULT_MIN_USABLE_COVERAGE * 100.0

    # Quality evidence
    qual = analysis.quality
    assert isinstance(qual, ObservationQualityEvidence)
    assert qual.quality_dataset == CLOUD_SCORE_PLUS_S2_HARMONIZED
    assert qual.min_usable_coverage_threshold == DEFAULT_MIN_USABLE_COVERAGE
    assert qual.max_scene_cloud_threshold == 20.0
    assert qual.quality_mask_applied is True
    assert qual.is_usable is True

    # Freshness
    fresh = analysis.freshness
    assert isinstance(fresh, ObservationFreshness)
    assert fresh.reference_date == "2026-08-31"
    assert fresh.observation_age_days == 15
    assert fresh.lookback_window_days == 30

    # Region metadata
    reg = analysis.region
    assert isinstance(reg, AnalysisRegionMetadata)
    assert reg.latitude == PUNJAB_LATITUDE
    assert reg.longitude == PUNJAB_LONGITUDE
    assert reg.radius_m == 100.0
    assert reg.geometry_type == "PointBuffer"
    assert reg.scale_m == 10.0

    # Regional statistics
    stats = analysis.statistics
    assert isinstance(stats, NdviRegionalStatistics)
    assert -1.0 <= stats.min <= stats.mean <= stats.max <= 1.0
    assert -1.0 <= stats.min <= stats.median <= stats.max <= 1.0
    assert stats.valid_pixel_count is not None and stats.valid_pixel_count >= 1


def test_analyze_regional_ndvi_live_pre_sentinel2_no_data(ee_session: str) -> None:
    """Test 21 (LIVE PIPELINE NO DATA): Pre-Sentinel-2 date window returns clean status='no_data'."""
    result = analyze_regional_ndvi(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
        start_date="1990-01-01",
        end_date="1990-01-31",
    )

    assert result.status == "no_data"
    assert result.dataset == TEST_DATASET
    assert result.image_count == 0
    assert result.data is None
    assert result.error is None


def test_analyze_regional_ndvi_live_strict_usable_coverage_rejection(ee_session: str) -> None:
    """Test 22 (LIVE PIPELINE STRICT COVERAGE REJECTION): Pre-Sentinel-2 or strict coverage yields no_data."""
    result = analyze_regional_ndvi(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
        start_date="1990-01-01",
        end_date="1990-01-02",
        min_usable_coverage=0.99,
    )

    assert result.status == "no_data"
    assert result.dataset == TEST_DATASET
    assert result.image_count == 0
    assert result.data is None
    assert result.error is None


def test_analyze_regional_ndvi_live_statistical_envelope(ee_session: str) -> None:
    """Test 23 (LIVE STATISTICAL ENVELOPE): Verifies strict mathematical envelope consistency on live result."""
    result = analyze_regional_ndvi(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=100.0,
        start_date="2026-08-01",
        end_date="2026-08-31",
    )

    assert result.status == "success"
    stats = result.data.statistics
    eps = 1e-6

    assert -1.0 <= stats.min <= 1.0
    assert -1.0 <= stats.max <= 1.0
    assert -1.0 <= stats.mean <= 1.0
    assert -1.0 <= stats.median <= 1.0

    assert stats.min - eps <= stats.mean <= stats.max + eps
    assert stats.min - eps <= stats.median <= stats.max + eps
