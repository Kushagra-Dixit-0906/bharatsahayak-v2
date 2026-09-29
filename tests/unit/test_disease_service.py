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
"""Unit tests for Phase 5D Isolated Gemini Crop Problem Advisory Service.

Tests strict JSON parsing, Pydantic validation, defense-in-depth safety checks,
provenance verification, and error handling using a deterministic offline FakeGeminiClient.
"""

import json
from typing import Any
from unittest.mock import MagicMock
import pytest

from app.disease.retriever import KnowledgeRetrievalResult
from app.disease.service import (
    AdvisoryParsingError,
    AdvisorySafetyRejectionError,
    AdvisoryValidationError,
    GeminiGenerationError,
    generate_crop_problem_advisory,
)
from app.disease.types import (
    CropProblemAdvisory,
    KnowledgeEntry,
)

# ---------------------------------------------------------------------------
# Test Fake Client & Synthetic Fixtures
# ---------------------------------------------------------------------------


class FakeGeminiClient:
    """Deterministic mock Gemini client for offline unit testing."""

    def __init__(
        self,
        response_text: str | None = None,
        raise_error: Exception | None = None,
    ) -> None:
        self.response_text = response_text
        self.raise_error = raise_error
        self.last_model: str | None = None
        self.last_prompt: str | None = None
        self.last_config: Any | None = None

    def generate_content(
        self,
        model: str,
        contents: str,
        config: Any | None = None,
    ) -> Any:
        self.last_model = model
        self.last_prompt = contents
        self.last_config = config

        if self.raise_error is not None:
            raise self.raise_error

        mock_resp = MagicMock()
        mock_resp.text = self.response_text
        return mock_resp


SAMPLE_ENTRY_RICE = KnowledgeEntry(
    entry_id="TEST_RICE_001",
    crop="Rice",
    plant_part="leaf",
    symptom_keywords=["brown", "spot", "oval"],
    condition_name="Rice Brown Spot",
    scientific_name="Bipolaris oryzae",
    category="fungal",
    description="Oval brown spots on leaf blades with yellow halos.",
    safe_cultural_practices=["Maintain balanced soil moisture", "Field sanitation"],
    clarifying_observations=["Check if lesions have grey centers"],
    source_id="SRC_TEST_SYNTHETIC_001",
)

SAMPLE_RETRIEVAL_RESULT = KnowledgeRetrievalResult(
    entry=SAMPLE_ENTRY_RICE,
    retrieval_score=15.0,
    matched_terms=["rice", "leaf", "brown", "spot"],
    matched_fields=["crop", "plant_part", "symptom_keywords"],
)


@pytest.fixture
def valid_advisory_payload() -> dict[str, Any]:
    """Returns a valid, compliant CropProblemAdvisory dictionary."""
    return {
        "status": "success",
        "crop_identified": "Rice",
        "reported_symptoms": ["brown oval spots on leaves", "yellowing around lesions"],
        "possible_conditions": [
            {
                "condition_name": "Rice Brown Spot",
                "scientific_name": "Bipolaris oryzae",
                "category": "fungal",
                "symptom_match": "strong_match",
                "reasoning": "Reported brown oval spots closely align with reference descriptions of Bipolaris oryzae.",
            }
        ],
        "safe_cultural_actions": [
            {
                "action_type": "sanitation",
                "description": "Remove heavily infected plant debris from bunds and field edges.",
            },
            {
                "action_type": "water_management",
                "description": "Ensure balanced field irrigation to avoid excessive moisture stress.",
            },
        ],
        "environmental_context_summary": None,
        "uncertainty_reasons": [
            "Microscopic or visual examination of conidia required for definitive confirmation."
        ],
        "clarifying_questions": [
            "Do the spots have distinct grey centers?",
            "Are the symptoms concentrated on older or younger leaves?",
        ],
        "expert_referral_urgency": "advisory",
        "expert_referral_recommendation": "Consult local Krishi Vigyan Kendra (KVK) if symptoms spread rapidly across the field.",
        "knowledge_sources": [
            {
                "source_id": "SRC_TEST_SYNTHETIC_001",
                "document_title": "Field Guide to Rice Diseases",
                "organization": "Synthetic Test Extension Service",
                "relevant_excerpt": "Brown spot causes oval lesions with brown margins on leaf blades.",
            }
        ],
        "is_fallback": False,
    }


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_valid_advisory_generation(valid_advisory_payload):
    """A & H: Valid structured response returns parsed, validated CropProblemAdvisory."""
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    result = generate_crop_problem_advisory(
        farmer_query="My rice crop has brown oval spots on the leaves.",
        retrieved_knowledge=[SAMPLE_ENTRY_RICE],
        client=client,
    )

    assert isinstance(result, CropProblemAdvisory)
    assert result.status == "success"
    assert result.crop_identified == "Rice"
    assert len(result.possible_conditions) == 1
    assert result.possible_conditions[0].condition_name == "Rice Brown Spot"
    assert result.possible_conditions[0].symptom_match == "strong_match"
    assert len(result.safe_cultural_actions) == 2
    assert result.knowledge_sources[0].source_id == "SRC_TEST_SYNTHETIC_001"
    assert result.is_fallback is False


