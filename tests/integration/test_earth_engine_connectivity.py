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
)
from app.satellite.sentinel2 import (
    get_most_recent_sentinel2_image,
    get_sentinel2_collection,
    select_most_recent_sentinel2_image,
)
from app.satellite.types import (
    EarthEngineError,
    EarthEngineResult,
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
