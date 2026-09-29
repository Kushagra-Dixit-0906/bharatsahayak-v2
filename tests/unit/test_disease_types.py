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
"""Unit tests for Phase 5D Step 1 domain contracts and knowledge corpus structure."""

import pytest
from pydantic import ValidationError

from app.disease import (
    DEFAULT_CORPUS,
    AgriculturalKnowledgeCorpus,
    CropProblemAdvisory,
    KnowledgeEntry,
    KnowledgeReference,
    KnowledgeSourceProvenance,
    PossibleCondition,
    SafeCulturalAction,
    get_empty_corpus,
)


def test_knowledge_reference_instantiation() -> None:
    """Test A: KnowledgeReference instantiates correctly with valid fields."""
    ref = KnowledgeReference(
        source_id="TEST_SOURCE_01",
        document_title="Sample Agricultural Guide",
        organization="Test Agriculture Department",
        relevant_excerpt="Symptoms include brown oval lesions on leaf blades.",
    )
    assert ref.source_id == "TEST_SOURCE_01"
    assert ref.document_title == "Sample Agricultural Guide"
    assert ref.organization == "Test Agriculture Department"
    assert "brown oval lesions" in ref.relevant_excerpt


def test_possible_condition_instantiation_candidate_semantics() -> None:
    """Test A & F: PossibleCondition represents candidate condition, not confirmed diagnosis."""
    condition = PossibleCondition(
        condition_name="Brown Spot",
        scientific_name="Bipolaris oryzae",
        category="fungal",
        symptom_match="strong_match",
        reasoning="Reported brown oval spots with yellow halos align with literature descriptions.",
    )
    assert condition.condition_name == "Brown Spot"
    assert condition.scientific_name == "Bipolaris oryzae"
    assert condition.category == "fungal"
    assert condition.symptom_match == "strong_match"


def test_possible_condition_optional_scientific_name() -> None:
    """Test F: scientific_name defaults to None when not provided by verified literature."""
    condition = PossibleCondition(
        condition_name="Unspecified Leaf Scorching",
        category="abiotic_nutrient",
        symptom_match="possible_match",
        reasoning="Yellowing margins may indicate potassium imbalance or moisture stress.",
    )
    assert condition.scientific_name is None
    assert condition.category == "abiotic_nutrient"


def test_safe_cultural_action_instantiation() -> None:
    """Test A: SafeCulturalAction instantiates with valid non-chemical action types."""
    action = SafeCulturalAction(
        action_type="sanitation",
        description="Remove and burn or compost deeply any severely infected lower leaves.",
    )
    assert action.action_type == "sanitation"
    assert "Remove and burn" in action.description


def test_crop_problem_advisory_instantiation() -> None:
    """Test A: CropProblemAdvisory instantiates with complete advisory structure."""
    ref = KnowledgeReference(
        source_id="TEST_SRC",
        document_title="Rice Advisory Bulletin",
        organization="Agri Extension",
        relevant_excerpt="Avoid excess nitrogen fertilizer.",
    )
    cond = PossibleCondition(
        condition_name="Rice Blast",
        scientific_name="Magnaporthe oryzae",
        category="fungal",
        symptom_match="possible_match",
        reasoning="Spindle-shaped lesions match blast symptoms.",
    )
    action = SafeCulturalAction(
        action_type="water_management",
        description="Maintain shallow water layer and avoid drying out soil completely.",
    )
    advisory = CropProblemAdvisory(
        status="success",
        crop_identified="Rice",
        reported_symptoms=["spindle-shaped lesions with grey center", "leaf tip drying"],
        possible_conditions=[cond],
        safe_cultural_actions=[action],
        environmental_context_summary="Recent 30-day rainfall indicates persistent high moisture.",
        uncertainty_reasons=["Physical inspection required to verify fungal conidia."],
        clarifying_questions=["Are lesions present on the leaf neck or collar?"],
        expert_referral_recommendation="Consult local KVK if lesions spread to more than 10% of field canopy.",
        knowledge_sources=[ref],
        is_fallback=False,
    )
    assert advisory.status == "success"
    assert advisory.crop_identified == "Rice"
    assert len(advisory.possible_conditions) == 1
    assert len(advisory.safe_cultural_actions) == 1
    assert len(advisory.knowledge_sources) == 1
    assert advisory.is_fallback is False


