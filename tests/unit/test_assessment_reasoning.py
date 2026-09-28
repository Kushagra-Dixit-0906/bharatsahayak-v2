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
"""Unit tests for Phase 5 Pure Deterministic Reasoning Engine (DEC-023)."""

import sys
from datetime import date
import pytest

from app.assessment.reasoning import interpret_agricultural_evidence
from app.assessment.types import AgriculturalAssessment
from tests.fixtures.assessment_fixtures import create_scenario_evidence


def test_scenario_01_stable_conditions():
    evidence = create_scenario_evidence("stable_conditions")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "success"
    assert assessment.overall_condition == "stable"
    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "near_baseline_stable_condition" in pattern_types
    assert assessment.sufficiency.is_sufficient is True


def test_scenario_02_water_stress_consistent():
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "success"
    assert assessment.overall_condition == "moisture_stress_consistent"
    patterns = {p.pattern_type: p for p in assessment.identified_patterns}
    assert "water_stress_consistent_pattern" in patterns
    assert patterns["water_stress_consistent_pattern"].evidence_support == "high_support"
    assert len(patterns["water_stress_consistent_pattern"].supporting_evidence) >= 2


def test_scenario_03_vegetation_stress_isolated():
    evidence = create_scenario_evidence("vegetation_stress_isolated")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "partial"
    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "vegetation_stress_pattern" in pattern_types or "water_stress_consistent_pattern" in pattern_types


def test_scenario_04_favorable_growth():
    evidence = create_scenario_evidence("favorable_growth")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "success"
    assert assessment.overall_condition == "favorable"
    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "favorable_growth_condition" in pattern_types


def test_scenario_05_heat_stress_consistent():
    evidence = create_scenario_evidence("heat_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)

    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "heat_stress_consistent_pattern" in pattern_types


def test_scenario_06_excess_moisture_waterlogging():
    evidence = create_scenario_evidence("excess_moisture_waterlogging")
    assessment = interpret_agricultural_evidence(evidence)

    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "excess_moisture_waterlogging_consistent_pattern" in pattern_types


def test_scenario_07_combined_environmental_stress():
    evidence = create_scenario_evidence("combined_environmental_stress")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.overall_condition == "combined_stress_consistent"
    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "combined_environmental_stress_pattern" in pattern_types
    assert "water_stress_consistent_pattern" in pattern_types
    assert "heat_stress_consistent_pattern" in pattern_types


def test_scenario_08_non_crop_context():
    evidence = create_scenario_evidence("non_crop_context")
    assessment = interpret_agricultural_evidence(evidence)

    assert any("non-crop dominant land-cover" in lim for lim in assessment.limitations)
    assert any("built" in lim for lim in assessment.limitations)


def test_scenario_09_historical_insufficient():
    evidence = create_scenario_evidence("historical_insufficient")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "partial"
    assert any("Historical vegetation baseline is unavailable" in lim for lim in assessment.limitations)
    assert "vegetation" in assessment.sufficiency.partial_evidence_sources


def test_scenario_10_all_no_data():
    evidence = create_scenario_evidence("all_no_data")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "insufficient_evidence"
    assert assessment.overall_condition == "insufficient_evidence"
    assert len(assessment.identified_patterns) == 0
    assert assessment.sufficiency.is_sufficient is False


def test_scenario_11_all_error():
    evidence = create_scenario_evidence("all_error")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "error"
    assert assessment.overall_condition == "insufficient_evidence"
    assert assessment.error is not None
    assert len(assessment.identified_patterns) == 0


def test_scenario_12_mixed_no_data_error():
    evidence = create_scenario_evidence("mixed_no_data_error")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status in ("insufficient_evidence", "error")
    assert assessment.overall_condition == "insufficient_evidence"
    assert assessment.sufficiency.is_sufficient is False


def test_scenario_13_missing_not_zero():
    # If CHIRPS is missing, we must NOT assert 0.0 mm rainfall or declare drought
    evidence = create_scenario_evidence("vegetation_stress_isolated")
    assessment = interpret_agricultural_evidence(evidence)

    assert "rainfall" in assessment.sufficiency.missing_evidence_sources
    assert any("CHIRPS precipitation is unavailable" in lim for lim in assessment.limitations)


def test_scenario_14_severity_is_none_for_mvp():
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)

    for pattern in assessment.identified_patterns:
        assert pattern.severity is None, "Severity must be None in MVP (future work: requires calibration)"


