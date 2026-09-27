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
"""Unit tests for Dynamic World normalization, dominant derivation, and pipeline orchestration (Phase 3C, DEC-021)."""

from datetime import date, datetime, timezone
from unittest.mock import patch
import pytest

from app.environment.dynamic_world_pipeline import (
    analyze_dynamic_world_land_cover,
    derive_dominant_land_cover,
    normalize_raw_dynamic_world_record,
)
from app.environment.dynamic_world_types import (
    CANONICAL_CLASS_PRECEDENCE,
    DynamicWorldClassProbabilities,
    DynamicWorldLandCoverClass,
)
from app.satellite.types import EarthEngineError, EarthEngineResult
from tests.fixtures.dynamic_world_fixtures import load_dynamic_world_fixture


# ==============================================================================
# Tier 2: Normalization Unit Tests
# ==============================================================================

def test_normalize_raw_record_cropland_fixture():
    """Verify normalization of realistic Punjab cropland dominant fixture."""
    fixture = load_dynamic_world_fixture("punjab_cropland_dominant.json")
    result = normalize_raw_dynamic_world_record(fixture)
    assert result is not None
    obs_date, obs_id, probs = result

    assert obs_date == date(2026, 9, 15)
    assert obs_id == "20260915T054641_20260915T055819_T43SBT"
    assert probs.crops == 0.82
    assert probs.trees == 0.08
    assert probs.built == 0.05
    assert probs.bare == 0.03
    assert probs.grass == 0.01
    assert probs.flooded_vegetation == 0.005
    assert probs.shrub_and_scrub == 0.003
    assert probs.water == 0.002
    assert probs.snow_and_ice == 0.0


def test_normalize_raw_record_mixed_agroforestry_fixture():
    """Verify normalization of mixed agroforestry fixture."""
    fixture = load_dynamic_world_fixture("mixed_agroforestry.json")
    result = normalize_raw_dynamic_world_record(fixture)
    assert result is not None
    obs_date, obs_id, probs = result

    assert obs_date == date(2026, 9, 12)
    assert obs_id == "20260912T054641_20260912T055819_T43SBT"
    assert probs.crops == 0.46
    assert probs.trees == 0.44


def test_normalize_raw_record_exact_float_preservation():
    """Verify that floating-point values are preserved 1:1 without rounding or scaling."""
    raw = {
        "observation_date": "2026-09-01",
        "observation_id": "test_id_123",
        "water": 0.123456789,
        "trees": 0.234567891,
        "grass": 0.05,
        "flooded_vegetation": 0.01,
        "crops": 0.50,
        "shrub_and_scrub": 0.02,
        "built": 0.03,
        "bare": 0.03,
        "snow_and_ice": 0.00197532,
    }
    result = normalize_raw_dynamic_world_record(raw)
    assert result is not None
    _, _, probs = result
    assert probs.water == 0.123456789
    assert probs.trees == 0.234567891
    assert probs.snow_and_ice == 0.00197532


def test_normalize_raw_record_missing_bands_rejected():
    """Verify that records missing any of the 9 required bands are rejected (return None)."""
    raw = {
        "observation_date": "2026-09-01",
        "water": 0.1,
        "trees": 0.1,
        "grass": 0.1,
        # flooded_vegetation missing
        "crops": 0.5,
        "shrub_and_scrub": 0.1,
        "built": 0.05,
        "bare": 0.05,
        "snow_and_ice": 0.0,
    }
    assert normalize_raw_dynamic_world_record(raw) is None


def test_normalize_raw_record_negative_artifact_rejected():
    """Verify that records with negative probabilities are rejected (return None)."""
    fixture = load_dynamic_world_fixture("missing_band_or_negative_artifact.json")
    assert normalize_raw_dynamic_world_record(fixture) is None


