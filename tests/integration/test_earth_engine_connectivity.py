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

from app.satellite.types import EarthEngineError, EarthEngineResult

TEST_POINT = [75.7196, 30.9157]  # [longitude, latitude] near Ludhiana, Punjab
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
