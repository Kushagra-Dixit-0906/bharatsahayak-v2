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
    """Formats a CropProblemAdvisory into clean, farmer-friendly structured text without internal IDs."""
    crop_title = advisory.crop_identified if advisory.crop_identified and advisory.crop_identified.lower() != "unknown" else "Crop"
    lines: list[str] = [
        f"🌾 Crop Problem Advisory for {crop_title}:",
    ]
    if advisory.reported_symptoms:
        lines.append(f"Reported Symptoms: {', '.join(advisory.reported_symptoms)}")
    lines.append("")

    if advisory.possible_conditions:
        lines.append("Possible Candidate Conditions (Non-Definitive Hypotheses):")
        for idx, cond in enumerate(advisory.possible_conditions, 1):
            sci_suffix = f" ({cond.scientific_name})" if cond.scientific_name else ""
            lines.append(f"{idx}. {cond.condition_name}{sci_suffix}")
            lines.append(f"   Why to consider: {cond.reasoning}")
        lines.append("")
    else:
        lines.append("Possible Candidate Conditions: No matching condition identified from verified agricultural corpus.")
        lines.append("")

    if advisory.safe_cultural_actions:
        lines.append("Safe Cultural & Preventive Actions (What you can do now):")
        for action in advisory.safe_cultural_actions:
            lines.append(f"• {action.description}")
        lines.append("")

    if advisory.clarifying_questions:
        lines.append("What to check in your field:")
        for q in advisory.clarifying_questions:
            lines.append(f"• {q}")
        lines.append("")

    if advisory.uncertainty_reasons:
        lines.append("Diagnostic Limitations & Uncertainty:")
        for reason in advisory.uncertainty_reasons:
            lines.append(f"• {reason}")
        lines.append("")

    if advisory.expert_referral_recommendation or advisory.expert_referral_urgency != "none":
        lines.append("When to seek expert help:")
        if advisory.expert_referral_recommendation:
            lines.append(f"• {advisory.expert_referral_recommendation}")
        else:
            lines.append("• If symptoms spread rapidly across the field, collect a fresh plant sample and consult your local Krishi Vigyan Kendra (KVK) or Block Agriculture Officer.")
        lines.append("")

    if advisory.knowledge_sources:
        sources_str = ", ".join(f"{src.document_title} ({src.organization})" for src in advisory.knowledge_sources)
        lines.append(f"Verified Institutional References: {sources_str}")
        lines.append("")

    return "\n".join(lines).strip()


