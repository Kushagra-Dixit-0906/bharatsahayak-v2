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
"""Unit tests for Phase 5D Deterministic Knowledge Retrieval Provider.

Tests deterministic retrieval, alias normalization (English/Hindi/Devanagari),
ranking, tie-breaking, empty corpus safety, and absence of numerical disease confidence.

NOTE: All test fixtures in this module are SYNTHETIC TEST FIXTURES used solely
to verify matching logic mechanics. They do not represent authoritative agricultural
claims or real-world verified documents.
"""

import pytest

from app.disease.corpus import (
    DEFAULT_CORPUS,
    AgriculturalKnowledgeCorpus,
    get_empty_corpus,
)
from app.disease.retriever import (
    KnowledgeRetrievalResult,
    retrieve_knowledge,
    retrieve_knowledge_entries,
)
from app.disease.types import (
    KnowledgeEntry,
    KnowledgeSourceProvenance,
)

# ---------------------------------------------------------------------------
# Synthetic Test Fixtures (FOR UNIT TESTING ONLY)
# ---------------------------------------------------------------------------

SYNTHETIC_TEST_SOURCE = KnowledgeSourceProvenance(
    source_id="SRC_TEST_SYNTHETIC_001",
    organization="Synthetic Test Extension Service",
    document_title="Synthetic Test Field Guide for Automated Unit Testing",
    version_or_year="2026",
    source_url="https://example.org/test-field-guide",
    license_or_usage_terms="Test Use Only - Synthetic Fixture",
    retrieval_date="2026-09-28",
    crops_covered=["Rice", "Wheat", "Tomato"],
    disease_topics=["Brown Spot", "Blast", "Leaf Rust", "Early Blight"],
    attribution_requirement="Synthetic Test Fixture",
    redistribution_status="bundled_permitted",
)

TEST_ENTRY_RICE_BROWN_SPOT = KnowledgeEntry(
    entry_id="TEST_RICE_001",
    crop="Rice",
    plant_part="leaf",
    symptom_keywords=["brown", "spot", "oval"],
    condition_name="Rice Brown Spot",
    scientific_name="Bipolaris oryzae",
    category="fungal",
    description="Fungal spots on leaves with oval shape and brown margins.",
    safe_cultural_practices=["Maintain balanced soil moisture", "Field sanitation"],
    clarifying_observations=["Check if spots have gray centers"],
    source_id="SRC_TEST_SYNTHETIC_001",
)

TEST_ENTRY_RICE_BLAST = KnowledgeEntry(
    entry_id="TEST_RICE_002",
    crop="Rice",
    plant_part="leaf",
    symptom_keywords=["spindle", "lesion", "gray", "spot"],
    condition_name="Rice Blast",
    scientific_name="Magnaporthe oryzae",
    category="fungal",
    description="Spindle shaped diamond lesions with gray center on rice foliage.",
    safe_cultural_practices=["Avoid excessive nitrogen", "Ensure water drainage"],
    clarifying_observations=["Observe leaf collars and node discoloration"],
    source_id="SRC_TEST_SYNTHETIC_001",
)

TEST_ENTRY_RICE_SHEATH_BLIGHT = KnowledgeEntry(
    entry_id="TEST_RICE_003",
    crop="Rice",
    plant_part="sheath",
    symptom_keywords=["blight", "irregular", "spot", "water-soaked"],
    condition_name="Sheath Blight",
    scientific_name="Rhizoctonia solani",
    category="fungal",
    description="Water-soaked irregular spots on leaf sheath near waterline.",
    safe_cultural_practices=["Proper plant spacing", "Clean bunds"],
    clarifying_observations=["Check lower leaf sheath near water level"],
    source_id="SRC_TEST_SYNTHETIC_001",
)

TEST_ENTRY_WHEAT_LEAF_RUST = KnowledgeEntry(
    entry_id="TEST_WHEAT_001",
    crop="Wheat",
    plant_part="leaf",
    symptom_keywords=["rust", "orange", "brown", "pustule"],
    condition_name="Wheat Brown Rust",
    scientific_name="Puccinia triticina",
    category="fungal",
    description="Orange brown pustules scattered randomly on wheat leaves.",
    safe_cultural_practices=["Scout fields regularly", "Use clean seed"],
    clarifying_observations=["Check if powder rubs off onto fingertips"],
    source_id="SRC_TEST_SYNTHETIC_001",
)

