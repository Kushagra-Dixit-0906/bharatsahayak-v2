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
"""Unit tests for Phase 5 domain types and contracts (DEC-023)."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.assessment.types import (
    AgriculturalAssessment,
    AssessmentStatus,
    AssessmentSufficiency,
    EnvironmentalStressPattern,
    EnvironmentalStressPatternType,
    EvidenceSupportLevel,
    OverallEnvironmentalCondition,
    SupportingEvidenceItem,
)
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError
from tests.fixtures.assessment_fixtures import create_scenario_evidence


def test_supporting_evidence_item_valid():
    item = SupportingEvidenceItem(
        source="vegetation",
        metric_name="departure_band",
        observed_value="moderately_below_normal",
        reference_context="Phase 2 baseline anomaly",
    )
    assert item.source == "vegetation"
    assert item.metric_name == "departure_band"
    assert item.observed_value == "moderately_below_normal"
    assert item.reference_context == "Phase 2 baseline anomaly"


def test_supporting_evidence_item_immutability():
    item = SupportingEvidenceItem(
        source="rainfall",
        metric_name="total_precipitation_mm",
        observed_value=12.5,
    )
    with pytest.raises(ValidationError):
        item.source = "reanalysis"  # type: ignore[misc]


def test_environmental_stress_pattern_valid():
    pattern = EnvironmentalStressPattern(
        pattern_type="water_stress_consistent_pattern",
        evidence_support="high_support",
        severity=None,
        description="Vegetation vigor is below historical baseline.",
        supporting_evidence=[
            SupportingEvidenceItem(
                source="vegetation",
                metric_name="departure_band",
                observed_value="significantly_below_normal",
            )
        ],
        conflicting_signals=[],
    )
    assert pattern.pattern_type == "water_stress_consistent_pattern"
    assert pattern.evidence_support == "high_support"
    assert pattern.severity is None
    assert len(pattern.supporting_evidence) == 1


def test_environmental_stress_pattern_extra_field_forbidden():
    with pytest.raises(ValidationError):
        EnvironmentalStressPattern(
            pattern_type="water_stress_consistent_pattern",
            evidence_support="high_support",
            description="Test",
            fake_field=123,  # type: ignore[call-arg]
        )


def test_assessment_sufficiency_valid():
    suff = AssessmentSufficiency(
        is_sufficient=True,
        sources_evaluated_count=4,
        sources_available_count=4,
        sources_fully_available_count=4,
        missing_evidence_sources=[],
        partial_evidence_sources=[],
        maximum_data_lag_days=3,
        sufficiency_summary="All sources available.",
    )
    assert suff.is_sufficient is True
    assert suff.sources_evaluated_count == 4
    assert suff.maximum_data_lag_days == 3


def test_assessment_sufficiency_count_invariant_violation():
    with pytest.raises(ValidationError, match="Count violation"):
        AssessmentSufficiency(
            is_sufficient=True,
            sources_evaluated_count=4,
            sources_available_count=2,
            sources_fully_available_count=3,  # fully > available
            sufficiency_summary="Invalid",
        )


def test_agricultural_assessment_valid_model():
    evidence = create_scenario_evidence("stable_conditions")
    suff = AssessmentSufficiency(
        is_sufficient=True,
        sources_evaluated_count=4,
        sources_available_count=4,
        sources_fully_available_count=4,
        missing_evidence_sources=[],
        partial_evidence_sources=[],
        maximum_data_lag_days=3,
        sufficiency_summary="All sources fully available.",
    )
    assessment = AgriculturalAssessment(
        region=evidence.region,
        reference_date=evidence.reference_date,
        evidence=evidence,
        status="success",
        overall_condition="stable",
        identified_patterns=[],
        sufficiency=suff,
        conflicting_signals=[],
        limitations=[],
        pipeline_version="5.0.0",
        error=None,
    )
    assert assessment.status == "success"
    assert assessment.overall_condition == "stable"
    assert assessment.pipeline_version == "5.0.0"
    assert assessment.error is None


def test_agricultural_assessment_immutability():
    evidence = create_scenario_evidence("stable_conditions")
    suff = AssessmentSufficiency(
        is_sufficient=True,
        sources_evaluated_count=4,
        sources_available_count=4,
        sources_fully_available_count=4,
        sufficiency_summary="All sources available.",
    )
    assessment = AgriculturalAssessment(
        region=evidence.region,
        reference_date=evidence.reference_date,
        evidence=evidence,
        status="success",
        overall_condition="stable",
        identified_patterns=[],
        sufficiency=suff,
        conflicting_signals=[],
        limitations=[],
    )
    with pytest.raises(ValidationError):
        assessment.overall_condition = "favorable"  # type: ignore[misc]


def test_agricultural_assessment_error_invariant():
    evidence = create_scenario_evidence("stable_conditions")
    suff = AssessmentSufficiency(
        is_sufficient=False,
        sources_evaluated_count=4,
        sources_available_count=0,
        sources_fully_available_count=0,
        sufficiency_summary="Error",
    )
    # status='error' requires error object
    with pytest.raises(ValidationError, match="status='error' requires an error"):
        AgriculturalAssessment(
            region=evidence.region,
            reference_date=evidence.reference_date,
            evidence=evidence,
            status="error",
            overall_condition="insufficient_evidence",
            identified_patterns=[],
            sufficiency=suff,
            error=None,
        )


def test_agricultural_assessment_non_error_with_error_rejected():
    evidence = create_scenario_evidence("stable_conditions")
    suff = AssessmentSufficiency(
        is_sufficient=True,
        sources_evaluated_count=4,
        sources_available_count=4,
        sources_fully_available_count=4,
        sufficiency_summary="Success",
    )
    with pytest.raises(ValidationError, match="cannot contain a top-level error"):
        AgriculturalAssessment(
            region=evidence.region,
            reference_date=evidence.reference_date,
            evidence=evidence,
            status="success",
            overall_condition="stable",
            identified_patterns=[],
            sufficiency=suff,
            error=EarthEngineError(type="TestError", message="Test"),
        )