def _format_environmental_assessment_text(resp: FarmerAgriculturalResponse) -> str:
    """Formats a FarmerAgriculturalResponse into structured text for MCP clients / Orchestrator."""
    lines: list[str] = [
        f"🌾 {resp.headline}",
        "",
        resp.summary,
        "",
    ]
    if resp.observations:
        lines.append("Field Observations:" if resp.language == "en" else "खेत की स्थिति:")
        for obs in resp.observations:
            lines.append(f"• {obs}")
        lines.append("")

    if resp.interpretation:
        lines.append("What this means for your crop:" if resp.language == "en" else "आपकी फसल के लिए इसका क्या अर्थ है:")
        lines.append(resp.interpretation)
        lines.append("")

    if resp.recommended_next_steps:
        lines.append("Recommended Actions:" if resp.language == "en" else "सलाह और अगले कदम:")
        for step in resp.recommended_next_steps:
            lines.append(f"• {step.description}")
        lines.append("")

    if resp.limitations:
        lines.append("Limitations & Data Freshness:" if resp.language == "en" else "सीमाएं व डेटा ताजगी:")
        for lim in resp.limitations:
            lines.append(f"• {lim}")
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
        if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"],
                scopes=[
                    "https://www.googleapis.com/auth/earthengine",
                    "https://www.googleapis.com/auth/cloud-platform",
                ],
            )
            ee.Initialize(
                credentials=credentials,
                project=os.environ.get("EE_PROJECT_ID", "bharatsahayak-v2"),
            )
        else:
            ee.Initialize(
                project=os.environ.get("EE_PROJECT_ID", "bharatsahayak-v2")
            )
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
def get_weather_advisory(
    location: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    crop: str = "",
    language: str = "en",
) -> str:
    """Gets current weather conditions and a 3-day short-term forecast for an agricultural location.

    Args:
        location: The state, district, or city in India (e.g., Punjab, Uttar Pradesh, Jaipur, Lucknow).
        latitude: Optional latitude coordinate in decimal degrees.
        longitude: Optional longitude coordinate in decimal degrees.
        crop: Optional crop name being grown (e.g., wheat, rice, cotton).
        language: Response language ('en' for English, 'hi' for Hindi).
    """
    from app.weather_service import get_weather_advisory_impl
    return get_weather_advisory_impl(
        location=location,
        latitude=latitude,
        longitude=longitude,
        crop=crop,
        language=language,
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
            "🌾 Crop Problem Advisory:\n"
            "Identified Crop: Unknown / Not specified\n\n"
            "No crop or symptoms were provided. Please specify your crop and observed field symptoms (e.g., leaf spots, yellowing, wilting) so we can provide safe cultural guidance."
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
def search_government_schemes(state: str = "", crop: str = "", mode: str = "central") -> str:
    """Finds Indian government schemes, subsidies, and eligibility criteria.

    Call this tool in two distinct phases:
      1. mode="central"  — returns ONLY national/central schemes (e.g. PM-KISAN, PMFBY, KCC, PMKSY, eNAM).
      2. mode="state"    — returns ONLY state-specific programs for the given state.
         Do NOT repeat or include central schemes when mode="state".

    Args:
        state: Indian state or union territory name (required when mode="state").
        crop:  Crop name (optional — leave blank if not specified by the farmer).
        mode:  "central" for central/national schemes only (default),
               "state" for state-specific schemes only.
    """
    st  = (state or "").lower().strip()
    _crp = (crop or "").lower().strip()   # retained for future use; not required
    m   = (mode or "central").lower().strip()

    # ── Central / national schemes ────────────────────────────────────────────
    central_schemes = [
        "1. PM-KISAN (Pradhan Mantri Kisan Samman Nidhi)\n"
        "   - Details: Direct income support of ₹6,000/year in three equal instalments to all\n"
        "     landholding farmer families.\n"
        "   - Eligibility: All small and marginal farmers with cultivable land.\n"
        "   - Documents: Aadhaar, land ownership papers, bank account details.\n"
        "   - Apply: pmkisan.gov.in or nearest CSC / Krishi Vigyan Kendra.",

        "2. PMFBY (Pradhan Mantri Fasal Bima Yojana)\n"
        "   - Details: Crop insurance protecting against natural disasters, pests, and diseases.\n"
        "   - Premium: 1.5% for Rabi crops, 2.0% for Kharif crops, 5% for horticulture.\n"
        "   - Documents: Land sowing certificate, Aadhaar, bank passbook.\n"
        "   - Apply: Through your bank or insurance company at the start of the sowing season.",

        "3. KCC (Kisan Credit Card)\n"
        "   - Details: Revolving short-term credit (up to ₹3 lakh at 4% interest with timely repayment)\n"
        "     for seeds, fertilisers, pesticides, and post-harvest needs.\n"
        "   - Eligibility: All farmers, sharecroppers, oral lessees, and SHG members.\n"
        "   - Apply: Any nationalised bank, RRB, or cooperative bank.",

        "4. PMKSY (Pradhan Mantri Krishi Sinchayee Yojana)\n"
        "   - Details: Subsidises drip and sprinkler irrigation systems ('Har Khet Ko Pani').\n"
        "   - Benefit: Up to 55% subsidy for small/marginal farmers.\n"
        "   - Apply: State agriculture department or district collector office.",

        "5. eNAM (National Agriculture Market)\n"
        "   - Details: Online trading platform for agricultural commodities across 1,000+ mandis.\n"
        "   - Benefit: Better price discovery and reduced broker dependence.\n"
        "   - Apply: enam.gov.in — register through your local mandi.",
    ]

    # ── State-specific schemes ─────────────────────────────────────────────────
    state_entries: list[str] = []

    if "uttar pradesh" in st or st == "up":
        state_entries = [
            "📍 Uttar Pradesh — State-Specific Agricultural Support\n"
            "\n"
            "1. UP Mukhyamantri Krishak Durghatna Kalyan Yojana\n"
            "   - Details: ₹5 lakh compensation for accidental death of a farmer; ₹2–3 lakh for disability.\n"
            "   - Eligibility: Registered farmers aged 18–70 in Uttar Pradesh.\n"
            "   - Apply: Block agriculture office within 45 days of the accident.",

            "2. UP Kisan Karj Rahat Yojana (Debt Waiver)\n"
            "   - Details: One-time waiver of short-term crop loans up to ₹1 lakh for small and marginal farmers.\n"
            "   - Eligibility: UP farmers with outstanding Kisan Credit Card or crop loans as of a notified date.\n"
            "   - Apply: Your district cooperative bank or Gram Sabh.",

            "3. Paramparagat Krishi Vikas Yojana (PKVY) — UP cluster subsidy\n"
            "   - Details: UP channels central PKVY funds; clusters of 50 farmers get ₹50,000/ha for organic\n"
            "     certification, inputs, and capacity-building over 3 years.\n"
            "   - Apply: UP Agriculture Department (upagriculture.com).",

            "4. UP Solar Pump Yojana\n"
            "   - Details: 70–90% subsidy on solar-powered irrigation pumps (up to 10 HP) under the\n"
            "     PM-KUSUM component B scheme administered by UP.\n"
            "   - Eligibility: All UP farmers with agricultural land.\n"
            "   - Apply: upagriculture.com or nearest district agriculture office.",

            "5. UP Gehu/Dhan Kharid (Wheat & Paddy Procurement)\n"
            "   - Details: Government procurement of wheat (Rabi) and paddy (Kharif) at Minimum Support Price\n"
            "     directly into the farmer's bank account via the UP Food & Civil Supplies Department.\n"
            "   - Eligibility: Registered UP farmers with valid land records.\n"
            "   - Apply: fcs.up.gov.in — register before the procurement window opens each season.",
        ]

    elif "maharashtra" in st:
        state_entries = [
            "📍 Maharashtra — State-Specific Agricultural Support\n"
            "\n"
            "1. Gopinath Munde Shetkari Apghat Vima Yojana\n"
            "   - Details: ₹2 lakh accidental death/disability insurance for all registered farmers at no premium.\n"
            "   - Apply: District agriculture office within 90 days of incident.",

            "2. Magel Tyala Shet Tale (On-Demand Farm Pond) Scheme\n"
            "   - Details: Financial assistance to construct farm ponds for rainwater harvesting; subsidy up to\n"
            "     ₹75,000 per pond under MNREGA/state funds.\n"
            "   - Eligibility: SC/ST and small-marginal Maharashtra farmers; dry-land priority.\n"
            "   - Apply: Gram Panchayat or block development office.",

            "3. Nano DAP / Nano Urea Subsidy — Maharashtra\n"
            "   - Details: Maharashtra distributes IFFCO nano-urea and nano-DAP at subsidised rates through\n"
            "     cooperative societies to reduce input costs.\n"
            "   - Apply: District central cooperative bank or primary agricultural credit society.",

            "4. Maharashtra Chief Minister's Solar Agriculture Feeder Scheme\n"
            "   - Details: Daytime solar-powered feeders to provide 8-hour quality power for farm pumps.\n"
            "   - Benefit: Reduces electricity costs for irrigated farming.\n"
            "   - Apply: MSEDCL office or mahaurja.com.",
        ]

    elif "punjab" in st:
        state_entries = [
            "📍 Punjab — State-Specific Agricultural Support\n"
            "\n"
            "1. Punjab Free Power Scheme (Muft Bijli Yojana)\n"
            "   - Details: Free electricity for agricultural tube wells (unlimited units) to all registered Punjab farmers.\n"
            "   - Eligibility: Farmers with tube-well connections registered with PSPCL.",

            "2. Punjab Crop Diversification Scheme\n"
            "   - Details: ₹17,500/acre incentive to diversify from paddy to direct-seeded rice or maize/cotton\n"
            "     in notified water-stressed districts.\n"
            "   - Apply: Punjab Agriculture and Farmers' Welfare Department.",

            "3. Punjab New Farmer Scheme (Naujawan Kisaan)\n"
            "   - Details: Subsidised training and seed/tool kits for young farmers (18–40 years) entering agriculture.\n"
            "   - Apply: Punjab Agriculture University (PAU) extension centres.",
        ]

    elif "karnataka" in st:
        state_entries = [
            "📍 Karnataka — State-Specific Agricultural Support\n"
            "\n"
            "1. Krishi Bhagya Scheme\n"
            "   - Details: 80–90% subsidy for farm ponds, polythene lining, and diesel/solar pumpsets for\n"
            "     rainwater harvesting in dry-zone districts.\n"
            "   - Eligibility: All Karnataka farmers in designated dry-zone districts.",

            "2. Raitha Siri / Karnataka Raitha Samparka Kendra\n"
            "   - Details: Single-window centres providing soil testing, seeds, fertilisers, and extension advice.\n"
            "   - Apply: Nearest Raitha Samparka Kendra in your taluk.",

            "3. Karnataka Bhoomi (Land Records Portal)\n"
            "   - Details: Free digitised RTC (Record of Rights, Tenancy & Crops) for all Karnataka land records.\n"
            "   - Benefit: Required document for most scheme applications — obtain instantly at bhoomi.karnataka.gov.in.",
        ]

    elif "rajasthan" in st:
        state_entries = [
            "📍 Rajasthan — State-Specific Agricultural Support\n"
            "\n"
            "1. Rajasthan Krishi Processing, Agri-Business & Agri-Export Promotion Policy\n"
            "   - Details: 25–50% capital subsidy for setting up farm-level processing and cold-chain units.\n"
            "   - Apply: Rajasthan Agro Processing & Marketing Corporation.",

            "2. Tarbandi Yojana (Fencing Scheme)\n"
            "   - Details: 50% subsidy (up to ₹40,000) for installing barbed-wire fencing to protect crops\n"
            "     from wild animals and stray cattle.\n"
            "   - Eligibility: Farmers with minimum 0.5 hectare in their own name.\n"
            "   - Apply: District agriculture office.",

            "3. Rajasthan Mukhyamantri Krishak Saathi Yojana\n"
            "   - Details: ₹5,000–₹2 lakh compensation for injury or death while engaged in agricultural activities.\n"
            "   - Apply: Block agriculture office within 6 months.",
        ]

    elif "haryana" in st:
        state_entries = [
            "📍 Haryana — State-Specific Agricultural Support\n"
            "\n"
            "1. Mera Pani Meri Virasat\n"
            "   - Details: ₹7,000/acre incentive to shift paddy area to less water-intensive crops (maize, cotton,\n"
            "     bajra, moong, sunflower).\n"
            "   - Apply: Haryana Agriculture Department — agriharyana.gov.in.",

            "2. Bhavantar Bharpai Yojana (Price Deficiency Payment)\n"
            "   - Details: Compensates farmers when market price falls below the support price for select vegetables\n"
            "     and fruits; payment directly into bank account.\n"
            "   - Apply: Haryana e-disha portal.",

            "3. Haryana Solar Water Pumping Scheme (PM-KUSUM Component C)\n"
            "   - Details: 60% subsidy on solar pumps; existing electric pumps solarised at low cost.\n"
            "   - Apply: Haryana Renewable Energy Development Agency (HAREDA).",
        ]

    elif "gujarat" in st:
        state_entries = [
            "📍 Gujarat — State-Specific Agricultural Support\n"
            "\n"
            "1. IKHEDUT Portal\n"
            "   - Details: Single portal for 100+ Gujarat state agriculture, horticulture, fisheries,\n"
            "     and animal husbandry schemes.\n"
            "   - Apply: ikhedut.gujarat.gov.in — online application, subsidy directly credited to bank.",

            "2. Mukhyamantri Bagayat Yojana (Horticulture Scheme)\n"
            "   - Details: 50% subsidy on drip irrigation and horticulture nursery development for Gujarat farmers.\n"
            "   - Apply: Gujarat Horticulture Department via IKHEDUT portal.",
        ]

    elif "tamil nadu" in st or "tamilnadu" in st:
        state_entries = [
            "📍 Tamil Nadu — State-Specific Agricultural Support\n"
            "\n"
            "1. Tamil Nadu Chief Minister's Comprehensive Crop Insurance\n"
            "   - Details: Additional state-funded crop insurance layer on top of PMFBY; covers shortfall\n"
            "     up to 100% of crop value in notified calamities.\n"
            "   - Apply: Through your cooperative bank at time of Kharif/Rabi registration.",

            "2. TNSF (Tamil Nadu Seed Farm Corporation) Subsidised Seeds\n"
            "   - Details: Certified seeds of rice, pulses, and oilseeds supplied at 50% subsidy through\n"
            "     cooperative societies.\n"
            "   - Apply: Primary Agricultural Cooperative Society (PACS) in your village.",

            "3. Uzhavar Santhai (Farmer's Market)\n"
            "   - Details: Direct-to-consumer market stalls for TN farmers, eliminating middlemen.\n"
            "   - Benefit: Farmers earn 20–40% more than mandi prices.\n"
            "   - Apply: Tamil Nadu Agriculture Marketing Department.",
        ]

    elif "bihar" in st:
        state_entries = [
            "📍 Bihar — State-Specific Agricultural Support\n"
            "\n"
            "1. Bihar Rajya Fasal Sahayata Yojana\n"
            "   - Details: State-funded crop loss compensation (₹7,500–₹10,000/ha) for 18 notified crops;\n"
            "     does not require premium payment by farmers.\n"
            "   - Apply: pacsonline.bih.nic.in",

            "2. DBT Agriculture Portal Bihar\n"
            "   - Details: Direct Benefit Transfer for seeds, fertilisers, and PM-KISAN through the Bihar\n"
            "     state agriculture portal. Subsidy on inputs (urea, DAP) credited directly.\n"
            "   - Apply: dbtagriculture.bihar.gov.in",

            "3. Bihar Krishi Input Anudan Yojana\n"
            "   - Details: ₹13,500/ha for irrigated land and ₹6,800/ha for non-irrigated land affected by\n"
            "     natural calamities, droughts, or unseasonal rains.\n"
            "   - Apply: Bihar district agriculture office after calamity declaration.",
        ]

    elif "west bengal" in st or "westbengal" in st:
        state_entries = [
            "📍 West Bengal — State-Specific Agricultural Support\n"
            "\n"
            "1. Krishak Bandhu Scheme\n"
            "   - Details: ₹10,000/acre/year income support for registered WB farmers (paid in two instalments);\n"
            "     minimum 1 acre; also provides ₹2 lakh accidental death cover.\n"
            "   - Apply: matirkatha.net or block agriculture office.",

            "2. Banglar Krishi Sech Yojana\n"
            "   - Details: Subsidised solar-powered micro-irrigation and water-lifting equipment for WB farmers.\n"
            "   - Apply: West Bengal Agriculture Department district office.",
        ]

    elif "andhra pradesh" in st or "ap" == st:
        state_entries = [
            "📍 Andhra Pradesh — State-Specific Agricultural Support\n"
            "\n"
            "1. YSR Rythu Bharosa (AP Farmer Investment Support)\n"
            "   - Details: ₹13,500/year per farmer family for agricultural inputs, paid in two instalments;\n"
            "     stacks with PM-KISAN for a combined ₹19,500/year.\n"
            "   - Apply: AP Agriculture Department or meeseva.gov.in.",

            "2. YSR Free Crop Insurance\n"
            "   - Details: Full premium for PMFBY paid by the AP government — farmers enrol at zero cost.\n"
            "   - Apply: Through your cooperative bank at the start of each season.",

            "3. AP Micro-Irrigation Scheme\n"
            "   - Details: 100% subsidy on drip and sprinkler irrigation for small/marginal farmers;\n"
            "     50% for others under AP MIDH.\n"
            "   - Apply: AP Horticulture Department.",
        ]

    elif "madhya pradesh" in st or st == "mp":
        state_entries = [
            "📍 Madhya Pradesh — State-Specific Agricultural Support\n"
            "\n"
            "1. MP Mukhyamantri Kisan Kalyan Yojana\n"
            "   - Details: Additional ₹4,000/year state income support on top of PM-KISAN, bringing the total\n"
            "     to ₹10,000/year for eligible MP farmers.\n"
            "   - Apply: farmers.mp.gov.in",

            "2. MP Bhavantar Bhugtan Yojana\n"
            "   - Details: Compensates for the gap between MSP and market price for 8 Kharif crops;\n"
            "     payment to bank account after mandi sale.\n"
            "   - Apply: Farmer registration at mpfsts.mp.gov.in",

            "3. Jal Jeevan Mission — MP Micro-Irrigation\n"
            "   - Details: MP channels additional central funds for drip and sprinkler systems; up to 80%\n"
            "     subsidy in tribal/backward districts.\n"
            "   - Apply: MP Agriculture Department or district collector office.",
        ]

    # ── Build the response based on requested mode ─────────────────────────────
    if m == "state":
        if state_entries:
            return "\n\n".join(state_entries)
        else:
            state_label = state.strip() if state else "your state"
            return (
                f"State-specific scheme data for '{state_label}' is not currently available in the local verified database. "
                "However, Central Government schemes (PM-KISAN, PMFBY, KCC, PMKSY, eNAM) are available nationwide — "
                "apply through your nearest bank, CSC, or Krishi Vigyan Kendra (KVK)."
            )

    # mode == "central" (or any default) — return central schemes only
    return "\n\n".join(central_schemes)

@mcp.tool()
def calculate_farming_profitability(crop: str, acreage: float = 1.0, expected_yield_per_acre: float = 20.0) -> str:
    """Calculates estimated costs, expected revenue, and net profit for cultivating a crop on a specific farm size.
    
    Args:
        crop: The crop name (e.g., wheat, rice, cotton).
        acreage: The farm size in acres (e.g., 1.0, 2.0, 5.0).
        expected_yield_per_acre: Estimated yield in quintals (100 kg) per acre.
    """
    crp = crop.lower()
    
    if "wheat" in crp:
        cost_per_acre = 15000
        msp_per_quintal = 2275
        yield_default = 18.0 if expected_yield_per_acre == 20.0 else expected_yield_per_acre
    elif "rice" in crp or "paddy" in crp:
        cost_per_acre = 18000
        msp_per_quintal = 2183
        yield_default = 22.0 if expected_yield_per_acre == 20.0 else expected_yield_per_acre
    elif "cotton" in crp:
        cost_per_acre = 22000
        msp_per_quintal = 6620
        yield_default = 8.0 if expected_yield_per_acre == 20.0 else expected_yield_per_acre
    elif "mustard" in crp:
        cost_per_acre = 12000
        msp_per_quintal = 5650
        yield_default = 7.0 if expected_yield_per_acre == 20.0 else expected_yield_per_acre
    elif "soybean" in crp:
        cost_per_acre = 14000
        msp_per_quintal = 4600
        yield_default = 8.0 if expected_yield_per_acre == 20.0 else expected_yield_per_acre
    else:
        cost_per_acre = 16000
        msp_per_quintal = 2500
        yield_default = expected_yield_per_acre
        
    actual_yield = yield_default
    total_cost = cost_per_acre * acreage
    total_yield = actual_yield * acreage
    total_revenue = total_yield * msp_per_quintal
    net_profit = total_revenue - total_cost
    farm_label = f"{acreage:.1f} acre(s)" if acreage != 1.0 else "1.0 acre (Illustrative Benchmark Example)"

    return (
        f"📊 Illustrative Farming Profitability Analysis for {crop} — Farming Profitability Analysis for {acreage:.1f} acre(s) of {crop} ({farm_label}):\n\n"
        f"Assumptions & Baseline Values:\n"
        f"• Farm Size Considered: {acreage:.1f} acre(s)\n"
        f"• Assumed Cost of Cultivation: Rs. {cost_per_acre:,} per acre benchmark\n"
        f"• Assumed Baseline Yield: {actual_yield:.1f} quintals per acre\n"
        f"• Assumed Price Benchmark (Govt MSP): Rs. {msp_per_quintal:,} per quintal (Govt MSP Benchmark of Rs. {msp_per_quintal}/quintal)\n\n"
        f"Transparent Calculation Breakdown (illustrative benchmark calculation):\n"
        f"• Total Estimated Cultivation Cost: Rs. {total_cost:,.2f}\n"
        f"• Total Estimated Production: {total_yield:.1f} quintals\n"
        f"• Gross Revenue (at MSP benchmark): Rs. {total_revenue:,.2f}\n"
        f"• Estimated Net Return: Rs. {net_profit:,.2f}\n\n"
        f"⚠️ Important Disclaimers:\n"
        f"• Illustrative estimate — not a guaranteed return.\n"
        f"• Actual profit depends on your local yield, input costs, crop quality, and realized local mandi selling price. Actual income will vary based on local mandi prices.\n"
        f"• Please verify current local mandi rates and actual input, seed, labour, and irrigation costs before making financial or cultivation decisions.\n"
        f"• We recommend consulting your local Krishi Vigyan Kendra (KVK) or block agriculture officer for area-specific cost-of-cultivation estimates.\n\n"
        f"Tips to improve profitability:\n"
        f"1. Use micro-irrigation (drip/sprinkler) to reduce water costs and boost yield.\n"
        f"2. Apply balanced integrated nutrient management (IPNM) with organic compost to lower fertilizer expenses.\n"
        f"3. Sell through e-NAM (National Agriculture Market) or farmer producer organizations (FPOs) for better price realization."
    )

if __name__ == "__main__":
    mcp.run(transport="stdio")
