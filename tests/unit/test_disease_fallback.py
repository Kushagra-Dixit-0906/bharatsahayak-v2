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
"""Unit tests for Phase 5D Deterministic Safe Fallback Generator."""

import pytest

from app.assessment.gemini_types import assessment_to_gemini_context
from app.assessment.reasoning import interpret_agricultural_evidence
from app.disease.corpus import AgriculturalKnowledgeCorpus
from app.disease.fallback import generate_deterministic_crop_advisory
from app.disease.retriever import KnowledgeRetrievalResult
from app.disease.types import (
    CropProblemAdvisory,
    KnowledgeEntry,
    KnowledgeSourceProvenance,
)
from tests.fixtures.assessment_fixtures import create_scenario_evidence

# ---------------------------------------------------------------------------
# Synthetic Test Fixtures
# ---------------------------------------------------------------------------

SYNTHETIC_SOURCE = KnowledgeSourceProvenance(
    source_id="SRC_TEST_SYNTHETIC_001",
    organization="Synthetic Test Extension Service",
    document_title="Rice Disease Field Guide",
    version_or_year="2026",
    source_url="https://example.org/test-field-guide",
    license_or_usage_terms="Test Use Only",
    retrieval_date="2026-09-28",
    crops_covered=["Rice"],
    disease_topics=["Brown Spot", "Blast"],
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

ENTRY_RICE_BLAST = KnowledgeEntry(
    entry_id="TEST_RICE_002",
    crop="Rice",
    plant_part="leaf",
    symptom_keywords=["spindle", "lesion", "gray"],
    condition_name="Rice Blast",
    scientific_name="Magnaporthe oryzae",
    category="fungal",
    description="Spindle-shaped lesions with grey center.",
    safe_cultural_practices=["Avoid excess nitrogen", "Ensure water drainage"],
    clarifying_observations=["Check leaf neck and collar"],
    source_id="SRC_TEST_SYNTHETIC_001",
)

CORPUS = AgriculturalKnowledgeCorpus(
    sources={"SRC_TEST_SYNTHETIC_001": SYNTHETIC_SOURCE},
    entries=[ENTRY_RICE_BROWN_SPOT, ENTRY_RICE_BLAST],
)


def test_fallback_empty_retrieval_insufficient_evidence():
    """A: Empty retrieval context produces insufficient_evidence with no forced conditions."""
    advisory = generate_deterministic_crop_advisory(
        farmer_query="My crop has strange marks.",
        retrieved_results=[],
        corpus=CORPUS,
    )

    assert isinstance(advisory, CropProblemAdvisory)
    assert advisory.status == "insufficient_evidence"
    assert advisory.possible_conditions == []
    assert advisory.safe_cultural_actions == []
    assert advisory.knowledge_sources == []
    assert advisory.is_fallback is True
    assert len(advisory.clarifying_questions) > 0
    assert advisory.expert_referral_urgency == "advisory"


def test_fallback_weak_match():
    """B: Weak match produces partial status without forcing strong diagnosis."""
    weak_result = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=3.0,
        matched_terms=["spot"],
        matched_fields=["symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="I see a spot.",
        retrieved_results=[weak_result],
        corpus=CORPUS,
    )

    assert advisory.status == "partial"
    assert len(advisory.possible_conditions) == 1
    assert advisory.possible_conditions[0].symptom_match in ("weak_match", "possible_match")
    assert advisory.is_fallback is True


def test_fallback_strong_deterministic_evidence():
    """C: Strong deterministic overlap produces candidate condition (not confirmed diagnosis)."""
    strong_result = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=20.0,
        matched_terms=["rice", "leaf", "brown", "spot", "oval"],
        matched_fields=["crop", "plant_part", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="My rice leaves have brown oval spots.",
        retrieved_results=[strong_result],
        corpus=CORPUS,
    )

    assert advisory.status == "success"
    assert advisory.crop_identified == "Rice"
    assert len(advisory.possible_conditions) == 1
    cond = advisory.possible_conditions[0]
    assert cond.condition_name == "Rice Brown Spot"
    assert cond.symptom_match == "strong_match"
    assert "differential hypothesis" in cond.reasoning
    assert "ground verification is required" in cond.reasoning
    assert advisory.is_fallback is True


def test_fallback_multiple_candidate_entries():
    """D: Multiple retrieved candidates are preserved deterministically."""
    res1 = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "leaf", "spot"],
        matched_fields=["crop", "plant_part", "symptom_keywords"],
    )
    res2 = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BLAST,
        retrieval_score=12.0,
        matched_terms=["rice", "leaf"],
        matched_fields=["crop", "plant_part"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice leaf problems with spots and lesions.",
        retrieved_results=[res1, res2],
        corpus=CORPUS,
    )

    assert len(advisory.possible_conditions) == 2
    assert advisory.possible_conditions[0].condition_name == "Rice Brown Spot"
    assert advisory.possible_conditions[1].condition_name == "Rice Blast"


