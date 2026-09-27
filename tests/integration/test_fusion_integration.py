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
"""Live Earth Engine integration tests for Multi-Source Evidence Fusion (Phase 4, DEC-022)."""

from datetime import date
import os
import ee
import pytest

from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.fusion import fetch_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import HistoricalNdviAnalysis

# Approved test reference coordinates: Ludhiana, Punjab
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
def test_live_fusion_end_to_end_punjab(ee_session: str) -> None:
    """Executes live end-to-end multi-source evidence fusion against Punjab parcel coordinates."""
    target_ref_date = date(2024, 7, 15)

    evidence = fetch_agricultural_environmental_evidence(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        reference_date=target_ref_date,
        radius_m=100.0,
    )

    # 1. Structural Verification
    assert isinstance(evidence, AgriculturalEnvironmentalEvidence)
    assert evidence.reference_date == target_ref_date
    assert evidence.pipeline_version == "4.0.0"
    assert evidence.region.latitude == pytest.approx(PUNJAB_LATITUDE)
    assert evidence.region.longitude == pytest.approx(PUNJAB_LONGITUDE)
    assert evidence.region.radius_m == 100.0

    # 2. Source Subsystem Verification
    assert isinstance(evidence.vegetation, HistoricalNdviAnalysis)
    assert isinstance(evidence.reanalysis, ERA5LandAnalysis)
    assert isinstance(evidence.rainfall, CHIRPSRainfallAnalysis)
    assert isinstance(evidence.land_cover, DynamicWorldAnalysis)

    # 3. Status and Availability Counts
    assert evidence.status in ("success", "partial")
    assert evidence.sources_requested_count == 4
    assert evidence.sources_available_count >= 1
    assert 0 <= evidence.sources_fully_available_count <= evidence.sources_available_count <= 4
    assert evidence.is_fully_available == (evidence.sources_fully_available_count == 4)

    # 4. Native Spatial Resolutions Preserved
    assert evidence.reanalysis.spatial_resolution_km == 11.1
    assert evidence.rainfall.spatial_resolution_km == 5.566
    assert evidence.land_cover.spatial_resolution_m == 10.0

    # 5. Temporal Latency & Provenance Integrity
    if evidence.reanalysis.status == "success":
        assert evidence.reanalysis.latest_available_date is not None
        assert evidence.reanalysis.latest_available_date <= target_ref_date
        assert evidence.reanalysis.data_lag_days is not None
        assert evidence.reanalysis.data_lag_days >= 0

    if evidence.rainfall.status == "success":
        assert evidence.rainfall.latest_available_date is not None
        assert evidence.rainfall.latest_available_date <= target_ref_date
        assert evidence.rainfall.data_lag_days is not None
        assert evidence.rainfall.data_lag_days >= 0

    if evidence.land_cover.status == "success":
        assert evidence.land_cover.observation_date is not None
        assert evidence.land_cover.observation_date <= target_ref_date
        assert evidence.land_cover.dominant_class is not None

    if evidence.vegetation.status in ("success", "insufficient_history"):
        assert evidence.current_vegetation is not None
        assert evidence.current_vegetation.statistics is not None
        assert -1.0 <= evidence.current_vegetation.statistics.mean <= 1.0
