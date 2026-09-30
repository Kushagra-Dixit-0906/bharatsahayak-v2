# ruff: noqa
import datetime
import os
from zoneinfo import ZoneInfo
from typing import AsyncGenerator, Any

from google.adk.workflow import Workflow, START, node
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools import AgentTool
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.apps import App, ResumabilityConfig
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# MCP Imports
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from app.crop_knowledge import (
    find_crop_info,
    infer_primary_season,
    is_single_primary_season_crop,
    get_current_calendar_season,
)
from .config import config

# -----------------------------------------------------------------------------
# 0. MCP Toolset Setup
# -----------------------------------------------------------------------------

# Configure connection to the local MCP server running over stdio
mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="uv",
            args=["run", "app/mcp_server.py"],
        ),
        timeout=120.0,
    ),
)

# -----------------------------------------------------------------------------
# 1. State & Output Schemas
# -----------------------------------------------------------------------------

class FarmerProfile(BaseModel):
    language: str = "English"
    location: str = "Unknown"
    latitude: float | None = None
    longitude: float | None = None
    crops: list[str] = []
    farm_size: str = "Unknown"
    farmer_selected_season: str | None = None
    inferred_season: str | None = None
    current_calendar_season: str = "Kharif"
    season: str | None = None

class WorkflowState(BaseModel):
    farmer_profile: FarmerProfile = FarmerProfile()
    user_query: str = ""
    audit_log: list[dict] = []

class OrchestratorOutput(BaseModel):
    response: str = Field(
        default="",
        description="The final farming advice or the response compiled from the sub-agents."
    )
    needs_more_info: bool = Field(
        default=False,
        description="True if we need to ask the farmer for missing profile details (e.g., location/state, crop type, or land size) to answer their query."
    )
    info_request_message: str = Field(
        default="",
        description="The friendly question to ask the farmer if needs_more_info is True."
    )

    @field_validator("response", mode="before")
    @classmethod
    def ensure_string_response(cls, v: Any) -> str:
        if isinstance(v, dict):
            if "request" in v:
                return str(v["request"])
            if "query" in v:
                return str(v["query"])
            if "response" in v:
                return str(v["response"])
            import json
            return json.dumps(v, ensure_ascii=False)
        return str(v) if v is not None else ""

class AdvisorInput(BaseModel):
    request: str = Field(
        default="",
        description="The farmer query or details for the advisor."
    )
    query: str | None = Field(
        default=None,
        description="User query string."
    )
    crop: str | None = Field(
        default=None,
        description="Crop name if specified."
    )
    symptoms: str | None = Field(
        default=None,
        description="Observed symptoms or crop issues."
    )
    location: str | None = Field(
        default=None,
        description="Farmer location, state, or district."
    )

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def assemble_request(self) -> "AdvisorInput":
        if not self.request.strip():
            parts = []
            if self.query and self.query.strip():
                parts.append(self.query.strip())
            if self.crop and self.crop.strip():
                parts.append(f"Crop: {self.crop.strip()}")
            if self.symptoms and self.symptoms.strip():
                parts.append(f"Symptoms: {self.symptoms.strip()}")
            if self.location and self.location.strip():
                parts.append(f"Location: {self.location.strip()}")
            if parts:
                object.__setattr__(self, "request", " | ".join(parts))
        return self

# -----------------------------------------------------------------------------
# 2. Specialized LLM Agents (Sub-Agents)
# -----------------------------------------------------------------------------

farming_advisor = LlmAgent(
    name="farming_advisor",
    description="Advises on crop recommendations, seasonal cultivation planning, and farming profitability.",
    input_schema=AdvisorInput,
    model=Gemini(model=config.model),
    instruction=(
        "You are BharatSahayak's Farming Advisor. Your goal is to help Indian farmers with agricultural queries.\n"
        "Follow these rules when formulating your response:\n"
        "1. Provide region (state/district) and season-specific crop recommendations.\n"
        "2. When recommending crops for general crop advice queries, output ONLY grounded agronomic information without financial figures. Use this clean format:\n"
        "   🌱 Recommended Crop: [Crop Name]\n"
        "   🌾 Crop Suitability: [Why chosen / context fit for the region, soil, or climate]\n"
        "   📍 Region / Soil: [Stated region/soil context, or 'General / Agro-climatic suitability' if unstated]\n"
        "   📅 Season: [Kharif / Rabi / Zaid]\n"
        "   💧 Water & Irrigation Considerations: [Water requirements, drainage, critical irrigation stages]\n"
        "   🚜 Cultivation Considerations: [Soil preparation, spacing, basic seed rate]\n"
        "   ⚠️ Important Risks: [Key vulnerabilities such as unseasonal rain, temperature sensitivity, or common pests]\n"
        "   🏛 Helpful Scheme: [One verified scheme, e.g. PM-KISAN, PMFBY]\n"
        "   ➡ Practical Next Steps: [1. Soil testing, 2. Quality certified seeds, 3. Field preparation]\n"
        "3. CRITICAL RULES ON FINANCIAL / PROFITABILITY CLAIMS:\n"
        "   - NEVER invent, assume, or hardcode arbitrary investment or profit amounts, acreage, yield, or revenue.\n"
        "   - NEVER invent or hardcode arbitrary figures like '₹10,000 investment' or '₹35,000 profit per acre'.\n"
        "   - Ordinary crop recommendation/advice MUST NOT include financial figures unless the farmer explicitly asks about cost, investment, profit, revenue, economics, profitability, or returns.\n"
        "   - When the farmer EXPLICITLY asks about profitability, economics, costs, or returns:\n"
        "     * ALWAYS call `calculate_farming_profitability`.\n"
        "     * If farm size is provided, use that acreage; if farm size is unstated, use acreage=1.0 and clearly state that the figures represent an 'Illustrative Benchmark Example (per 1 Acre)', never pretending it is the farmer's actual farm size.\n"
        "     * Present the calculation transparently with all assumptions clearly labelled.\n"
        "     * Explicitly state that returns are illustrative and NOT guaranteed, and depend on actual local mandi prices, yield, and input costs.\n"
        "     * Do NOT say 'You will earn...', 'Expected profit is...' without assumptions, or 'Guaranteed income...'.\n"
        "     * Suggest verifying local mandi rates and consulting their local Krishi Vigyan Kendra (KVK) or block agriculture officer.\n"
        "4. CRITICAL SEASON REASONING & SEPARATION RULES:\n"
        "   - If a 'Requested / Farmer-Selected Season' is specified, that season is strictly AUTHORITATIVE. You MUST provide crop advice for that requested season, even if the 'Current Calendar Season' is different (e.g. if the farmer requested Kharif while the current calendar month is Rabi, advise for their planned Kharif cultivation).\n"
        "   - Never override or change the farmer's explicitly chosen season to match the current calendar date.\n"
        "   - NEVER silently fabricate regions (e.g. do not invent 'Northern India' unless derived from verified user context).\n"
        "5. Suggest crop varieties suitable for the region/season and identify selling opportunities (e.g., local mandis, e-NAM, processors).\n"
        "6. If the user is new to farming or a beginner, provide beginner-friendly crop recommendations along with a step-by-step farming plan (soil preparation, sowing, irrigation, harvesting).\n"
        "7. If the user asks about or refers to another state or location in their query, prioritize and answer for that location/state instead of assuming or requesting the saved profile location.\n"
        "8. You MUST formulate your entire response strictly in the target Output Language specified in the 'Language' field of the Farmer Profile. The 'Language' field is the absolute authority: if Language is Hindi, output exclusively in Hindi (with translated emojis and headings), even if the user query was typed in English; if Language is English, output exclusively in English, even if the user query was typed in Hindi. Never switch output languages based on the input text script or language. When responding in Hindi, translate emojis and headings naturally while preserving the exact layout.\n"
        "Keep answers simple, easy to understand, and concise."
    ),
    tools=[mcp_toolset]
)