def test_malformed_json_response_raises_parsing_error():
    """B: Malformed or unparseable JSON raises AdvisoryParsingError."""
    client = FakeGeminiClient(response_text="This is not JSON at all.")

    with pytest.raises(AdvisoryParsingError, match="Malformed JSON"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_empty_response_raises_parsing_error():
    """Empty model response raises AdvisoryParsingError."""
    client = FakeGeminiClient(response_text="   ")

    with pytest.raises(AdvisoryParsingError, match="empty or whitespace"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_missing_required_field_raises_validation_error(valid_advisory_payload):
    """C: Missing required field (e.g. crop_identified) raises AdvisoryValidationError."""
    del valid_advisory_payload["crop_identified"]
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisoryValidationError, match="Schema validation failed"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_extra_unsupported_field_raises_validation_error(valid_advisory_payload):
    """D: Extra unexpected field raises AdvisoryValidationError (extra='forbid')."""
    valid_advisory_payload["unauthorized_field"] = "some value"
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisoryValidationError, match="Schema validation failed"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_invalid_enum_value_raises_validation_error(valid_advisory_payload):
    """E: Invalid enum literal (e.g. invalid status or match level) raises AdvisoryValidationError."""
    valid_advisory_payload["status"] = "diagnosed_confirmed"  # Invalid status
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisoryValidationError, match="Schema validation failed"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_chemical_dosage_prescription_rejected(valid_advisory_payload):
    """F: Chemical spray dosage in reasoning or actions is rejected by safety validation."""
    valid_advisory_payload["safe_cultural_actions"].append(
        {
            "action_type": "sanitation",
            "description": "Spray Mancozeb at 2.5 g/L across all foliage.",
        }
    )
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Banned quantitative chemical dosage"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_chemical_name_prescription_rejected(valid_advisory_payload):
    """F: Chemical active ingredient prescription is rejected by safety validation."""
    valid_advisory_payload["possible_conditions"][0]["reasoning"] = (
        "Apply chlorpyrifos to eliminate larvae."
    )
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Banned chemical prescription"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_hallucinated_source_id_rejected(valid_advisory_payload):
    """G: Model citing a source_id not present in supplied retrieval context is rejected."""
    valid_advisory_payload["knowledge_sources"][0]["source_id"] = "FABRICATED_ICAR_SOURCE_999"
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Hallucinated or unregistered source_id"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_empty_retrieval_context_with_no_sources_succeeds(valid_advisory_payload):
    """I: Empty retrieval context with no cited sources succeeds cleanly."""
    valid_advisory_payload["status"] = "insufficient_evidence"
    valid_advisory_payload["possible_conditions"] = []
    valid_advisory_payload["knowledge_sources"] = []
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    result = generate_crop_problem_advisory(
        farmer_query="My crop has strange spots.",
        retrieved_knowledge=[],
        client=client,
    )
    assert result.status == "insufficient_evidence"
    assert len(result.possible_conditions) == 0
    assert len(result.knowledge_sources) == 0


def test_empty_retrieval_context_with_hallucinated_sources_rejected(valid_advisory_payload):
    """I: Empty retrieval context rejects any cited sources if model invents them."""
    # Supplied knowledge is empty, but model output includes knowledge_sources
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Hallucinated or unregistered source_id cited"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[],
            client=client,
        )


def test_invented_quantitative_environmental_data_rejected(valid_advisory_payload):
    """K: Invented quantitative environmental measurements when no env context was supplied are rejected."""
    valid_advisory_payload["environmental_context_summary"] = (
        "Satellite telemetry indicates NDVI = 0.35 and rainfall = 45mm."
    )
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Invented quantitative environmental measurements"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            environmental_context=None,
            client=client,
        )


def test_numerical_confidence_claim_rejected(valid_advisory_payload):
    """Q: Model attempting to output numerical confidence percentages is rejected."""
    valid_advisory_payload["possible_conditions"][0]["reasoning"] = (
        "We have 95% confidence that this is brown spot."
    )
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Banned numerical confidence"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_absolute_diagnosis_claim_rejected(valid_advisory_payload):
    """R: Absolute diagnosis claim is rejected by safety validation."""
    valid_advisory_payload["possible_conditions"][0]["reasoning"] = (
        "This is a confirmed diagnosis of brown spot."
    )
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    with pytest.raises(AdvisorySafetyRejectionError, match="Banned absolute diagnosis"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_client_api_exception_raises_gemini_generation_error():
    """S: Client raising network or API error raises GeminiGenerationError."""
    client = FakeGeminiClient(raise_error=RuntimeError("Google GenAI API connection failed"))

    with pytest.raises(GeminiGenerationError, match="Gemini client invocation failed"):
        generate_crop_problem_advisory(
            farmer_query="Rice spots",
            retrieved_knowledge=[SAMPLE_ENTRY_RICE],
            client=client,
        )


def test_hindi_language_prompt_passed_to_client(valid_advisory_payload):
    """O: Passing language='hi' builds Hindi prompt and invokes client."""
    client = FakeGeminiClient(response_text=json.dumps(valid_advisory_payload))

    generate_crop_problem_advisory(
        farmer_query="धान के पत्तों पर भूरे दाग",
        retrieved_knowledge=[SAMPLE_ENTRY_RICE],
        language="hi",
        client=client,
    )

    assert client.last_prompt is not None
    assert "Target Language: hi" in client.last_prompt
    assert "Hindi (हिंदी)" in client.last_prompt
