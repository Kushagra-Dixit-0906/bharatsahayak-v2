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
"""Unit tests for satellite and Earth Engine result contracts and type definitions."""

import json

from pydantic import ValidationError
import pytest

from app.satellite.types import EarthEngineError, EarthEngineResult


def test_valid_success_result() -> None:
    """Test creating a valid success result with dataset and image count."""
    result = EarthEngineResult(
        status="success",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=5,
        data={"info": "sample_data"},
    )
    assert result.status == "success"
    assert result.dataset == "COPERNICUS/S2_SR_HARMONIZED"
    assert result.image_count == 5
    assert result.data == {"info": "sample_data"}
    assert result.error is None


def test_valid_no_data_result() -> None:
    """Test creating a valid no_data result with image_count=0 and no error."""
    result = EarthEngineResult(
        status="no_data",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=0,
        error=None,
    )
    assert result.status == "no_data"
    assert result.dataset == "COPERNICUS/S2_SR_HARMONIZED"
    assert result.image_count == 0
    assert result.data is None
    assert result.error is None


def test_valid_error_result() -> None:
    """Test creating a valid error result with structured error details."""
    error = EarthEngineError(
        type="EEInitializationError",
        message="Earth Engine client failed to initialize with provided credentials.",
    )
    result = EarthEngineResult(
        status="error",
        error=error,
    )
    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "EEInitializationError"
    assert "credentials" in result.error.message
    assert result.dataset is None
    assert result.image_count is None


def test_invalid_status_rejected() -> None:
    """Test that an invalid status string raises a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        EarthEngineResult(status="pending")  # type: ignore[arg-type]

    assert "status" in str(exc_info.value)


def test_negative_image_count_rejected() -> None:
    """Test that a negative image_count raises a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        EarthEngineResult(
            status="success",
            image_count=-1,
        )
    assert "image_count" in str(exc_info.value)


def test_model_serialization() -> None:
    """Test model serialization using model_dump() and model_dump_json()."""
    error = EarthEngineError(
        type="QueryTimeout",
        message="Request timed out after 30 seconds.",
    )
    result = EarthEngineResult(
        status="error",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=0,
        data={"query_time_ms": 30000},
        error=error,
    )

    dumped_dict = result.model_dump()
    assert dumped_dict == {
        "status": "error",
        "dataset": "COPERNICUS/S2_SR_HARMONIZED",
        "image_count": 0,
        "data": {"query_time_ms": 30000},
        "error": {
            "type": "QueryTimeout",
            "message": "Request timed out after 30 seconds.",
        },
    }

    dumped_json = result.model_dump_json()
    parsed_json = json.loads(dumped_json)
    assert parsed_json["status"] == "error"
    assert parsed_json["error"]["type"] == "QueryTimeout"

    # Also test success serialization without error
    success_result = EarthEngineResult(
        status="success",
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        image_count=3,
    )
    success_dict = success_result.model_dump()
    assert success_dict["status"] == "success"
    assert success_dict["error"] is None
    assert success_dict["image_count"] == 3


def test_observation_quality_evidence_valid() -> None:
    """Test creating a valid ObservationQualityEvidence instance."""
    from app.satellite.types import ObservationQualityEvidence, SatelliteQualityEvidence

    assert SatelliteQualityEvidence is ObservationQualityEvidence

    evidence = ObservationQualityEvidence(
        quality_mask_applied=True,
        is_usable=True,
    )
    assert evidence.quality_dataset == "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
    assert evidence.min_usable_coverage_threshold == 0.70
    assert evidence.max_scene_cloud_threshold == 20.0
    assert evidence.quality_mask_applied is True
    assert evidence.is_usable is True

    # Test required booleans (cannot omit)
    with pytest.raises(ValidationError):
        ObservationQualityEvidence(quality_mask_applied=True)  # type: ignore[call-arg]

    with pytest.raises(ValidationError):
        ObservationQualityEvidence(is_usable=True)  # type: ignore[call-arg]


@pytest.mark.parametrize("invalid_thresh", [-0.1, 1.1])
def test_observation_quality_evidence_threshold_bounds(invalid_thresh: float) -> None:
    """Test boundary validation for ObservationQualityEvidence thresholds."""
    from app.satellite.types import ObservationQualityEvidence

    with pytest.raises(ValidationError):
        ObservationQualityEvidence(
            min_usable_coverage_threshold=invalid_thresh,
            quality_mask_applied=True,
            is_usable=True,
        )


@pytest.mark.parametrize("invalid_cloud", [-0.1, 100.1])
def test_observation_quality_evidence_cloud_bounds(invalid_cloud: float) -> None:
    """Test boundary validation for max_scene_cloud_threshold."""
    from app.satellite.types import ObservationQualityEvidence

    with pytest.raises(ValidationError):
        ObservationQualityEvidence(
            max_scene_cloud_threshold=invalid_cloud,
            quality_mask_applied=True,
            is_usable=True,
        )