weather_advisor = LlmAgent(
    name="weather_advisor",
    description="Provides localized weather forecasts and short-term farming weather advisories.",
    input_schema=AdvisorInput,
    model=Gemini(model=config.model),
    instruction=(
        "You are BharatSahayak's Weather Advisor. Your purpose is to provide clear current weather conditions and a 3-day short-term forecast for the farmer's location.\n"
        "Follow these rules when formulating your response:\n"
        "1. Always call the `get_weather_advisory` tool with the location (or coordinates) and language from the Farmer Profile.\n"
        "2. Present the live weather data clearly: current temperature, weather condition, precipitation, humidity, wind, and the 3-day short-term forecast.\n"
        "3. Include a short, practical farming weather note based on the forecast (e.g. if rain is expected, advise caution with spraying or irrigation).\n"
        "4. Do NOT generate complex chemical prescriptions, quantitative fertilizer dosages, or deep environmental model interpretations.\n"
        "5. You MUST formulate your entire response strictly in the target Output Language specified in the 'Language' field of the Farmer Profile. The 'Language' field is the absolute authority: if Language is Hindi, respond exclusively in Hindi; if Language is English, respond exclusively in English. Never switch output languages based on the input text script.\n"
        "Keep answers concise, clear, and farmer-friendly."
    ),
    tools=[mcp_toolset]
)

gov_schemes_advisor = LlmAgent(
    name="gov_schemes_advisor",
    description="Helps farmers discover government agricultural schemes, subsidies, and application steps.",
    input_schema=AdvisorInput,
    model=Gemini(model=config.model),
    instruction=(
        "You are BharatSahayak's Government Schemes Advisor. Follow these rules when formulating your response:\n"
        "1. When the user asks general questions about government schemes or subsidies, ALWAYS call `search_government_schemes(mode='central')` to present ONLY Central Government schemes. Do NOT include state schemes in general scheme queries, even if a state is mentioned in the profile.\n"
        "2. When the user explicitly asks for state-specific schemes for a particular state (e.g. 'Show me ONLY state-specific schemes in Uttar Pradesh'), call `search_government_schemes(state='<State>', mode='state')`. Do NOT repeat or include central schemes when answering a state-specific request.\n"
        "3. For each relevant scheme, make sure to detail: eligibility criteria, required documents, benefits (subsidies/income support), and the step-by-step application process.\n"
        "4. You MUST formulate your entire response strictly in the target Output Language specified in the 'Language' field of the Farmer Profile. The 'Language' field is the absolute authority: if Language is Hindi, respond exclusively in Hindi, even if the user query was in English; if Language is English, respond exclusively in English, even if the user query was in Hindi. Never switch output languages based on the input text script.\n"
        "Translate agricultural schemes into simple, easy-to-understand terms."
    ),
    tools=[mcp_toolset]
)

crop_disease_advisor = LlmAgent(
    name="crop_disease_advisor",
    description="Advises on crop health, pests, and plant diseases using non-chemical cultural practices.",
    input_schema=AdvisorInput,
    model=Gemini(model=config.model),
    instruction=(
        "You are BharatSahayak's Crop Health & Disease Advisor. Follow these strict rules when formulating your response:\n"
        "1. Always use the `get_crop_disease_info` tool to look up verified agricultural knowledge based on the crop and observed symptoms.\n"
        "2. Location or GPS coordinates are NEVER required for disease analysis. Do NOT ask the farmer for their location, GPS, or farm size.\n"
        "3. Treat the tool output as authoritative reference evidence. Do NOT invent ungrounded disease facts, pathogens, or treatments.\n"
        "4. Frame findings as candidate possibilities or hypotheses, NEVER as confirmed or definitive clinical diagnoses.\n"
        "5. Provide ONLY safe, non-chemical cultural and preventative practices (e.g. sanitation, crop rotation, moisture management, resistant varieties). You MUST NEVER recommend chemical pesticides, fungicides, insecticides, dosages (e.g., ml/L, g/L), active ingredients, or chemical spray schedules.\n"
        "6. Include clarifying field observations or follow-up questions from the tool output when symptoms are ambiguous, and clearly state when the farmer should consult a local Krishi Vigyan Kendra (KVK) or extension officer.\n"
        "7. You MUST formulate your entire response strictly in the target Output Language specified in the 'Language' field of the Farmer Profile. The 'Language' field is the absolute authority: if Language is Hindi, respond exclusively in Hindi, even if the user query was in English; if Language is English, respond exclusively in English, even if the user query was in Hindi. Never switch output languages based on the input text script.\n"
        "Explain symptoms and safe cultural steps in simple, clear, farmer-friendly terms."
    ),
    tools=[mcp_toolset]
)