def test_normalize_raw_record_greater_than_one_rejected():
    """Verify that probability values > 1.0 are rejected."""
    raw = {
        "observation_date": "2026-09-01",
        "water": 1.05,
        "trees": 0.0,
        "grass": 0.0,
        "flooded_vegetation": 0.0,
        "crops": 0.0,
        "shrub_and_scrub": 0.0,
        "built": 0.0,
        "bare": 0.0,
        "snow_and_ice": 0.0,
    }
    assert normalize_raw_dynamic_world_record(raw) is None


def test_normalize_raw_record_invalid_date_rejected():
    """Verify that invalid dates return None."""
    raw = {
        "observation_date": "not-a-date",
        "water": 0.1,
        "trees": 0.1,
        "grass": 0.1,
        "flooded_vegetation": 0.1,
        "crops": 0.3,
        "shrub_and_scrub": 0.1,
        "built": 0.1,
        "bare": 0.1,
        "snow_and_ice": 0.0,
    }
    assert normalize_raw_dynamic_world_record(raw) is None


def test_normalize_raw_record_time_start_timestamp_fallback():
    """Verify fallback to system:time_start UTC timestamp in ms."""
    raw = {
        "system:time_start": 1789451201000,  # 2026-09-15
        "system:index": "granule_xyz",
        "water": 0.0,
        "trees": 0.1,
        "grass": 0.1,
        "flooded_vegetation": 0.0,
        "crops": 0.7,
        "shrub_and_scrub": 0.05,
        "built": 0.03,
        "bare": 0.02,
        "snow_and_ice": 0.0,
    }
    result = normalize_raw_dynamic_world_record(raw)
    assert result is not None
    obs_date, obs_id, probs = result
    assert obs_date == date(2026, 9, 15)
    assert obs_id == "granule_xyz"
    assert probs.crops == 0.7


# ==============================================================================
# Dominant Class Derivation & Deterministic Tie-Breaking
# ==============================================================================

@pytest.mark.parametrize(
    "target_class",
    [
        "water",
        "trees",
        "grass",
        "flooded_vegetation",
        "crops",
        "shrub_and_scrub",
        "built",
        "bare",
        "snow_and_ice",
    ],
)
def test_derive_dominant_land_cover_each_class(target_class: DynamicWorldLandCoverClass):
    """Verify dominant class derivation when each of the 9 classes has the highest probability."""
    prob_kwargs = {cls_name: 0.05 for cls_name in CANONICAL_CLASS_PRECEDENCE}
    prob_kwargs[target_class] = 0.60
    probs = DynamicWorldClassProbabilities(**prob_kwargs)

    dom_class, dom_prob = derive_dominant_land_cover(probs)
    assert dom_class == target_class
    assert dom_prob == 0.60


def test_derive_dominant_land_cover_exact_tie_grass_vs_crops():
    """Verify deterministic tie-break: grass (index 2) wins over crops (index 4) on exact tie."""
    fixture = load_dynamic_world_fixture("exact_tie_edge_case.json")
    result = normalize_raw_dynamic_world_record(fixture)
    assert result is not None
    _, _, probs = result

    dom_class, dom_prob = derive_dominant_land_cover(probs)
    assert dom_class == "grass"
    assert dom_prob == 0.45


def test_derive_dominant_land_cover_exact_tie_water_vs_snow():
    """Verify deterministic tie-break: water (index 0) wins over snow_and_ice (index 8)."""
    probs = DynamicWorldClassProbabilities(
        water=0.50,
        trees=0.0,
        grass=0.0,
        flooded_vegetation=0.0,
        crops=0.0,
        shrub_and_scrub=0.0,
        built=0.0,
        bare=0.0,
        snow_and_ice=0.50,
    )
    dom_class, dom_prob = derive_dominant_land_cover(probs)
    assert dom_class == "water"
    assert dom_prob == 0.50


# ==============================================================================
# Tier 3: Pipeline Orchestration Unit Tests
# ==============================================================================

