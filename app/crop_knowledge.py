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
"""Deterministic agricultural crop-season knowledge layer for India.

Provides authoritative crop-season classifications and regional associations
to ground conversational crop reasoning without ungrounded LLM guessing.
"""

from dataclasses import dataclass, field
import datetime
from typing import Literal

SeasonType = Literal["Kharif", "Rabi", "Zaid"]


@dataclass(frozen=True)
class CropSeasonInfo:
    canonical_name: str
    aliases: list[str]
    primary_seasons: list[SeasonType]
    secondary_seasons: list[SeasonType] = field(default_factory=list)
    is_multi_season: bool = False
    region_notes: str = ""
    region_season_override: dict[str, SeasonType] = field(default_factory=dict)


# Authoritative database of major Indian agricultural crops and verified seasonal cycles
CROP_SEASON_DATABASE: list[CropSeasonInfo] = [
    # ── Cereals & Food Grains ──────────────────────────────────────────────
    CropSeasonInfo(
        canonical_name="rice",
        aliases=["rice", "paddy", "चावल", "धान"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Rabi"],  # Boro/summer rice in WB, Assam, Odisha, South
        is_multi_season=True,
        region_notes="Predominantly Kharif across North, Central, and Gangetic plains (e.g. UP, Punjab, Haryana, Bihar). Grown as Rabi/Boro in WB, Odisha, and southern irrigated belts.",
    ),
    CropSeasonInfo(
        canonical_name="wheat",
        aliases=["wheat", "गेहूं", "गेहूँ"],
        primary_seasons=["Rabi"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Strictly a Rabi (winter) crop across North, Central, and Western India (Punjab, Haryana, UP, MP, Rajasthan, Bihar).",
    ),
    CropSeasonInfo(
        canonical_name="barley",
        aliases=["barley", "जौ"],
        primary_seasons=["Rabi"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Rabi cereal grown across Rajasthan, UP, Haryana, and MP.",
    ),
    CropSeasonInfo(
        canonical_name="maize",
        aliases=["maize", "corn", "मक्का", "मक्की"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Rabi"],
        is_multi_season=True,
        region_notes="Primarily Kharif across Karnataka, MP, Rajasthan, Maharashtra; also cultivated as high-yielding Rabi maize in Bihar, AP, and Tamil Nadu.",
    ),
    CropSeasonInfo(
        canonical_name="sorghum",
        aliases=["sorghum", "jowar", "ज्वार"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Rabi"],
        is_multi_season=True,
        region_notes="Kharif in North/Central India; important Rabi crop in Maharashtra and Karnataka.",
    ),
    CropSeasonInfo(
        canonical_name="bajra",
        aliases=["bajra", "pearl millet", "बाजरा"],
        primary_seasons=["Kharif"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Predominantly Kharif crop suited for arid/semi-arid regions of Rajasthan, Gujarat, Haryana, UP, and Maharashtra.",
    ),

    # ── Pulses / Legumes ───────────────────────────────────────────────────
    CropSeasonInfo(
        canonical_name="chickpea",
        aliases=["chickpea", "gram", "chana", "चना"],
        primary_seasons=["Rabi"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Major Rabi pulse in MP, Maharashtra, Rajasthan, UP, and Karnataka.",
    ),
    CropSeasonInfo(
        canonical_name="pigeonpea",
        aliases=["pigeonpea", "tur", "arhar", "अरहर", "तुअर"],
        primary_seasons=["Kharif"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Long-duration Kharif pulse grown in Maharashtra, MP, Karnataka, UP, and Gujarat.",
    ),
    CropSeasonInfo(
        canonical_name="moong",
        aliases=["moong", "green gram", "मूंग"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Zaid"],
        is_multi_season=True,
        region_notes="Grown in Kharif across Rajasthan, Maharashtra, MP; widely cultivated as short-duration Summer Moong (Zaid) in irrigated plains (UP, Punjab, Haryana, Bihar).",
    ),
    CropSeasonInfo(
        canonical_name="summer_moong",
        aliases=["summer moong", "zaid moong", "ग्रीष्मकालीन मूंग"],
        primary_seasons=["Zaid"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Short-duration catch crop sown after Rabi harvest in March-April.",
    ),
    CropSeasonInfo(
        canonical_name="urad",
        aliases=["urad", "black gram", "उड़द"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Rabi", "Zaid"],
        is_multi_season=True,
        region_notes="Primarily Kharif in MP, UP, Rajasthan; Rabi in rice fallows of Andhra Pradesh, Tamil Nadu.",
    ),
    CropSeasonInfo(
        canonical_name="lentil",
        aliases=["lentil", "masoor", "मसूर"],
        primary_seasons=["Rabi"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Rabi pulse in UP, MP, Bihar, and West Bengal.",
    ),
    CropSeasonInfo(
        canonical_name="peas",
        aliases=["peas", "matar", "field pea", "मटर"],
        primary_seasons=["Rabi"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Cool-season Rabi crop grown across UP, MP, Punjab, and Bihar.",
    ),

    # ── Oilseeds ───────────────────────────────────────────────────────────
    CropSeasonInfo(
        canonical_name="mustard",
        aliases=["mustard", "sarson", "rapeseed", "toria", "सरसों", "राई"],
        primary_seasons=["Rabi"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Key winter Rabi oilseed in Rajasthan, UP, Haryana, MP, and Gujarat.",
    ),
    CropSeasonInfo(
        canonical_name="soybean",
        aliases=["soybean", "soya", "सोयाबीन"],
        primary_seasons=["Kharif"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Major rainfed Kharif oilseed in MP, Maharashtra, Rajasthan, and Karnataka.",
    ),
    CropSeasonInfo(
        canonical_name="groundnut",
        aliases=["groundnut", "peanut", "mungfali", "मूंगफली"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Rabi"],
        is_multi_season=True,
        region_notes="Kharif in Gujarat, Rajasthan, MP; Rabi/summer groundnut in AP, Tamil Nadu, Karnataka, and Odisha.",
    ),

    # ── Commercial & Cash Crops ────────────────────────────────────────────
    CropSeasonInfo(
        canonical_name="cotton",
        aliases=["cotton", "kapas", "कपास"],
        primary_seasons=["Kharif"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Long-duration Kharif cash crop in Gujarat, Maharashtra, Telangana, Punjab, Haryana, and Rajasthan.",
    ),
    CropSeasonInfo(
        canonical_name="sugarcane",
        aliases=["sugarcane", "ganna", "गन्ना"],
        primary_seasons=["Kharif"],
        secondary_seasons=["Rabi"],
        is_multi_season=True,
        region_notes="Annual / perennial crop planted in Autumn (Rabi) or Spring/Kharif across UP, Maharashtra, Karnataka, and Tamil Nadu.",
    ),

    # ── Vegetables & Zaid Crops ───────────────────────────────────────────
    CropSeasonInfo(
        canonical_name="watermelon",
        aliases=["watermelon", "tarbooz", "तरबूज"],
        primary_seasons=["Zaid"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Zaid (summer) cucurbit sown in February-March across riverbeds and irrigated fields.",
    ),
    CropSeasonInfo(
        canonical_name="muskmelon",
        aliases=["muskmelon", "kharbooja", "खरबूजा"],
        primary_seasons=["Zaid"],
        secondary_seasons=[],
        is_multi_season=False,
        region_notes="Zaid summer fruit crop requiring warm, dry weather for ripening.",
    ),
    CropSeasonInfo(
        canonical_name="cucumber",
        aliases=["cucumber", "kheera", "खीरा"],
        primary_seasons=["Zaid"],
        secondary_seasons=["Kharif"],
        is_multi_season=True,
        region_notes="Popular Zaid vegetable; also grown during Kharif in frost-free regions.",
    ),
    CropSeasonInfo(
        canonical_name="potato",
        aliases=["potato", "aaloo", "aalu", "आलू"],
        primary_seasons=["Rabi"],
        secondary_seasons=["Kharif"],
        is_multi_season=True,
        region_notes="Major Rabi tuber in UP, West Bengal, Bihar, Punjab; Kharif crop in higher altitude hill regions.",
    ),
    CropSeasonInfo(
        canonical_name="onion",
        aliases=["onion", "pyaz", "pyaaz", "प्याज", "प्याज़"],
        primary_seasons=["Rabi"],
        secondary_seasons=["Kharif"],
        is_multi_season=True,
        region_notes="Rabi onion (main storage crop) across Maharashtra, MP, Gujarat; Kharif/Late-Kharif in Maharashtra and Karnataka.",
    ),
    CropSeasonInfo(
        canonical_name="tomato",
        aliases=["tomato", "tamatar", "टमाटर"],
        primary_seasons=["Rabi", "Kharif", "Zaid"],
        secondary_seasons=[],
        is_multi_season=True,
        region_notes="Multi-season horticultural vegetable cultivated year-round depending on local microclimate.",
    ),
]


def find_crop_info(crop_name: str) -> CropSeasonInfo | None:
    """Finds verified crop-season information by crop name or alias."""
    if not crop_name or not crop_name.strip():
        return None
    name_clean = crop_name.lower().strip()
    
    # 1. Exact match on canonical_name or exact alias
    for info in CROP_SEASON_DATABASE:
        if name_clean == info.canonical_name or any(name_clean == a.lower() for a in info.aliases):
            return info
            
    # 2. Substring match (longest alias first to prevent short aliases shadowing longer specific ones)
    sorted_db = sorted(
        CROP_SEASON_DATABASE,
        key=lambda x: max(len(a) for a in x.aliases),
        reverse=True
    )
    for info in sorted_db:
        if any(a.lower() in name_clean or name_clean in a.lower() for a in info.aliases):
            return info
    return None


def infer_primary_season(crop_name: str, region: str | None = None) -> SeasonType | None:
    """Deterministically infers the primary agricultural season for a crop in a given region.

    Args:
        crop_name: Name of the crop (e.g., 'rice', 'wheat', 'mustard', 'soybean').
        region: Optional state or region (e.g., 'Uttar Pradesh', 'Punjab', 'Rajasthan').

    Returns:
        SeasonType ('Kharif', 'Rabi', or 'Zaid') or None if unknown/unresolvable.
    """
    info = find_crop_info(crop_name)
    if not info:
        return None

    if region and info.region_season_override:
        reg_clean = region.lower().strip()
        for reg_key, season in info.region_season_override.items():
            if reg_key.lower() in reg_clean:
                return season

    # Check primary season list
    if info.primary_seasons:
        return info.primary_seasons[0]

    return None


def is_single_primary_season_crop(crop_name: str, region: str | None = None) -> bool:
    """Returns True if the crop has a single dominant seasonal cycle in the region.

    For example, Wheat, Mustard, Soybean, Cotton, and Rice in Northern/Gangetic India
    have one dominant cultivation window.
    """
    info = find_crop_info(crop_name)
    if not info:
        return False

    # Check for dominant regional patterns
    reg_clean = (region or "").lower()
    gangetic_north = ["uttar pradesh", "punjab", "haryana", "bihar", "rajasthan", "madhya pradesh", "up", "mp"]

    if info.canonical_name == "rice":
        if any(g in reg_clean for g in gangetic_north) or not reg_clean:
            return True  # Strictly Kharif in North/Central plains

    if not info.is_multi_season:
        return True

    return False


def get_current_calendar_season(ref_date: datetime.date | None = None) -> SeasonType:
    """Returns the current agricultural calendar season in India based on month.

    - Kharif: June to October (Monsoon sowing)
    - Rabi: November to March (Winter sowing)
    - Zaid: April to May (Summer pre-monsoon)
    """
    if ref_date is None:
        ref_date = datetime.date.today()

    month = ref_date.month
    if 6 <= month <= 10:
        return "Kharif"
    elif month >= 11 or month <= 3:
        return "Rabi"
    else:
        return "Zaid"
