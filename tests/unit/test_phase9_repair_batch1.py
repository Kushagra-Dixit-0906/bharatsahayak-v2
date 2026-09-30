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
"""Targeted unit tests for Phase 9 Repair Batch 1."""

import pytest
from google.genai import types

from app.agent import (
    detect_language,
    extract_coordinates,
    extract_crops,
    extract_season,
    farming_advisor,
    crop_disease_advisor,
    orchestrator,
    is_disease_query,
    is_crop_recommendation_request,
    is_season_missing,
    load_farmer_profile,
    _hitl_checkpoint_impl,
)
from app.assessment.gemini_prompt import build_gemini_prompt
from app.assessment.gemini_types import (
    GeminiAssessmentContext,
    ContextPatternSummary,
    VerifiedFarmerContext,
    PresentationPreferences,
)
from app.assessment.types import SupportingEvidenceItem
from app.satellite.types import AnalysisRegionMetadata
from app.mcp_server import (
    search_government_schemes,
    calculate_farming_profitability,
)
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
import datetime


# =============================================================================
# 1. LANGUAGE — LATEST FARMER INPUT IS THE AUTHORITY
# =============================================================================

def test_language_detection_hindi_english():
    assert detect_language("What should I grow?") == "English"
    assert detect_language("मुझे गेहूं के बारे में बताओ") == "Hindi"
    assert detect_language("सिंचाई कब करनी चाहिए?") == "Hindi"
    assert detect_language("What about irrigation?") == "English"


def test_language_detection_preserves_numeric_default():
    assert detect_language("16.758842, 74.032992", default="English") == "English"
    assert detect_language("16.758842, 74.032992", default="Hindi") == "Hindi"
    assert detect_language("26.8462, 80.9490", default="Hindi") == "Hindi"


def test_language_switching_in_same_session():
    # Turn 1: Hindi input
    class MockContext:
        def __init__(self):
            self.state = {}
            self.resume_inputs = {}

    ctx = MockContext()
    ev1 = load_farmer_profile(ctx, types.Content(parts=[types.Part.from_text(text="नमस्ते, मुझे सहायता चाहिए")]))
    assert ctx.state["farmer_profile"]["language"] == "Hindi"
    assert "Output Language is Hindi" in ev1.output

    # Turn 2: English input in same session
    ev2 = load_farmer_profile(ctx, types.Content(parts=[types.Part.from_text(text="Now tell me about wheat cultivation")]))
    assert ctx.state["farmer_profile"]["language"] == "English"
    assert "Output Language is English" in ev2.output

    # Turn 3: Hindi input again in same session
    ev3 = load_farmer_profile(ctx, types.Content(parts=[types.Part.from_text(text="गेहूं में खाद कब डालें?")]))
    assert ctx.state["farmer_profile"]["language"] == "Hindi"
    assert "Output Language is Hindi" in ev3.output


@pytest.mark.asyncio
async def test_hitl_language_follows_latest_input():
    # Test Hindi HITL
    class MockContext:
        def __init__(self, lang, query):
            self.state = {
                "farmer_profile": {"language": lang, "crops": []},
                "user_query": query,
            }
            self.resume_inputs = {}

    ctx_hi = MockContext("Hindi", "मुझे फसल का सुझाव दें")
    gen_hi = _hitl_checkpoint_impl(ctx_hi, {"needs_more_info": True, "info_request_message": ""})
    req_hi = [item async for item in gen_hi][0]
    assert isinstance(req_hi, RequestInput)
    assert "मौसम" in req_hi.message  # Hindi prompt

    # Test English HITL
    ctx_en = MockContext("English", "What crop should I grow?")
    gen_en = _hitl_checkpoint_impl(ctx_en, {"needs_more_info": True, "info_request_message": ""})
    req_en = [item async for item in gen_en][0]
    assert isinstance(req_en, RequestInput)
    assert "season" in req_en.message  # English prompt


@pytest.mark.asyncio
async def test_hitl_resume_dynamic_language_switch():
    class MockContext:
        def __init__(self, lang, query, resume_val):
            self.state = {
                "farmer_profile": {"language": lang, "crops": [], "location": "Uttar Pradesh"},
                "user_query": query,
            }
            self.resume_inputs = {"more_info": resume_val}

    # Start in English query, resume in Hindi
    ctx = MockContext("English", "What should I grow in Uttar Pradesh?", "खरीफ")
    gen = _hitl_checkpoint_impl(ctx, {"needs_more_info": True, "info_request_message": ""})
    events = [item async for item in gen]
    assert len(events) == 1
    assert ctx.state["farmer_profile"]["language"] == "Hindi"
    assert "Output Language is Hindi" in events[0].output


