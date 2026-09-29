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
"""Unit tests for Phase 5D Unified Crop Problem & Disease Advisory Pipeline."""

import json
from typing import Any
from unittest.mock import MagicMock
import pytest

from app.assessment.gemini_types import assessment_to_gemini_context
from app.assessment.reasoning import interpret_agricultural_evidence
from app.disease.corpus import (
    DEFAULT_CORPUS,
    AgriculturalKnowledgeCorpus,
    get_empty_corpus,
)
from app.disease.pipeline import run_crop_problem_pipeline
from app.disease.types import (
    CropProblemAdvisory,
    KnowledgeEntry,
    KnowledgeSourceProvenance,
)
from tests.fixtures.assessment_fixtures import create_scenario_evidence

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


SYNTHETIC_SOURCE = KnowledgeSourceProvenance(
    source_id="SRC_TEST_SYNTHETIC_001",
    organization="Synthetic Test Extension Service",
    document_title="Rice Disease Field Guide",
    version_or_year="2026",
    source_url="https://example.org/test-field-guide",
    license_or_usage_terms="Test Use Only",
    retrieval_date="2026-09-28",
    crops_covered=["Rice"],
    disease_topics=["Brown Spot"],
    attribution_requirement="Synthetic Fixture",
    redistribution_status="bundled_permitted",
)

ENTRY_RICE_BROWN_SPOT = KnowledgeEntry(
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

SYNTHETIC_CORPUS = AgriculturalKnowledgeCorpus(
    sources={"SRC_TEST_SYNTHETIC_001": SYNTHETIC_SOURCE},
    entries=[ENTRY_RICE_BROWN_SPOT],
)


@pytest.fixture
def valid_gemini_advisory_payload() -> dict[str, Any]:
    """Returns a valid, compliant CropProblemAdvisory dictionary."""
    return {
        "status": "success",
        "crop_identified": "Rice",
        "reported_symptoms": ["brown oval spots on leaves"],
        "possible_conditions": [
            {
                "condition_name": "Rice Brown Spot",
                "scientific_name": "Bipolaris oryzae",
                "category": "fungal",
                "symptom_match": "strong_match",
                "reasoning": "Reported symptoms match reference literature.",
            }
        ],
        "safe_cultural_actions": [
            {
                "action_type": "sanitation",
                "description": "Field sanitation and debris removal.",
            }
        ],
        "environmental_context_summary": None,
        "uncertainty_reasons": ["Microscopic test needed for definitive confirmation."],
        "clarifying_questions": ["Do spots have grey centers?"],
        "expert_referral_urgency": "none",
        "expert_referral_recommendation": None,
        "knowledge_sources": [
            {
                "source_id": "SRC_TEST_SYNTHETIC_001",
                "document_title": "Rice Disease Field Guide",
                "organization": "Synthetic Test Extension Service",
                "relevant_excerpt": "Brown spot causes oval lesions on leaves.",
            }
        ],
        "is_fallback": False,
    }


# ---------------------------------------------------------------------------
# Pipeline Test Cases
# ---------------------------------------------------------------------------


def test_pipeline_gemini_succeeds(valid_gemini_advisory_payload):
    """A: When Gemini succeeds, return validated advisory with is_fallback=False."""
    client = FakeGeminiClient(response_text=json.dumps(valid_gemini_advisory_payload))

    advisory = run_crop_problem_pipeline(
        farmer_query="My rice leaves have brown spots.",
        corpus=SYNTHETIC_CORPUS,
        client=client,
    )

    assert isinstance(advisory, CropProblemAdvisory)
    assert advisory.status == "success"
    assert advisory.crop_identified == "Rice"
    assert advisory.is_fallback is False
    assert advisory.possible_conditions[0].condition_name == "Rice Brown Spot"


def test_pipeline_gemini_unavailable_triggers_fallback():
    """B: When Gemini raises network/client error, pipeline triggers deterministic fallback."""
    client = FakeGeminiClient(raise_error=RuntimeError("Google GenAI connection timeout"))

    advisory = run_crop_problem_pipeline(
        farmer_query="My rice leaves have brown oval spots.",
        corpus=SYNTHETIC_CORPUS,
        client=client,
    )

    assert isinstance(advisory, CropProblemAdvisory)
    assert advisory.is_fallback is True
    assert advisory.crop_identified == "Rice"
    assert advisory.possible_conditions[0].condition_name == "Rice Brown Spot"


def test_pipeline_gemini_malformed_json_triggers_fallback():
    """C: When Gemini returns malformed JSON, pipeline routes to fallback."""
    client = FakeGeminiClient(response_text="Error: Malformed JSON output {{{{")

    advisory = run_crop_problem_pipeline(
        farmer_query="My rice leaves have brown spots.",
        corpus=SYNTHETIC_CORPUS,
        client=client,
    )

    assert isinstance(advisory, CropProblemAdvisory)
    assert advisory.is_fallback is True
    assert advisory.crop_identified == "Rice"


def test_pipeline_gemini_schema_failure_triggers_fallback(valid_gemini_advisory_payload):
    """D: When Gemini output violates Pydantic schema, pipeline routes to fallback."""
    del valid_gemini_advisory_payload["crop_identified"]
    client = FakeGeminiClient(response_text=json.dumps(valid_gemini_advisory_payload))

    advisory = run_crop_problem_pipeline(
        farmer_query="My rice leaves have brown spots.",
        corpus=SYNTHETIC_CORPUS,
        client=client,
    )

    assert isinstance(advisory, CropProblemAdvisory)
    assert advisory.is_fallback is True
    assert advisory.crop_identified == "Rice"


def test_pipeline_gemini_safety_rejection_triggers_fallback(valid_gemini_advisory_payload):
    """E: When Gemini output contains chemical spray prescription, safety rejection triggers fallback."""
    valid_gemini_advisory_payload["safe_cultural_actions"].append(
        {
            "action_type": "sanitation",
            "description": "Spray Mancozeb at 2.5 g/L.",
        }
    )
    client = FakeGeminiClient(response_text=json.dumps(valid_gemini_advisory_payload))

    advisory = run_crop_problem_pipeline(
        farmer_query="My rice leaves have brown spots.",
        corpus=SYNTHETIC_CORPUS,
        client=client,
    )

    assert isinstance(advisory, CropProblemAdvisory)
    assert advisory.is_fallback is True
    # Verify fallback sanitized output contains no Mancozeb
    for action in advisory.safe_cultural_actions:
        assert "mancozeb" not in action.description.lower()
        assert "g/l" not in action.description.lower()


def test_pipeline_empty_retrieval_and_gemini_failure():
    """F: Empty retrieval corpus and Gemini failure safely yields insufficient_evidence fallback."""
    empty_corpus = AgriculturalKnowledgeCorpus(sources={}, entries=[])
    client = FakeGeminiClient(raise_error=RuntimeError("Gemini down"))

    advisory = run_crop_problem_pipeline(
        farmer_query="Unknown leaf disease.",
        corpus=empty_corpus,
        client=client,
    )

    assert advisory.status == "insufficient_evidence"
    assert advisory.possible_conditions == []
    assert advisory.safe_cultural_actions == []
    assert advisory.is_fallback is True


def test_pipeline_environmental_context_passthrough(valid_gemini_advisory_payload):
    """G: Environmental context is ingested and passed through into the prompt."""
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)

    client = FakeGeminiClient(response_text=json.dumps(valid_gemini_advisory_payload))

    advisory = run_crop_problem_pipeline(
        farmer_query="Rice leaves drying",
        corpus=SYNTHETIC_CORPUS,
        environmental_context=assessment,
        client=client,
    )

    assert advisory.is_fallback is False
    assert client.last_prompt is not None
    assert "<environmental_observation_data>" in client.last_prompt
    assert "moisture_stress_consistent" in client.last_prompt


