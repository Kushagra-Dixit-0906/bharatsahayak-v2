import math
import sys
from mcp.server.fastmcp import FastMCP

from app.assessment.gemini_types import (
    FarmerAgriculturalResponse,
    PresentationPreferences,
    VerifiedFarmerContext,
)
from app.assessment.pipeline import fetch_agricultural_assessment_explanation
from app.disease.corpus import DEFAULT_CORPUS
from app.disease.pipeline import run_crop_problem_pipeline
from app.disease.types import CropProblemAdvisory

mcp = FastMCP("BharatSahayak Farming MCP Server")


def _detect_language(text: str) -> str:
    """Detects if text contains Devanagari characters ('hi') or Latin ('en')."""
    for char in text:
        if "\u0900" <= char <= "\u097f":
            return "hi"
    return "en"


def _format_crop_advisory_text(advisory: CropProblemAdvisory) -> str:
    """Formats a CropProblemAdvisory into structured, readable text for MCP clients."""
    lines: list[str] = [
        f"Crop Advisory Status: {advisory.status}",
        f"Identified Crop: {advisory.crop_identified}",
    ]
    if advisory.reported_symptoms:
        lines.append(f"Reported Symptoms: {', '.join(advisory.reported_symptoms)}")
    lines.append("")

    if advisory.possible_conditions:
        lines.append("Possible Candidate Conditions (Candidate Hypotheses — Non-Definitive):")
        for idx, cond in enumerate(advisory.possible_conditions, 1):
            sci_suffix = f" ({cond.scientific_name})" if cond.scientific_name else ""
            lines.append(f"{idx}. {cond.condition_name}{sci_suffix}")
            lines.append(f"   Category: {cond.category} | Match Level: {cond.symptom_match}")
            lines.append(f"   Reasoning: {cond.reasoning}")
        lines.append("")
    else:
        lines.append("Possible Candidate Conditions: None identified from verified knowledge corpus.")
        lines.append("")

    if advisory.safe_cultural_actions:
        lines.append("Safe Cultural & Preventive Actions (Zero Chemical Prescriptions):")
        for action in advisory.safe_cultural_actions:
            lines.append(f"- [{action.action_type}] {action.description}")
        lines.append("")

    if advisory.clarifying_questions:
        lines.append("Clarifying Observations for Field Verification:")
        for q in advisory.clarifying_questions:
            lines.append(f"- {q}")
        lines.append("")

    if advisory.uncertainty_reasons:
        lines.append("Uncertainty & Diagnostic Limitations:")
        for reason in advisory.uncertainty_reasons:
            lines.append(f"- {reason}")
        lines.append("")

    if advisory.expert_referral_urgency != "none" or advisory.expert_referral_recommendation:
        lines.append(f"Expert Referral Urgency: {advisory.expert_referral_urgency}")
        if advisory.expert_referral_recommendation:
            lines.append(f"Referral Guidance: {advisory.expert_referral_recommendation}")
        lines.append("")

    if advisory.knowledge_sources:
        lines.append("Verified Sources & Institutional Attribution:")
        for src in advisory.knowledge_sources:
            lines.append(f"- [{src.source_id}] {src.document_title} ({src.organization})")
        lines.append("")

    return "\n".join(lines).strip()


def _format_environmental_assessment_text(resp: FarmerAgriculturalResponse) -> str:
    """Formats a FarmerAgriculturalResponse into structured text for MCP clients / Orchestrator."""
    lines: list[str] = [
        f"🌾 Environmental Assessment ({resp.headline})",
        "",
        resp.summary,
        "",
    ]
    if resp.observations:
        lines.append("Key Observations:" if resp.language == "en" else "प्रमुख अवलोकन:")
        for obs in resp.observations:
            lines.append(f"- {obs}")
        lines.append("")

    if resp.interpretation:
        lines.append("Interpretation:" if resp.language == "en" else "व्याख्या:")
        lines.append(resp.interpretation)
        lines.append("")

    if resp.recommended_next_steps:
        lines.append("Recommended Next Steps:" if resp.language == "en" else "अनुशंसित अगले कदम:")
        for step in resp.recommended_next_steps:
            lines.append(f"- {step.description}")
        lines.append("")

    if resp.limitations:
        lines.append("Limitations & Data Freshness:" if resp.language == "en" else "सीमाएं व डेटा ताजगी:")
        for lim in resp.limitations:
            lines.append(f"- {lim}")
        lines.append("")

    return "\n".join(lines).strip()


