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
"""Unit tests for Dynamic World Land-Cover Context domain models (Phase 3C, DEC-021)."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.environment.dynamic_world_types import (
    CANONICAL_CLASS_PRECEDENCE,
    DynamicWorldAnalysis,
    DynamicWorldClassProbabilities,
    DynamicWorldLandCoverClass,
)
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError


def test_canonical_class_precedence():
    """Verify that canonical class precedence contains all 9 classes in exact GEE index order."""
    expected = (
        "water",
        "trees",
        "grass",
        "flooded_vegetation",
        "crops",
        "shrub_and_scrub",
        "built",
        "bare",
        "snow_and_ice",
    )
    assert CANONICAL_CLASS_PRECEDENCE == expected
    assert len(CANONICAL_CLASS_PRECEDENCE) == 9


def test_dynamic_world_class_probabilities_valid():
    """Verify valid creation of DynamicWorldClassProbabilities."""
    probs = DynamicWorldClassProbabilities(
        water=0.01,
        trees=0.10,
        grass=0.05,
        flooded_vegetation=0.02,
        crops=0.75,
        shrub_and_scrub=0.02,
        built=0.03,
        bare=0.02,
        snow_and_ice=0.0,
    )
    assert probs.crops == 0.75
    assert probs.trees == 0.10
    assert probs.water == 0.01
    assert probs.snow_and_ice == 0.0


def test_dynamic_world_class_probabilities_immutability():
    """Verify DynamicWorldClassProbabilities is frozen/immutable."""
    probs = DynamicWorldClassProbabilities(
        water=0.0,
        trees=0.1,
        grass=0.1,
        flooded_vegetation=0.0,
        crops=0.8,
        shrub_and_scrub=0.0,
        built=0.0,
        bare=0.0,
        snow_and_ice=0.0,
    )
    with pytest.raises(ValidationError):
        probs.crops = 0.9  # type: ignore


def test_dynamic_world_class_probabilities_extra_forbidden():
    """Verify extra fields are forbidden."""
    with pytest.raises(ValidationError):
        DynamicWorldClassProbabilities(
            water=0.0,
            trees=0.1,
            grass=0.1,
            flooded_vegetation=0.0,
            crops=0.8,
            shrub_and_scrub=0.0,
            built=0.0,
            bare=0.0,
            snow_and_ice=0.0,
            extra_field=0.5,  # type: ignore
        )


@pytest.mark.parametrize(
    "invalid_val",
    [-0.01, -1.0, 1.01, 2.0],
)
def test_dynamic_world_class_probabilities_range_validation(invalid_val):
    """Verify probabilities outside [0.0, 1.0] are rejected."""
    with pytest.raises(ValidationError):
        DynamicWorldClassProbabilities(
            water=invalid_val,
            trees=0.1,
            grass=0.1,
            flooded_vegetation=0.0,
            crops=0.8,
            shrub_and_scrub=0.0,
            built=0.0,
            bare=0.0,
            snow_and_ice=0.0,
        )


def test_dynamic_world_class_probabilities_missing_field():
    """Verify missing required probability fields raise ValidationError."""
    with pytest.raises(ValidationError):
        DynamicWorldClassProbabilities(  # type: ignore
            water=0.0,
            trees=0.1,
            grass=0.1,
            # crops missing
            flooded_vegetation=0.0,
            shrub_and_scrub=0.0,
            built=0.0,
            bare=0.0,
            snow_and_ice=0.0,
        )


def test_dynamic_world_analysis_success_valid():
    """Verify valid creation of DynamicWorldAnalysis in success state."""
    region = AnalysisRegionMetadata(
        latitude=30.9,
        longitude=75.85,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )
    probs = DynamicWorldClassProbabilities(
        water=0.002,
        trees=0.08,
        grass=0.01,
        flooded_vegetation=0.005,
        crops=0.82,
        shrub_and_scrub=0.003,
        built=0.05,
        bare=0.03,
        snow_and_ice=0.0,
    )
    analysis = DynamicWorldAnalysis(
        region=region,
        requested_end_date=date(2026, 9, 20),
        observation_date=date(2026, 9, 15),
        observation_id="20260915T054641_20260915T055819_T43SBT",
        data_lag_days=5,
        dominant_class="crops",
        dominant_probability=0.82,
        class_probabilities=probs,
        dataset="GOOGLE/DYNAMICWORLD/V1",
        spatial_resolution_m=10.0,
        status="success",
        pipeline_version="3.1.0",
        error=None,
    )
    assert analysis.status == "success"
    assert analysis.dominant_class == "crops"
    assert analysis.dominant_probability == 0.82
    assert analysis.data_lag_days == 5
    assert analysis.observation_id == "20260915T054641_20260915T055819_T43SBT"
    assert analysis.class_probabilities.crops == 0.82
    assert analysis.spatial_resolution_m == 10.0
    assert analysis.pipeline_version == "3.1.0"


def test_dynamic_world_analysis_no_data_state():
    """Verify DynamicWorldAnalysis in no_data state preserves context metadata."""
    region = AnalysisRegionMetadata(
        latitude=30.9,
        longitude=75.85,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )
    analysis = DynamicWorldAnalysis(
        region=region,
        requested_end_date=date(2026, 9, 20),
        observation_date=None,
        observation_id=None,
        data_lag_days=None,
        dominant_class=None,
        dominant_probability=None,
        class_probabilities=None,
        dataset="GOOGLE/DYNAMICWORLD/V1",
        spatial_resolution_m=10.0,
        status="no_data",
        pipeline_version="3.1.0",
        error=None,
    )
    assert analysis.status == "no_data"
    assert analysis.observation_date is None
    assert analysis.dominant_class is None
    assert analysis.class_probabilities is None
    assert analysis.region.latitude == 30.9
    assert analysis.requested_end_date == date(2026, 9, 20)
    assert analysis.dataset == "GOOGLE/DYNAMICWORLD/V1"


def test_dynamic_world_analysis_error_state():
    """Verify DynamicWorldAnalysis in error state preserves context metadata and error."""
    region = AnalysisRegionMetadata(
        latitude=30.9,
        longitude=75.85,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )
    err = EarthEngineError(type="EEException", message="Earth Engine connection timeout")
    analysis = DynamicWorldAnalysis(
        region=region,
        requested_end_date=date(2026, 9, 20),
        status="error",
        error=err,
    )
    assert analysis.status == "error"
    assert analysis.error is not None
    assert analysis.error.type == "EEException"
    assert analysis.error.message == "Earth Engine connection timeout"
    assert analysis.observation_date is None
    assert analysis.class_probabilities is None


def test_dynamic_world_analysis_immutability():
    """Verify DynamicWorldAnalysis is frozen/immutable."""
    region = AnalysisRegionMetadata(
        latitude=30.9,
        longitude=75.85,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )
    analysis = DynamicWorldAnalysis(
        region=region,
        requested_end_date=date(2026, 9, 20),
        status="no_data",
    )
    with pytest.raises(ValidationError):
        analysis.status = "success"  # type: ignore
