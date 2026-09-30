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
"""Targeted unit tests for Phase 9 Targeted Repair Batch (Crop Advice, Profitability, Season Reasoning, Disease Formatting)."""

import pytest
from google.genai import types

from app.agent import (
    farming_advisor,
    crop_disease_advisor,
    is_disease_query,
    is_crop_recommendation_request,
    is_season_missing,
    load_farmer_profile,
    _hitl_checkpoint_impl,
)
from app.crop_knowledge import (
    find_crop_info,
    infer_primary_season,
    is_single_primary_season_crop,
    get_current_calendar_season,
)
from app.mcp_server import (
    calculate_farming_profitability,
    get_crop_disease_info,
)
from google.adk.events.request_input import RequestInput


# =============================================================================
# 1. NORMAL CROP RECOMMENDATION CONTAINS NO FABRICATED FINANCIAL FIGURES
# =============================================================================

def test_farming_advisor_prompt_prohibits_unprompted_financial_figures():
    instr = farming_advisor.instruction
    # Rule 3 states ordinary crop advice must NOT include financial figures
    assert "MUST NOT include financial figures" in instr
    assert "NEVER invent or hardcode arbitrary figures" in instr
    assert "unless the farmer explicitly asks about cost, investment, profit, revenue, economics, profitability, or returns" in instr


# =============================================================================
# 2, 3, 4. PROFITABILITY IS EXPLICITLY ILLUSTRATIVE & TIGHTENED ASSUMPTIONS
# =============================================================================

def test_profitability_with_explicit_acreage():
    res = calculate_farming_profitability(crop="wheat", acreage=3.0, expected_yield_per_acre=18.0)
    assert "Illustrative Farming Profitability Analysis for wheat" in res
    assert "3.0 acre(s)" in res
    assert "Assumptions & Baseline Values" in res
    assert "Assumed Cost of Cultivation: Rs. 15,000 per acre" in res
    assert "Assumed Price Benchmark (Govt MSP): Rs. 2,275 per quintal" in res
    assert "Illustrative estimate — not a guaranteed return" in res
    assert "Actual profit depends on your local yield, input costs" in res
    assert "Krishi Vigyan Kendra (KVK)" in res


def test_profitability_with_default_single_acre():
    res = calculate_farming_profitability(crop="rice", acreage=1.0)
    assert "1.0 acre (Illustrative Benchmark Example)" in res
    assert "Illustrative estimate — not a guaranteed return" in res
    assert "You will earn" not in res
    assert "Guaranteed" not in res


# =============================================================================
# 5, 6, 7, 8, 9, 10. GENERAL CROP-SEASON DETERMINISTIC KNOWLEDGE LAYER
# =============================================================================

def test_crop_season_knowledge_lookups():
    # 5. Rice + UP -> Kharif
    assert infer_primary_season("rice", "Uttar Pradesh") == "Kharif"
    assert is_single_primary_season_crop("rice", "Uttar Pradesh") is True

    # 6. Wheat + UP -> Rabi
    assert infer_primary_season("wheat", "Uttar Pradesh") == "Rabi"
    assert is_single_primary_season_crop("wheat", "Uttar Pradesh") is True

    # 7. Mustard + UP / Rajasthan -> Rabi
    assert infer_primary_season("mustard", "Rajasthan") == "Rabi"
    assert is_single_primary_season_crop("mustard", "Rajasthan") is True

    # 8. Soybean -> Kharif
    assert infer_primary_season("soybean", "Madhya Pradesh") == "Kharif"
    assert is_single_primary_season_crop("soybean") is True

    # 9. Summer moong -> Zaid
    assert infer_primary_season("summer moong") == "Zaid"
    assert infer_primary_season("watermelon") == "Zaid"

    # 10. Multi-season crop
    maize_info = find_crop_info("maize")
    assert maize_info.is_multi_season is True
    assert "Kharif" in maize_info.primary_seasons
    assert "Rabi" in maize_info.secondary_seasons


