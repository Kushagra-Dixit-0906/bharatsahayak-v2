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

"""Focused unit tests for location extraction, coordinate persistence, and model configuration."""

from types import SimpleNamespace
import pytest
from google.genai import types

from app.agent import (
    extract_coordinates,
    extract_location,
    load_farmer_profile,
    _hitl_checkpoint_impl,
)
from app.config import config


def test_state_name_retained_without_fabricating_coordinates() -> None:
    """Verifies that state/district names are extracted to profile location but DO NOT fabricate coordinates."""
    ctx = SimpleNamespace(state={})
    node_input = types.Content(
        parts=[types.Part.from_text(text="I'm a rice farmer in Uttar Pradesh and I have 3 acres.")]
    )
    event = load_farmer_profile(ctx, node_input)
    profile = ctx.state["farmer_profile"]

    # State retained
    assert profile["location"] == "Uttar Pradesh"
    assert "rice" in profile["crops"]
    assert profile["farm_size"] == "3 acres"

    # Coordinates MUST remain None (never fabricated or silently assumed)
    assert profile["latitude"] is None
    assert profile["longitude"] is None
    assert "Coordinates:" not in event.output


def test_explicit_coordinates_extracted_and_persisted() -> None:
    """Verifies that explicitly provided coordinates are extracted and set in the profile."""
    ctx = SimpleNamespace(state={})
    node_input = types.Content(
        parts=[types.Part.from_text(text="I am farming in Kotoli, Maharashtra at 16.774931, 74.046179")]
    )
    event = load_farmer_profile(ctx, node_input)
    profile = ctx.state["farmer_profile"]

    assert profile["location"] == "Maharashtra"
    assert profile["latitude"] == pytest.approx(16.774931, rel=1e-5)
    assert profile["longitude"] == pytest.approx(74.046179, rel=1e-5)
    assert "- Coordinates: 16.774931, 74.046179" in event.output


def test_extract_coordinates_formats() -> None:
    """Tests various explicit coordinate formats and verifies no coordinates extracted from plain text."""
    # Standard pair
    res = extract_coordinates("My farm is located at 16.774931, 74.046179")
    assert res is not None
    assert res[0] == pytest.approx(16.774931, rel=1e-5)
    assert res[1] == pytest.approx(74.046179, rel=1e-5)

    # Labeled format with comma
    res2 = extract_coordinates("lat: 26.846708, lon: 80.946159")
    assert res2 is not None
    assert res2[0] == pytest.approx(26.846708, rel=1e-5)
    assert res2[1] == pytest.approx(80.946159, rel=1e-5)

    # Labeled format with words
    res3 = extract_coordinates("latitude 15.317277, longitude 75.713888")
    assert res3 is not None
    assert res3[0] == pytest.approx(15.317277, rel=1e-5)
    assert res3[1] == pytest.approx(75.713888, rel=1e-5)

    # Plain text / state name only - MUST return None
    assert extract_coordinates("I am a farmer in Uttar Pradesh") is None
    assert extract_coordinates("Punjab farm near Ludhiana") is None
    assert extract_coordinates("Barabanki district") is None
    assert extract_coordinates("Maharashtra 5 acres") is None


@pytest.mark.asyncio
async def test_hitl_resume_with_explicit_coordinates() -> None:
    """Verifies that resuming HITL with coordinates updates latitude/longitude in the profile."""
    ctx = SimpleNamespace(
        state={
            "user_query": "What is the condition of my farm?",
            "farmer_profile": {
                "language": "English",
                "location": "Maharashtra",
                "latitude": None,
                "longitude": None,
                "crops": ["sugarcane"],
                "farm_size": "Unknown",
                "season": None,
            },
        },
        resume_inputs={"more_info": {"result": "Farm coordinates: 16.774931, 74.046179"}},
    )
    node_input = {
        "response": "",
        "needs_more_info": True,
        "info_request_message": "Please provide coordinates",
    }

    events = [e async for e in _hitl_checkpoint_impl(ctx, node_input)]
    assert len(events) == 1
    event = events[0]
    profile = ctx.state["farmer_profile"]

    assert profile["latitude"] == pytest.approx(16.774931, rel=1e-5)
    assert profile["longitude"] == pytest.approx(74.046179, rel=1e-5)
    assert "- Coordinates: 16.774931, 74.046179" in event.output


@pytest.mark.asyncio
async def test_hitl_resume_with_state_only_retains_location_without_coordinates() -> None:
    """Verifies that resuming HITL with only state name updates location but leaves coordinates None."""
    ctx = SimpleNamespace(
        state={
            "user_query": "What crop can I grow?",
            "farmer_profile": {
                "language": "English",
                "location": "Unknown",
                "latitude": None,
                "longitude": None,
                "crops": [],
                "farm_size": "Unknown",
                "season": "Kharif",
            },
        },
        resume_inputs={"more_info": {"result": "Uttar Pradesh"}},
    )
    node_input = {
        "response": "",
        "needs_more_info": True,
        "info_request_message": "Please provide your location",
    }

    events = [e async for e in _hitl_checkpoint_impl(ctx, node_input)]
    assert len(events) == 1
    event = events[0]
    profile = ctx.state["farmer_profile"]

    assert profile["location"] == "Uttar Pradesh"
    assert profile["latitude"] is None
    assert profile["longitude"] is None
    assert "Coordinates:" not in event.output


def test_gemini_model_configuration() -> None:
    """Verifies that the default Gemini model resolves to gemini-3.5-flash-lite."""
    assert config.model == "gemini-3.5-flash-lite"