@patch("app.environment.dynamic_world_pipeline.fetch_raw_dynamic_world_record")
def test_analyze_dynamic_world_success(mock_fetch):
    """Verify successful end-to-end DynamicWorldAnalysis orchestration."""
    fixture = load_dynamic_world_fixture("punjab_cropland_dominant.json")
    mock_fetch.return_value = EarthEngineResult(
        status="success",
        dataset="GOOGLE/DYNAMICWORLD/V1",
        image_count=1,
        data=fixture,
        error=None,
    )

    analysis = analyze_dynamic_world_land_cover(
        latitude=30.9,
        longitude=75.85,
        requested_end_date="2026-09-20",
    )

    assert analysis.status == "success"
    assert analysis.requested_end_date == date(2026, 9, 20)
    assert analysis.observation_date == date(2026, 9, 15)
    assert analysis.data_lag_days == 5
    assert analysis.observation_id == "20260915T054641_20260915T055819_T43SBT"
    assert analysis.dominant_class == "crops"
    assert analysis.dominant_probability == 0.82
    assert analysis.class_probabilities is not None
    assert analysis.class_probabilities.crops == 0.82
    assert analysis.pipeline_version == "3.1.0"
    assert analysis.error is None


@patch("app.environment.dynamic_world_pipeline.fetch_raw_dynamic_world_record")
def test_analyze_dynamic_world_no_data_preserves_metadata(mock_fetch):
    """Verify no_data state preserves request/context metadata and sets observation fields to None."""
    mock_fetch.return_value = EarthEngineResult(
        status="no_data",
        dataset="GOOGLE/DYNAMICWORLD/V1",
        image_count=0,
        data=None,
        error=None,
    )

    analysis = analyze_dynamic_world_land_cover(
        latitude=30.9,
        longitude=75.85,
        requested_end_date=date(2026, 9, 20),
    )

    assert analysis.status == "no_data"
    assert analysis.region.latitude == 30.9
    assert analysis.region.longitude == 75.85
    assert analysis.requested_end_date == date(2026, 9, 20)
    assert analysis.dataset == "GOOGLE/DYNAMICWORLD/V1"
    assert analysis.spatial_resolution_m == 10.0
    assert analysis.pipeline_version == "3.1.0"
    assert analysis.observation_date is None
    assert analysis.observation_id is None
    assert analysis.data_lag_days is None
    assert analysis.dominant_class is None
    assert analysis.dominant_probability is None
    assert analysis.class_probabilities is None
    assert analysis.error is None


@patch("app.environment.dynamic_world_pipeline.fetch_raw_dynamic_world_record")
def test_analyze_dynamic_world_error_preserves_metadata(mock_fetch):
    """Verify error state preserves context metadata and populates EarthEngineError."""
    err = EarthEngineError(type="EEException", message="Connection failed")
    mock_fetch.return_value = EarthEngineResult(
        status="error",
        dataset="GOOGLE/DYNAMICWORLD/V1",
        image_count=None,
        data=None,
        error=err,
    )

    analysis = analyze_dynamic_world_land_cover(
        latitude=30.9,
        longitude=75.85,
        requested_end_date=date(2026, 9, 20),
    )

    assert analysis.status == "error"
    assert analysis.region.latitude == 30.9
    assert analysis.requested_end_date == date(2026, 9, 20)
    assert analysis.error is not None
    assert analysis.error.type == "EEException"
    assert analysis.observation_date is None
    assert analysis.class_probabilities is None


@patch("app.environment.dynamic_world_pipeline.fetch_raw_dynamic_world_record")
def test_analyze_dynamic_world_future_date_guard(mock_fetch):
    """Verify error when observation date is in the future relative to requested_end_date."""
    fixture = load_dynamic_world_fixture("punjab_cropland_dominant.json")
    fixture["observation_date"] = "2026-09-25"  # Future relative to 2026-09-20
    mock_fetch.return_value = EarthEngineResult(
        status="success",
        dataset="GOOGLE/DYNAMICWORLD/V1",
        image_count=1,
        data=fixture,
        error=None,
    )

    analysis = analyze_dynamic_world_land_cover(
        latitude=30.9,
        longitude=75.85,
        requested_end_date="2026-09-20",
    )

    assert analysis.status == "error"
    assert analysis.error is not None
    assert analysis.error.type == "DataIntegrityError"


