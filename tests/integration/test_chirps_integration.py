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
"""Live integration tests for Phase 3B CHIRPS Earth Engine rainfall boundary (DEC-020)."""

from datetime import date
import os

import ee
import pytest

from app.environment.chirps import (
    CHIRPS_DATASET,
    fetch_raw_chirps_rainfall_timeseries,
)
from app.environment.chirps_pipeline import analyze_chirps_rainfall
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


def test_live_chirps_collection_connectivity(ee_session: str) -> None:
    """Verifies that the UCSB-CHC/CHIRPS/V3/DAILY_SAT collection is accessible via live EE."""
    geometry = create_analysis_region(PUNJAB_LATITUDE, PUNJAB_LONGITUDE, radius_m=100.0)
    # Query a known past window (e.g. 2024-07-01 to 2024-07-10)
    collection = (
        ee.ImageCollection(CHIRPS_DATASET)
        .filterBounds(geometry)
        .filterDate("2024-07-01", "2024-07-11")
    )
    count = int(collection.size().getInfo())
    assert count > 0, f"Expected > 0 images in live CHIRPS archive for 2024-07-01..10, got {count}"


def test_live_fetch_raw_chirps_rainfall_timeseries(ee_session: str) -> None:
    """Verifies live Tier 1 retrieval and spatial reduction over a 30-day lookback."""
    geometry = create_analysis_region(PUNJAB_LATITUDE, PUNJAB_LONGITUDE, radius_m=100.0)
    target_end = date(2024, 7, 31)

    result = fetch_raw_chirps_rainfall_timeseries(
        region=geometry,
        requested_end_date=target_end,
        lookback_days=30,
    )

    assert result.status == "success"
    assert result.dataset == CHIRPS_DATASET
    assert result.image_count is not None
    assert result.image_count > 0
    assert result.data is not None
    assert len(result.data) == result.image_count
    assert result.error is None

    # Check raw record keys
    first_record = result.data[0]
    assert "observation_date" in first_record
    assert "precipitation" in first_record


def test_live_analyze_chirps_rainfall_pipeline(ee_session: str) -> None:
    """Verifies live end-to-end orchestration and window aggregation over a 90-day window."""
    target_end = date(2024, 8, 15)

    analysis = analyze_chirps_rainfall(
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
    assert analysis.dataset == CHIRPS_DATASET
    assert analysis.spatial_resolution_km == 5.566
    assert analysis.pipeline_version == "3.1.0"

    # Invariants for daily observations
    for obs in analysis.daily_observations:
        assert obs.observation_date <= target_end
        if obs.precipitation_mm is not None:
            assert obs.precipitation_mm >= 0.0

    # Window statistics
    assert analysis.recent_7_days is not None
    assert analysis.recent_7_days.days_requested == 7
    assert analysis.recent_30_days is not None
    assert analysis.recent_30_days.days_requested == 30
    assert analysis.recent_90_days is not None
    assert analysis.recent_90_days.days_requested == 90