def test_fallback_source_provenance_preserved():
    """E: Fallback citations resolve to entry.source_id and corpus metadata."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "leaf", "brown", "spot"],
        matched_fields=["crop", "plant_part", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice brown spot",
        retrieved_results=[res],
        corpus=CORPUS,
    )

    assert len(advisory.knowledge_sources) == 1
    src = advisory.knowledge_sources[0]
    assert src.source_id == "SRC_TEST_SYNTHETIC_001"
    assert src.document_title == "Rice Disease Field Guide"
    assert src.organization == "Synthetic Test Extension Service"


def test_fallback_safe_cultural_practices_copied_strictly():
    """F: Safe cultural practices are derived strictly from entry.safe_cultural_practices."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice brown spot",
        retrieved_results=[res],
        corpus=CORPUS,
    )

    action_texts = [a.description for a in advisory.safe_cultural_actions]
    assert "Maintain balanced soil moisture" in action_texts
    assert "Field sanitation" in action_texts


def test_fallback_no_chemical_or_dosage_text():
    """G: Verifies fallback contains zero chemical spray prescriptions or quantitative dosages."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="What spray should I apply for brown spots?",
        retrieved_results=[res],
        corpus=CORPUS,
    )

    full_text = " ".join(
        [
            advisory.crop_identified,
            *(a.description for a in advisory.safe_cultural_actions),
            *(c.reasoning for c in advisory.possible_conditions),
            *(advisory.uncertainty_reasons),
        ]
    ).lower()

    for banned in ["spray mancozeb", "urea", "chlorpyrifos", "kg/acre", "g/l", "ml/l", "dose", "concentration"]:
        assert banned not in full_text


def test_fallback_no_numerical_confidence_or_certainty():
    """H & I: No numerical confidence or definitive diagnosis claims in fallback."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice brown spot",
        retrieved_results=[res],
        corpus=CORPUS,
    )

    for cond in advisory.possible_conditions:
        assert cond.symptom_match in ("strong_match", "possible_match", "weak_match", "insufficient_information")
        assert "confirmed diagnosis" not in cond.reasoning.lower()
        assert "100%" not in cond.reasoning


def test_fallback_clarifying_observations_copied_to_questions():
    """J: Entry clarifying_observations populate clarifying_questions."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice brown spot",
        retrieved_results=[res],
        corpus=CORPUS,
    )

    assert "Check if lesions have grey centers" in advisory.clarifying_questions


def test_fallback_environmental_context_none():
    """K: When environmental context is None, summary is None."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice brown spot",
        retrieved_results=[res],
        corpus=CORPUS,
        environmental_context=None,
    )

    assert advisory.environmental_context_summary is None


def test_fallback_environmental_context_provided():
    """L: When environmental context is provided, it is summarized without diagnosing disease."""
    evidence = create_scenario_evidence("water_stress_consistent")
    assessment = interpret_agricultural_evidence(evidence)

    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="Rice brown spot",
        retrieved_results=[res],
        corpus=CORPUS,
        environmental_context=assessment,
    )

    assert advisory.environmental_context_summary is not None
    assert "moisture_stress_consistent" in advisory.environmental_context_summary
    assert "does not establish disease identity" in advisory.environmental_context_summary


def test_fallback_hindi_localization():
    """M: Hindi language selection localizes reasoning, uncertainty, and questions."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    advisory = generate_deterministic_crop_advisory(
        farmer_query="धान के पत्ते पर भूरे दाग",
        retrieved_results=[res],
        corpus=CORPUS,
        language="hi",
    )

    assert advisory.is_fallback is True
    assert "Rice Brown Spot" in advisory.possible_conditions[0].condition_name
    assert "संभावित स्थिति" in advisory.possible_conditions[0].reasoning
    assert "दृश्य लक्षणों" in advisory.uncertainty_reasons[0]


def test_fallback_deterministic_repeated_execution():
    """N: Repeated execution with identical parameters yields identical outputs."""
    res = KnowledgeRetrievalResult(
        entry=ENTRY_RICE_BROWN_SPOT,
        retrieval_score=15.0,
        matched_terms=["rice", "brown", "spot"],
        matched_fields=["crop", "symptom_keywords"],
    )

    adv1 = generate_deterministic_crop_advisory("Rice leaf spot", [res], corpus=CORPUS)
    adv2 = generate_deterministic_crop_advisory("Rice leaf spot", [res], corpus=CORPUS)

    assert adv1.model_dump() == adv2.model_dump()