# -----------------------------------------------------------------------------
# 3. Orchestrator LLM Agent
# -----------------------------------------------------------------------------

orchestrator = LlmAgent(
    name="orchestrator",
    model=Gemini(model=config.model),
    instruction=(
        "You are BharatSahayak's primary Orchestrator.\n"
        "Your task is to analyze the user's input/query, check the farmer's profile, and delegate the query to the correct advisor using tools.\n"
        "If you need missing information to answer the query (e.g. the farmer's state or farm size), set needs_more_info to True and write a helpful prompt in info_request_message.\n"
        "However, if the user specifies or asks about another state or location in their query, prioritize that location for tool calling and response instead of asking for or assuming the saved profile location.\n"
        "Ensure that both the final response and the info_request_message are strictly in the target Output Language specified in the 'Language' field of the Farmer Profile. The 'Language' field is the absolute authority: if Language is Hindi, your response MUST be in Hindi (Devanagari), even if the user typed in English; if Language is English, your response MUST be in English, even if the user typed in Hindi or Devanagari. Never switch output languages based on the input query text script.\n"
        "Follow these strict rules for specific queries:\n"
        "1. If the User Query is a greeting (e.g. 'hello', 'hi', 'hey', 'start') or asks what the bot can do, you MUST set needs_more_info to False and return the following exact welcome message in the response field:\n"
        "   👋 Welcome to BharatSahayak!\n\n"
        "   I can help you with:\n\n"
        "   🌾 Crop recommendations\n"
        "   🌦 Weather advisories\n"
        "   🦠 Disease diagnosis\n"
        "   🏛 Government schemes\n"
        "   💰 Profitability analysis\n\n"
        "   Try asking:\n"
        "   \"I am a wheat farmer in Punjab.\"\n"
        "   \"What crop should I grow?\"\n"
        "   \"My rice leaves have brown spots.\"\n"
        "2. If the User Query is purely providing profile information (e.g. declaring location, crop, or farm size) and does NOT contain any question or request for advice, you MUST set needs_more_info to False and return the following structured profile update message in the response field:\n"
        "   ✅ Profile Updated\n\n"
        "   📍 Location: [Location from Farmer Profile, e.g. Punjab]\n"
        "   🌾 Crop: [Crops from Farmer Profile, e.g. Potato]\n"
        "   🚜 Farm Size: [Farm Size from Farmer Profile (include this line ONLY if the farm size is known/provided, e.g. 2 acres, otherwise omit this line completely)]\n\n"
        "   I can now help you with:\n"
        "   🌦 Weather advisories\n"
        "   🦠 Disease diagnosis\n"
        "   🏛 Government schemes\n"
        "   💰 Profit improvement\n"
        "   🌱 Crop recommendations\n\n"
        "   Ask me anything about your farming needs.\n"
        "3. CRITICAL RULE FOR CROP HEALTH / DISEASE / PEST QUERIES: Crop health, pest, and disease advisories do NOT require GPS, farm coordinates, or location. When a crop name and/or symptoms are present (e.g. 'My rice leaves have brown spots and some leaves are turning yellow'), NEVER ask the farmer for their location, state, or GPS coordinates. Set needs_more_info to False and delegate immediately to crop_disease_advisor or call get_crop_disease_info. Only set needs_more_info to True if both the crop and symptoms are completely missing.\n"
        "4. For environmental assessment, satellite vegetation health (NDVI), farm environmental condition, or soil moisture/climate trend queries, you MUST call the `get_environmental_assessment` tool with the farm's exact latitude and longitude from the Farmer Profile and language='hi' if the Language in Farmer Profile is Hindi, or language='en' if English. When `get_environmental_assessment` returns an advisory, you MUST return its exact text directly in the `response` field without summarizing, modifying, or re-interpreting it.\n"
        "5. If an environmental assessment or farm satellite condition query is received but exact farm coordinates are missing from the Farmer Profile (no latitude/longitude coordinates), you MUST NOT call `get_environmental_assessment` with fabricated or default coordinates. Instead, set `needs_more_info` to True and prompt the farmer in `info_request_message` to provide their farm coordinates (latitude and longitude, e.g. 16.7749, 74.0461).\n"
        "6. For ordinary weather forecasts and short-term rain/irrigation tips, delegate to `weather_advisor`.\n"
        "7. When translating the welcome or profile updated responses for Hindi or other languages, translate the text naturally while preserving the exact layout, structure, and emojis.\n"
        "You MUST respond ONLY with a valid JSON object conforming to the OrchestratorOutput schema. Do not include any conversational preamble or wrap the JSON in markdown code blocks."
    ),
    tools=[
        AgentTool(farming_advisor),
        AgentTool(weather_advisor),
        AgentTool(gov_schemes_advisor),
        AgentTool(crop_disease_advisor),
        mcp_toolset
    ],
    output_schema=OrchestratorOutput
)

# -----------------------------------------------------------------------------
# 4. Workflow Nodes (Python functions)
# -----------------------------------------------------------------------------

