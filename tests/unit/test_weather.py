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
"""Comprehensive unit tests for the standalone Weather Module."""

import pytest
from unittest.mock import patch

from app.weather_service import (
    resolve_coordinates,
    format_weather_forecast_text,
    get_weather_advisory_impl,
    WMO_WEATHER_CODES,
    INDIAN_LOCATION_COORDINATES,
)
from app.mcp_server import get_weather_advisory
from app.agent import (
    is_weather_query,
    is_weather_location_missing,
    _hitl_checkpoint_impl,
    detect_language,
    weather_advisor,
)
from google.adk.events.request_input import RequestInput


# =============================================================================
# 1 & 2. CURRENT WEATHER & FORECAST PARSING
# =============================================================================

SAMPLE_OPEN_METEO_DATA = {
    "latitude": 26.85,
    "longitude": 80.95,
    "current": {
        "temperature_2m": 31.5,
        "relative_humidity_2m": 62,
        "precipitation": 0.0,
        "weather_code": 1,
        "wind_speed_10m": 12.4,
    },
    "daily": {
        "time": ["2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03"],
        "weather_code": [1, 61, 2, 0],
        "temperature_2m_max": [33.0, 29.5, 31.0, 32.5],
        "temperature_2m_min": [24.0, 22.0, 23.5, 24.0],
        "precipitation_probability_max": [10, 75, 20, 5],
        "precipitation_sum": [0.0, 18.5, 1.2, 0.0],
    }
}


def test_format_weather_forecast_english():
    text = format_weather_forecast_text(
        data=SAMPLE_OPEN_METEO_DATA,
        location_name="Lucknow",
        language="en",
    )
    # 1. Current conditions present
    assert "Current Weather for Lucknow:" in text
    assert "Temperature: 31.5°C" in text
    assert "Condition: Mainly clear" in text
    assert "Humidity: 62%" in text
    assert "Precipitation: 0.0 mm" in text
    assert "Wind Speed: 12.4 km/h" in text

    # 2. 3-day forecast present
    assert "3-Day Short-Term Forecast:" in text
    assert "Day 1 (2026-10-01): 22.0°C to 29.5°C" in text
    assert "Rain Chance: 75% (18.5 mm)" in text

    # 3. Practical note present without fake prescriptions
    assert "Practical Farming Weather Note:" in text
    assert "Rain is expected in the upcoming days" in text


def test_format_weather_forecast_hindi():
    text = format_weather_forecast_text(
        data=SAMPLE_OPEN_METEO_DATA,
        location_name="लखनऊ",
        language="hi",
    )
    assert "लखनऊ के लिए वर्तमान मौसम स्थिति:" in text
    assert "• तापमान: 31.5°C" in text
    assert "• मौसम: मुख्य रूप से साफ" in text
    assert "• आर्द्रता (नमी): 62%" in text
    assert "📅 आगामी 3 दिनों का मौसम पूर्वानुमान:" in text
    assert "💡 कृषि मौसम सुझाव:" in text
    assert "वर्षा की संभावना है" in text


# =============================================================================
# 3 & 4. LOCATION RESOLUTION & DIRECT COORDINATES
# =============================================================================

def test_resolve_coordinates_states_and_cities():
    # State names
    punjab = resolve_coordinates(location="Punjab")
    assert punjab is not None
    assert round(punjab[0], 2) == 31.15
    assert round(punjab[1], 2) == 75.34

    up = resolve_coordinates(location="Uttar Pradesh")
    assert up is not None
    assert round(up[0], 2) == 26.85
    assert round(up[1], 2) == 80.95

    # City names
    jaipur = resolve_coordinates(location="Jaipur")
    assert jaipur is not None
    assert round(jaipur[0], 2) == 26.91
    assert round(jaipur[1], 2) == 75.79

    # Hindi city / state names
    lucknow_hi = resolve_coordinates(location="लखनऊ")
    assert lucknow_hi is not None
    assert round(lucknow_hi[0], 2) == 26.85


def test_resolve_coordinates_direct_coordinates():
    direct = resolve_coordinates(latitude=16.7749, longitude=74.0461)
    assert direct is not None
    assert direct[0] == 16.7749
    assert direct[1] == 74.0461


# =============================================================================
# 5, 6, 7. MISSING LOCATION & HITL LOCATION PROMPTS
# =============================================================================

