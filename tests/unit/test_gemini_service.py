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
"""Unit tests for Phase 5C Isolated Gemini Explanation Service (DEC-024)."""

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from app.assessment.gemini_service import (
    FarmerAgriculturalResponse,
    RecommendedNextStep,
    explain_agricultural_assessment,
    generate_deterministic_fallback_explanation,
)
from app.assessment.gemini_types import (
    ContextPatternSummary,
    GeminiAssessmentContext,
    PresentationPreferences,
    VerifiedFarmerContext,
    assessment_to_gemini_context,
)
from app.assessment.reasoning import interpret_agricultural_evidence
from app.assessment.types import SupportingEvidenceItem
from app.satellite.types import AnalysisRegionMetadata
from tests.fixtures.assessment_fixtures import create_scenario_evidence


class FakeGeminiClient:
    """Mock Gemini client for deterministic offline unit testing."""

    def __init__(self, response_text: str | None = None, raise_error: Exception | None = None) -> None:
        self.response_text = response_text
        self.raise_error = raise_error
        self.last_model: str | None = None
        self.last_prompt: str | None = None
        self.last_config: Any | None = None

    def generate_content(self, model: str, contents: str, config: Any | None = None) -> Any:
        self.last_model = model
        self.last_prompt = contents
        self.last_config = config

        if self.raise_error is not None:
            raise self.raise_error

        mock_resp = MagicMock()
        mock_resp.text = self.response_text
        return mock_resp


@pytest.fixture
def water_stress_context() -> GeminiAssessmentContext:
    """Produces a deterministic water stress GeminiAssessmentContext with structured evidence."""
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)
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
    return assessment_to_gemini_context(
        assessment, farmer_context=farmer_ctx, presentation=presentation
    )


@pytest.fixture
def insufficient_evidence_context() -> GeminiAssessmentContext:
    """Produces a deterministic insufficient evidence GeminiAssessmentContext."""
    evidence = create_scenario_evidence("all_no_data")
    assessment = interpret_agricultural_evidence(evidence)
    return assessment_to_gemini_context(assessment)


@pytest.fixture
def valid_response_dict() -> dict[str, Any]:
    """Produces a valid FarmerAgriculturalResponse dictionary."""
    return {
        "language": "hi",
        "headline": "उपग्रह आंकड़े खेत में नमी की कमी की स्थिति दर्शाते हैं।",
        "summary": "कम वर्षा और सूखी ऊपरी मिट्टी के कारण फसल में नमी का तनाव देखा गया है।",
        "observations": [
            "NDVI में सामान्य से अधिक गिरावट (-0.16) देखी गई है।",
            "पिछले 30 दिनों में केवल 4.2 मिमी वर्षा दर्ज की गई है।",
        ],
        "interpretation": "यह स्थिति मिट्टी की नमी में कमी के कारण उत्पन्न पर्यावरणीय तनाव के अनुरूप है।",
        "recommended_next_steps": [
            {
                "action_type": "soil_moisture_manual_check",
                "description": "खेत में जड़ क्षेत्र की मिट्टी की नमी की प्रत्यक्ष जांच करें।",
                "urgency": "advisory",
            },
            {
                "action_type": "field_visual_inspection",
                "description": "पत्तियों पर धूप के समय मुरझाने के संकेतों की जांच करें।",
                "urgency": "advisory",
            },
        ],
        "limitations": [
            "ERA5-Land डेटा में 5 दिन का प्रकाशन अंतराल हो सकता है।",
        ],
        "is_fallback": False,
    }


# ==============================================================================
# A. Successful Valid Response
# ==============================================================================