def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    """Security Checkpoint Node - PII scrubbing, prompt injection detection, and content safety."""
    import re
    import sys
    import json
    
    text_query = ""
    if node_input and node_input.parts:
        text_query = "".join(part.text for part in node_input.parts if part.text)
        
    # Initialize audit logs list in state
    if "audit_log" not in ctx.state:
        ctx.state["audit_log"] = []
        
    audit_entry = {
        "timestamp": datetime.datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(),
        "input_length": len(text_query),
        "severity": "INFO",
        "action": "PASS",
        "details": "Input query passed security checks."
    }
    
    # 1. PII Scrubbing (Aadhaar number, mobile, email)
    aadhaar_pattern = r"\b\d{4}\s\d{4}\s\d{4}\b|\b\d{12}\b"
    mobile_pattern = r"\b[6-9]\d{9}\b"
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    
    scrubbed = False
    if re.search(aadhaar_pattern, text_query):
        text_query = re.sub(aadhaar_pattern, "[AADHAAR_REDACTED]", text_query)
        scrubbed = True
    if re.search(mobile_pattern, text_query):
        text_query = re.sub(mobile_pattern, "[PHONE_REDACTED]", text_query)
        scrubbed = True
    if re.search(email_pattern, text_query):
        text_query = re.sub(email_pattern, "[EMAIL_REDACTED]", text_query)
        scrubbed = True
        
    if scrubbed:
        audit_entry["action"] = "SCRUBBED"
        audit_entry["severity"] = "WARNING"
        audit_entry["details"] = "PII (Aadhaar/Mobile/Email) detected and redacted."
        
    # 2. Prompt Injection, Exfiltration & Safety Patterns
    rejection_msg = (
        "🔒 Security Alert\n\n"
        "I can't provide private information, passwords, API keys, hidden\n"
        "instructions, system prompts, or internal system details.\n\n"
        "Please remove sensitive information from your request and try again."
    )

    injection_or_override_patterns = [
        # Override / ignore instructions
        r"\b(?:ignore|disregard|forget|bypass|override|drop)\s+(?:all\s+)?(?:previous|prior|above|system|developer|hidden)?\s*(?:instructions|rules|prompts|directions|guidelines|constraints|safeguards|filters)\b",
        # Bypass security / guardrails
        r"\b(?:bypass|disable|override|jailbreak)\s+(?:rules|security|guardrails|safeguards|filters|safety\s+checks)\b",
        # Developer / unrestricted mode switching
        r"\b(?:you\s+are\s+now\s+in|enter|switch\s+to|enable)\s+(?:developer\s+mode|dan\s+mode|god\s+mode|jailbreak\s+mode|unrestricted\s+mode)\b",
        # Jailbreak / prompt injection keywords
        r"\b(?:jailbreak|prompt\s+injection)\b",
    ]

    exfiltration_patterns = [
        # 1. System prompts / system instructions extraction
        r"\b(?:reveal|show|give(?:\s+me)?|display|print|leak|output|dump|extract|provide|tell(?:\s+me)?|expose|share|read|send|list|what\s+is\s+your|what\s+are\s+your|what's\s+your)\b.*?\b(?:system\s+prompt|system\s+instructions?|system\s+message|base\s+prompt|initial\s+prompt)\b",
        # 2. Hidden instructions / developer instructions extraction
        r"\b(?:reveal|show|give(?:\s+me)?|display|print|leak|output|dump|extract|provide|tell(?:\s+me)?|expose|share|read|send|list|what\s+is\s+your|what\s+are\s+your|what's\s+your)\b.*?\b(?:hidden\s+instructions?|developer\s+instructions?|developer\s+mode\s+instructions?|confidential\s+instructions?|internal\s+instructions?)\b",
        # 3. API keys / access tokens / authentication secrets extraction
        r"\b(?:reveal|show|give(?:\s+me)?|display|print|leak|output|dump|extract|provide|tell(?:\s+me)?|expose|share|read|send|list|what\s+is\s+the|what\s+are\s+the|what\s+is\s+your|what's\s+the|what's\s+your)\b.*?\b(?:api\s*keys?|api\s*secret|access\s*tokens?|auth\s*tokens?|bearer\s*tokens?|secret\s*keys?|private\s*keys?|credentials?)\b",
        # 4. Internal tools / tool schemas / implementation details extraction
        r"\b(?:reveal|show|give(?:\s+me)?|display|print|leak|output|dump|extract|provide|tell(?:\s+me)?|expose|share|read|send|list|what\s+is\s+your|what\s+are\s+your|what's\s+your)\b.*?\b(?:internal\s+tools?|tool\s+schemas?|internal\s+schemas?|internal\s+implementation|internal\s+system\s+details?|mcp\s+tool\s+schemas?|mcp\s+tools?)\b",
        # 5. Private farmer information / private user data extraction
        r"\b(?:reveal|show|give(?:\s+me)?|display|print|leak|output|dump|extract|provide|tell(?:\s+me)?|expose|share|read|send|list|what\s+is|what\s+are)\b.*?\b(?:private\s+farmer(?:\s+info|\s+data|\s+information)?|farmer\s+data|farmer\s+profile|farmer\s+information|private\s+user(?:\s+info|\s+data)?|all\s+farmers?(?:\s+data|\s+info)?|other\s+farmers?(?:\s+data|\s+info)?|user\s+records?|private\s+information)\b",
    ]

    sensitive_credential_patterns = [
        # High-risk financial credentials (bank pin, ATM pin, netbanking password, CVV, credit card)
        r"\b(?:bank\s+pin|atm\s+pin|netbanking\s+password|credit\s+card|cvv|master\s+password|admin\s+password)\b",
        # Direct credential key-value assignment (password: 123, pin: 456)
        r"\b(?:password|passwd|pin)\s*[:=]\s*\S+",
        # Providing personal passwords / PINs (e.g. "my password is ...", "my pin is ...")
        r"\b(?:my\s+password\s+is|here\s+is\s+my\s+password|my\s+pin\s+is|my\s+account\s+password\s+is)\b",
        # Sensitive identity / auth tokens
        r"\b(?:aadhaar\s+password|aadhaar\s+pin|aadhaar\s+otp)\b",
    ]

    harmful_agricultural_patterns = [
        r"\b(?:how\s+to\s+poison\s+crops|how\s+to\s+sabotage\s+soil|make\s+explosives|sabotage\s+crops)\b",
    ]

    all_security_patterns = (
        injection_or_override_patterns
        + exfiltration_patterns
        + sensitive_credential_patterns
        + harmful_agricultural_patterns
    )

    is_blocked = False
    matched_detail = ""
    for pattern in all_security_patterns:
        if re.search(pattern, text_query, re.IGNORECASE):
            is_blocked = True
            matched_detail = f"Security violation matched pattern: {pattern}"
            break

    if is_blocked:
        audit_entry["action"] = "BLOCKED_SECURITY"
        audit_entry["severity"] = "CRITICAL"
        audit_entry["details"] = matched_detail
        ctx.state["audit_log"].append(audit_entry)
        print(f"[SECURITY ALERT] {json.dumps(audit_entry)}", file=sys.stderr)
        return Event(output=rejection_msg, route="security_breach")
        
    # Log successful check
    ctx.state["audit_log"].append(audit_entry)
    print(f"[SECURITY AUDIT] {json.dumps(audit_entry)}", file=sys.stderr)
    
    if scrubbed:
        scrubbed_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=text_query)]
        )
        return Event(output=scrubbed_content)

    return Event(output=node_input)

