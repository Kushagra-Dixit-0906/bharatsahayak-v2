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
"""Unit tests for Phase 5D Batch 2 Production Agricultural Knowledge Corpus.

Validates:
1. Batch 2 corpus structure, non-emptiness, versioning, and provenance integrity.
2. Exactly five intended Batch 2 crops (Pigeon pea: 5, Groundnut: 5, Soybean: 5, Cotton: 4, Sugarcane: 4 = 23 total).
3. 100% unique entry IDs and source IDs across the complete combined corpus.
4. All source references resolve with zero orphan records.
5. Verified source provenance grounded in real institutional sources (TNAU Agritech Portal).
6. Strict zero-chemical invariants (no active ingredients, dosages, or chemical schedules).
7. Qualitative, non-diagnostic candidate language (no claims of certainty or diagnosis).
8. Grounded deterministic retrieval over representative English and Hindi/Hinglish farmer queries.
9. Crop isolation, alias normalization (including Devanagari), and deterministic repeated execution.
10. Preservation of Batch 1 records, empty corpus safety, and pipeline immutability.
"""

import re
import pytest

from app.disease.batch1_data import BATCH1_ENTRIES, BATCH1_SOURCES
from app.disease.batch2_data import BATCH2_ENTRIES, BATCH2_SOURCES
from app.disease.corpus import (
    DEFAULT_CORPUS,
    AgriculturalKnowledgeCorpus,
    get_empty_corpus,
)
from app.disease.retriever import retrieve_knowledge


# ---------------------------------------------------------------------------
# 1-6: Corpus Structural Invariants, Uniqueness, and Provenance Integrity
# ---------------------------------------------------------------------------


def test_batch2_corpus_is_non_empty():
    """1: Batch 2 corpus is non-empty with 23 verified entries and 5 verified sources."""
    assert len(BATCH2_ENTRIES) == 23
    assert len(BATCH2_SOURCES) == 5


def test_exactly_five_batch2_crops_represented():
    """2: Exactly the five intended Batch 2 crops are represented."""
    crops_in_batch2 = {entry.crop for entry in BATCH2_ENTRIES}
    expected_crops = {"Pigeon pea", "Groundnut", "Soybean", "Cotton", "Sugarcane"}
    assert crops_in_batch2 == expected_crops


def test_exact_entry_count_by_crop_in_batch2():
    """Confirms exact entry counts: Pigeon pea=5, Groundnut=5, Soybean=5, Cotton=4, Sugarcane=4 (23 total)."""
    counts: dict[str, int] = {}
    for entry in BATCH2_ENTRIES:
        counts[entry.crop] = counts.get(entry.crop, 0) + 1

    assert counts["Pigeon pea"] == 5
    assert counts["Groundnut"] == 5
    assert counts["Soybean"] == 5
    assert counts["Cotton"] == 4
    assert counts["Sugarcane"] == 4
    assert len(BATCH2_ENTRIES) == 23


def test_all_entry_ids_and_source_ids_are_unique_across_full_corpus():
    """3 & 4: All entry IDs and Source IDs across Batch 1 + Batch 2 are strictly unique."""
    all_entry_ids = [e.entry_id for e in DEFAULT_CORPUS.entries]
    assert len(all_entry_ids) == len(set(all_entry_ids))
    assert len(all_entry_ids) == 52

    all_source_ids = list(DEFAULT_CORPUS.sources.keys())
    assert len(all_source_ids) == len(set(all_source_ids))
    assert len(all_source_ids) == 10


def test_all_source_references_resolve_with_zero_orphans():
    """5 & 6: Every Batch 2 entry references a valid source and provenance integrity check returns zero errors."""
    errors = DEFAULT_CORPUS.validate_provenance_integrity()
    assert errors == []

    # Standalone Batch 2 corpus validation
    batch2_corpus = AgriculturalKnowledgeCorpus(
        sources=BATCH2_SOURCES,
        entries=BATCH2_ENTRIES,
        corpus_version="1.2.0-batch2",
    )
    assert batch2_corpus.validate_provenance_integrity() == []


def test_batch2_verified_sources_metadata():
    """Verifies that all Batch 2 sources are grounded in real institutional extension portals."""
    for source_id, source in BATCH2_SOURCES.items():
        assert source.organization == "Tamil Nadu Agricultural University (TNAU)"
        assert source.source_url.startswith("https://agritech.tnau.ac.in")
        assert source.version_or_year == "2024"
        assert source.redistribution_status == "bundled_permitted"
        assert source.retrieval_date == "2026-09-28"
        assert len(source.disease_topics) > 0


# ---------------------------------------------------------------------------
# 7-8: Zero-Chemical & Non-Diagnostic Language Audits
# ---------------------------------------------------------------------------

