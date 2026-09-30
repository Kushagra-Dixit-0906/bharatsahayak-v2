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
"""Unit tests for the get_environmental_assessment MCP tool."""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from app.assessment.gemini_types import (
    AgriculturalAssessmentExplanationResponse,
    FarmerAgriculturalResponse,
    GeminiAssessmentContext,
    OverallEnvironmentalCondition,
    PresentationPreferences,
    RecommendedNextStep,
    VerifiedFarmerContext,
    assessment_to_gemini_context,
)
from app.assessment.reasoning import interpret_agricultural_evidence
from app.mcp_server import (
    _format_environmental_assessment_text,
    get_environmental_assessment,
)
from tests.fixtures.assessment_fixtures import create_scenario_evidence


def _mock_explanation_response(language: str = "en") -> AgriculturalAssessmentExplanationResponse:
    evidence = create_scenario_evidence("stable_conditions")
    assessment = interpret_agricultural_evidence(evidence)
    if language == "hi":
        farmer_resp = FarmerAgriculturalResponse(
            language="hi",
            headline="सामान्य पर्यावरणीय स्थिति",
            summary="आपके क्षेत्र में वनस्पति स्वास्थ्य और नमी का स्तर सामान्य है।",
            observations=["एनडीवीआई सामान्य स्तर (0.65) पर है।", "मिट्टी की नमी पर्याप्त है।"],
            interpretation="हालिया वर्षा और तापमान धान की फसल के विकास के लिए अनुकूल हैं।",
            recommended_next_steps=[
                RecommendedNextStep(
                    action_type="ongoing_monitoring",
                    description="नियमित रूप से फसल की स्थिति का निरीक्षण करते रहें।",
                    urgency="routine",
                )
            ],
            limitations=["डेटा 100 मीटर के दायरे पर आधारित है।"],
            is_fallback=False,
        )
    else:
        farmer_resp = FarmerAgriculturalResponse(
            language="en",
            headline="Normal Environmental Conditions",
            summary="Vegetation vigor and moisture levels across your farm parcel are within expected seasonal ranges.",
            observations=["NDVI is at normal healthy baseline (0.65).", "Soil moisture is adequate."],
            interpretation="Recent precipitation and temperatures support healthy crop development.",
            recommended_next_steps=[
                RecommendedNextStep(
                    action_type="ongoing_monitoring",
                    description="Continue routine field monitoring and standard irrigation schedules.",
                    urgency="routine",
                )
            ],
            limitations=["Observations represent an approximate 100-meter circular buffer."],
            is_fallback=False,
        )
    farmer_context = VerifiedFarmerContext(preferred_language=language)
    presentation = PresentationPreferences(target_language=language)
    context = assessment_to_gemini_context(
        assessment=assessment,
        farmer_context=farmer_context,
        presentation=presentation,
    )
    return AgriculturalAssessmentExplanationResponse(
        assessment=assessment,
        explanation=farmer_resp,
        context_used=context,
    )


def test_get_environmental_assessment_invalid_coordinates() -> None:
    """Verifies that invalid latitude/longitude arguments return clear error messages."""
    res_lat = get_environmental_assessment(latitude=120.0, longitude=81.5)
    assert "Error: Invalid latitude coordinate" in res_lat

    res_lon = get_environmental_assessment(latitude=26.7, longitude=250.0)
    assert "Error: Invalid longitude coordinate" in res_lon


def test_get_environmental_assessment_context_propagation_english() -> None:
    """Verifies that coordinates, crop, state, and district are propagated correctly to V2."""
    mock_resp = _mock_explanation_response(language="en")
    with patch(
        "app.mcp_server.fetch_agricultural_assessment_explanation",
        return_value=mock_resp,
    ) as mock_fetch:
        result = get_environmental_assessment(
            latitude=26.784146,
            longitude=81.544683,
            crop="Rice",
            state="Uttar Pradesh",
            district="Barabanki",
            language="en",
        )

        mock_fetch.assert_called_once()
        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["latitude"] == pytest.approx(26.784146)
        assert kwargs["longitude"] == pytest.approx(81.544683)
        assert kwargs["farmer_context"].crop == "rice"
        assert kwargs["presentation"].target_language == "en"

        assert "Normal Environmental Conditions" in result
        assert "Field Observations:" in result
        assert "Recommended Actions:" in result


def test_get_environmental_assessment_context_propagation_hindi() -> None:
    """Verifies that Hindi presentation preferences and translations are preserved."""
    mock_resp = _mock_explanation_response(language="hi")
    with patch(
        "app.mcp_server.fetch_agricultural_assessment_explanation",
        return_value=mock_resp,
    ) as mock_fetch:
        result = get_environmental_assessment(
            latitude=26.784146,
            longitude=81.544683,
            crop="धान",
            state="उत्तर प्रदेश",
            language="hi",
        )

        mock_fetch.assert_called_once()
        kwargs = mock_fetch.call_args.kwargs
        assert kwargs["presentation"].target_language == "hi"

        assert "सामान्य पर्यावरणीय स्थिति" in result
        assert "खेत की स्थिति:" in result
        assert "सलाह और अगले कदम:" in result