TEST_ENTRY_TOMATO_EARLY_BLIGHT = KnowledgeEntry(
    entry_id="TEST_TOMATO_001",
    crop="Tomato",
    plant_part="leaf",
    symptom_keywords=["brown", "spot", "concentric", "yellow", "ring"],
    condition_name="Tomato Early Blight",
    scientific_name="Alternaria solani",
    category="fungal",
    description="Dark brown concentric rings on lower tomato leaves with yellow halos.",
    safe_cultural_practices=["Remove lower infected foliage", "Mulching"],
    clarifying_observations=["Examine lower mature leaves first"],
    source_id="SRC_TEST_SYNTHETIC_001",
)


@pytest.fixture
def test_synthetic_corpus() -> AgriculturalKnowledgeCorpus:
    """Fixture returning a multi-crop synthetic knowledge corpus for testing."""
    return AgriculturalKnowledgeCorpus(
        sources={"SRC_TEST_SYNTHETIC_001": SYNTHETIC_TEST_SOURCE},
        entries=[
            TEST_ENTRY_RICE_BROWN_SPOT,
            TEST_ENTRY_RICE_BLAST,
            TEST_ENTRY_RICE_SHEATH_BLIGHT,
            TEST_ENTRY_WHEAT_LEAF_RUST,
            TEST_ENTRY_TOMATO_EARLY_BLIGHT,
        ],
        corpus_version="test-1.0",
    )


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_production_default_corpus_batch1_properties():
    """Confirms production DEFAULT_CORPUS contains verified Batch 1 & 2 records and empty corpus helper works."""
    empty_corpus = get_empty_corpus()
    assert len(empty_corpus.entries) == 0
    assert len(empty_corpus.sources) == 0
    assert len(DEFAULT_CORPUS.entries) == 52
    assert len(DEFAULT_CORPUS.sources) == 10
    assert DEFAULT_CORPUS.validate_provenance_integrity() == []




def test_retrieval_on_empty_corpus_returns_empty_list():
    """A: Querying against an empty corpus safely returns an empty list."""
    empty_corpus = get_empty_corpus()
    results = retrieve_knowledge("rice leaves have brown spots", empty_corpus)
    assert results == []

    entries = retrieve_knowledge_entries("rice leaves have brown spots", empty_corpus)
    assert entries == []


def test_exact_crop_match(test_synthetic_corpus):
    """B: Query with explicit crop retrieves matching crop records."""
    results = retrieve_knowledge("rice brown spot on leaf", test_synthetic_corpus)
    assert len(results) >= 1
    assert results[0].entry.entry_id == "TEST_RICE_001"
    assert results[0].entry.crop == "Rice"
    assert "crop" in results[0].matched_fields


def test_crop_aliases_english_and_hindi(test_synthetic_corpus):
    """C: Test crop aliases ('paddy', 'dhan', 'धान', 'gehun', 'गेहूं')."""
    # Paddy alias
    res_paddy = retrieve_knowledge("paddy leaf has brown spot", test_synthetic_corpus)
    assert len(res_paddy) >= 1
    assert res_paddy[0].entry.crop == "Rice"

    # Dhan alias (transliterated)
    res_dhan = retrieve_knowledge("dhan me brown spot", test_synthetic_corpus)
    assert len(res_dhan) >= 1
    assert res_dhan[0].entry.crop == "Rice"

    # Dhan in Devanagari
    res_dev = retrieve_knowledge("धान के पत्ते पर brown spot", test_synthetic_corpus)
    assert len(res_dev) >= 1
    assert res_dev[0].entry.crop == "Rice"

    # Wheat aliases
    res_gehun = retrieve_knowledge("gehun ke patte par rust", test_synthetic_corpus)
    assert len(res_gehun) >= 1
    assert res_gehun[0].entry.crop == "Wheat"

    res_wheat_dev = retrieve_knowledge("गेहूं के पत्ते पर rust", test_synthetic_corpus)
    assert len(res_wheat_dev) >= 1
    assert res_wheat_dev[0].entry.crop == "Wheat"