def extract_season(text: str) -> str | None:
    """Extracts season names (Kharif/Rabi/Zaid) from text."""
    text_lower = text.lower()
    seasons_map = {
        "kharif": "Kharif",
        "rabi": "Rabi",
        "zaid": "Zaid",
        "खरीफ": "Kharif",
        "रबी": "Rabi",
        "जायद": "Zaid",
        "ज़ैद": "Zaid"
    }
    for key, val in seasons_map.items():
        if key in text_lower:
            return val
    return None

def extract_location(text: str) -> str | None:
    text_lower = text.lower()
    
    # If the reply contains only season or season-related words, do not extract it as a location
    words = text_lower.split()
    non_season_words = [w for w in words if w not in [
        "kharif", "rabi", "zaid", "season", "खरीफ", "रबी", "जायद", "ज़ैद", "मौसम", "in", "the", "a", "an", "is", "planning", "to", "farm"
    ]]
    if not non_season_words:
        return None

    import re
    if re.search(r"\bup\b", text_lower) or "यूपी" in text_lower or "यू पी" in text_lower:
        return "Uttar Pradesh"
    if re.search(r"\bmp\b", text_lower) or "एमपी" in text_lower or "एम पी" in text_lower:
        return "Madhya Pradesh"
    if re.search(r"\bap\b", text_lower):
        return "Andhra Pradesh"

    state_mapping = {
        "punjab": "Punjab", "पंजाब": "Punjab",
        "karnataka": "Karnataka", "कर्नाटक": "Karnataka",
        "haryana": "Haryana", "हरियाणा": "Haryana",
        "maharashtra": "Maharashtra", "महाराष्ट्र": "Maharashtra",
        "gujarat": "Gujarat", "गुजरात": "Gujarat",
        "rajasthan": "Rajasthan", "राजस्थान": "Rajasthan",
        "tamil nadu": "Tamil Nadu", "तमिलनाडु": "Tamil Nadu", "तमिल नाडु": "Tamil Nadu",
        "andhra pradesh": "Andhra Pradesh", "आंध्र प्रदेश": "Andhra Pradesh", "आंध्रप्रदेश": "Andhra Pradesh",
        "telangana": "Telangana", "तेलंगाना": "Telangana",
        "uttar pradesh": "Uttar Pradesh", "उत्तर प्रदेश": "Uttar Pradesh", "उत्तरप्रदेश": "Uttar Pradesh",
        "madhya pradesh": "Madhya Pradesh", "मध्य प्रदेश": "Madhya Pradesh", "मध्यप्रदेश": "Madhya Pradesh",
        "bihar": "Bihar", "बिहार": "Bihar",
        "west bengal": "West Bengal", "पश्चिम बंगाल": "West Bengal",
        "odisha": "Odisha", "ओडिशा": "Odisha",
        "kerala": "Kerala", "केरल": "Kerala",
        "assam": "Assam", "असम": "Assam",
        "himachal pradesh": "Himachal Pradesh", "हिमाचल प्रदेश": "Himachal Pradesh", "हिमाचलप्रदेश": "Himachal Pradesh",
        "uttarakhand": "Uttarakhand", "उत्तराखंड": "Uttarakhand",
        "chhattisgarh": "Chhattisgarh", "छत्तीसगढ़": "Chhattisgarh",
        "jharkhand": "Jharkhand", "झारखंड": "Jharkhand",
        "bangalore": "Karnataka", "बैंगलोर": "Karnataka", "बेंगलुरु": "Karnataka",
        "bengaluru": "Karnataka",
        "mumbai": "Maharashtra", "मुंबई": "Maharashtra",
        "pune": "Maharashtra", "पुणे": "Maharashtra",
        "nagpur": "Maharashtra", "नागपुर": "Maharashtra",
        "hyderabad": "Telangana", "हैदराबाद": "Telangana",
        "chennai": "Tamil Nadu", "चेन्नई": "Tamil Nadu",
        "jaipur": "Rajasthan", "जयपुर": "Rajasthan",
        "lucknow": "Uttar Pradesh", "लखनऊ": "Uttar Pradesh",
        "patna": "Bihar", "पटना": "Bihar",
        "kolkata": "West Bengal", "कोलकाता": "West Bengal",
        "bhopal": "Madhya Pradesh", "भोपाल": "Madhya Pradesh",
        "ahmedabad": "Gujarat", "अहमदाबाद": "Gujarat",
        "barabanki": "Uttar Pradesh", "बाराबंकी": "Uttar Pradesh"
    }
    for key, val in state_mapping.items():
        if key in text_lower:
            return val
            
    words = text.strip().split()
    words_lower = [w.lower() for w in words]
    if len(words) <= 2 and not any(w in words_lower for w in ["i", "am", "in", "from", "live", "my", "is"]):
        cleaned = "".join(c for c in text if c.isalnum() or c.isspace()).strip()
        if cleaned:
            return cleaned.title()
            
    match = re.search(r"\b(?:in|from|at)\s+([A-Za-z]+)", text)
    if match:
        loc = match.group(1).strip()
        if loc.lower() not in ["the", "my", "a", "an", "this", "some"]:
            return loc.capitalize()
    return None

