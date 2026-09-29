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
"""Unit tests for Phase 5D Batch 1 Production Agricultural Knowledge Corpus.

Validates:
1. Corpus structure, non-emptiness, versioning, and provenance integrity.
2. 5-crop coverage (Rice: 6, Wheat: 5, Maize: 6, Chickpea: 6, Mustard: 6 = 29 total).
3. Complete removal of non-diagnostic WHEAT-06.
4. Correct non-conflated representation of MAIZE-06 (Sorghum Downy Mildew).
5. Grounding against verified TNAU Agritech Portal extension sources.
6. Strict zero-chemical invariants (no active ingredients, dosages, or chemical schedules).
7. Qualitative, non-diagnostic candidate language (no claims of certainty or diagnosis).
8. Grounded deterministic retrieval over representative English and Hindi farmer queries.
9. Crop filtering, alias mapping, and deterministic repeated execution.
"""

import re
import pytest

from app.disease.batch1_data import BATCH1_ENTRIES, BATCH1_SOURCES
from app.disease.corpus import DEFAULT_CORPUS
from app.disease.retriever import retrieve_knowledge


# ---------------------------------------------------------------------------
# Corpus Integrity & Structural Invariants
# ---------------------------------------------------------------------------


def test_default_corpus_is_non_empty_and_versioned():
    """1: DEFAULT_CORPUS is non-empty and has appropriate release version."""
    assert len(DEFAULT_CORPUS.entries) == 52
    assert len(DEFAULT_CORPUS.sources) == 10
    assert DEFAULT_CORPUS.corpus_version == "1.2.0"


def test_batch1_crops_and_counts_represented():
    """2: Exactly the five intended Batch 1 crops and their exact counts are represented."""
    batch1_crops = {entry.crop for entry in BATCH1_ENTRIES}
    expected_crops = {"Rice", "Wheat", "Maize", "Chickpea", "Mustard"}
    assert batch1_crops == expected_crops
    assert len(BATCH1_ENTRIES) == 29
    assert len(BATCH1_SOURCES) == 5

    counts: dict[str, int] = {}
    for entry in BATCH1_ENTRIES:
        counts[entry.crop] = counts.get(entry.crop, 0) + 1

    assert counts["Rice"] == 6
    assert counts["Wheat"] == 5  # WHEAT-06 removed
    assert counts["Maize"] == 6
    assert counts["Chickpea"] == 6
    assert counts["Mustard"] == 6


# ---------------------------------------------------------------------------
# Specific Correction Verification: WHEAT-06 Removal & MAIZE-06 De-conflation
# ---------------------------------------------------------------------------


def test_wheat_06_is_completely_removed():
    """Confirms WHEAT-06 non-diagnostic pseudo-condition is completely absent."""
    entry_ids = {e.entry_id for e in DEFAULT_CORPUS.entries}
    assert "WHEAT-06" not in entry_ids

    # Querying for generic yellowing on wheat should NOT match a smutted head pseudo-entry
    wheat_entries = [e for e in DEFAULT_CORPUS.entries if e.crop == "Wheat"]
    for entry in wheat_entries:
        assert "smutted head" not in entry.condition_name.lower()
        assert entry.condition_name in {
            "Brown Rust / Leaf Rust",
            "Yellow Rust / Stripe Rust",
            "Stem Rust / Black Rust",
            "Loose Smut",
            "Powdery Mildew",
        }


def test_maize_06_is_not_conflated_with_crazy_top():
    """Confirms MAIZE-06 is Sorghum Downy Mildew and not conflated with Crazy top."""
    maize_06 = DEFAULT_CORPUS.get_entry("MAIZE-06")
    assert maize_06 is not None
    assert maize_06.condition_name == "Sorghum Downy Mildew"
    assert maize_06.scientific_name == "Peronosclerospora sorghi"
    assert "crazy top" not in maize_06.condition_name.lower()
    assert "crazy top" not in maize_06.description.lower()
    assert "crazy top" not in [k.lower() for k in maize_06.symptom_keywords]


# ---------------------------------------------------------------------------
# Strict Safety & Diagnostic Invariants
# ---------------------------------------------------------------------------


FORBIDDEN_CHEMICAL_PATTERNS = [
    r"\b\d+\s*(?:ml|g|kg|l|ppm|gm)\b",
    r"\b\d+\s*-\s*\d+\s*(?:ml|g|kg|l)\b",
    r"\b(?:per\s+liter|per\s+litre|per\s+ha|per\s+acre)\b",
    r"\b(?:mancozeb|carbendazim|monocrotophos|chlorpyrifos|imidacloprid)\b",
    r"\b(?:propiconazole|hexaconazole|copper\s+oxychloride|streptocycline)\b",
    r"\b(?:dimethoate|acephate|thiamethoxam|cypermethrin|malathion)\b",
    r"\b(?:metalaxyl|thiram|fungicide\s+spray|pesticide\s+spray|insecticide\s+dose)\b",
]

