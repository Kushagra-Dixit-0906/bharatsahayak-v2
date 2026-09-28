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
"""Unit tests for Phase 5C Step 4 Unified Assessment & Explanation Pipeline (DEC-024).

Verifies the integration of Phase 5B deterministic assessment and Phase 5C Gemini natural language
explanation, enforcing Phase 5B authority, transparency, strict Gemini call policies, error fallback
semantics, and language/context propagation without live network calls.
"""

import copy
from datetime import date
import json
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from app.assessment.gemini_service import GeminiModelClient
from app.assessment.gemini_types import (
    AgriculturalAssessmentExplanationResponse,
    FarmerAgriculturalResponse,
    GeminiAssessmentContext,
    PresentationPreferences,
    RecommendedNextStep,
    VerifiedFarmerContext,
)
from app.assessment.pipeline import (
    evaluate_agricultural_assessment,
    evaluate_and_explain_agricultural_assessment,
    fetch_agricultural_assessment_explanation,
)
from app.assessment.types import AgriculturalAssessment
from tests.fixtures.assessment_fixtures import create_scenario_evidence


class FakeGeminiClient:
    """Mock Gemini client for deterministic offline unit testing."""

    def __init__(
        self,
        response_text: str | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.response_text = response_text
        self.raise_error = raise_error
        self.call_count = 0
        self.last_model: str | None = None
        self.last_prompt: str | None = None
        self.last_config: Any | None = None

    def generate_content(
        self, model: str, contents: str, config: Any | None = None
    ) -> Any:
        self.call_count += 1
        self.last_model = model
        self.last_prompt = contents
        self.last_config = config

        if self.raise_error is not None:
            raise self.raise_error

        mock_resp = MagicMock()
        mock_resp.text = self.response_text
        return mock_resp


def _make_valid_gemini_response_json(
    language: str = "en",
    headline: str = "Field vegetation is aligned with seasonal norms.",
    summary: str = "Satellite greenness and soil moisture are within normal ranges.",
    observations: list[str] | None = None,
    interpretation: str = "Current observations show stable conditions.",
    steps: list[dict[str, str]] | None = None,
    limitations: list[str] | None = None,
) -> str:
    """Helper to generate a valid JSON payload matching FarmerAgriculturalResponse."""
    payload = {
        "language": language,
        "headline": headline,
        "summary": summary,
        "observations": observations
        if observations is not None
        else ["Vegetation index indicates normal canopy density."],
        "interpretation": interpretation,
        "recommended_next_steps": steps
        if steps is not None
        else [
            {
                "action_type": "ongoing_monitoring",
                "description": "Continue routine weekly field monitoring.",
                "urgency": "routine",
            }
        ],
        "limitations": limitations
        if limitations is not None
        else ["No significant cloud cover detected."],
        "is_fallback": False,
    }
    return json.dumps(payload)


# ==============================================================================
# 1. Successful Assessment → Gemini Explanation
# ==============================================================================


def test_successful_assessment_gemini_explanation():
    """Verifies successful assessment triggers Gemini and returns unified response with is_fallback=False."""
    evidence = create_scenario_evidence("stable_conditions")
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(
            language="en",
            headline="Stable crop conditions observed across the parcel.",
            summary="Vegetation vigor and weather patterns match historical averages.",
        )
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    assert isinstance(response, AgriculturalAssessmentExplanationResponse)
    assert response.assessment.status == "success"
    assert response.assessment.overall_condition == "stable"
    assert isinstance(response.explanation, FarmerAgriculturalResponse)
    assert response.explanation.is_fallback is False
    assert response.explanation.headline == "Stable crop conditions observed across the parcel."
    assert fake_client.call_count == 1
    assert response.context_used.assessment_status == "success"


# ==============================================================================
# 2. Partial Assessment → Gemini Explanation
# ==============================================================================


def test_partial_assessment_gemini_explanation_preserves_limitations():
    """Verifies partial assessment calls Gemini and retains limitations."""
    evidence = create_scenario_evidence("vegetation_stress_isolated")
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(
            language="en",
            headline="Vegetation departure observed while weather data was partially missing.",
            summary="Lower greenness detected; rainfall records were unavailable.",
            limitations=["Rainfall data stream was missing."],
        )
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    assert response.assessment.status == "partial"
    assert response.explanation.is_fallback is False
    assert fake_client.call_count == 1
    assert response.context_used.assessment_status == "partial"
    assert "rainfall" in response.context_used.missing_evidence_sources


# ==============================================================================
# 3. Insufficient Evidence → Gemini Explanation & Upgrade Guard
# ==============================================================================


def test_insufficient_evidence_gemini_explanation_cannot_upgrade():
    """Verifies insufficient evidence passes to Gemini, but cannot be upgraded to thriving."""
    evidence = create_scenario_evidence("all_no_data")
    # Gemini tries to hallucinate a thriving claim
    invalid_gemini_text = _make_valid_gemini_response_json(
        language="en",
        headline="Crop is thriving and in excellent condition.",
        summary="Crop is completely healthy and thriving with strong growth.",
    )
    fake_client = FakeGeminiClient(response_text=invalid_gemini_text)

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    assert response.assessment.status == "insufficient_evidence"
    assert response.assessment.overall_condition == "insufficient_evidence"
    # Rejection triggers deterministic fallback
    assert response.explanation.is_fallback is True
    assert fake_client.call_count == 1
    assert "insufficient" in response.explanation.headline.lower()


# ==============================================================================
# 4. Conflicting Signals Assessment
# ==============================================================================


def test_conflicting_signals_assessment_explanation():
    """Verifies assessment conflict data is untouched and Gemini explanation is formed."""
    evidence = create_scenario_evidence("conflicting_ndvi_rainfall")
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(
            language="en",
            headline="Contrasting vegetation greenness and rainfall signals observed.",
            summary="Vegetation shows below-average vigor despite heavy recent rainfall.",
        )
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    assert response.assessment.status == "success"
    assert len(response.assessment.conflicting_signals) > 0
    assert response.explanation.is_fallback is False
    assert fake_client.call_count == 1
    assert len(response.context_used.conflicting_signals) > 0


# ==============================================================================
# 5. Gemini API Failure → Fallback
# ==============================================================================


def test_gemini_api_failure_preserves_assessment_and_sets_fallback():
    """Verifies that Gemini API exception preserves assessment and sets is_fallback=True."""
    evidence = create_scenario_evidence("stable_conditions")
    fake_client = FakeGeminiClient(
        raise_error=RuntimeError("Google API 503 Service Unavailable")
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    assert response.assessment.status == "success"
    assert response.assessment.overall_condition == "stable"
    assert response.explanation.is_fallback is True
    assert response.explanation.language == "en"
    assert "stable" in response.explanation.headline.lower() or "seasonal" in response.explanation.headline.lower()


# ==============================================================================
# 6. Gemini Validation Failure → Deterministic Fallback
# ==============================================================================


def test_gemini_validation_failure_preserves_assessment_and_returns_fallback():
    """Verifies that banned content (e.g. chemical prescription) triggers fallback."""
    evidence = create_scenario_evidence("water_stress_consistent")
    # Invalid response prescribing pesticide dosage
    toxic_text = _make_valid_gemini_response_json(
        language="en",
        headline="Moisture stress detected.",
        summary="Apply 50 ml/ha of chlorpyrifos immediately.",
    )
    fake_client = FakeGeminiClient(response_text=toxic_text)

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    assert response.assessment.status == "success"
    assert response.assessment.overall_condition == "moisture_stress_consistent"
    assert response.explanation.is_fallback is True
    assert fake_client.call_count == 1
    # Fallback must be safe and not contain chlorpyrifos
    assert "chlorpyrifos" not in response.explanation.summary.lower()


# ==============================================================================
# 7. Hindi Localization
# ==============================================================================


def test_hindi_localization_propagation():
    """Verifies Hindi preference is propagated to Gemini and fallback paths."""
    evidence = create_scenario_evidence("water_stress_consistent")
    fake_client = FakeGeminiClient(
        response_text=json.dumps(
            {
                "language": "hi",
                "headline": "खेत में नमी की कमी के लक्षण देखे गए हैं।",
                "summary": "कम वर्षा और कम मिट्टी की नमी के कारण फसल तनाव में है।",
                "observations": ["मिट्टी की नमी ऐतिहासिक सामान्य से कम है।"],
                "interpretation": "उपग्रह और मौसम आंकड़े नमी की कमी का संकेत देते हैं।",
                "recommended_next_steps": [
                    {
                        "action_type": "soil_moisture_manual_check",
                        "description": "खेत में जाकर मिट्टी की नमी की जांच करें।",
                        "urgency": "advisory",
                    }
                ],
                "limitations": ["बादलों का कोई प्रभाव नहीं देखा गया।"],
                "is_fallback": False,
            }
        )
    )

    presentation = PresentationPreferences(target_language="hi")
    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        presentation=presentation,
        client=fake_client,
    )

    assert response.explanation.language == "hi"
    assert response.explanation.is_fallback is False
    assert "नमी" in response.explanation.headline
    assert response.context_used.presentation.target_language == "hi"


# ==============================================================================
# 8. Farmer Context Propagation
# ==============================================================================


def test_farmer_context_propagation():
    """Verifies verified farmer context is included in context_used without altering assessment."""
    evidence = create_scenario_evidence("stable_conditions")
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(language="en")
    )
    farmer_ctx = VerifiedFarmerContext(
        crop="wheat",
        crop_stage="flowering",
        irrigation_available=True,
        preferred_language="en",
        context_status="verified",
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        farmer_context=farmer_ctx,
        client=fake_client,
    )

    assert response.context_used.farmer_context.crop == "wheat"
    assert response.context_used.farmer_context.crop_stage == "flowering"
    assert response.context_used.farmer_context.irrigation_available is True
    assert response.context_used.farmer_context.context_status == "verified"
    # Assessment itself is unaffected
    assert response.assessment.overall_condition == "stable"


