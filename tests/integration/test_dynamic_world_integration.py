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
"""Live Earth Engine integration tests for Dynamic World Land-Cover Context (Phase 3C, DEC-021)."""

from datetime import date, timedelta
import os

import ee
import pytest

from app.environment.dynamic_world import (
    DYNAMIC_WORLD_DATASET,
    DYNAMIC_WORLD_PROBABILITY_BANDS,
    fetch_raw_dynamic_world_record,
)
from app.environment.dynamic_world_pipeline import analyze_dynamic_world_land_cover
from app.environment.dynamic_world_types import CANONICAL_CLASS_PRECEDENCE
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


@pytest.mark.integration
def test_live_dynamic_world_collection_connectivity(ee_session: str) -> None:
    """Verifies that the GOOGLE/DYNAMICWORLD/V1 collection is accessible via live EE."""
    geometry = create_analysis_region(PUNJAB_LATITUDE, PUNJAB_LONGITUDE, radius_m=100.0)
    collection = (
        ee.ImageCollection(DYNAMIC_WORLD_DATASET)
        .filterBounds(geometry)
        .filterDate("2024-05-01", "2024-06-01")
        .select(DYNAMIC_WORLD_PROBABILITY_BANDS)
    )
    count = int(collection.size().getInfo())
    assert count > 0, f"Expected > 0 images in live Dynamic World archive for 2024-05-01..31, got {count}"


@pytest.mark.integration
def test_live_dynamic_world_fetch_record(ee_session: str) -> None:
    """Verify live Earth Engine retrieval for Dynamic World V1 over Punjab coordinates."""
    geom = create_analysis_region(PUNJAB_LATITUDE, PUNJAB_LONGITUDE, 100.0)
    end_date = date(2024, 6, 1)

    result = fetch_raw_dynamic_world_record(
        region=geom,
        requested_end_date=end_date,
        lookback_days=30,
    )

    assert result.status in ("success", "no_data")
    if result.status == "success":
        assert result.data is not None
        assert isinstance(result.data, dict)
        for band in CANONICAL_CLASS_PRECEDENCE:
            assert band in result.data
            val = result.data[band]
            assert val is not None
            assert 0.0 <= float(val) <= 1.0


@pytest.mark.integration
def test_live_dynamic_world_pipeline_orchestration(ee_session: str) -> None:
    """Verify end-to-end live orchestration of DynamicWorldAnalysis over Punjab coordinates."""
    end_date = date(2024, 6, 1)

    analysis = analyze_dynamic_world_land_cover(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        requested_end_date=end_date,
        radius_m=100.0,
        lookback_days=30,
    )

    assert analysis.status in ("success", "no_data")
    assert analysis.region.latitude == PUNJAB_LATITUDE
    assert analysis.region.longitude == PUNJAB_LONGITUDE
    assert analysis.requested_end_date == end_date
    assert analysis.spatial_resolution_m == 10.0
    assert analysis.pipeline_version == "3.1.0"
    assert analysis.dataset == "GOOGLE/DYNAMICWORLD/V1"

    if analysis.status == "success":
        assert analysis.observation_date is not None
        # Verify observation date is within [end_date - 29, end_date]
        window_start = end_date - timedelta(days=29)
        assert window_start <= analysis.observation_date <= end_date
        assert analysis.observation_id is not None
        assert analysis.dominant_class in CANONICAL_CLASS_PRECEDENCE
        assert analysis.dominant_probability is not None
        assert 0.0 <= analysis.dominant_probability <= 1.0
        assert analysis.class_probabilities is not None

        # Verify sum of probabilities is close to 1.0
        probs = analysis.class_probabilities
        total_prob = sum(getattr(probs, cls_name) for cls_name in CANONICAL_CLASS_PRECEDENCE)
        assert 0.80 <= total_prob <= 1.20  # Tolerance for unweighted spatial averaging
        assert analysis.error is None