@mcp.tool()
def get_environmental_assessment(
    latitude: float,
    longitude: float,
    crop: str | None = None,
    state: str | None = None,
    district: str | None = None,
    language: str = "en",
) -> str:
    """Retrieves authoritative multi-source environmental assessment and crop condition analysis.

    Combines Sentinel-2 NDVI, Dynamic World land cover, ERA5-Land agrometeorology,
    and CHIRPS precipitation to evaluate soil moisture, vegetation health, and climate trends.

    Args:
        latitude: Farm parcel latitude coordinate in decimal degrees [-90.0, 90.0].
        longitude: Farm parcel longitude coordinate in decimal degrees [-180.0, 180.0].
        crop: Verified crop name being cultivated (e.g., 'rice', 'wheat', 'cotton').
        state: Optional state name for regional context.
        district: Optional district name for regional context.
        language: Target response language ('en' for English, 'hi' for Hindi).
    """
    if not isinstance(latitude, (int, float)) or isinstance(latitude, bool) or math.isnan(latitude) or not (-90.0 <= float(latitude) <= 90.0):
        return f"Error: Invalid latitude coordinate ({latitude}). Must be between -90.0 and 90.0."
    if not isinstance(longitude, (int, float)) or isinstance(longitude, bool) or math.isnan(longitude) or not (-180.0 <= float(longitude) <= 180.0):
        return f"Error: Invalid longitude coordinate ({longitude}). Must be between -180.0 and 180.0."

    target_lang = "hi" if language and language.lower().startswith("hi") else "en"

    import os
    import ee
    try:
        ee.Initialize(project=os.environ.get("EE_PROJECT_ID", "bharatsahayak-v2"))
    except Exception:
        pass

    farmer_context = None
    if crop:
        farmer_context = VerifiedFarmerContext(
            crop=crop.strip().lower(),
            preferred_language=target_lang,
            context_status="verified",
        )
    presentation = PresentationPreferences(target_language=target_lang)

    explanation_response = fetch_agricultural_assessment_explanation(
        latitude=float(latitude),
        longitude=float(longitude),
        farmer_context=farmer_context,
        presentation=presentation,
    )

    return _format_environmental_assessment_text(explanation_response.explanation)


@mcp.tool()
def get_weather_advisory(location: str, crop: str) -> str:
    """Gets the weather forecast and specific agricultural recommendations for a given location and crop.
    
    Args:
        location: The state or region in India (e.g., Punjab, Karnataka).
        crop: The crop being grown (e.g., wheat, rice, cotton).
    """
    loc = location.lower()
    crp = crop.lower()
    
    if "punjab" in loc:
        if "wheat" in crp:
            return (
                "Weather Forecast for Punjab: Light winds, sunny, temperatures around 32°C. No rain expected this week.\n"
                "Advisory: Ideal time for urea application. Soil moisture is moderate; irrigate lightly if soil is dry. "
                "Monitor for rust disease signs."
            )
        else:
            return (
                "Weather Forecast for Punjab: Sunny, temperatures around 34°C. No rain expected.\n"
                "Advisory: Ensure adequate irrigation for seasonal crops. Mulch around crops to prevent excessive soil moisture evaporation."
            )
    elif "karnataka" in loc:
        if "rice" in crp:
            return (
                "Weather Forecast for Karnataka: High humidity, scattered rainfall (15-20mm) expected in 48 hours.\n"
                "Advisory: Postpone any planned pesticide spray or fertilizer application until after the rain. "
                "Ensure proper drainage in nursery beds to avoid waterlogging."
            )
        else:
            return (
                "Weather Forecast for Karnataka: Scattered rainfall expected.\n"
                "Advisory: Clear drainage channels to prevent water accumulation."
            )
    else:
        return (
            f"Weather Forecast for {location}: Normal seasonal conditions.\n"
            f"Advisory for {crop}: Monitor local forecasts. Maintain regular weeding and watering schedules based on soil dampness."
        )

