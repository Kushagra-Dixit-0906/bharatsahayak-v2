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
"""Unit tests for Phase 5C Gemini Assessment Context & Projection Serializer (DEC-024)."""

from datetime import date
import pytest
from pydantic import ValidationError

from app.assessment.gemini_types import (
    ContextPatternSummary,
    GeminiAssessmentContext,
    PresentationPreferences,
    VerifiedFarmerContext,
    assessment_to_gemini_context,
)
from app.assessment.reasoning import interpret_agricultural_evidence
from app.assessment.types import (
    AgriculturalAssessment,
    AssessmentSufficiency,
    EnvironmentalStressPattern,
    SupportingEvidenceItem,
)
from app.satellite.types import AnalysisRegionMetadata
from tests.fixtures.assessment_fixtures import create_scenario_evidence


@pytest.fixture
def stable_assessment() -> AgriculturalAssessment:
    """Produces a deterministic stable AgriculturalAssessment."""
    evidence = create_scenario_evidence("stable_conditions")
    return interpret_agricultural_evidence(evidence)


@pytest.fixture
def water_stress_assessment() -> AgriculturalAssessment:
    """Produces a deterministic water stress AgriculturalAssessment with supporting evidence."""
    evidence = create_scenario_evidence("water_stress_consistent")
    return interpret_agricultural_evidence(evidence)


@pytest.fixture
def conflicting_assessment() -> AgriculturalAssessment:
    """Produces a deterministic conflicting signals AgriculturalAssessment."""
    evidence = create_scenario_evidence("conflicting_ndvi_rainfall")
    return interpret_agricultural_evidence(evidence)


@pytest.fixture
def insufficient_evidence_assessment() -> AgriculturalAssessment:
    """Produces a deterministic insufficient evidence AgriculturalAssessment."""
    evidence = create_scenario_evidence("all_no_data")
    return interpret_agricultural_evidence(evidence)


# ==============================================================================
# 1. Basic Serialization
# ==============================================================================

def test_basic_serialization(stable_assessment: AgriculturalAssessment) -> None:
    """Verifies that a valid AgriculturalAssessment serializes into a valid GeminiAssessmentContext."""
    context = assessment_to_gemini_context(stable_assessment)

    assert isinstance(context, GeminiAssessmentContext)
    assert context.overall_condition == stable_assessment.overall_condition
    assert context.assessment_status == stable_assessment.status
    assert context.reference_date == stable_assessment.reference_date
    assert context.region == stable_assessment.region
    assert context.is_sufficient == stable_assessment.sufficiency.is_sufficient


# ==============================================================================
# 2. Pattern Preservation
# ==============================================================================

def test_pattern_type_preservation(water_stress_assessment: AgriculturalAssessment) -> None:
    """Verifies that all pattern_type values are identical before and after projection."""
    context = assessment_to_gemini_context(water_stress_assessment)

    assert len(context.identified_patterns) == len(water_stress_assessment.identified_patterns)
    for orig_pattern, proj_pattern in zip(
        water_stress_assessment.identified_patterns, context.identified_patterns
    ):
        assert proj_pattern.pattern_type == orig_pattern.pattern_type
        assert proj_pattern.technical_summary == orig_pattern.description


# ==============================================================================
# 3. Evidence Support Preservation
# ==============================================================================

def test_evidence_support_preservation(
    water_stress_assessment: AgriculturalAssessment,
    conflicting_assessment: AgriculturalAssessment,
) -> None:
    """Verifies that categorical evidence_support levels are preserved without numerical distortion."""
    for assess in [water_stress_assessment, conflicting_assessment]:
        context = assessment_to_gemini_context(assess)
        for orig_pattern, proj_pattern in zip(assess.identified_patterns, context.identified_patterns):
            assert proj_pattern.evidence_support == orig_pattern.evidence_support
            assert proj_pattern.evidence_support in [
                "high_support",
                "moderate_support",
                "limited_support",
                "conflicted_support",
            ]


# ==============================================================================
# 4. Structured Supporting Evidence Preservation
# ==============================================================================