def test_is_weather_query_detection():
    assert is_weather_query("What is the weather today?") is True
    assert is_weather_query("Give me a weather advisory and farming tips for my area.") is True
    assert is_weather_query("मेरे खेत के लिए मौसम की जानकारी और कृषि सलाह दें।") is True
    assert is_weather_query("Will it rain tomorrow in Barabanki?") is True
    assert is_weather_query("What is the temperature in Jaipur?") is True

    # Non-weather queries
    assert is_weather_query("What crop should I grow?") is False
    assert is_weather_query("My tomato leaves have yellow spots") is False
    assert is_weather_query("Analyze satellite farm environment at 26.8, 80.9") is False


def test_is_weather_location_missing():
    # Missing location
    assert is_weather_location_missing("What is the weather like?", {}) is True
    assert is_weather_location_missing("Give me a weather advisory", {"location": "Unknown"}) is True

    # Location provided in query
    assert is_weather_location_missing("What is the weather in Punjab?", {}) is False
    assert is_weather_location_missing("Weather in Barabanki", {}) is False

    # Location provided in profile
    assert is_weather_location_missing("What is the weather?", {"location": "Uttar Pradesh"}) is False
    assert is_weather_location_missing("What is the weather?", {"latitude": 26.85, "longitude": 80.95}) is False


@pytest.mark.asyncio
async def test_hitl_weather_location_clarification_en_and_hi():
    class MockContext:
        def __init__(self, query, profile):
            self.state = {"user_query": query, "farmer_profile": profile}
            self.resume_inputs = {}

    # English query without location
    ctx_en = MockContext(
        "Give me a weather advisory and farming tips for my area.",
        {"language": "English", "location": "Unknown"}
    )
    gen_en = _hitl_checkpoint_impl(ctx_en, {})
    items_en = [item async for item in gen_en]
    assert len(items_en) == 1
    assert isinstance(items_en[0], RequestInput)
    assert "Please share your State, District, or City" in items_en[0].message

    # Hindi query without location
    ctx_hi = MockContext(
        "मेरे खेत के लिए मौसम की जानकारी और कृषि सलाह दें।",
        {"language": "Hindi", "location": "Unknown"}
    )
    gen_hi = _hitl_checkpoint_impl(ctx_hi, {})
    items_hi = [item async for item in gen_hi]
    assert len(items_hi) == 1
    assert isinstance(items_hi[0], RequestInput)
    assert "राज्य, जिला या शहर" in items_hi[0].message


# =============================================================================
# 8. DATA / API FAILURE HANDLING (NO FAKE DATA)
# =============================================================================

def test_weather_advisory_api_failure_handling():
    with patch("app.weather_service.fetch_open_meteo_weather", return_value=None):
        # English failure message
        res_en = get_weather_advisory_impl(location="Lucknow", language="en")
        assert "⚠️ Live weather data is currently unavailable for Lucknow" in res_en
        assert "Punjab" not in res_en  # Old static mock is removed

        # Hindi failure message
        res_hi = get_weather_advisory_impl(location="Lucknow", language="hi")
        assert "लाइव मौसम डेटा उपलब्ध नहीं हो पा रहा है" in res_hi


# =============================================================================
# 9. MCP TOOL & OPTIONAL CROP PARAMETER
# =============================================================================

def test_mcp_get_weather_advisory_optional_crop():
    with patch("app.weather_service.fetch_open_meteo_weather", return_value=SAMPLE_OPEN_METEO_DATA):
        # Without crop parameter
        res1 = get_weather_advisory(location="Punjab")
        assert "Current Weather for Punjab:" in res1
        assert "3-Day Short-Term Forecast:" in res1

        # With crop parameter
        res2 = get_weather_advisory(location="Uttar Pradesh", crop="wheat", language="hi")
        assert "वर्तमान मौसम स्थिति" in res2


# =============================================================================
# 10 & 11. ISOLATION & LANGUAGE PRESERVATION
# =============================================================================

def test_weather_advisor_instruction_rules():
    instr = weather_advisor.instruction
    assert "get_weather_advisory" in instr
    assert "Do NOT generate complex chemical prescriptions" in instr
    assert "strictly in the target Output Language" in instr


def test_neutral_weather_location_preserves_hindi_language():
    # Proper nouns like "Lucknow", "Jaipur", "UP" do not flip Hindi session to English
    assert detect_language("Lucknow", default="Hindi") == "Hindi"
    assert detect_language("Jaipur", default="Hindi") == "Hindi"
    assert detect_language("Barabanki", default="Hindi") == "Hindi"
    assert detect_language("Punjab", default="Hindi") == "Hindi"
    assert detect_language("UP", default="Hindi") == "Hindi"