def test_smart_season_reasoning_for_rice_farmer_in_up():
    query = "I am a rice farmer in Uttar Pradesh. What should I grow for this season?"
    # Season should NOT be marked missing because Rice in UP deterministically implies Kharif
    assert is_season_missing(query, {"location": "Uttar Pradesh", "crops": ["rice"]}) is False


def test_generic_crop_recommendation_requires_season_clarification():
    # 12. Generic open query without crop requires season clarification
    query = "What crop should I grow this season?"
    assert is_crop_recommendation_request(query) is True
    assert is_season_missing(query, {}) is True


# =============================================================================
# 11. SEPARATE REQUESTED SEASON FROM CALENDAR SEASON
# =============================================================================

def test_requested_season_authoritative_over_calendar():
    class MockContext:
        def __init__(self):
            self.state = {}
            self.resume_inputs = {}

    ctx = MockContext()
    # Farmer explicitly asks for Kharif
    ev = load_farmer_profile(ctx, types.Content(parts=[types.Part.from_text(text="I want to plan a Kharif crop")]))
    assert ctx.state["farmer_profile"]["farmer_selected_season"] == "Kharif"
    assert "Requested / Farmer-Selected Season: Kharif (AUTHORITATIVE" in ev.output
    assert "Current Calendar Season:" in ev.output


# =============================================================================
# 13, 14. DISEASE FARMER-FACING OUTPUT CLEANUP & CANDIDATE UNCERTAINTY
# =============================================================================

def test_disease_farmer_facing_output_cleanup():
    output = get_crop_disease_info(crop="rice", symptoms="brown spots with yellow halo on leaves")
    
    # 13. Does not expose internal terminology
    assert "Crop Advisory Status:" not in output
    assert "strong_match" not in output
    assert "moderate_match" not in output
    assert "[nutrient_balance]" not in output
    assert "[water_management]" not in output
    assert "[src_" not in output

    # 14. Preserves candidate-condition/uncertainty language
    assert "Possible Candidate Conditions (Non-Definitive Hypotheses)" in output
    assert "Safe Cultural & Preventive Actions" in output
    assert "When to seek expert help" in output
    assert "Krishi Vigyan Kendra (KVK)" in output


# =============================================================================
# 15. LANGUAGE REGRESSION & PROGRESSIVE REGION CLARIFICATION TESTS
# =============================================================================

from app.agent import detect_language, is_region_missing, extract_location


def test_detect_language_with_neutral_tokens():
    # 1. Hindi input -> Hindi
    assert detect_language("मेरे खेत के लिए कौन सी फसल अच्छी रहेगी?") == "Hindi"
    
    # 2. English input -> English
    assert detect_language("What crop should I grow this season?") == "English"
    
    # 3. Neutral button/choice tokens preserve the existing default/session language
    assert detect_language("Zaid", default="Hindi") == "Hindi"
    assert detect_language("Kharif", default="Hindi") == "Hindi"
    assert detect_language("Rabi", default="Hindi") == "Hindi"
    assert detect_language("yes", default="Hindi") == "Hindi"
    assert detect_language("no", default="Hindi") == "Hindi"
    
    assert detect_language("Zaid", default="English") == "English"
    assert detect_language("Kharif", default="English") == "English"
    
    # 4. Explicit language switching in same session
    assert detect_language("Tell me about wheat", default="Hindi") == "English"
    assert detect_language("मुझे गेहूं के बारे में बताओ", default="English") == "Hindi"


def test_extract_location_shortcuts_and_states():
    assert extract_location("I am in UP") == "Uttar Pradesh"
    assert extract_location("UP") == "Uttar Pradesh"
    assert extract_location("यूपी") == "Uttar Pradesh"
    assert extract_location("I live in MP") == "Madhya Pradesh"
    assert extract_location("AP") == "Andhra Pradesh"
    assert extract_location("Rajasthan") == "Rajasthan"