def test_structured_supporting_evidence_preservation(
    water_stress_assessment: AgriculturalAssessment,
) -> None:
    """Verifies that every SupportingEvidenceItem preserves source, metric_name, observed_value, reference_context."""
    context = assessment_to_gemini_context(water_stress_assessment)

    for orig_pattern, proj_pattern in zip(
        water_stress_assessment.identified_patterns, context.identified_patterns
    ):
        assert len(proj_pattern.supporting_evidence) == len(orig_pattern.supporting_evidence)
        for orig_item, proj_item in zip(orig_pattern.supporting_evidence, proj_pattern.supporting_evidence):
            assert isinstance(proj_item, SupportingEvidenceItem)
            assert proj_item.source == orig_item.source
            assert proj_item.metric_name == orig_item.metric_name
            assert proj_item.observed_value == orig_item.observed_value
            assert proj_item.reference_context == orig_item.reference_context


# ==============================================================================
# 5. Status & Overall Condition Preservation
# ==============================================================================

def test_status_and_overall_condition_preservation(
    stable_assessment: AgriculturalAssessment,
    water_stress_assessment: AgriculturalAssessment,
    conflicting_assessment: AgriculturalAssessment,
    insufficient_evidence_assessment: AgriculturalAssessment,
) -> None:
    """Verifies that operational status and overall_condition are preserved exactly."""
    for assess in [
        stable_assessment,
        water_stress_assessment,
        conflicting_assessment,
        insufficient_evidence_assessment,
    ]:
        context = assessment_to_gemini_context(assess)
        assert context.assessment_status == assess.status
        assert context.overall_condition == assess.overall_condition


# ==============================================================================
# 6. Sufficiency & Metadata Preservation (No Arbitrary 14-Day Rule)
# ==============================================================================

def test_sufficiency_preservation(water_stress_assessment: AgriculturalAssessment) -> None:
    """Verifies that sufficiency fields and lag metadata are projected without alteration."""
    context = assessment_to_gemini_context(water_stress_assessment)

    assert context.is_sufficient == water_stress_assessment.sufficiency.is_sufficient
    assert context.missing_evidence_sources == water_stress_assessment.sufficiency.missing_evidence_sources
    assert context.partial_evidence_sources == water_stress_assessment.sufficiency.partial_evidence_sources
    assert context.maximum_data_lag_days == water_stress_assessment.sufficiency.maximum_data_lag_days


# ==============================================================================
# 7. Conflicts & Limitations Preservation
# ==============================================================================

def test_conflicts_and_limitations_preservation(
    conflicting_assessment: AgriculturalAssessment,
) -> None:
    """Verifies that conflicting signals and limitations lists are preserved exactly."""
    context = assessment_to_gemini_context(conflicting_assessment)

    assert context.conflicting_signals == conflicting_assessment.conflicting_signals
    assert len(context.conflicting_signals) > 0
    assert context.limitations == conflicting_assessment.limitations


# ==============================================================================
# 8. Insufficient Evidence Non-Upgrading
# ==============================================================================

def test_insufficient_evidence_not_upgraded(
    insufficient_evidence_assessment: AgriculturalAssessment,
) -> None:
    """Verifies that insufficient evidence assessments are preserved as insufficient and never upgraded."""
    context = assessment_to_gemini_context(insufficient_evidence_assessment)

    assert context.assessment_status == "insufficient_evidence"
    assert context.overall_condition == "insufficient_evidence"
    assert context.is_sufficient is False
    assert len(context.missing_evidence_sources) == 4
    assert context.identified_patterns == []


# ==============================================================================
# 9. Empty Optional Collections
# ==============================================================================