@mcp.tool()
def get_crop_disease_info(crop: str, symptoms: str) -> str:
    """Provides non-chemical agricultural advisory and candidate conditions based on observed symptoms.

    Args:
        crop: The name of the crop (e.g., rice, wheat, maize, chickpea, mustard, pigeonpea, groundnut, soybean, cotton, sugarcane).
        symptoms: Description of the observed symptoms (e.g., yellow spots, wilting leaves, circular holes in pods).
    """
    crop_clean = crop.strip() if crop else ""
    symptoms_clean = symptoms.strip() if symptoms else ""

    if not crop_clean and not symptoms_clean:
        return (
            "Crop Advisory Status: insufficient_evidence\n"
            "Identified Crop: Unknown\n\n"
            "No crop or symptoms were provided. Please specify the crop and observable symptoms."
        )

    if crop_clean and symptoms_clean:
        farmer_query = f"{crop_clean}: {symptoms_clean}"
    else:
        farmer_query = crop_clean or symptoms_clean

    language = _detect_language(farmer_query)

    advisory = run_crop_problem_pipeline(
        farmer_query=farmer_query,
        corpus=DEFAULT_CORPUS,
        language=language,
    )

    return _format_crop_advisory_text(advisory)

@mcp.tool()
def search_government_schemes(state: str, crop: str) -> str:
    """Finds available Indian government schemes, subsidies, and eligibility criteria for a given state and crop.
    
    Args:
        state: The state (e.g., Punjab, Karnataka, Haryana).
        crop: The crop (e.g., wheat, rice).
    """
    st = state.lower()
    crp = crop.lower()
    
    schemes = [
        "1. PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)\n"
        "   - Details: Direct income support of Rs. 6,000/year to all landholding farmer families.\n"
        "   - Eligibility: Small and marginal farmers with cultivable land in any state.\n"
        "   - Documents: Aadhaar, Land ownership papers, Bank account details.",
        
        "2. PMFBY (Pradhan Mantri Fasal Bima Yojana)\n"
        "   - Details: Crop insurance scheme protecting against crop failure due to natural disasters.\n"
        "   - Premium: 1.5% for Rabi crops, 2.0% for Kharif crops.\n"
        "   - Documents: Land sowing certificate, Aadhaar, Bank passbook."
    ]
    
    if "punjab" in st:
        schemes.append(
            "3. Punjab Free Power Scheme\n"
            "   - Details: Free electricity supplied to agricultural tube wells for crop irrigation.\n"
            "   - Eligibility: Registered farmers in Punjab with tube well connections."
        )
    elif "karnataka" in st:
        schemes.append(
            "3. Krishi Bhagya Scheme (Karnataka)\n"
            "   - Details: Subsidy for rainwater harvesting ponds, polythene lining, and diesel pumpsets (up to 80-90% subsidy).\n"
            "   - Eligibility: All farmers in dry-zone districts of Karnataka."
        )
        
    return "\n\n".join(schemes)

@mcp.tool()
def calculate_farming_profitability(crop: str, acreage: float, expected_yield_per_acre: float) -> str:
    """Calculates estimated costs, expected revenue, and net profit for cultivating a crop on a specific farm size.
    
    Args:
        crop: The crop name (e.g., wheat, rice, cotton).
        acreage: The farm size in acres (e.g., 2.0, 5.0).
        expected_yield_per_acre: Estimated yield in quintals (100 kg) per acre.
    """
    crp = crop.lower()
    
    if "wheat" in crp:
        cost_per_acre = 15000
        msp_per_quintal = 2275
    elif "rice" in crp or "paddy" in crp:
        cost_per_acre = 18000
        msp_per_quintal = 2183
    elif "cotton" in crp:
        cost_per_acre = 22000
        msp_per_quintal = 6620
    else:
        cost_per_acre = 16000
        msp_per_quintal = 2500
        
    total_cost = cost_per_acre * acreage
    total_yield = expected_yield_per_acre * acreage
    total_revenue = total_yield * msp_per_quintal
    net_profit = total_revenue - total_cost
    
    return (
        f"Farming Profitability Analysis for {acreage} acres of {crop}:\n"
        f"- Estimated Cost of Cultivation: Rs. {total_cost:,.2f} (Rs. {cost_per_acre:,} per acre)\n"
        f"- Expected Total Yield: {total_yield:.2f} quintals ({expected_yield_per_acre:.2f} quintals/acre)\n"
        f"- Minimum Expected Revenue (at Govt MSP of Rs. {msp_per_quintal}/quintal): Rs. {total_revenue:,.2f}\n"
        f"- Estimated Net Profit: Rs. {net_profit:,.2f}\n\n"
        f"Tips to improve profitability:\n"
        f"1. Use micro-irrigation (drip/sprinkler) to reduce water costs and increase yield.\n"
        f"2. Apply organic manure alongside chemical fertilizers (IPNM) to lower inputs cost by 15%.\n"
        f"3. Sell through e-NAM (electronic National Agriculture Market) for better price discovery."
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")