def test_observation_freshness_valid() -> None:
    """Test creating a valid ObservationFreshness instance."""
    from app.satellite.types import ObservationFreshness, SatelliteFreshness

    assert SatelliteFreshness is ObservationFreshness

    freshness = ObservationFreshness(
        reference_date="2026-08-31",
        observation_age_days=15,
        lookback_window_days=30,
    )
    assert freshness.reference_date == "2026-08-31"
    assert freshness.observation_age_days == 15
    assert freshness.lookback_window_days == 30

    # Negative observation_age_days rejected
    with pytest.raises(ValidationError):
        ObservationFreshness(
            reference_date="2026-08-31",
            observation_age_days=-1,
        )

    # Non-positive lookback_window_days rejected
    with pytest.raises(ValidationError):
        ObservationFreshness(
            reference_date="2026-08-31",
            observation_age_days=5,
            lookback_window_days=0,
        )


def test_analysis_region_metadata_valid() -> None:
    """Test creating a valid AnalysisRegionMetadata instance."""
    from app.satellite.types import AnalysisRegionMetadata, SatelliteRegionMetadata

    assert SatelliteRegionMetadata is AnalysisRegionMetadata

    region = AnalysisRegionMetadata(
        latitude=30.9157,
        longitude=75.7196,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )
    assert region.latitude == 30.9157
    assert region.longitude == 75.7196
    assert region.radius_m == 100.0
    assert region.geometry_type == "PointBuffer"
    assert region.scale_m == 10.0


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (-90.1, 75.0),
        (90.1, 75.0),
        (30.0, -180.1),
        (30.0, 180.1),
    ],
)
def test_analysis_region_metadata_lat_lon_bounds(lat: float, lon: float) -> None:
    """Test latitude and longitude boundary validation in AnalysisRegionMetadata."""
    from app.satellite.types import AnalysisRegionMetadata

    with pytest.raises(ValidationError):
        AnalysisRegionMetadata(latitude=lat, longitude=lon)


@pytest.mark.parametrize("invalid_dim", [0.0, -10.0])
def test_analysis_region_metadata_dimensions(invalid_dim: float) -> None:
    """Test strictly positive radius_m and scale_m in AnalysisRegionMetadata."""
    from app.satellite.types import AnalysisRegionMetadata

    with pytest.raises(ValidationError):
        AnalysisRegionMetadata(latitude=30.0, longitude=75.0, radius_m=invalid_dim)

    with pytest.raises(ValidationError):
        AnalysisRegionMetadata(latitude=30.0, longitude=75.0, scale_m=invalid_dim)


def test_regional_ndvi_analysis_composite() -> None:
    """Test creating and serializing a RegionalNdviAnalysis composite domain payload."""
    from app.satellite.types import (
        AnalysisRegionMetadata,
        NdviRegionalStatistics,
        ObservationFreshness,
        ObservationQualityEvidence,
        RegionalNdviAnalysis,
        SatelliteRegionalAnalysis,
        Sentinel2ImageMetadata,
    )

    assert SatelliteRegionalAnalysis is RegionalNdviAnalysis

    analysis = RegionalNdviAnalysis(
        observation=Sentinel2ImageMetadata(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251_20260816T055032_T43REQ",
            acquisition_date="2026-08-16T05:50:41.321000+00:00",
            cloud_percentage=10.0,
            spacecraft_name="Sentinel-2A",
            mgrs_tile="43REQ",
            product_id="S2A_TEST",
            system_time_start=1786859441321,
            usable_coverage_percentage=95.0,
            clear_threshold=0.60,
            quality_band="cs_cdf",
        ),
        quality=ObservationQualityEvidence(
            quality_mask_applied=True,
            is_usable=True,
        ),
        freshness=ObservationFreshness(
            reference_date="2026-08-31",
            observation_age_days=15,
            lookback_window_days=30,
        ),
        region=AnalysisRegionMetadata(
            latitude=30.9157,
            longitude=75.7196,
            radius_m=100.0,
            scale_m=10.0,
        ),
        statistics=NdviRegionalStatistics(
            mean=0.55,
            median=0.54,
            min=0.20,
            max=0.85,
            valid_pixel_count=314,
        ),
        pipeline_version="1.0.0",
    )

    dumped = analysis.model_dump()
    assert dumped["pipeline_version"] == "1.0.0"
    assert dumped["observation"]["image_id"].startswith("COPERNICUS/S2_SR_HARMONIZED")
    assert dumped["quality"]["quality_mask_applied"] is True
    assert dumped["quality"]["is_usable"] is True
    assert dumped["freshness"]["observation_age_days"] == 15
    assert dumped["region"]["geometry_type"] == "PointBuffer"
    assert dumped["statistics"]["mean"] == 0.55