def test_plant_part_aliases(test_synthetic_corpus):
    """D: Plant part aliases ('leaves', 'patta', 'patte', 'पत्ते', 'sheath')."""
    # Plural 'leaves'
    res_leaves = retrieve_knowledge("rice leaves oval spots", test_synthetic_corpus)
    assert any(r.entry.plant_part == "leaf" for r in res_leaves)
    assert "plant_part" in res_leaves[0].matched_fields

    # Hindi 'patte'
    res_patte = retrieve_knowledge("rice patte brown spot", test_synthetic_corpus)
    assert "plant_part" in res_patte[0].matched_fields

    # Devanagari 'पत्ते'
    res_dev_part = retrieve_knowledge("rice पत्ते brown spot", test_synthetic_corpus)
    assert "plant_part" in res_dev_part[0].matched_fields

    # Sheath part
    res_sheath = retrieve_knowledge("rice sheath blight", test_synthetic_corpus)
    assert res_sheath[0].entry.entry_id == "TEST_RICE_003"
    assert res_sheath[0].entry.plant_part == "sheath"


def test_symptom_keyword_matches(test_synthetic_corpus):
    """E: Symptom keyword matching for colors, shapes, conditions."""
    results = retrieve_knowledge("rice brown oval spots on leaf", test_synthetic_corpus)
    assert len(results) >= 1
    top = results[0]
    assert top.entry.entry_id == "TEST_RICE_001"
    assert "brown" in top.matched_terms
    assert "spot" in top.matched_terms
    assert "oval" in top.matched_terms


def test_multiple_symptom_matches_rank_higher(test_synthetic_corpus):
    """F: Entry matching multiple symptoms ranks deterministically above partial matches."""
    # TEST_RICE_001 has symptoms: brown, spot, oval
    # Query with all 3 symptoms + leaf + rice
    results = retrieve_knowledge("rice leaf brown oval spots", test_synthetic_corpus)
    assert len(results) >= 2
    # TEST_RICE_001 matches rice (10) + leaf (4) + brown (3) + spot (3) + oval (3) = 23.0 + condition tokens
    # TEST_RICE_002 matches rice (10) + leaf (4) + spot (3) = 17.0
    assert results[0].entry.entry_id == "TEST_RICE_001"
    assert results[0].retrieval_score > results[1].retrieval_score


def test_irrelevant_query_returns_empty(test_synthetic_corpus):
    """G: Irrelevant nonsense query returns zero results."""
    results = retrieve_knowledge("random unrelated xylophone query 12345", test_synthetic_corpus)
    assert results == []


def test_crop_mismatch_exclusion(test_synthetic_corpus):
    """H: When query explicitly specifies 'rice', wheat and tomato entries are excluded."""
    results = retrieve_knowledge("rice rust pustules on leaf", test_synthetic_corpus)
    # Wheat rust has 'rust', 'pustule', 'leaf', but query specifies 'rice'
    for r in results:
        assert r.entry.crop == "Rice"


def test_missing_crop_searches_across_all_crops(test_synthetic_corpus):
    """I: Query without specified crop matches candidate conditions across any crop."""
    # No crop specified: 'brown spot on leaf'
    results = retrieve_knowledge("brown spot on leaf", test_synthetic_corpus)
    assert len(results) >= 2
    crops_found = {r.entry.crop for r in results}
    # Both Rice and Tomato have brown spots on leaves
    assert "Rice" in crops_found or "Tomato" in crops_found


def test_missing_plant_part_does_not_invent_part(test_synthetic_corpus):
    """J: Query without plant part matches without asserting a plant part."""
    results = retrieve_knowledge("rice brown spot", test_synthetic_corpus)
    assert len(results) >= 1
    # Check that 'plant_part' is NOT listed in matched_fields if part was not in query
    assert "plant_part" not in results[0].matched_fields


def test_top_k_parameter_enforced(test_synthetic_corpus):
    """K: Retriever respects top_k limit."""
    results = retrieve_knowledge("leaf spots", test_synthetic_corpus, top_k=2)
    assert len(results) <= 2

    results_single = retrieve_knowledge("leaf spots", test_synthetic_corpus, top_k=1)
    assert len(results_single) == 1


def test_invalid_top_k_raises_error(test_synthetic_corpus):
    """K: top_k < 1 raises ValueError."""
    with pytest.raises(ValueError, match="top_k must be >= 1"):
        retrieve_knowledge("rice leaf", test_synthetic_corpus, top_k=0)