# ==============================================================================
# 9. Context and Evidence Immutability
# ==============================================================================


def test_input_evidence_and_context_immutability():
    """Verifies that evidence, assessment, and context objects are not mutated."""
    evidence = create_scenario_evidence("stable_conditions")
    evidence_snapshot = copy.deepcopy(evidence)
    farmer_ctx = VerifiedFarmerContext(crop="mustard")
    presentation = PresentationPreferences(target_language="en")

    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(language="en")
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        farmer_context=farmer_ctx,
        presentation=presentation,
        client=fake_client,
    )

    # Verify input evidence wasn't mutated
    assert evidence == evidence_snapshot
    assert isinstance(response.context_used, GeminiAssessmentContext)


# ==============================================================================
# 10. Phase 5B Transparency Invariant
# ==============================================================================


def test_phase_5b_transparency_invariant():
    """CRITICAL INVARIANT: direct_phase5b_assessment == unified_pipeline.assessment."""
    evidence = create_scenario_evidence("water_stress_consistent")

    direct_assessment = evaluate_agricultural_assessment(evidence)
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(language="en")
    )

    unified_response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    # Full object equality check across all fields
    assert unified_response.assessment == direct_assessment
    assert unified_response.assessment.status == direct_assessment.status
    assert unified_response.assessment.overall_condition == direct_assessment.overall_condition
    assert unified_response.assessment.identified_patterns == direct_assessment.identified_patterns
    assert unified_response.assessment.conflicting_signals == direct_assessment.conflicting_signals
    assert unified_response.assessment.limitations == direct_assessment.limitations
    assert unified_response.assessment.sufficiency == direct_assessment.sufficiency