FORBIDDEN_CHEMICAL_PATTERNS = [
    r"\b\d+\s*(?:ml|g|kg|l|ppm|gm)\b",
    r"\b\d+\s*-\s*\d+\s*(?:ml|g|kg|l)\b",
    r"\b(?:per\s+liter|per\s+litre|per\s+ha|per\s+acre)\b",
    r"\b(?:mancozeb|carbendazim|monocrotophos|chlorpyrifos|imidacloprid)\b",
    r"\b(?:propiconazole|hexaconazole|copper\s+oxychloride|streptocycline)\b",
    r"\b(?:dimethoate|acephate|thiamethoxam|cypermethrin|malathion)\b",
    r"\b(?:metalaxyl|thiram|fungicide\s+spray|pesticide\s+spray|insecticide\s+dose)\b",
    r"\b(?:chemical\s+spray|chemical\s+control|spray\s+schedule)\b",
]

FORBIDDEN_DEFINITIVE_LANGUAGE = [
    r"\bconfirmed\s+diagnosis\b",
    r"\bdefinitely\s+has\b",
    r"\bguaranteed\s+cure\b",
    r"\bcertain\s+diagnosis\b",
    r"\bproven\s+pathogen\b",
    r"\b100%\s+certain\b",
    r"\bthis\s+is\s+definitely\b",
    r"\bproven\s+diagnosis\b",
]


def test_batch2_zero_chemical_guarantee():
    """7: Production Batch 2 entries contain ZERO chemical active ingredients, dosages, or spray rates."""
    for entry in BATCH2_ENTRIES:
        text_corpus = (
            f"{entry.description} "
            + " ".join(entry.safe_cultural_practices)
            + " ".join(entry.clarifying_observations)
        ).lower()

        for pattern in FORBIDDEN_CHEMICAL_PATTERNS:
            match = re.search(pattern, text_corpus)
            assert match is None, (
                f"Entry '{entry.entry_id}' in crop '{entry.crop}' contains forbidden chemical text: "
                f"matched '{match.group()}'"
            )


def test_batch2_non_definitive_candidate_language():
    """8: Production Batch 2 entries use non-diagnostic candidate framing with zero clinical certainty."""
    for entry in BATCH2_ENTRIES:
        text_corpus = entry.description.lower()
        for pattern in FORBIDDEN_DEFINITIVE_LANGUAGE:
            match = re.search(pattern, text_corpus)
            assert match is None, (
                f"Entry '{entry.entry_id}' contains forbidden definitive diagnostic wording: "
                f"matched '{match.group()}'"
            )


# ---------------------------------------------------------------------------
# 9-11: English & Hindi/Hinglish Retrieval and Determinism
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_crop", "expected_condition_substring"),
    [
        # Pigeon pea (English & Hindi)
        ("pigeon pea leaves show yellow mosaic patches and bushy stunted look", "Pigeon pea", "Sterility Mosaic"),
        ("अरहर के पौधों में बांझपन और पत्तियां पीली हो रही हैं", "Pigeon pea", "Sterility Mosaic"),
        ("arhar wilt with dark brown vascular xylem line", "Pigeon pea", "Fusarium Wilt"),
        ("toor stems snapping with dark girdling lesion after heavy rain", "Pigeon pea", "Phytophthora"),
        ("pigeonpea pods have circular bore holes with caterpillars feeding", "Pigeon pea", "Gram Pod Borer"),
        ("tur pod seeds are shriveled and dry pods have tiny pinholes", "Pigeon pea", "Pod Fly"),

        # Groundnut (English & Hindi)
        ("groundnut collar region has dense white mycelium and mustard seed sclerotia", "Groundnut", "Stem Rot"),
        ("मूंगफली के तने पर सफेद फफूंद और सरसों जैसे दाने हैं", "Groundnut", "Stem Rot"),
        ("groundnut leaves have circular brown spots with bright yellow halo", "Groundnut", "Early Leaf Spot"),
        ("mungfali tikka with black spots and severe defoliation", "Groundnut", "Late Leaf Spot"),
        ("peanut leaves have orange brown powdery pustules on underside", "Groundnut", "Groundnut Rust"),
        ("groundnut terminal bud turning brown and necrotic with stunting", "Groundnut", "Bud Necrosis"),

        # Soybean (English & Hindi)
        ("soybean leaves have bright yellow mosaic patches", "Soybean", "Yellow Mosaic"),
        ("सोयाबीन की पत्तियों पर पीले चकत्ते और मोज़ेक है", "Soybean", "Yellow Mosaic"),
        ("soybean pods have sunken brown spots with black pinhead acervuli", "Soybean", "Anthracnose"),
        ("soyabean stem has two parallel ring cuts and drooping top", "Soybean", "Girdle Beetle"),
        ("soybean stem split open shows reddish brown zig zag tunnel in pith", "Soybean", "Stem Fly"),
        ("soybean leaves stuck together with cobweb mycelium in rainy weather", "Soybean", "Aerial Blight"),

        # Cotton (English & Hindi)
        ("cotton flower buds twisted in rosette shape with caterpillar inside boll", "Cotton", "Pink Bollworm"),
        ("कपास में गुलाबी सुंडी और मुड़े हुए फूल", "Cotton", "Pink Bollworm"),
        ("cotton leaf edges curling downwards with brick red hopper burn", "Cotton", "Jassid"),
        ("cotton leaves have angular water soaked lesions and black arm on stem", "Cotton", "Bacterial Blight"),
        ("cotton green bolls rotting with matted moldy lint inside", "Cotton", "Boll Rot"),

        # Sugarcane (English & Hindi)
        ("sugarcane split stalk shows red internal tissue with transverse white bands and sour smell", "Sugarcane", "Red Rot"),
        ("गन्ने को चीरने पर अंदर लाल रंग और सफेद पट्टियां दिखाई देती हैं", "Sugarcane", "Red Rot"),
        ("sugarcane terminal shoot produces long black curved whip with sooty spores", "Sugarcane", "Sugarcane Smut"),
        ("sugarcane yellow midrib spreading to leaf lamina with green top spindle", "Sugarcane", "Yellow Leaf Disease"),
        ("ganna young shoot has dead heart that pulls out easily with foul smell", "Sugarcane", "Early Shoot Borer"),
    ],
)
def test_batch2_representative_retrieval_queries(query: str, expected_crop: str, expected_condition_substring: str):
    """9 & 10: Deterministic retrieval accurately matches Batch 2 English and Hindi queries."""
    results = retrieve_knowledge(query=query, corpus=DEFAULT_CORPUS, top_k=3)
    assert len(results) > 0, f"Query '{query}' returned zero retrieval results."

    top_entry = results[0].entry
    assert top_entry.crop == expected_crop, (
        f"Query '{query}' expected crop '{expected_crop}', got '{top_entry.crop}'"
    )
    if expected_condition_substring:
        assert expected_condition_substring.lower() in top_entry.condition_name.lower(), (
            f"Query '{query}' expected condition containing '{expected_condition_substring}', "
            f"got '{top_entry.condition_name}'"
        )