def test_empty_optional_collections() -> None:
    """Verifies that empty optional collections in assessments project cleanly."""
    region = AnalysisRegionMetadata(
        latitude=28.7,
        longitude=77.1,
        radius_m=100.0,
    )
    sufficiency = AssessmentSufficiency(
        is_sufficient=True,
        sources_evaluated_count=4,
        sources_available_count=4,
        sources_fully_available_count=4,
        missing_evidence_sources=[],
        partial_evidence_sources=[],
        maximum_data_lag_days=0,
        sufficiency_summary="Complete evidence.",
    )
    evidence = create_scenario_evidence("stable_conditions")

    minimal_assessment = AgriculturalAssessment(
        region=region,
        reference_date=date(2026, 9, 15),
        evidence=evidence,
        status="success",
        overall_condition="stable",
        identified_patterns=[],
        sufficiency=sufficiency,
        conflicting_signals=[],
        limitations=[],
        pipeline_version="5.0.0",
    )

    context = assessment_to_gemini_context(minimal_assessment)
    assert context.identified_patterns == []
    assert context.conflicting_signals == []
    assert context.limitations == []
    assert context.missing_evidence_sources == []
    assert context.partial_evidence_sources == []


# ==============================================================================
# 10. Immutability & Zero Mutation Side Effects
# ==============================================================================

def test_immutability_and_zero_mutation(water_stress_assessment: AgriculturalAssessment) -> None:
    """Verifies that projection does not mutate input assessment and context models are frozen."""
    orig_dump = water_stress_assessment.model_dump()
    context = assessment_to_gemini_context(water_stress_assessment)
    post_dump = water_stress_assessment.model_dump()

    # Verify input assessment was not mutated
    assert orig_dump == post_dump

    # Verify context is frozen/immutable
    with pytest.raises(ValidationError):
        context.overall_condition = "stable"  # type: ignore[misc]

    if context.identified_patterns:
        with pytest.raises(ValidationError):
            context.identified_patterns[0].evidence_support = "limited_support"  # type: ignore[misc]


# ==============================================================================
# 11. Farmer Context Boundary (Personalization, NOT Evidence)
# ==============================================================================

def test_farmer_context_is_not_evidence(water_stress_assessment: AgriculturalAssessment) -> None:
    """Verifies that supplying farmer personalization context does NOT alter environmental evidence."""
    farmer_ctx = VerifiedFarmerContext(
        crop="wheat",
        crop_stage="vegetative",
        irrigation_available=True,
        preferred_language="hi",
        context_status="verified",
    )
    presentation = PresentationPreferences(
        target_language="hi",
        communication_tone="rural_empathetic_concise",
    )

    context = assessment_to_gemini_context(
        water_stress_assessment,
        farmer_context=farmer_ctx,
        presentation=presentation,
    )

    # Personalization is captured
    assert context.farmer_context.crop == "wheat"
    assert context.farmer_context.crop_stage == "vegetative"
    assert context.farmer_context.irrigation_available is True
    assert context.farmer_context.context_status == "verified"
    assert context.presentation.target_language == "hi"

    # Environmental evidence remains strictly untouched
    assert context.overall_condition == water_stress_assessment.overall_condition
    assert context.assessment_status == water_stress_assessment.status
    assert len(context.identified_patterns) == len(water_stress_assessment.identified_patterns)


# ==============================================================================
# 12. Security & PII Boundary Enforcement
# ==============================================================================

def test_security_pii_boundary_rejection() -> None:
    """Verifies that extra or sensitive PII fields (Aadhaar, phone, bank) are forbidden and rejected."""
    with pytest.raises(ValidationError):
        VerifiedFarmerContext(
            crop="wheat",
            aadhaar_number="1234-5678-9012",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        VerifiedFarmerContext(
            phone_number="+919876543210",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        GeminiAssessmentContext(
            overall_condition="stable",
            assessment_status="success",
            reference_date=date(2026, 9, 15),
            region=AnalysisRegionMetadata(
                latitude=28.7, longitude=77.1, radius_m=100.0
            ),
            is_sufficient=True,
            farmer_name="Ramesh Kumar",  # type: ignore[call-arg]
        )


# ==============================================================================
# 13. Type Safety
# ==============================================================================

def test_serializer_type_safety() -> None:
    """Verifies that passing invalid types to assessment_to_gemini_context raises TypeError."""
    with pytest.raises(TypeError, match="assessment must be an AgriculturalAssessment instance"):
        assessment_to_gemini_context(None)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="assessment must be an AgriculturalAssessment instance"):
        assessment_to_gemini_context({"status": "success"})  # type: ignore[arg-type]