def detect_language(text: str, default: str = "English") -> str:
    """Detects if the user is typing in Hindi (Devanagari) or English.
    If text contains no alphabetic/script characters, or is a neutral choice/button token
    (e.g., 'Kharif', 'Rabi', 'Zaid', 'yes', 'no') or an entity response (e.g. State/UT name),
    preserves the default/current session language.
    """
    if not text or not text.strip():
        return default
    for char in text:
        if '\u0900' <= char <= '\u097f':
            return "Hindi"
    clean = text.strip().lower()
    neutral_tokens = {
        "kharif", "rabi", "zaid", "yes", "no", "central", "state", "ok", "okay",
        "ha", "haan", "nahi", "nahi thanks"
    }
    if clean in neutral_tokens or not any(c.isalpha() for c in text):
        return default

    # If the input is just an entity/location response (e.g., "UP", "Uttar Pradesh", "Punjab")
    # without conversational English sentence structure, preserve the ongoing session language.
    words = clean.split()
    conversational_markers = {
        "tell", "what", "how", "why", "when", "which", "where", "who", "whom",
        "explain", "about", "give", "show", "can", "is", "are", "do", "does", "did",
        "i", "my", "me", "we", "our", "farm", "crop", "crops", "suggest", "recommend",
        "season", "help", "need", "want", "please", "sir"
    }
    if len(words) <= 3 and not any(w in conversational_markers for w in words):
        loc = extract_location(text)
        if loc:
            return default

    return "English"

def extract_coordinates(text: str) -> tuple[float, float] | None:
    """Extracts latitude and longitude from text if present (e.g. '16.774931, 74.046179' or 'lat 26.78 lon 81.54')."""
    import re
    patterns = [
        # Explicit labels: lat: 16.77, lon: 74.04 or latitude 16.77 longitude 74.04
        r"(?:lat(?:itude)?\s*[:=]?\s*)([+-]?\d{1,2}\.\d+)\s*[,;]?\s*(?:lon(?:gitude)?\s*[:=]?\s*)([+-]?\d{1,3}\.\d+)",
        # Standard coordinate pair: 16.774931, 74.046179 or 16.774931,74.046179
        r"(?:lat(?:itude)?\s*[:=]?\s*)?([+-]?\d{1,2}\.\d+)\s*,\s*(?:lon(?:gitude)?\s*[:=]?\s*)?([+-]?\d{1,3}\.\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                lat = float(match.group(1))
                lon = float(match.group(2))
                if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
                    return lat, lon
            except ValueError:
                pass
    return None

def extract_crops(text: str, current_crops: list[str]) -> list[str]:
    text_lower = text.lower()
    crop_mappings = {
        "wheat": "wheat", "गेहूं": "wheat", "गेहूँ": "wheat",
        "rice": "rice", "चावल": "rice", "धान": "rice", "paddy": "paddy",
        "cotton": "cotton", "कपास": "cotton",
        "potato": "potato", "आलू": "potato",
        "tomato": "tomato", "टमाटर": "tomato",
        "maize": "maize", "मक्का": "maize", "मक्की": "maize",
        "sugarcane": "sugarcane", "गन्ना": "sugarcane",
        "mustard": "mustard", "सरसों": "mustard",
        "onion": "onion", "प्याज": "onion", "प्याज़": "onion",
        "soybean": "soybean", "सोयाबीन": "soybean",
        "vegetables": "vegetables", "सब्जियां": "vegetables", "सब्ज़ी": "vegetables"
    }
    updated_crops = list(current_crops)
    for key, val in crop_mappings.items():
        if key in text_lower:
            if val not in updated_crops:
                updated_crops.append(val)
    return updated_crops

def extract_farm_size(text: str) -> str | None:
    import re
    text_lower = text.lower()
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:acres?|एकड़|एकड़)", text_lower)
    if match:
        return f"{match.group(1)} acres"
    return None

def load_farmer_profile(ctx: Context, node_input: types.Content) -> Event:
    """Loads and updates the farmer profile based on conversation input."""
    text_query = ""
    if node_input and node_input.parts:
        text_query = "".join(part.text for part in node_input.parts if part.text)
    
    ctx.state["user_query"] = text_query
    
    if "farmer_profile" not in ctx.state:
        ctx.state["farmer_profile"] = {
            "language": "English",
            "location": "Unknown",
            "latitude": None,
            "longitude": None,
            "crops": [],
            "farm_size": "Unknown",
            "farmer_selected_season": None,
            "inferred_season": None,
            "current_calendar_season": "Kharif",
            "season": None
        }
    
    profile = ctx.state["farmer_profile"]
    current_lang = profile.get("language", "English")
    profile["language"] = detect_language(text_query, default=current_lang)
    
    loc = extract_location(text_query)
    if loc:
        profile["location"] = loc

    coords = extract_coordinates(text_query)
    if coords:
        profile["latitude"], profile["longitude"] = coords
        
    profile["crops"] = extract_crops(text_query, profile.get("crops", []))
    
    sz = extract_farm_size(text_query)
    if sz:
        profile["farm_size"] = sz
        
    # Season reasoning & separation
    current_calendar_season = get_current_calendar_season()
    profile["current_calendar_season"] = current_calendar_season

    explicit_season = extract_season(text_query)
    if explicit_season:
        profile["farmer_selected_season"] = explicit_season
        profile["season"] = explicit_season
    elif not profile.get("farmer_selected_season") and not profile.get("season"):
        crops_to_check = profile.get("crops", []) or extract_crops(text_query, [])
        if crops_to_check:
            inferred = infer_primary_season(crops_to_check[0], profile.get("location"))
            if inferred:
                profile["inferred_season"] = inferred
                profile["season"] = inferred

    season_lines = []
    if profile.get("farmer_selected_season"):
        season_lines.append(f"- Requested / Farmer-Selected Season: {profile['farmer_selected_season']} (AUTHORITATIVE: You MUST advise for this requested season, regardless of current calendar month)")
    elif profile.get("inferred_season"):
        season_lines.append(f"- Inferred Normal Crop Season: {profile['inferred_season']} (Based on verified agricultural cultivation norms)")
    season_lines.append(f"- Current Calendar Season: {current_calendar_season}")
    season_str = "\n".join(season_lines) + "\n"

    coords_str = f"- Coordinates: {profile.get('latitude')}, {profile.get('longitude')}\n" if (profile.get("latitude") is not None and profile.get("longitude") is not None) else ""
    target_lang = profile.get("language", "English")
    orchestrator_prompt = (
        f"Farmer Profile:\n"
        f"- Location: {profile.get('location', 'Unknown')}\n"
        f"{coords_str}"
        f"- Crops: {', '.join(profile.get('crops', [])) if profile.get('crops') else 'None declared'}\n"
        f"- Farm Size: {profile.get('farm_size', 'Unknown')}\n"
        f"- Language: {target_lang}\n"
        f"{season_str}"
        f"User Query: {text_query}\n\n"
        f"IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is {target_lang}. You MUST produce your entire response and all messages strictly in {target_lang}, regardless of the script or language in the User Query."
    )
    
    return Event(output=orchestrator_prompt, state={"farmer_profile": profile})