def test_deterministic_ordering(test_synthetic_corpus):
    """L: Repeated execution with same parameters produces identical output and ordering."""
    query = "rice brown spots on leaves"
    res1 = retrieve_knowledge(query, test_synthetic_corpus)
    res2 = retrieve_knowledge(query, test_synthetic_corpus)
    res3 = retrieve_knowledge(query, test_synthetic_corpus)

    assert [r.entry.entry_id for r in res1] == [r.entry.entry_id for r in res2]
    assert [r.entry.entry_id for r in res2] == [r.entry.entry_id for r in res3]
    assert [r.retrieval_score for r in res1] == [r.retrieval_score for r in res2]


def test_tie_breaking_via_entry_id():
    """M: Equal scores resolve deterministically by entry_id in ascending lexicographical order."""
    # Create two synthetic entries with identical attributes except entry_id
    entry_b = KnowledgeEntry(
        entry_id="TEST_B_002",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=["spot"],
        condition_name="Problem B",
        category="unknown",
        description="Identical description test.",
        source_id="SRC_TEST_SYNTHETIC_001",
    )
    entry_a = KnowledgeEntry(
        entry_id="TEST_A_001",
        crop="Rice",
        plant_part="leaf",
        symptom_keywords=["spot"],
        condition_name="Problem A",
        category="unknown",
        description="Identical description test.",
        source_id="SRC_TEST_SYNTHETIC_001",
    )

    corpus = AgriculturalKnowledgeCorpus(
        sources={"SRC_TEST_SYNTHETIC_001": SYNTHETIC_TEST_SOURCE},
        # Pass in reverse order to ensure sorting is not order-dependent
        entries=[entry_b, entry_a],
        corpus_version="test-1.0",
    )

    results = retrieve_knowledge("rice spot", corpus)
    assert len(results) == 2
    assert results[0].retrieval_score == results[1].retrieval_score
    # Lexicographical tie breaker: TEST_A_001 comes before TEST_B_002
    assert results[0].entry.entry_id == "TEST_A_001"
    assert results[1].entry.entry_id == "TEST_B_002"


def test_no_numerical_confidence_semantics(test_synthetic_corpus):
    """N: Verify retrieval_score is an internal ranking score and not a confidence probability."""
    results = retrieve_knowledge("rice leaf brown spots", test_synthetic_corpus)
    for res in results:
        # Score is purely heuristic ranking (e.g. >= 1.0, not bounded [0, 1] probability)
        assert isinstance(res.retrieval_score, float)
        assert not hasattr(res.entry, "confidence")
        assert not hasattr(res.entry, "probability")
        assert not hasattr(res, "confidence")
        assert not hasattr(res, "probability")


def test_hindi_devanagari_query_support(test_synthetic_corpus):
    """P: Hindi Devanagari query matching with explicit aliases."""
    hindi_query = "धान के पत्तों पर भूरे दाग हैं"
    results = retrieve_knowledge(hindi_query, test_synthetic_corpus)
    assert len(results) >= 1
    assert results[0].entry.entry_id == "TEST_RICE_001"
    assert results[0].entry.crop == "Rice"
    assert "crop" in results[0].matched_fields
    assert "plant_part" in results[0].matched_fields
    assert "symptom_keywords" in results[0].matched_fields


def test_punctuation_and_case_normalization(test_synthetic_corpus):
    """Q: Punctuation, capitalization, and whitespace normalization produce identical results."""
    clean_query = "rice leaf brown spots"
    messy_query = "  RICE,  leaf -- BROWN  SPOTS!?!  "

    res_clean = retrieve_knowledge(clean_query, test_synthetic_corpus)
    res_messy = retrieve_knowledge(messy_query, test_synthetic_corpus)

    assert [r.entry.entry_id for r in res_clean] == [r.entry.entry_id for r in res_messy]
    assert [r.retrieval_score for r in res_clean] == [r.retrieval_score for r in res_messy]


def test_retrieve_knowledge_entries_convenience_helper(test_synthetic_corpus):
    """Verifies retrieve_knowledge_entries returns pure list of KnowledgeEntry objects."""
    entries = retrieve_knowledge_entries("tomato concentric rings on leaf", test_synthetic_corpus)
    assert len(entries) >= 1
    assert isinstance(entries[0], KnowledgeEntry)
    assert entries[0].entry_id == "TEST_TOMATO_001"