def test_pipeline_environmental_context_absent_works_cleanly(valid_gemini_advisory_payload):
    """H: Environmental context absent still executes advisory pipeline smoothly."""
    client = FakeGeminiClient(response_text=json.dumps(valid_gemini_advisory_payload))

    advisory = run_crop_problem_pipeline(
        farmer_query="Rice leaf spots",
        corpus=SYNTHETIC_CORPUS,
        environmental_context=None,
        client=client,
    )

    assert advisory.is_fallback is False


def test_pipeline_hindi_query_handling():
    """J: Hindi language query routes with language='hi'."""
    client = FakeGeminiClient(raise_error=RuntimeError("Offline fallback"))

    advisory = run_crop_problem_pipeline(
        farmer_query="धान के पत्तों पर भूरे दाग",
        corpus=SYNTHETIC_CORPUS,
        language="hi",
        client=client,
    )

    assert advisory.is_fallback is True
    assert advisory.crop_identified == "Rice"
    assert "संभावित स्थिति" in advisory.possible_conditions[0].reasoning


def test_pipeline_empty_query_raises_error():
    """Validates empty query raises ValueError."""
    with pytest.raises(ValueError, match="farmer_query must not be empty"):
        run_crop_problem_pipeline(
            farmer_query="   ",
            corpus=SYNTHETIC_CORPUS,
        )


def test_pipeline_immutability_of_inputs():
    """M: Verifies pipeline execution does NOT mutate any input structures."""
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)
    gemini_ctx = assessment_to_gemini_context(assessment)

    assessment_dump_before = assessment.model_dump()
    gemini_ctx_dump_before = gemini_ctx.model_dump()
    corpus_dump_before = SYNTHETIC_CORPUS.model_dump()

    client = FakeGeminiClient(raise_error=RuntimeError("Offline fallback"))

    run_crop_problem_pipeline(
        farmer_query="Rice leaf brown spots",
        corpus=SYNTHETIC_CORPUS,
        environmental_context=assessment,
        client=client,
    )

    assert assessment.model_dump() == assessment_dump_before
    assert gemini_ctx.model_dump() == gemini_ctx_dump_before
    assert SYNTHETIC_CORPUS.model_dump() == corpus_dump_before


def test_pipeline_production_default_corpus_properties():
    """N: Confirms production DEFAULT_CORPUS has valid Batch 1 & 2 records and get_empty_corpus() works."""
    empty_corpus = get_empty_corpus()
    assert len(empty_corpus.entries) == 0
    assert len(empty_corpus.sources) == 0
    assert len(DEFAULT_CORPUS.entries) == 52
    assert len(DEFAULT_CORPUS.sources) == 10
    assert DEFAULT_CORPUS.validate_provenance_integrity() == []