# =============================================================================
# 2. GOVERNMENT SCHEMES — CENTRAL VS STATE ISOLATION & NO REPEATED DROPDOWN
# =============================================================================

def test_central_schemes_isolation():
    res = search_government_schemes(mode="central")
    assert "PM-KISAN" in res
    assert "PMFBY" in res
    assert "KCC" in res
    assert "Uttar Pradesh — State-Specific" not in res
    assert "Krishi Bhagya" not in res


def test_state_schemes_up():
    res = search_government_schemes(state="Uttar Pradesh", mode="state")
    assert "Uttar Pradesh — State-Specific" in res
    assert "PM-KISAN (Pradhan Mantri" not in res


def test_state_schemes_unsupported_state():
    res = search_government_schemes(state="Jharkhand", mode="state")
    assert "not currently available in the local verified database" in res
    assert "Central Government schemes" in res


# =============================================================================
# 3. DISEASE FLOW — NO UNNECESSARY LOCATION REQUEST
# =============================================================================

def test_disease_query_classification():
    q1 = "My rice leaves have brown spots and some leaves are turning yellow."
    assert is_disease_query(q1) is True
    assert is_crop_recommendation_request(q1) is False

    q2 = "टमाटर के पत्तों में पीले धब्बे दिख रहे हैं"
    assert is_disease_query(q2) is True
    assert is_crop_recommendation_request(q2) is False


def test_disease_advisor_instructions_prohibit_location_requirement():
    instr = crop_disease_advisor.instruction
    assert "Location or GPS coordinates are NEVER required" in instr
    assert "Do NOT ask the farmer for their location, GPS, or farm size" in instr


# =============================================================================
# 4. CROP RECOMMENDATION — NO UNSUPPORTED ECONOMIC FABRICATION
# =============================================================================

def test_farming_advisor_instructions_prohibit_economic_fabrication():
    instr = farming_advisor.instruction
    assert "NEVER invent, assume, or hardcode arbitrary investment or profit amounts" in instr
    assert "NEVER silently fabricate regions" in instr


# =============================================================================
# 5. CROP + SEASON REASONING
# =============================================================================

def test_season_reasoning_with_known_crop():
    # User specifies crop -> season reasoning should not block with generic HITL
    query = "I am a rice farmer in Uttar Pradesh. What should I consider for this season?"
    assert is_crop_recommendation_request(query) is False
    assert is_season_missing(query) is False

    # Empty open query -> requires season clarification
    open_query = "What should I grow?"
    assert is_crop_recommendation_request(open_query) is True
    assert is_season_missing(open_query) is True


# =============================================================================
# 6. PROFITABILITY — TIGHTEN ASSUMPTIONS & BENCHMARKS
# =============================================================================

def test_profitability_benchmark_output():
    res = calculate_farming_profitability(crop="rice", acreage=2.0, expected_yield_per_acre=20.0)
    assert "Farming Profitability Analysis for 2.0 acre(s) of rice" in res
    assert "Rs. 18,000 per acre benchmark" in res
    assert "Govt MSP Benchmark of Rs. 2183/quintal" in res
    assert "illustrative benchmark calculation" in res
    assert "Actual income will vary based on local mandi prices" in res


# =============================================================================
# 7 & 8. GEMINI PROMPT & HINDI QUALITY
# =============================================================================

def test_gemini_prompt_hindi_and_farmer_friendly_guidance():
    ctx = GeminiAssessmentContext(
        reference_date=datetime.date(2026, 9, 30),
        region=AnalysisRegionMetadata(
            latitude=16.7588,
            longitude=74.0329,
            buffer_radius_m=250.0,
            analysis_start_date=datetime.date(2026, 8, 31),
            analysis_end_date=datetime.date(2026, 9, 30),
        ),
        overall_condition="stable",
        assessment_status="success",
        is_sufficient=True,
        missing_evidence_sources=[],
        partial_evidence_sources=[],
        maximum_data_lag_days=30,
        identified_patterns=[
            ContextPatternSummary(
                pattern_type="near_baseline_stable_condition",
                evidence_support="high_support",
                technical_summary="Vegetation vigor stable",
                supporting_evidence=[
                    SupportingEvidenceItem(
                        source="vegetation",
                        metric_name="ndvi_mean",
                        observed_value=0.52,
                        reference_context="Historical median 0.50",
                    )
                ],
            )
        ],
        conflicting_signals=[],
        limitations=[],
        farmer_context=VerifiedFarmerContext(
            preferred_language="hi",
            context_status="unknown",
        ),
        presentation=PresentationPreferences(target_language="hi"),
    )
    prompt = build_gemini_prompt(ctx)
    assert "<technical_summary>" not in prompt
    assert "When target_language is 'hi' (Hindi):" in prompt
    assert "Strictly avoid technical jargon" in prompt
    assert "Devanagari" in prompt