# ==============================================================================
# 11. Error Status Semantics (Gemini NOT Invoked)
# ==============================================================================


def test_error_status_bypasses_gemini_and_returns_error_fallback():
    """Verifies assessment.status == 'error' bypasses Gemini and produces deterministic error fallback."""
    evidence = create_scenario_evidence("all_error")
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(language="en")
    )

    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        client=fake_client,
    )

    # Gemini client must NOT be invoked
    assert fake_client.call_count == 0
    # Assessment status remains error
    assert response.assessment.status == "error"
    # Farmer explanation is deterministic fallback
    assert response.explanation.is_fallback is True
    # Must NOT claim insufficient evidence
    assert "insufficient evidence" not in response.explanation.headline.lower()
    assert "insufficient evidence" not in response.explanation.summary.lower()
    # Must communicate service/data unavailability
    assert (
        "error" in response.explanation.headline.lower()
        or "unavailable" in response.explanation.headline.lower()
    )
    # Observations must be empty
    assert len(response.explanation.observations) == 0


def test_error_status_hindi_localization():
    """Verifies assessment.status == 'error' with Hindi presentation preference."""
    evidence = create_scenario_evidence("all_error")
    fake_client = FakeGeminiClient()

    presentation = PresentationPreferences(target_language="hi")
    response = evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        presentation=presentation,
        client=fake_client,
    )

    assert fake_client.call_count == 0
    assert response.assessment.status == "error"
    assert response.explanation.language == "hi"
    assert response.explanation.is_fallback is True
    assert "त्रुटि" in response.explanation.headline or "उपलब्ध नहीं" in response.explanation.headline
    assert len(response.explanation.observations) == 0


# ==============================================================================
# 12. Fallback Status Propagation
# ==============================================================================


def test_fallback_status_propagation_success_vs_failure():
    """Verifies is_fallback is False on valid Gemini output and True on failure/fallback."""
    evidence = create_scenario_evidence("stable_conditions")

    # Success case
    client_ok = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(language="en")
    )
    resp_ok = evaluate_and_explain_agricultural_assessment(
        evidence=evidence, client=client_ok
    )
    assert resp_ok.explanation.is_fallback is False

    # Gemini failure case
    client_err = FakeGeminiClient(raise_error=TimeoutError("Request timed out"))
    resp_err = evaluate_and_explain_agricultural_assessment(
        evidence=evidence, client=client_err
    )
    assert resp_err.explanation.is_fallback is True
    assert resp_err.assessment.status == "success"  # Assessment status unchanged


# ==============================================================================
# 13. Coordinate-Based Pipeline Orchestration
# ==============================================================================


def test_fetch_agricultural_assessment_explanation_orchestration():
    """Verifies fetch_agricultural_assessment_explanation orchestrates evidence fetch and explanation."""
    evidence = create_scenario_evidence("stable_conditions")
    fake_client = FakeGeminiClient(
        response_text=_make_valid_gemini_response_json(
            language="en",
            headline="Stable crop conditions observed across the region.",
        )
    )

    with patch(
        "app.assessment.pipeline.fetch_agricultural_environmental_evidence",
        return_value=evidence,
    ) as mock_fetch:
        response = fetch_agricultural_assessment_explanation(
            latitude=30.9010,
            longitude=75.8573,
            reference_date=date(2026, 9, 15),
            radius_m=100.0,
            client=fake_client,
        )

        assert mock_fetch.called
        assert isinstance(response, AgriculturalAssessmentExplanationResponse)
        assert response.assessment.status == "success"
        assert response.explanation.is_fallback is False
        assert fake_client.call_count == 1