def test_batch2_crop_filtering_isolation():
    """Crop filtering strictly prevents cross-crop leakage for Batch 2 queries."""
    for crop_name in ["Pigeon pea", "Groundnut", "Soybean", "Cotton", "Sugarcane"]:
        query = f"{crop_name} leaf brown spots and wilting"
        results = retrieve_knowledge(query=query, corpus=DEFAULT_CORPUS, top_k=5)
        for res in results:
            assert res.entry.crop == crop_name, (
                f"Query for '{crop_name}' returned unexpected crop entry '{res.entry.crop}' "
                f"(ID: {res.entry.entry_id})"
            )


def test_batch2_retrieval_determinism():
    """11: Retrieval over Batch 2 queries produces 100% identical scores, ordering, and terms across runs."""
    query = "groundnut leaves with yellow halo brown spots and collar rot"
    run1 = retrieve_knowledge(query, DEFAULT_CORPUS, top_k=5)
    run2 = retrieve_knowledge(query, DEFAULT_CORPUS, top_k=5)

    assert len(run1) == len(run2)
    for r1, r2 in zip(run1, run2, strict=True):
        assert r1.entry.entry_id == r2.entry.entry_id
        assert r1.retrieval_score == r2.retrieval_score
        assert r1.matched_terms == r2.matched_terms
        assert r1.matched_fields == r2.matched_fields


# ---------------------------------------------------------------------------
# 12-15: Corpus Invariants, Batch 1 Preservation, and Empty Corpus Safety
# ---------------------------------------------------------------------------


def test_empty_corpus_behavior_unchanged():
    """12: Empty corpus helper continues to return clean empty corpus with zero errors."""
    empty = get_empty_corpus()
    assert len(empty.entries) == 0
    assert len(empty.sources) == 0
    assert empty.validate_provenance_integrity() == []
    results = retrieve_knowledge("pigeonpea wilt", empty, top_k=5)
    assert results == []


def test_batch1_entries_and_retrieval_remain_intact():
    """13 & 14: Batch 1 entries (29) remain fully intact and retrievable alongside Batch 2."""
    batch1_ids = {e.entry_id for e in BATCH1_ENTRIES}
    assert len(batch1_ids) == 29

    corpus_batch1_ids = {e.entry_id for e in DEFAULT_CORPUS.entries if e.crop in {"Rice", "Wheat", "Maize", "Chickpea", "Mustard"}}
    assert corpus_batch1_ids == batch1_ids

    # Verify Rice blast retrieval still works perfectly
    blast_res = retrieve_knowledge("rice spindle shaped lesions on leaf with gray center", DEFAULT_CORPUS, top_k=3)
    assert blast_res[0].entry.entry_id == "RICE-03"
    assert blast_res[0].entry.condition_name == "Rice Blast"

    # Verify Wheat yellow rust retrieval still works perfectly
    rust_res = retrieve_knowledge("wheat yellow stripes on leaves", DEFAULT_CORPUS, top_k=3)
    assert rust_res[0].entry.entry_id == "WHEAT-02"
    assert rust_res[0].entry.condition_name == "Yellow Rust / Stripe Rust"