def is_disease_query(query: str) -> bool:
    """Checks if the query is asking about crop disease, pests, or plant symptoms."""
    q = query.lower()
    disease_indicators = [
        "disease", "pest", "spots", "yellow", "wilt", "rot", "blight", "rust",
        "fungus", "infection", "symptoms", "leaves turning", "brown spots",
        "insects", "damage", "attack", "curl", "mildew", "canker",
        "रोग", "कीट", "धब्बे", "पीले", "पत्ते", "फंगस", "सड़न", "झुलसा", "कीड़े"
    ]
    return any(w in q for w in disease_indicators)

def is_crop_recommendation_request(query: str, profile: dict | None = None) -> bool:
    """Checks if the user is requesting crop recommendations from scratch."""
    if is_disease_query(query):
        return False

    q = query.lower()

    # Exclude government schemes and weather/environmental from crop recommendation HITL
    scheme_or_weather = [
        "scheme", "subsid", "yojana", "योजना", "सब्सिडी",
        "weather", "forecast", "barish", "rain", "temperature", "humidity", "बारिश", "मौसम का हाल"
    ]
    if any(k in q for k in scheme_or_weather):
        return False

    # 1. Wants to start farming
    if "start farming" in q or "farming startup" in q or "farming business" in q or "खेती शुरू" in q or "खेती करना" in q:
        return True

    rec_patterns = [
        "what crop", "which crop", "what crops", "which crops", "what to grow", "which to grow", "what should i grow",
        "crop should i grow", "crops should i grow", "recommend crop", "recommend crops", "recommend a crop",
        "suggest crop", "suggest crops", "suggest a crop", "crop recommendation", "crop recommendations",
        "crop suggestion", "crop suggestions", "crop to cultivate", "crops to cultivate", "recommendations for crop",
        "recommendations for crops", "best crop", "best crops", "suitable crop", "suitable crops",
        "कौन सी फसल", "कौनसी फसल", "क्या उगाएं", "क्या उगाना", "फसल उगानी", "फसल उगाएं",
        "फसल का सुझाव", "फसल की सिफारिश", "सबसे अच्छी फसल", "उपयुक्त फसल"
    ]
    return any(p in q for p in rec_patterns)

def is_season_missing(query: str, profile: dict | None = None) -> bool:
    """Checks if the season is unknown and cannot be inferred from context or declared crops."""
    # 1. Season explicitly provided in query or already selected by farmer
    if extract_season(query) is not None:
        return False

    if profile and (profile.get("farmer_selected_season") or profile.get("season")):
        return False

    # 2. Check if a crop is specified in query or profile with a clear primary season
    known_crops = profile.get("crops", []) if profile else []
    query_crops = extract_crops(query, [])
    all_crops = list(dict.fromkeys(known_crops + query_crops))

    loc = profile.get("location") if profile else extract_location(query)
    for c in all_crops:
        inferred = infer_primary_season(c, loc)
        if inferred:
            # If crop has a single clear primary season in this region/context, season is deterministically resolvable
            if is_single_primary_season_crop(c, loc):
                return False

    # If no crops or multi-season crops without clear context, season is missing
    if not all_crops:
        return True

    return False

def is_region_missing(query: str, profile: dict | None = None) -> bool:
    """Checks if the geographic region (State/UT) is unknown for crop recommendation."""
    if profile:
        loc = profile.get("location")
        if loc and str(loc).strip().lower() not in ["unknown", "none", "", "null"]:
            return False
    if extract_location(query) is not None:
        return False
    return True

def is_weather_query(query: str) -> bool:
    """Checks if the user query is asking for weather, forecast, rain, or temperature conditions."""
    if is_disease_query(query):
        return False
    q = query.lower()
    # Exclude environmental assessment queries that specifically ask for satellite/NDVI analysis
    env_markers = [
        "satellite", "environmental assessment", "ndvi", "dynamic world", "chirps",
        "farm environment", "उपग्रह", "खेत पर्यावरण"
    ]
    if any(m in q for m in env_markers):
        return False

    weather_keywords = [
        "weather", "forecast", "temperature", "humidity", "rain", "rainfall", "barish", "precipitation",
        "wind", "climate advisory", "weather advisory", "मौसम", "पूर्वानुमान", "बारिश", "तापमान", "हवा"
    ]
    return any(k in q for k in weather_keywords)

def is_weather_location_missing(query: str, profile: dict | None = None) -> bool:
    """Checks if location or coordinates are missing for a weather forecast query."""
    if profile:
        if profile.get("latitude") is not None and profile.get("longitude") is not None:
            return False
        loc = profile.get("location")
        if loc and str(loc).strip().lower() not in ["unknown", "none", "", "null"]:
            return False
    if extract_coordinates(query) is not None:
        return False
    if extract_location(query) is not None:
        return False
    return True