def test_models_extra_forbid() -> None:
    """Test B: Verify all models reject unauthorized extra fields (extra='forbid')."""
    with pytest.raises(ValidationError):
        KnowledgeReference(
            source_id="S1",
            document_title="Title",
            organization="Org",
            relevant_excerpt="Text",
            extra_field="invalid",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        PossibleCondition(
            condition_name="Spot",
            category="fungal",
            symptom_match="strong_match",
            reasoning="Reason",
            chemical_dosage="2.5g/L",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        SafeCulturalAction(
            action_type="sanitation",
            description="Clean field",
            chemical_spray="Mancozeb",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        CropProblemAdvisory(
            status="success",
            crop_identified="Wheat",
            reported_symptoms=["rust spots"],
            confidence_percentage=95.0,  # type: ignore[call-arg]
        )


def test_models_frozen_immutability() -> None:
    """Test C: Verify all models are frozen and reject in-place attribute mutations."""
    cond = PossibleCondition(
        condition_name="Blast",
        category="fungal",
        symptom_match="possible_match",
        reasoning="Reason",
    )
    with pytest.raises(ValidationError):
        cond.condition_name = "Rust"  # type: ignore[misc]

    ref = KnowledgeReference(
        source_id="S1",
        document_title="Title",
        organization="Org",
        relevant_excerpt="Text",
    )
    with pytest.raises(ValidationError):
        ref.organization = "Mutated Org"  # type: ignore[misc]


def test_advisory_status_values() -> None:
    """Verify AdvisoryStatus accepts only the approved operational status literals."""
    for valid_status in ["success", "partial", "insufficient_evidence", "error"]:
        advisory = CropProblemAdvisory(
            status=valid_status,  # type: ignore[arg-type]
            crop_identified="Rice",
            reported_symptoms=["yellow leaves"],
        )
        assert advisory.status == valid_status

    # Reject deprecated/drifted status values
    for invalid_status in [
        "conditions_identified",
        "possible_conditions_found",
        "insufficient_symptoms",
        "crop_not_covered",
        "completed",
        "failed",
    ]:
        with pytest.raises(ValidationError):
            CropProblemAdvisory(
                status=invalid_status,  # type: ignore[arg-type]
                crop_identified="Rice",
                reported_symptoms=["yellow leaves"],
            )


def test_expert_referral_urgency_values() -> None:
    """Verify ExpertReferralUrgency accepts only 'none', 'advisory', 'urgent_inspection'."""
    for valid_urgency in ["none", "advisory", "urgent_inspection"]:
        advisory = CropProblemAdvisory(
            status="success",
            crop_identified="Rice",
            reported_symptoms=["yellow leaves"],
            expert_referral_urgency=valid_urgency,  # type: ignore[arg-type]
        )
        assert advisory.expert_referral_urgency == valid_urgency

    # Reject unapproved values
    for invalid_urgency in ["routine", "recommended", "urgent", "not_required", "high"]:
        with pytest.raises(ValidationError):
            CropProblemAdvisory(
                status="success",
                crop_identified="Rice",
                reported_symptoms=["yellow leaves"],
                expert_referral_urgency=invalid_urgency,  # type: ignore[arg-type]
            )


def test_pathogen_category_values() -> None:
    """Verify PathogenCategory accepts only approved scientific taxonomy categories."""
    valid_categories = [
        "fungal",
        "bacterial",
        "viral",
        "nematode",
        "pest_damage",
        "abiotic_nutrient",
        "unknown",
    ]
    for cat in valid_categories:
        cond = PossibleCondition(
            condition_name="Test Problem",
            category=cat,  # type: ignore[arg-type]
            symptom_match="possible_match",
            reasoning="Test reasoning.",
        )
        assert cond.category == cat

    for invalid_cat in ["genetic", "toxic", "magic", "other", "severe"]:
        with pytest.raises(ValidationError):
            PossibleCondition(
                condition_name="Test Problem",
                category=invalid_cat,  # type: ignore[arg-type]
                symptom_match="possible_match",
                reasoning="Test reasoning.",
            )


def test_symptom_match_level_values() -> None:
    """Test D: SymptomMatchLevel accepts only authorized qualitative match literals."""
    for valid_level in ["strong_match", "possible_match", "weak_match", "insufficient_information"]:
        cond = PossibleCondition(
            condition_name="Condition",
            category="fungal",
            symptom_match=valid_level,  # type: ignore[arg-type]
            reasoning="Reasoning",
        )
        assert cond.symptom_match == valid_level

    # Reject invalid literals such as statistical confidence or percentages
    for invalid_level in ["high_confidence", "95%", "certain", "confirmed", "high_match"]:
        with pytest.raises(ValidationError):
            PossibleCondition(
                condition_name="Condition",
                category="fungal",
                symptom_match=invalid_level,  # type: ignore[arg-type]
                reasoning="Reasoning",
            )


def test_no_numerical_confidence_field_in_contracts() -> None:
    """Test E: Confirms no numerical confidence or probability fields exist in domain models."""
    for model_cls in [
        CropProblemAdvisory,
        PossibleCondition,
        SafeCulturalAction,
        KnowledgeReference,
        KnowledgeSourceProvenance,
        KnowledgeEntry,
    ]:
        field_names = model_cls.model_fields.keys()
        assert "confidence" not in field_names
        assert "confidence_score" not in field_names
        assert "probability" not in field_names
        assert "accuracy" not in field_names


def test_knowledge_source_provenance() -> None:
    """Test G: KnowledgeSourceProvenance instantiates with complete legal metadata."""
    prov = KnowledgeSourceProvenance(
        source_id="ICAR_SAMPLE_01",
        organization="Indian Council of Agricultural Research",
        document_title="Package of Practices for Rice",
        version_or_year="2023",
        source_url="https://example.org/icar-rice",
        license_or_usage_terms="Verified Open Research License",
        retrieval_date="2026-09-28",
        crops_covered=["Rice", "Paddy"],
        disease_topics=["Blast", "Brown Spot"],
        attribution_requirement="ICAR-NRRI Cuttack",
        redistribution_status="bundled_permitted",
    )
    assert prov.source_id == "ICAR_SAMPLE_01"
    assert prov.redistribution_status == "bundled_permitted"
    assert len(prov.crops_covered) == 2


def test_knowledge_entry_linkage_to_provenance() -> None:
    """Test H: KnowledgeEntry cleanly links to KnowledgeSourceProvenance via source_id."""
    prov = KnowledgeSourceProvenance(
        source_id="SRC_TNAU_01",
        organization="Tamil Nadu Agricultural University",
        document_title="Crop Protection Guide",
        version_or_year="2022",
        source_url="https://example.org/tnau-guide",
        license_or_usage_terms="Open Access Educational Use",
        retrieval_date="2026-09-28",
        crops_covered=["Tomato"],
        disease_topics=["Early Blight"],
        attribution_requirement="TNAU Agronomy Dept",
        redistribution_status="reference_only",
    )
    entry = KnowledgeEntry(
        entry_id="TOMATO_EARLY_BLIGHT_01",
        crop="Tomato",
        plant_part="leaf",
        symptom_keywords=["concentric rings", "dark brown spots", "lower leaves"],
        condition_name="Early Blight",
        scientific_name="Alternaria solani",
        category="fungal",
        description="Dark brown circular spots with concentric target-board rings on older foliage.",
        safe_cultural_practices=[
            "Remove and destroy lower infected leaves.",
            "Stake plants to improve canopy airflow.",
            "Avoid overhead irrigation to keep foliage dry.",
        ],
        clarifying_observations=[
            "Spots typically start on oldest leaves near the soil line.",
        ],
        source_id="SRC_TNAU_01",
    )
    assert entry.source_id == prov.source_id
    assert "concentric rings" in entry.symptom_keywords
    assert len(entry.safe_cultural_practices) == 3


def test_empty_corpus_validity() -> None:
    """Test I: An empty corpus is valid and provides a clean initial state."""
    empty_corpus = get_empty_corpus()
    assert len(empty_corpus.sources) == 0
    assert len(empty_corpus.entries) == 0
    assert empty_corpus.corpus_version == "1.0.0"
    assert empty_corpus.validate_provenance_integrity() == []
    # Production DEFAULT_CORPUS is initialized with verified Batch 1 & 2 entries
    assert DEFAULT_CORPUS.validate_provenance_integrity() == []
    assert len(DEFAULT_CORPUS.entries) == 52
    assert len(DEFAULT_CORPUS.sources) == 10




def test_corpus_provenance_integrity_validation() -> None:
    """Test corpus integrity validator catches orphan entries with unregistered source_id."""
    prov = KnowledgeSourceProvenance(
        source_id="VALID_SRC",
        organization="Test Org",
        document_title="Valid Guide",
        source_url="https://example.org/guide",
        license_or_usage_terms="Verified Open",
        retrieval_date="2026-09-28",
        crops_covered=["Rice"],
        disease_topics=["Blast"],
        attribution_requirement="Test Org",
        redistribution_status="reference_only",
    )
    valid_entry = KnowledgeEntry(
        entry_id="ENTRY_01",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=["spindle"],
        condition_name="Blast",
        category="fungal",
        description="Spindle lesions.",
        safe_cultural_practices=["Sanitation"],
        source_id="VALID_SRC",
    )
    orphan_entry = KnowledgeEntry(
        entry_id="ENTRY_02",
        crop="Wheat",
        plant_part="leaf",
        symptom_keywords=["rust"],
        condition_name="Wheat Rust",
        category="fungal",
        description="Pustules.",
        safe_cultural_practices=["Monitoring"],
        source_id="UNREGISTERED_SRC",
    )

    corpus = AgriculturalKnowledgeCorpus(
        sources={"VALID_SRC": prov},
        entries=[valid_entry, orphan_entry],
    )
    errors = corpus.validate_provenance_integrity()
    assert len(errors) == 1
    assert "UNREGISTERED_SRC" in errors[0]
    assert "ENTRY_02" in errors[0]

    # After adding the missing source, errors resolve
    prov_orphan = KnowledgeSourceProvenance(
        source_id="UNREGISTERED_SRC",
        organization="Wheat Board",
        document_title="Wheat Guide",
        source_url="https://example.org/wheat",
        license_or_usage_terms="Verified Open",
        retrieval_date="2026-09-28",
        crops_covered=["Wheat"],
        disease_topics=["Rust"],
        attribution_requirement="Wheat Board",
        redistribution_status="reference_only",
    )
    valid_corpus = AgriculturalKnowledgeCorpus(
        sources={"VALID_SRC": prov, "UNREGISTERED_SRC": prov_orphan},
        entries=[valid_entry, orphan_entry],
    )
    assert valid_corpus.validate_provenance_integrity() == []