def test_generic_crop_recommendation_progressive_region():
    # When season is known (e.g. Kharif) but region is unknown, is_region_missing is True
    query = "What crop should I grow for Kharif?"
    profile_without_loc = {"farmer_selected_season": "Kharif", "location": "Unknown"}
    assert is_crop_recommendation_request(query, profile_without_loc) is True
    assert is_season_missing(query, profile_without_loc) is False
    assert is_region_missing(query, profile_without_loc) is True
    
    # When region is known (e.g. Uttar Pradesh), is_region_missing is False
    profile_with_loc = {"farmer_selected_season": "Kharif", "location": "Uttar Pradesh"}
    assert is_region_missing(query, profile_with_loc) is False
    
    # Rice + UP -> Season inferred as Kharif, location is UP, no extra clarifications
    rice_up_query = "I am a rice farmer in Uttar Pradesh. What should I grow or consider for this season?"
    rice_up_profile = {"crops": ["rice"], "location": "Uttar Pradesh", "inferred_season": "Kharif"}
    assert is_season_missing(rice_up_query, rice_up_profile) is False
    assert is_region_missing(rice_up_query, rice_up_profile) is False


@pytest.mark.asyncio
async def test_hitl_checkpoint_language_and_region_flow():
    class MockContext:
        def __init__(self, query, profile, resume_inputs=None):
            self.state = {"user_query": query, "farmer_profile": profile}
            self.resume_inputs = resume_inputs or {}

    # Turn 1: Hindi query "मेरे खेत के लिए कौन सी फसल अच्छी रहेगी?"
    hindi_query = "मेरे खेत के लिए कौन सी फसल अच्छी रहेगी?"
    ctx1 = MockContext(
        hindi_query,
        {"language": "Hindi", "location": "Unknown", "crops": []}
    )
    generator1 = _hitl_checkpoint_impl(ctx1, {})
    item1 = None
    async for item in generator1:
        item1 = item
    assert isinstance(item1, RequestInput)
    assert "खरीफ" in item1.message  # Asks season in Hindi
    
    # Turn 2: User responds "Zaid" (neutral token). Language must remain Hindi!
    ctx2 = MockContext(
        hindi_query,
        {"language": "Hindi", "location": "Unknown", "crops": []},
        resume_inputs={"more_info": "Zaid"}
    )
    generator2 = _hitl_checkpoint_impl(ctx2, {})
    item2 = None
    async for item in generator2:
        item2 = item
    # Since location is still missing, it should ask for State/UT in Hindi!
    assert isinstance(item2, RequestInput)
    assert "राज्य (State/UT)" in item2.message
    assert ctx2.state["farmer_profile"]["language"] == "Hindi"
    assert ctx2.state["farmer_profile"]["farmer_selected_season"] == "Zaid"
    
    # Turn 3: User provides "Uttar Pradesh". Now complete!
    ctx3 = MockContext(
        hindi_query,
        {"language": "Hindi", "location": "Unknown", "crops": [], "farmer_selected_season": "Zaid"},
        resume_inputs={"more_info": "Uttar Pradesh"}
    )
    generator3 = _hitl_checkpoint_impl(ctx3, {})
    item3 = None
    async for item in generator3:
        item3 = item
    # Should proceed with Event containing Hindi language directive and UP location
    assert item3.output is not None
    assert ctx3.state["farmer_profile"]["location"] == "Uttar Pradesh"
    assert ctx3.state["farmer_profile"]["language"] == "Hindi"
    assert "The target Output Language is Hindi" in item3.output


def test_non_crop_flows_do_not_require_region():
    # Disease query
    disease_query = "My tomato leaves have dark brown spots with concentric rings."
    assert is_crop_recommendation_request(disease_query) is False
    assert is_disease_query(disease_query) is True
    
    # Environmental query
    env_query = "Assess environmental conditions for my land at 26.8467, 80.9462"
    assert is_crop_recommendation_request(env_query) is False