async def _hitl_checkpoint_impl(ctx: Context, node_input: Any) -> Event | AsyncGenerator:
    """Handles Human-in-the-Loop inputs if the orchestrator requests it."""
    query = ctx.state.get("user_query", "")
    profile = ctx.state.get("farmer_profile", {})
    language = profile.get("language", "English")
    if language == "Hindi":
        season_clarification_msg = (
            "🌾 सर्वोत्तम फसल की सिफारिश करने के लिए कृपया बताइए कि आप किस मौसम में खेती करना चाहते हैं:\n"
            "• खरीफ\n"
            "• रबी\n"
            "• ज़ायद"
        )
        region_clarification_msg = "🌾 सटीक फसल सलाह के लिए कृपया अपना राज्य (State/UT) बताइए (जैसे: उत्तर प्रदेश, पंजाब, महाराष्ट्र, राजस्थान)।"
        weather_location_msg = "🌦 मौसम और पूर्वानुमान की सटीक जानकारी के लिए कृपया अपना राज्य, जिला या शहर बताइए (जैसे: लखनऊ, पंजाब, जयपुर, बाराबंकी)।"
    else:
        season_clarification_msg = "To recommend the best crop, please tell me which season you are planning to farm in: Kharif, Rabi, or Zaid."
        region_clarification_msg = "To provide a tailored crop recommendation, please share your State/UT (e.g., Uttar Pradesh, Punjab, Maharashtra, Rajasthan)."
        weather_location_msg = "Please share your State, District, or City (e.g., Punjab, Uttar Pradesh, Jaipur, Lucknow) to get the local weather forecast."

    if hasattr(node_input, "model_dump"):
        node_input_dict = node_input.model_dump()
    elif isinstance(node_input, dict):
        node_input_dict = node_input
    elif hasattr(node_input, "__dict__"):
        node_input_dict = vars(node_input)
    else:
        node_input_dict = {"response": str(node_input) if node_input is not None else ""}

    # Progressive refinement for crop recommendations:
    # 1. First ensure season is known / selected
    # 2. Then ensure region (State/UT) is known
    if is_crop_recommendation_request(query, profile):
        if is_season_missing(query, profile):
            node_input_dict = {
                "response": "",
                "needs_more_info": True,
                "info_request_message": season_clarification_msg
            }
        elif is_region_missing(query, profile):
            node_input_dict = {
                "response": "",
                "needs_more_info": True,
                "info_request_message": region_clarification_msg
            }
    # Location refinement for Weather queries:
    elif is_weather_query(query) and is_weather_location_missing(query, profile):
        node_input_dict = {
            "response": "",
            "needs_more_info": True,
            "info_request_message": weather_location_msg
        }

    needs_more_info = node_input_dict.get("needs_more_info", False)
    info_request_message = node_input_dict.get("info_request_message", "")
    response = node_input_dict.get("response", "")

    if needs_more_info:
        if not ctx.resume_inputs or "more_info" not in ctx.resume_inputs:
            yield RequestInput(interrupt_id="more_info", message=info_request_message)
            return

        raw_answer = ctx.resume_inputs.pop("more_info")
        if isinstance(raw_answer, dict):
            user_answer = str(raw_answer.get("result", raw_answer)).strip()
        elif raw_answer is None:
            user_answer = ""
        else:
            user_answer = str(raw_answer).strip()

        original_query = ctx.state.get("user_query", "")
        if user_answer:
            updated_query = f"{original_query} (Additional farmer response: {user_answer})"
        else:
            updated_query = original_query
        ctx.state["user_query"] = updated_query

        # Update language based on user's answer (preserving session language for neutral option tokens)
        current_lang = profile.get("language", "English")
        if user_answer:
            profile["language"] = detect_language(user_answer, default=current_lang)

        if user_answer:
            season = extract_season(user_answer)
            if season:
                profile["farmer_selected_season"] = season
                profile["season"] = season

            loc = extract_location(user_answer)
            if loc:
                profile["location"] = loc

            coords = extract_coordinates(user_answer)
            if coords:
                profile["latitude"], profile["longitude"] = coords

            profile["crops"] = extract_crops(user_answer, profile.get("crops", []))

            sz = extract_farm_size(user_answer)
            if sz:
                profile["farm_size"] = sz

        current_calendar_season = profile.get("current_calendar_season", get_current_calendar_season())
        season_lines = []
        if profile.get("farmer_selected_season"):
            season_lines.append(f"- Requested / Farmer-Selected Season: {profile['farmer_selected_season']} (AUTHORITATIVE: You MUST advise for this requested season, regardless of current calendar month)")
        elif profile.get("inferred_season"):
            season_lines.append(f"- Inferred Crop Season: {profile['inferred_season']} (Derived from crop cultivation norms)")
        season_lines.append(f"- Current Calendar Season: {current_calendar_season}")
        season_str = "\n".join(season_lines) + "\n"

        # If this is a crop recommendation and region is still missing after season was provided, ask for State/UT
        if is_crop_recommendation_request(updated_query, profile) and is_region_missing(updated_query, profile):
            yield RequestInput(interrupt_id="more_info", message=region_clarification_msg)
            return

        coords_str = f"- Coordinates: {profile.get('latitude')}, {profile.get('longitude')}\n" if (profile.get("latitude") is not None and profile.get("longitude") is not None) else ""
        target_lang = profile.get("language", "English")
        orchestrator_prompt = (
            f"Farmer Profile:\n"
            f"- Location: {profile.get('location', 'Unknown')}\n"
            f"{coords_str}"
            f"- Crops: {', '.join(profile.get('crops', [])) if profile.get('crops') else 'None declared'}\n"
            f"- Farm Size: {profile.get('farm_size', 'Unknown')}\n"
            f"- Language: {target_lang}\n"
            f"{season_str}"
            f"User Query: {updated_query}\n\n"
            f"IMPORTANT LANGUAGE DIRECTIVE: The target Output Language is {target_lang}. You MUST produce your entire response strictly in {target_lang}, regardless of the script or language in the User Query."
        )

        yield Event(output=orchestrator_prompt, route="retry_with_info", state={"farmer_profile": profile, "user_query": updated_query})
        return

    yield Event(output=response)

hitl_checkpoint = node(rerun_on_resume=True)(_hitl_checkpoint_impl)

def format_final_output(node_input: str) -> Event:
    """Format and stream output to the UI."""
    yield Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=node_input)]
        )
    )
    yield Event(output=node_input)

# -----------------------------------------------------------------------------
# 5. Workflow Definitions
# -----------------------------------------------------------------------------

root_agent = Workflow(
    name="bharatsahayak_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {
            "__DEFAULT__": load_farmer_profile,
            "security_breach": format_final_output
        }),
        (load_farmer_profile, orchestrator),
        (orchestrator, hitl_checkpoint),
        (hitl_checkpoint, {
            "__DEFAULT__": format_final_output,
            "retry_with_info": orchestrator
        })
    ],
    description="BharatSahayak AI Farming Companion Workflow"
)

app = App(
    root_agent=root_agent,
    name="app",
    resumability_config=ResumabilityConfig(enabled=True)
)