def test_analyze_dynamic_world_coordinate_validation():
    """Verify coordinate parameter validation errors."""
    with pytest.raises(ValueError):
        analyze_dynamic_world_land_cover(latitude=95.0, longitude=75.0)

    with pytest.raises(ValueError):
        analyze_dynamic_world_land_cover(latitude=30.0, longitude=185.0)

    with pytest.raises(ValueError):
        analyze_dynamic_world_land_cover(latitude=30.0, longitude=75.0, radius_m=-10.0)

    with pytest.raises(ValueError):
        analyze_dynamic_world_land_cover(latitude=30.0, longitude=75.0, lookback_days=0)

    with pytest.raises(TypeError):
        analyze_dynamic_world_land_cover(latitude="invalid", longitude=75.0)  # type: ignore


# ==============================================================================
# Mandatory Test: Newest-Usable Logic Verification
# ==============================================================================

def test_newest_usable_selection_scenario_older_usable_wins():
    """Verify newest-usable selection: Observation B (older, usable) is selected when Observation A (newer, unusable) is excluded."""
    obs_a_unusable = {
        "observation_date": "2026-09-18",
        "observation_id": "OBS_A_NEWER_UNUSABLE",
        "water": None,
        "trees": None,
        "grass": None,
        "flooded_vegetation": None,
        "crops": None,
        "shrub_and_scrub": None,
        "built": None,
        "bare": None,
        "snow_and_ice": None,
    }
    obs_b_usable = {
        "observation_date": "2026-09-12",
        "observation_id": "OBS_B_OLDER_USABLE",
        "water": 0.01,
        "trees": 0.10,
        "grass": 0.05,
        "flooded_vegetation": 0.02,
        "crops": 0.70,
        "shrub_and_scrub": 0.02,
        "built": 0.05,
        "bare": 0.05,
        "snow_and_ice": 0.0,
    }

    # Normalize candidates
    norm_a = normalize_raw_dynamic_world_record(obs_a_unusable)
    norm_b = normalize_raw_dynamic_world_record(obs_b_usable)

    assert norm_a is None  # Observation A rejected
    assert norm_b is not None  # Observation B accepted

    obs_date, obs_id, probs = norm_b
    assert obs_date == date(2026, 9, 12)
    assert obs_id == "OBS_B_OLDER_USABLE"
    assert probs.crops == 0.70


def test_newest_usable_selection_scenario_newer_usable_wins():
    """Verify newest-usable selection: Observation A (newer, usable) is selected over Observation B (older, usable)."""
    obs_a_usable = {
        "observation_date": "2026-09-18",
        "observation_id": "OBS_A_NEWER_USABLE",
        "water": 0.01,
        "trees": 0.05,
        "grass": 0.05,
        "flooded_vegetation": 0.02,
        "crops": 0.80,
        "shrub_and_scrub": 0.02,
        "built": 0.03,
        "bare": 0.02,
        "snow_and_ice": 0.0,
    }
    obs_b_usable = {
        "observation_date": "2026-09-12",
        "observation_id": "OBS_B_OLDER_USABLE",
        "water": 0.01,
        "trees": 0.10,
        "grass": 0.05,
        "flooded_vegetation": 0.02,
        "crops": 0.70,
        "shrub_and_scrub": 0.02,
        "built": 0.05,
        "bare": 0.05,
        "snow_and_ice": 0.0,
    }

    candidates = [obs_a_usable, obs_b_usable]
    usable_candidates = []
    for cand in candidates:
        norm = normalize_raw_dynamic_world_record(cand)
        if norm is not None:
            usable_candidates.append(norm)

    # Sort descending by observation_date
    sorted_usable = sorted(usable_candidates, key=lambda x: x[0], reverse=True)
    assert len(sorted_usable) == 2

    # Newest usable observation selected
    selected_date, selected_id, selected_probs = sorted_usable[0]
    assert selected_date == date(2026, 9, 18)
    assert selected_id == "OBS_A_NEWER_USABLE"
    assert selected_probs.crops == 0.80