def test_successful_valid_gemini_response(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that a valid structured response from Gemini parses and passes all validation layers."""
    client = FakeGeminiClient(response_text=json.dumps(valid_response_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert isinstance(response, FarmerAgriculturalResponse)
    assert response.is_fallback is False
    assert response.language == "hi"
    assert response.headline == valid_response_dict["headline"]
    assert len(response.recommended_next_steps) == 2
    assert response.recommended_next_steps[0].action_type == "soil_moisture_manual_check"
    assert response.recommended_next_steps[0].urgency == "advisory"


# ==============================================================================
# B. Malformed JSON Fallback
# ==============================================================================

def test_malformed_json_triggers_fallback(
    water_stress_context: GeminiAssessmentContext,
) -> None:
    """Verifies that malformed JSON from Gemini triggers deterministic fallback."""
    client = FakeGeminiClient(response_text="INVALID JSON { unclosed: ...")

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert isinstance(response, FarmerAgriculturalResponse)
    assert response.is_fallback is True
    assert response.language == "hi"
    assert "नमी के तनाव" in response.headline or "moisture stress" in response.headline.lower()


# ==============================================================================
# C. Invalid Schema Fallback
# ==============================================================================

def test_invalid_schema_triggers_fallback(
    water_stress_context: GeminiAssessmentContext,
) -> None:
    """Verifies that missing required fields in Gemini JSON triggers deterministic fallback."""
    invalid_dict = {"headline": "Missing summary, interpretation, observations..."}
    client = FakeGeminiClient(response_text=json.dumps(invalid_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert isinstance(response, FarmerAgriculturalResponse)
    assert response.is_fallback is True


# ==============================================================================
# D. API Exception Fallback
# ==============================================================================

def test_api_exception_triggers_fallback(
    water_stress_context: GeminiAssessmentContext,
) -> None:
    """Verifies that network/API exceptions are caught and routed to deterministic fallback."""
    client = FakeGeminiClient(raise_error=RuntimeError("Google GenAI 503 Service Unavailable"))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert isinstance(response, FarmerAgriculturalResponse)
    assert response.is_fallback is True
    assert len(response.observations) > 0


# ==============================================================================
# E. Insufficient Evidence Non-Contradiction
# ==============================================================================

def test_insufficient_evidence_contradiction_rejected(
    insufficient_evidence_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that attempting to claim favorable crop health when evidence is insufficient triggers fallback."""
    contradictory_dict = dict(valid_response_dict)
    contradictory_dict["headline"] = "Excellent crop health observed across parcel!"
    contradictory_dict["summary"] = "The crop is thriving and favorable growth condition is confirmed."
    client = FakeGeminiClient(response_text=json.dumps(contradictory_dict))

    response = explain_agricultural_assessment(insufficient_evidence_context, client=client)

    # Contradictory claim rejected, fallback returned
    assert response.is_fallback is True
    assert "अपर्याप्त" in response.headline or "insufficient" in response.headline.lower()


# ==============================================================================
# F. Invented Confidence Score Rejected
# ==============================================================================

def test_invented_numerical_confidence_rejected(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that responses inventing artificial numerical confidence scores are rejected."""
    hallucinated_dict = dict(valid_response_dict)
    hallucinated_dict["interpretation"] = "Moisture stress diagnosed with 98% confidence score."
    client = FakeGeminiClient(response_text=json.dumps(hallucinated_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert response.is_fallback is True


# ==============================================================================
# G. Next Step Action Type Allowlist
# ==============================================================================

def test_unauthorized_action_type_rejected(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that an unauthorized action_type outside the 4 approved literals is rejected."""
    unauthorized_dict = dict(valid_response_dict)
    unauthorized_dict["recommended_next_steps"] = [
        {
            "action_type": "purchase_chemical_fertilizer",  # Unauthorized literal
            "description": "Buy and apply commercial fertilizer.",
            "urgency": "routine",
        }
    ]
    client = FakeGeminiClient(response_text=json.dumps(unauthorized_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert response.is_fallback is True


# ==============================================================================
# H. Urgency Allowlist
# ==============================================================================

def test_unauthorized_urgency_rejected(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that urgency values other than 'routine' or 'advisory' are rejected."""
    unauthorized_dict = dict(valid_response_dict)
    unauthorized_dict["recommended_next_steps"] = [
        {
            "action_type": "field_visual_inspection",
            "description": "Immediate critical field check.",
            "urgency": "critical_emergency",  # Unauthorized urgency
        }
    ]
    client = FakeGeminiClient(response_text=json.dumps(unauthorized_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert response.is_fallback is True


# ==============================================================================
# I. Prohibited Chemical & Dosage Prescriptions
# ==============================================================================

@pytest.mark.parametrize(
    "prohibited_phrase",
    [
        "Apply 50 kg/acre urea to restore nitrogen balance.",
        "Spray 2.5 litres/ha glyphosate immediately.",
        "Apply 100 kg of DAP fertilizer at root base.",
        "Spray mancozeb dosage for leaf protection.",
        "Apply 5 cm of irrigation water across field.",
        "Fungal blight confirmed by satellite spectral analysis.",
        "Guaranteed 100% crop loss if not treated.",
    ],
)
def test_banned_prescriptive_content_rejected(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
    prohibited_phrase: str,
) -> None:
    """Verifies that chemical prescriptions, dosages, depth math, and absolute disease claims are rejected."""
    banned_dict = dict(valid_response_dict)
    banned_dict["interpretation"] = f"Conditions noted. {prohibited_phrase}"
    client = FakeGeminiClient(response_text=json.dumps(banned_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert response.is_fallback is True


# ==============================================================================
# J. Normal Response Cannot Claim is_fallback=True
# ==============================================================================

def test_gemini_cannot_claim_fallback_flag(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that a normal Gemini response setting is_fallback=True is rejected."""
    tampered_dict = dict(valid_response_dict)
    tampered_dict["is_fallback"] = True  # Model should not assert fallback
    client = FakeGeminiClient(response_text=json.dumps(tampered_dict))

    response = explain_agricultural_assessment(water_stress_context, client=client)

    # Service triggers its own authoritative fallback
    assert response.is_fallback is True


# ==============================================================================
# K. Deterministic Fallback Generator Coverage
# ==============================================================================

@pytest.mark.parametrize(
    "scenario_name",
    [
        "stable_conditions",
        "water_stress_consistent",
        "heat_stress_consistent",
        "combined_environmental_stress",
        "favorable_growth",
        "conflicting_ndvi_rainfall",
        "all_no_data",
    ],
)
def test_deterministic_fallback_for_all_conditions(scenario_name: str) -> None:
    """Verifies that generate_deterministic_fallback_explanation works for all condition scenarios in EN & HI."""
    evidence = create_scenario_evidence(scenario_name)
    assessment = interpret_agricultural_evidence(evidence)

    for lang in ["en", "hi"]:
        context = assessment_to_gemini_context(
            assessment,
            presentation=PresentationPreferences(target_language=lang),  # type: ignore[arg-type]
        )
        fallback = generate_deterministic_fallback_explanation(context)

        assert isinstance(fallback, FarmerAgriculturalResponse)
        assert fallback.is_fallback is True
        assert fallback.language == lang
        assert len(fallback.headline) > 10
        assert len(fallback.summary) > 20
        assert len(fallback.interpretation) > 20
        for step in fallback.recommended_next_steps:
            assert step.action_type in [
                "field_visual_inspection",
                "soil_moisture_manual_check",
                "ongoing_monitoring",
                "missing_information_gathering",
            ]
            assert step.urgency in ["routine", "advisory"]


# ==============================================================================
# L. Context Immutability
# ==============================================================================

def test_service_does_not_mutate_context(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that calling explain_agricultural_assessment does not mutate the context."""
    before_dump = water_stress_context.model_dump()
    client = FakeGeminiClient(response_text=json.dumps(valid_response_dict))

    _ = explain_agricultural_assessment(water_stress_context, client=client)

    after_dump = water_stress_context.model_dump()
    assert before_dump == after_dump


# ==============================================================================
# M. Prompt Builder Invocation
# ==============================================================================

def test_service_invokes_prompt_builder(
    water_stress_context: GeminiAssessmentContext,
    valid_response_dict: dict[str, Any],
) -> None:
    """Verifies that the service builds the prompt via build_gemini_prompt and passes it to the client."""
    client = FakeGeminiClient(response_text=json.dumps(valid_response_dict))

    _ = explain_agricultural_assessment(water_stress_context, client=client)

    assert client.last_prompt is not None
    assert "=== SYSTEM ROLE & EPISTEMIC BOUNDARIES ===" in client.last_prompt
    assert "<assessment_data>" in client.last_prompt
    assert "overall_condition: moisture_stress_consistent" in client.last_prompt


# ==============================================================================
# N. Secret / Credential Leakage Protection
# ==============================================================================

def test_secret_safety_in_error_and_fallback(
    water_stress_context: GeminiAssessmentContext,
) -> None:
    """Verifies that exceptions containing fake API keys do not leak secrets into the response."""
    sensitive_error = RuntimeError("Authentication failed for key AIzaSyFakeSecretKey123456789")
    client = FakeGeminiClient(raise_error=sensitive_error)

    response = explain_agricultural_assessment(water_stress_context, client=client)

    assert "AIzaSyFakeSecretKey123456789" not in response.headline
    assert "AIzaSyFakeSecretKey123456789" not in response.summary
    assert "AIzaSyFakeSecretKey123456789" not in response.interpretation


# ==============================================================================
# O. Type Safety
# ==============================================================================

def test_service_type_safety() -> None:
    """Verifies that passing non-GeminiAssessmentContext raises TypeError."""
    with pytest.raises(TypeError, match="context must be a GeminiAssessmentContext instance"):
        explain_agricultural_assessment(None)  # type: ignore[arg-type]