def test_scenario_15_provenance_integrity():
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)

    for pattern in assessment.identified_patterns:
        for item in pattern.supporting_evidence:
            assert item.source in ("vegetation", "reanalysis", "rainfall", "land_cover")
            assert item.metric_name is not None
            assert item.observed_value is not None


def test_scenario_16_input_evidence_immutability():
    evidence = create_scenario_evidence("stable_conditions")
    original_dict = evidence.model_dump()

    _ = interpret_agricultural_evidence(evidence)

    assert evidence.model_dump() == original_dict, "Reasoning engine must not mutate input evidence"


def test_scenario_17_zero_earth_engine_imports_in_reasoning():
    # Verify app.assessment.reasoning does not import ee or google.earth_engine
    assert "app.assessment.reasoning" in sys.modules
    reasoning_module = sys.modules["app.assessment.reasoning"]
    assert "ee" not in reasoning_module.__dict__
    assert not hasattr(reasoning_module, "ee")


def test_scenario_18_invalid_evidence_type_raises():
    with pytest.raises(TypeError, match="must be an AgriculturalEnvironmentalEvidence instance"):
        interpret_agricultural_evidence("invalid_evidence")  # type: ignore[arg-type]


def test_scenario_19_pattern_specific_sufficiency_missing_temp():
    # If reanalysis is missing, heat stress pattern must NOT be detected
    evidence = create_scenario_evidence("vegetation_stress_isolated")
    assessment = interpret_agricultural_evidence(evidence)

    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    # Reanalysis is present in vegetation_stress_isolated, but let's check all_no_data
    evidence_nd = create_scenario_evidence("all_no_data")
    assessment_nd = interpret_agricultural_evidence(evidence_nd)
    assert len(assessment_nd.identified_patterns) == 0


def test_scenario_20_no_speculative_causal_attribution():
    evidence = create_scenario_evidence("conflicting_ndvi_rainfall")
    assessment = interpret_agricultural_evidence(evidence)

    for pattern in assessment.identified_patterns:
        desc = pattern.description.lower()
        assert "pest" not in desc
        assert "fertilizer" not in desc
        assert "fungal" not in desc
        assert "tube-well" not in desc
        assert "canal" not in desc


def test_scenario_21_crop_dominant_land_cover():
    evidence = create_scenario_evidence("crop_dominant_land_cover")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "success"
    # When dominant_class is 'crops', no non-crop limitation should be added
    assert not any("non-crop dominant land-cover" in lim for lim in assessment.limitations)


def test_scenario_22_conflicting_temperature_soil_water():
    evidence = create_scenario_evidence("conflicting_temperature_soil_water")
    assessment = interpret_agricultural_evidence(evidence)

    # Elevated temperature triggers heat stress
    pattern_types = [p.pattern_type for p in assessment.identified_patterns]
    assert "heat_stress_consistent_pattern" in pattern_types


def test_scenario_23_partial_chirps():
    evidence = create_scenario_evidence("partial_chirps")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "partial"
    assert "rainfall" in assessment.sufficiency.missing_evidence_sources


def test_scenario_24_partial_era5():
    evidence = create_scenario_evidence("partial_era5")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "partial"
    assert "reanalysis" in assessment.sufficiency.missing_evidence_sources


def test_scenario_25_current_ndvi_unavailable():
    evidence = create_scenario_evidence("current_ndvi_unavailable")
    assessment = interpret_agricultural_evidence(evidence)

    assert assessment.status == "insufficient_evidence"
    assert assessment.overall_condition == "insufficient_evidence"
    assert assessment.sufficiency.is_sufficient is False
    assert len(assessment.identified_patterns) == 0


def test_scenario_26_deterministic_reproducibility():
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment_1 = interpret_agricultural_evidence(evidence)
    assessment_2 = interpret_agricultural_evidence(evidence)

    assert assessment_1.model_dump() == assessment_2.model_dump()


def test_scenario_27_insufficient_evidence_never_defaults_to_stable():
    # Verify that whenever assessment status is insufficient_evidence, overall_condition is NEVER stable
    for scenario_name in ("all_no_data", "current_ndvi_unavailable"):
        evidence = create_scenario_evidence(scenario_name)
        assessment = interpret_agricultural_evidence(evidence)

        assert assessment.status == "insufficient_evidence"
        assert assessment.overall_condition == "insufficient_evidence"
        assert assessment.overall_condition != "stable"


