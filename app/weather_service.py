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
"""Live Weather Service using Open-Meteo Public API.

Provides lightweight current weather conditions and 3-day short-term forecasts
for Indian agricultural locations.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# ── Centroid coordinates for Indian States, UTs, and key farming districts ────
INDIAN_LOCATION_COORDINATES: dict[str, tuple[float, float]] = {
    # States & Capitals / Centroids
    "andhra pradesh": (15.9129, 79.7400),
    "ap": (15.9129, 79.7400),
    "arunachal pradesh": (28.2180, 94.7278),
    "assam": (26.2006, 92.9376),
    "bihar": (25.0961, 85.3131),
    "chhattisgarh": (21.2787, 81.8661),
    "goa": (15.2993, 74.1240),
    "gujarat": (22.2587, 71.1924),
    "haryana": (29.0588, 76.0856),
    "himachal pradesh": (31.1048, 77.1734),
    "jharkhand": (23.6102, 85.2799),
    "karnataka": (15.3173, 75.7139),
    "kerala": (10.8505, 76.2711),
    "madhya pradesh": (22.9734, 78.6569),
    "mp": (22.9734, 78.6569),
    "maharashtra": (19.7515, 75.7139),
    "manipur": (24.6637, 93.9063),
    "meghalaya": (25.4670, 91.3662),
    "mizoram": (23.1645, 92.9376),
    "nagaland": (26.1584, 94.5624),
    "odisha": (20.9517, 85.0985),
    "punjab": (31.1471, 75.3412),
    "rajasthan": (27.0238, 74.2179),
    "sikkim": (27.5330, 88.5122),
    "tamil nadu": (11.1271, 78.6569),
    "telangana": (18.1124, 79.0193),
    "tripura": (23.9408, 91.9882),
    "uttar pradesh": (26.8467, 80.9462),
    "up": (26.8467, 80.9462),
    "uttarakhand": (30.0668, 79.0193),
    "west bengal": (22.9868, 87.8550),
    # Union Territories
    "delhi": (28.7041, 77.1025),
    "chandigarh": (30.7333, 76.7794),
    "jammu and kashmir": (33.7782, 76.5762),
    "jammu": (32.7266, 74.8570),
    "kashmir": (34.0837, 74.7973),
    "srinagar": (34.0837, 74.7973),
    "ladakh": (34.1526, 77.5771),
    "puducherry": (11.9416, 79.8083),
    # Major Agricultural Districts & Cities
    "lucknow": (26.8467, 80.9462),
    "barabanki": (26.9268, 81.1834),
    "varanasi": (25.3176, 82.9739),
    "kanpur": (26.4499, 80.3319),
    "ludhiana": (30.9010, 75.8573),
    "amritsar": (31.6340, 74.8723),
    "karnal": (29.6857, 76.9905),
    "jaipur": (26.9124, 75.7873),
    "jodhpur": (26.2389, 73.0243),
    "kota": (25.2138, 75.8648),
    "indore": (22.7196, 75.8577),
    "bhopal": (23.2599, 77.4126),
    "nagpur": (21.1458, 79.0882),
    "pune": (18.5204, 73.8567),
    "nashik": (19.9975, 73.7898),
    "ahmedabad": (23.0225, 72.5714),
    "surat": (21.1702, 72.8311),
    "rajkot": (22.3039, 70.8022),
    "patna": (25.5941, 85.1376),
    "gaya": (24.7914, 85.0002),
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "mysuru": (12.2958, 76.6394),
    "mysore": (12.2958, 76.6394),
    "hyderabad": (17.3850, 78.4867),
    "warangal": (17.9689, 79.5941),
    "chennai": (13.0827, 80.2707),
    "coimbatore": (11.0168, 76.9558),
    "madurai": (9.9252, 78.1198),
    "kolkata": (22.5726, 88.3639),
    "bardhaman": (23.2324, 87.8615),
    "bhubaneswar": (20.2961, 85.8245),
    "cuttack": (20.4625, 85.8828),
    "raipur": (21.2514, 81.6296),
    "ranchi": (23.3441, 85.3096),
    # Hindi mappings
    "उत्तर प्रदेश": (26.8467, 80.9462),
    "यूपी": (26.8467, 80.9462),
    "पंजाब": (31.1471, 75.3412),
    "हरियाणा": (29.0588, 76.0856),
    "राजस्थान": (27.0238, 74.2179),
    "मध्य प्रदेश": (22.9734, 78.6569),
    "एमपी": (22.9734, 78.6569),
    "महाराष्ट्र": (19.7515, 75.7139),
    "बिहार": (25.0961, 85.3131),
    "गुजरात": (22.2587, 71.1924),
    "कर्नाटक": (15.3173, 75.7139),
    "तमिलनाडु": (11.1271, 78.6569),
    "पश्चिम बंगाल": (22.9868, 87.8550),
    "लखनऊ": (26.8467, 80.9462),
    "बाराबंकी": (26.9268, 81.1834),
    "जयपुर": (26.9124, 75.7873),
    "भोपाल": (23.2599, 77.4126),
    "पटना": (25.5941, 85.1376),
}

# ── WMO Weather Code Descriptions ─────────────────────────────────────────────
WMO_WEATHER_CODES: dict[int, dict[str, str]] = {
    0: {"en": "Clear sky", "hi": "साफ आसमान"},
    1: {"en": "Mainly clear", "hi": "मुख्य रूप से साफ"},
    2: {"en": "Partly cloudy", "hi": "आंशिक रूप से बादल"},
    3: {"en": "Overcast", "hi": "घने बादल"},
    45: {"en": "Foggy", "hi": "कोहरा"},
    48: {"en": "Depositing rime fog", "hi": "घना कोहरा"},
    51: {"en": "Light drizzle", "hi": "हल्की बूंदाबांदी"},
    53: {"en": "Moderate drizzle", "hi": "मध्यम बूंदाबांदी"},
    55: {"en": "Dense drizzle", "hi": "तेज बूंदाबांदी"},
    61: {"en": "Slight rain", "hi": "हल्की बारिश"},
    63: {"en": "Moderate rain", "hi": "मध्यम बारिश"},
    65: {"en": "Heavy rain", "hi": "भारी बारिश"},
    71: {"en": "Slight snow", "hi": "हल्की बर्फबारी"},
    73: {"en": "Moderate snow", "hi": "मध्यम बर्फबारी"},
    75: {"en": "Heavy snow", "hi": "भारी बर्फबारी"},
    80: {"en": "Slight rain showers", "hi": "हल्की बारिश की बौछारें"},
    81: {"en": "Moderate rain showers", "hi": "मध्यम बारिश की बौछारें"},
    82: {"en": "Violent rain showers", "hi": "तेज बारिश की बौछारें"},
    95: {"en": "Thunderstorm", "hi": "गरज-चमक के साथ तूफान"},
    96: {"en": "Thunderstorm with slight hail", "hi": "ओलावृष्टि के साथ आंधी"},
    99: {"en": "Thunderstorm with heavy hail", "hi": "भारी ओलावृष्टि व तूफान"},
}


def resolve_coordinates(
    location: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[float, float, str] | None:
    """Resolves latitude, longitude, and matched location name from input parameters."""
    if latitude is not None and longitude is not None:
        try:
            lat = float(latitude)
            lon = float(longitude)
            if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                loc_name = location.strip() if location else f"{lat:.2f}, {lon:.2f}"
                return lat, lon, loc_name
        except (ValueError, TypeError):
            pass

    if not location or not location.strip():
        return None

    clean_loc = location.strip().lower()
    # 1. Exact match in Indian coordinates dictionary
    if clean_loc in INDIAN_LOCATION_COORDINATES:
        lat, lon = INDIAN_LOCATION_COORDINATES[clean_loc]
        return lat, lon, location.strip().title()

    # 2. Substring match
    for key, (lat, lon) in INDIAN_LOCATION_COORDINATES.items():
        if key in clean_loc or clean_loc in key:
            return lat, lon, key.title()

    return None


def fetch_open_meteo_weather(lat: float, lon: float, timeout_seconds: float = 6.0) -> dict[str, Any] | None:
    """Fetches live current weather and 3-day forecast from Open-Meteo API.
    
    Returns raw JSON dict or None if request fails.
    """
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{lon:.4f}",
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
        "timezone": "auto",
        "forecast_days": "4",
    }
    url = f"https://api.open-meteo.com/v1/forecast?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "BharatSahayak-Weather/1.0 (agri-companion)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            if response.status == 200:
                content = response.read().decode("utf-8")
                return json.loads(content)
    except Exception as exc:
        logger.warning("Open-Meteo API request failed for (%s, %s): %s", lat, lon, exc)
        return None


def format_weather_forecast_text(
    data: dict[str, Any],
    location_name: str,
    crop: str = "",
    language: str = "en",
) -> str:
    """Formats Open-Meteo weather JSON into clean, farmer-friendly structured text."""
    is_hindi = language.lower().startswith("hi")
    current = data.get("current", {})
    daily = data.get("daily", {})

    temp = current.get("temperature_2m", "N/A")
    humidity = current.get("relative_humidity_2m", "N/A")
    precip = current.get("precipitation", 0.0)
    wind = current.get("wind_speed_10m", "N/A")
    code = current.get("weather_code", 0)

    cond_info = WMO_WEATHER_CODES.get(code, {"en": "Clear", "hi": "साफ"})
    current_cond = cond_info["hi"] if is_hindi else cond_info["en"]

    lines: list[str] = []
    if is_hindi:
        lines.append(f"🌦 {location_name} के लिए वर्तमान मौसम स्थिति:")
        lines.append(f"• तापमान: {temp}°C")
        lines.append(f"• मौसम: {current_cond}")
        lines.append(f"• आर्द्रता (नमी): {humidity}%")
        lines.append(f"• वर्षा: {precip} mm")
        lines.append(f"• हवा की गति: {wind} km/h")
        lines.append("")
        lines.append("📅 आगामी 3 दिनों का मौसम पूर्वानुमान:")
    else:
        lines.append(f"🌦 Current Weather for {location_name}:")
        lines.append(f"• Temperature: {temp}°C")
        lines.append(f"• Condition: {current_cond}")
        lines.append(f"• Humidity: {humidity}%")
        lines.append(f"• Precipitation: {precip} mm")
        lines.append(f"• Wind Speed: {wind} km/h")
        lines.append("")
        lines.append("📅 3-Day Short-Term Forecast:")

    dates = daily.get("time", [])
    t_max = daily.get("temperature_2m_max", [])
    t_min = daily.get("temperature_2m_min", [])
    w_codes = daily.get("weather_code", [])
    pop_max = daily.get("precipitation_probability_max", [])
    p_sum = daily.get("precipitation_sum", [])

    # Process next 3 days (excluding or starting from tomorrow)
    count = min(3, len(dates) - 1 if len(dates) > 1 else len(dates))
    start_idx = 1 if len(dates) > 3 else 0

    max_rain_expected = False
    for i in range(count):
        idx = start_idx + i
        if idx >= len(dates):
            break
        d_str = dates[idx]
        d_min = t_min[idx] if idx < len(t_min) else "N/A"
        d_max = t_max[idx] if idx < len(t_max) else "N/A"
        d_code = w_codes[idx] if idx < len(w_codes) else 0
        d_pop = pop_max[idx] if idx < len(pop_max) else 0
        d_psum = p_sum[idx] if idx < len(p_sum) else 0.0

        if (isinstance(d_pop, (int, float)) and d_pop >= 40) or (isinstance(d_psum, (int, float)) and d_psum > 2.0):
            max_rain_expected = True

        d_cond_info = WMO_WEATHER_CODES.get(d_code, {"en": "Fair", "hi": "सामान्य"})
        d_cond = d_cond_info["hi"] if is_hindi else d_cond_info["en"]

        if is_hindi:
            day_label = f"दिन {i+1} ({d_str})"
            lines.append(f"• {day_label}: {d_min}°C से {d_max}°C | {d_cond} | वर्षा की संभावना: {d_pop}% ({d_psum} mm)")
        else:
            day_label = f"Day {i+1} ({d_str})"
            lines.append(f"• {day_label}: {d_min}°C to {d_max}°C | {d_cond} | Rain Chance: {d_pop}% ({d_psum} mm)")

    lines.append("")
    # Practical farming alert note
    if is_hindi:
        lines.append("💡 कृषि मौसम सुझाव:")
        if max_rain_expected:
            lines.append("• अगले कुछ दिनों में वर्षा की संभावना है। कीटनाशक छिड़काव या अतिरिक्त सिंचाई स्थगित रखें।")
        else:
            lines.append("• मौसम सामान्य व अनुकूल रहने की संभावना है। खेत की आवश्यकतानुसार नियमित कार्य जारी रखें।")
    else:
        lines.append("💡 Practical Farming Weather Note:")
        if max_rain_expected:
            lines.append("• Rain is expected in the upcoming days. Consider postponing scheduled spraying and adjust irrigation accordingly.")
        else:
            lines.append("• Weather conditions appear stable. Regular fieldwork, weeding, and scheduled irrigation can proceed normally.")

    return "\n".join(lines).strip()


def get_weather_advisory_impl(
    location: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    crop: str = "",
    language: str = "en",
) -> str:
    """Main implementation for fetching live weather advisory for a farmer."""
    coords = resolve_coordinates(location=location, latitude=latitude, longitude=longitude)
    if not coords:
        if language.lower().startswith("hi"):
            return (
                "🌦 मौसम पूर्वानुमान के लिए स्थान की पहचान नहीं हो सकी। "
                "कृपया अपना राज्य, जिला या शहर बताएं (जैसे: उत्तर प्रदेश, पंजाब, जयपुर, लखनऊ)।"
            )
        return (
            "Could not determine coordinates for the requested location. "
            "Please specify your State, District, or City (e.g., Punjab, Uttar Pradesh, Jaipur, Lucknow) "
            "to get the local weather forecast."
        )

    lat, lon, resolved_name = coords
    data = fetch_open_meteo_weather(lat=lat, lon=lon)
    if not data:
        if language.lower().startswith("hi"):
            return (
                f"⚠️ वर्तमान में {resolved_name} के लिए लाइव मौसम डेटा उपलब्ध नहीं हो पा रहा है। "
                "कृपया कुछ देर बाद पुनः प्रयास करें।"
            )
        return (
            f"⚠️ Live weather data is currently unavailable for {resolved_name}. "
            "Please try again in a few moments."
        )

    return format_weather_forecast_text(
        data=data,
        location_name=resolved_name,
        crop=crop,
        language=language,
    )
