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
"""Live integration tests for Phase 3A ERA5-Land Earth Engine ingestion boundary (DEC-019)."""

from datetime import date, timedelta
import os

import ee
import pytest

from app.environment.era5 import (
    DEFAULT_LOOKBACK_DAYS,
    ERA5_LAND_DATASET,
    fetch_raw_era5_land_timeseries,
)
from app.environment.pipeline import analyze_era5_land
from app.satellite.geometry import create_analysis_region

# Reference location: Ludhiana, Punjab
PUNJAB_LATITUDE: float = 30.9157
PUNJAB_LONGITUDE: float = 75.7196


@pytest.fixture(scope="module")
def ee_session() -> str:
    """Initializes Earth Engine session or skips if credentials/network unavailable."""
    project_id = os.environ.get("EE_PROJECT_ID", "bharatsahayak-v2")
    try:
        ee.Initialize(project=project_id)
    except Exception as exc:
        pytest.skip(
            f"Earth Engine authentication not available or initialization failed: {exc}"
        )
    return project_id


def test_live_era5_land_collection_connectivity(ee_session: str) -> None:
    """Verifies that the ECMWF/ERA5_LAND/DAILY_AGGR collection is accessible via live EE."""
    geometry = create_analysis_region(PUNJAB_LATITUDE, PUNJAB_LONGITUDE, radius_m=100.0)
    # Query a known past window (e.g. 2024-07-01 to 2024-07-10)
    collection = (
        ee.ImageCollection(ERA5_LAND_DATASET)
        .filterBounds(geometry)
        .filterDate("2024-07-01", "2024-07-11")
    )
    count = int(collection.size().getInfo())
    assert count > 0, f"Expected > 0 images in live ERA5-Land archive for 2024-07-01..10, got {count}"


def test_live_fetch_raw_era5_land_timeseries(ee_session: str) -> None:
    """Verifies live Tier 1 retrieval and spatial reduction over a 30-day lookback."""
    geometry = create_analysis_region(PUNJAB_LATITUDE, PUNJAB_LONGITUDE, radius_m=100.0)
    target_end = date(2024, 7, 31)

    result = fetch_raw_era5_land_timeseries(
        region=geometry,
        requested_end_date=target_end,
        lookback_days=30,
    )

    assert result.status == "success"
    assert result.dataset == ERA5_LAND_DATASET
    assert result.image_count is not None
    assert result.image_count > 0
    assert result.data is not None
    assert len(result.data) == result.image_count
    assert result.error is None

    # Check raw record keys
    first_record = result.data[0]
    assert "observation_date" in first_record
    assert "temperature_2m" in first_record
    assert "total_precipitation_sum" in first_record
    assert "volumetric_soil_water_layer_1" in first_record
    assert "runoff_sum" in first_record


def test_live_analyze_era5_land_pipeline(ee_session: str) -> None:
    """Verifies live end-to-end orchestration and window aggregation over a 90-day window."""
    target_end = date(2024, 8, 15)

    analysis = analyze_era5_land(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        requested_end_date=target_end,
        radius_m=100.0,
        lookback_days=90,
    )

    assert analysis.status == "success"
    assert analysis.requested_end_date == target_end
    assert analysis.latest_available_date is not None
    assert analysis.latest_available_date <= target_end
    assert analysis.data_lag_days is not None
    assert analysis.data_lag_days >= 0
    assert len(analysis.daily_observations) > 0
    assert analysis.dataset == ERA5_LAND_DATASET
    assert analysis.spatial_resolution_km == 11.1
    assert analysis.pipeline_version == "3.0.0"

    # Invariants for daily observations
    for obs in analysis.daily_observations:
        assert obs.observation_date <= target_end
        if obs.temperature_c is not None:
            assert -100.0 <= obs.temperature_c <= 100.0
        if obs.precipitation_mm is not None:
            assert obs.precipitation_mm >= 0.0
        if obs.volumetric_soil_water_layer_1 is not None:
            assert 0.0 <= obs.volumetric_soil_water_layer_1 <= 1.0
        if obs.runoff_sum_mm is not None:
            assert obs.runoff_sum_mm >= 0.0

    # Window statistics
    assert analysis.recent_7_days is not None
    assert analysis.recent_7_days.days_requested == 7
    assert analysis.recent_30_days is not None
    assert analysis.recent_30_days.days_requested == 30
    assert analysis.recent_90_days is not None
    assert analysis.recent_90_days.days_requested == 90