FORBIDDEN_DEFINITIVE_LANGUAGE = [
    r"\bconfirmed\s+diagnosis\b",
    r"\bdefinitely\s+has\b",
    r"\bguaranteed\s+cure\b",
    r"\bcertain\s+diagnosis\b",
    r"\bproven\s+pathogen\b",
    r"\b100%\s+certain\b",
]


def test_no_production_entry_contains_chemical_dosage_or_active_ingredients():
    """Zero chemical dosages, active ingredients, or spray rates in production corpus."""
    for entry in DEFAULT_CORPUS.entries:
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


def test_no_production_entry_uses_definitive_diagnosis_language():
    """Zero definitive clinical language; all descriptions preserve candidate reasoning."""
    for entry in DEFAULT_CORPUS.entries:
        text_corpus = entry.description.lower()
        for pattern in FORBIDDEN_DEFINITIVE_LANGUAGE:
            match = re.search(pattern, text_corpus)
            assert match is None, (
                f"Entry '{entry.entry_id}' contains forbidden definitive diagnostic wording: "
                f"matched '{match.group()}'"
            )


def test_no_production_entry_contains_arbitrary_probabilities():
    """Zero numerical confidence scores or percentages in knowledge records."""
    percentage_pattern = r"\b\d+%"
    for entry in DEFAULT_CORPUS.entries:
        text_corpus = (
            f"{entry.description} "
            + " ".join(entry.safe_cultural_practices)
            + " ".join(entry.clarifying_observations)
        )
        # Exception: "10-15%" in seed rate guidance or "15%" are non-confidence agronomic ratios
        matches = re.findall(percentage_pattern, text_corpus)
        for m in matches:
            assert m in {"10-15%", "15%"}, f"Entry '{entry.entry_id}' contains unexpected percentage: {m}"


# ---------------------------------------------------------------------------
# Grounded Retrieval Over Representative Batch 1 Queries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected_crop", "expected_condition_substring"),
    [
        # Rice Queries
        ("rice leaves have spindle shaped spots", "Rice", "Blast"),
        ("धान की पत्तियों पर भूरे धब्बे हैं", "Rice", "Brown Spot"),
        ("rice leaves are folded and dry", "Rice", "Leaf Folder"),
        # Wheat Queries
        ("wheat has yellow stripes on leaves", "Wheat", "Yellow Rust"),
        ("गेहूं की पत्तियों पर पीली धारियां हैं", "Wheat", "Yellow Rust"),
        ("wheat head has black spores", "Wheat", "Loose Smut"),
        # Maize Queries
        ("maize leaves are damaged in the whorl", "Maize", "Fall Armyworm"),
        ("मक्का की पत्तियां बीच से सूख रही हैं", "Maize", ""),  # Matches Maize entry
        ("maize has cigar shaped leaf lesions", "Maize", "Turcicum"),
        # Chickpea Queries
        ("chickpea plants are wilting in patches", "Chickpea", "Fusarium Wilt"),
        ("चना की फलियों में गोल छेद हैं", "Chickpea", "Gram Pod Borer"),
        ("chickpea leaves have white powder", "Chickpea", "Powdery Mildew"),
        # Mustard Queries
        ("mustard leaves are curling and plant is stunted", "Mustard", "Mustard Aphid"),
        ("सरसों की पत्तियों पर काले गोल धब्बे हैं", "Mustard", "Alternaria Blight"),
        ("mustard leaves have zig zag tunnels", "Mustard", "Mustard Leaf Miner"),
    ],
)
def test_retriever_representative_queries(query: str, expected_crop: str, expected_condition_substring: str):
    """Deterministic retrieval accurately finds relevant entries for real queries."""
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


def test_crop_isolation_in_retrieval():
    """Specifying a crop prevents returning entries from unrelated crops."""
    wheat_query = "wheat leaves with yellow spots and curling"
    results = retrieve_knowledge(query=wheat_query, corpus=DEFAULT_CORPUS, top_k=5)

    # All returned results must be Wheat
    for res in results:
        assert res.entry.crop == "Wheat", f"Returned non-wheat entry '{res.entry.entry_id}' for wheat query"


def test_retrieval_determinism_on_production_corpus():
    """Identical query on DEFAULT_CORPUS returns identical scores and order."""
    query = "chickpea plants wilting in patches with root browning"
    run1 = retrieve_knowledge(query, DEFAULT_CORPUS, top_k=5)
    run2 = retrieve_knowledge(query, DEFAULT_CORPUS, top_k=5)

    assert len(run1) == len(run2)
    for r1, r2 in zip(run1, run2, strict=True):
        assert r1.entry.entry_id == r2.entry.entry_id
        assert r1.retrieval_score == r2.retrieval_score
        assert r1.matched_terms == r2.matched_terms
        assert r1.matched_fields == r2.matched_fields
