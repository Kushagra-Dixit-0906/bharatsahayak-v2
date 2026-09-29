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
"""Unit tests for modernized Phase 5D MCP disease tool integration.

Validates:
1. get_crop_disease_info calls Phase 5D disease pipeline over DEFAULT_CORPUS.
2. Strict Zero-Chemical Invariant: zero chemical active ingredients or dosages.
3. Non-diagnostic candidate framing: zero definitive diagnosis claims.
4. Grounded retrieval across Batch 1 (Rice, Wheat) and Batch 2 (Cotton, Sugarcane, Pigeonpea, etc.).
5. Hindi / Devanagari query handling.
6. Safe handling of unknown crops and empty inputs (insufficient_evidence).
7. Audit confirming complete elimination of legacy chemical strings and diagnostic claims.
"""

import re
import pytest

from app.mcp_server import get_crop_disease_info

# ---------------------------------------------------------------------------
# Safety & Zero-Chemical Audit Patterns
# ---------------------------------------------------------------------------

FORBIDDEN_CHEMICAL_PATTERNS = [
    r"\b\d+\s*(?:ml|g|kg|l|ppm|gm)\b",
    r"\b\d+\s*-\s*\d+\s*(?:ml|g|kg|l)\b",
    r"\b(?:per\s+liter|per\s+litre|per\s+ha|per\s+acre)\b",
    r"\b(?:mancozeb|carbendazim|monocrotophos|chlorpyrifos|imidacloprid)\b",
    r"\b(?:propiconazole|hexaconazole|copper\s+oxychloride|streptocycline)\b",
    r"\b(?:tricyclazole|dimethoate|acephate|thiamethoxam|cypermethrin|malathion)\b",
    r"\b(?:metalaxyl|thiram|fungicide\s+spray|pesticide\s+spray|insecticide\s+dose)\b",
    r"\b(?:spray\s+schedule|chemical\s+spray|chemical\s+control)\b",
]

FORBIDDEN_DEFINITIVE_LANGUAGE = [
    r"\bpotential\s+diagnosis:\s*brown\s+spot\b",
    r"\bconfirmed\s+diagnosis\b",
    r"\bdefinitely\s+has\b",
    r"\bguaranteed\s+cure\b",
    r"\bcertain\s+diagnosis\b",
    r"\bproven\s+pathogen\b",
    r"\b100%\s+certain\b",
    r"\bproven\s+diagnosis\b",
]


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_mcp_rice_query_zero_chemicals_and_grounded_output():
    """A: get_crop_disease_info on Rice brown spots returns Phase 5D output without chemicals."""
    output = get_crop_disease_info(crop="rice", symptoms="brown spots with yellow halo on leaves")
    assert "Crop Advisory Status:" in output
    assert "Brown Spot" in output or "Blast" in output

    # Must NOT contain forbidden chemical recommendations
    for pattern in FORBIDDEN_CHEMICAL_PATTERNS:
        match = re.search(pattern, output.lower())
        assert match is None, f"Rice MCP output contains forbidden chemical text: {match.group() if match else ''}"

    # Must contain safe cultural practices
    assert "Safe Cultural & Preventive Actions" in output


def test_mcp_wheat_query_uses_phase_5d_corpus():
    """B: get_crop_disease_info on Wheat yellow stripes uses Phase 5D corpus instead of old hardcoded string."""
    output = get_crop_disease_info(crop="wheat", symptoms="yellow stripes on leaves")
    assert "Crop Advisory Status:" in output
    assert "Yellow Rust" in output or "Rust" in output
    assert "Propiconazole" not in output
    assert "25 EC" not in output
    assert "1 ml/L" not in output

    for pattern in FORBIDDEN_CHEMICAL_PATTERNS:
        match = re.search(pattern, output.lower())
        assert match is None, f"Wheat MCP output contains forbidden chemical text: {match.group() if match else ''}"


def test_mcp_batch2_cotton_query_retrieves_pink_bollworm():
    """C: get_crop_disease_info retrieves Batch 2 crop (Cotton) correctly."""
    output = get_crop_disease_info(crop="cotton", symptoms="flower buds are twisting in rosette shape and caterpillars in bolls")
    assert "Crop Advisory Status:" in output
    assert "Pink Bollworm" in output
    assert "Cotton" in output
    assert "Safe Cultural & Preventive Actions" in output


def test_mcp_hindi_query_uses_phase_5d_retrieval():
    """D: get_crop_disease_info handles Devanagari Hindi inputs safely without crashing."""
    output = get_crop_disease_info(crop="धान", symptoms="पत्तियों पर भूरे धब्बे हैं")
    assert "Crop Advisory Status:" in output
    assert len(output) > 50

    for pattern in FORBIDDEN_CHEMICAL_PATTERNS:
        match = re.search(pattern, output.lower())
        assert match is None, f"Hindi MCP output contains forbidden chemical text: {match.group() if match else ''}"


def test_mcp_unknown_unsupported_crop_returns_insufficient_evidence():
    """E: get_crop_disease_info on unsupported crop with novel symptoms returns safe insufficient evidence behavior."""
    output = get_crop_disease_info(crop="dragonfruit", symptoms="unrecognized distortion")
    assert "insufficient_evidence" in output or "None identified" in output
    assert "Mancozeb" not in output
    assert "Neem Oil" not in output  # Legacy ungrounded fallback removed


def test_mcp_empty_input_handling():
    """Empty or whitespace inputs return safe insufficient evidence without crashing."""
    output = get_crop_disease_info(crop="", symptoms="")
    assert "insufficient_evidence" in output
    assert "Unknown" in output


def test_no_legacy_chemical_strings_in_output():
    """F: Rigorous check that legacy chemical active ingredients are completely absent from all test queries."""
    test_queries = [
        ("rice", "blast and neck rot"),
        ("wheat", "black powdery head"),
        ("maize", "cigar shaped lesions"),
        ("chickpea", "wilting in patches"),
        ("mustard", "white powder on leaves"),
        ("pigeonpea", "sterility mosaic bushy look"),
        ("groundnut", "tikka leaf spots with yellow halo"),
        ("soybean", "yellow mosaic mottling"),
        ("sugarcane", "red rot with sour smell"),
    ]

    for crop, symptoms in test_queries:
        res = get_crop_disease_info(crop=crop, symptoms=symptoms)
        for chem in ["mancozeb", "carbendazim", "tricyclazole", "propiconazole", "chlorpyrifos"]:
            assert chem not in res.lower(), f"Found legacy chemical '{chem}' in response for {crop}: {symptoms}"


def test_no_legacy_definitive_diagnosis_strings_in_output():
    """G: Rigorous check that legacy 'Potential Diagnosis:' syntax is replaced with candidate framing."""
    res = get_crop_disease_info(crop="rice", symptoms="brown spots on leaves")
    for pattern in FORBIDDEN_DEFINITIVE_LANGUAGE:
        match = re.search(pattern, res.lower())
        assert match is None, f"Found forbidden definitive diagnosis wording: {match.group() if match else ''}"
