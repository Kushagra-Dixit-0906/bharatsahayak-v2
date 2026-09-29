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
"""Phase 5D Isolated Gemini Crop Problem Advisory Service.

Coordinates prompt synthesis, structured Gemini model invocation, strict JSON/Pydantic
validation, and defense-in-depth safety checks for crop problem inquiries.

Architectural Invariants:
1. Isolated Reasoning Boundary: Uses Gemini strictly as a synthesis/reasoning engine over
   deterministic retrieval results and optional environmental evidence.
2. Zero Hallucinated Citations: Validates that all cited knowledge_sources resolve to
   actually supplied retrieval context.
3. Strict Defense-in-Depth: Scans for prohibited chemical spray prescriptions, quantitative
   dosages, and pseudo-confidence percentages.
4. Clean Failure Contract: Raises specific, controlled exceptions on schema, parsing,
   or safety violations (fallback orchestration deferred to Step 4).
"""

import json
import logging
import re
from typing import Sequence

from pydantic import ValidationError

from app.assessment.gemini_service import DefaultGeminiClient, GeminiModelClient
from app.assessment.gemini_types import GeminiAssessmentContext
from app.assessment.types import AgriculturalAssessment
from app.config import config
from app.disease.prompt import build_crop_problem_prompt
from app.disease.retriever import KnowledgeRetrievalResult
from app.disease.types import CropProblemAdvisory, KnowledgeEntry

logger = logging.getLogger(__name__)


# ==============================================================================
# Service Error Hierarchy
# ==============================================================================


class CropProblemAdvisoryError(Exception):
    """Base exception for all Phase 5D disease advisory service failures."""


class GeminiGenerationError(CropProblemAdvisoryError):
    """Raised when the Gemini client or API call fails or times out."""


class AdvisoryParsingError(CropProblemAdvisoryError):
    """Raised when the model output is not valid JSON or cannot be decoded."""


class AdvisoryValidationError(CropProblemAdvisoryError):
    """Raised when the model output fails Pydantic schema validation or enum constraints."""


class AdvisorySafetyRejectionError(CropProblemAdvisoryError):
    """Raised when post-validation defense-in-depth checks detect unsafe or hallucinated content."""


# ==============================================================================
# Defense-in-Depth Banned Content Patterns
# ==============================================================================

BANNED_DOSAGE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:kg|grams?|gms?|litres?|liters?|ml|quintals?)\s*(?:/|per|\s+per\s+)\s*(?:acre|hectare|ha|bigha|guntha|katha|litre|liter|l)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:kg|grams?|gms?|litres?|liters?|ml)\s+of\s+(?:urea|dap|fertilizer|npk|potash|mop|mancozeb|chlorpyrifos|carbendazim|imidacloprid|pesticide|fungicide)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d+(?:\.\d+)?\s*(?:g|gm|gms|ml)\s*/\s*(?:l|liter|litre)\b",
        re.IGNORECASE,
    ),
]

BANNED_CHEMICAL_PRESCRIPTIONS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:apply|spray|use|inject|treat\s+with|dose)\s+(?:urea|dap|glyphosate|mancozeb|chlorpyrifos|carbendazim|imidacloprid|monocrotophos|atrazine|paraquat|2,4-d|propiconazole|hexaconazole|thiamethoxam|cypermethrin|malathion|copper\s+oxychloride)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:mancozeb|chlorpyrifos|carbendazim|imidacloprid|monocrotophos|atrazine|paraquat|2,4-d|propiconazole|hexaconazole|thiamethoxam|cypermethrin|malathion)\s+(?:spray|dosage|treatment|application)\b",
        re.IGNORECASE,
    ),
]

BANNED_NUMERICAL_CONFIDENCE: list[re.Pattern[str]] = [
    re.compile(r"\b\d+%\s*(?:confidence|certainty|probability|sure)\b", re.IGNORECASE),
    re.compile(r"\b(?:confidence|probability)\s*(?:score|level)?\s*:\s*\d+", re.IGNORECASE),
]

BANNED_ABSOLUTE_CLAIMS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:confirmed|definitive|guaranteed|100%)\s+diagnosis\b", re.IGNORECASE),
    re.compile(r"\b(?:diagnosed\s+definitively\s+as|disease\s+is\s+confirmed)\b", re.IGNORECASE),
]


# ==============================================================================
# Post-Validation Safety Checks
# ==============================================================================


def validate_advisory_payload(
    advisory: CropProblemAdvisory,
    valid_source_ids: set[str],
    has_env_context: bool,
) -> tuple[bool, str]:
    """Performs defense-in-depth safety and provenance consistency checks on advisory payload.

    Args:
        advisory: The Pydantic-validated CropProblemAdvisory object.
        valid_source_ids: Set of source_id strings actually supplied in the prompt.
        has_env_context: Whether environmental context was provided in the prompt.

    Returns:
        tuple[bool, str]: (is_valid, rejection_reason)
    """
    # 1. Structural constraints
    if not advisory.crop_identified.strip():
        return False, "Empty crop_identified field"

    # Normal Gemini response must not claim to be fallback
    if advisory.is_fallback:
        return False, "Non-fallback Gemini response has is_fallback=True"

    # 2. Source ID Provenance Integrity Check
    for ref in advisory.knowledge_sources:
        if ref.source_id not in valid_source_ids:
            return False, f"Hallucinated or unregistered source_id cited: '{ref.source_id}'"

    # If no sources were provided, no knowledge sources may be claimed
    if not valid_source_ids and advisory.knowledge_sources:
        return False, "Knowledge sources cited when no knowledge entries were supplied"

    # 3. Environmental Grounding Check
    if not has_env_context and advisory.environmental_context_summary is not None:
        # Check if model fabricated specific numerical environmental measurements
        summary_text = advisory.environmental_context_summary
        if re.search(r"\b(?:ndvi|rainfall|precipitation|temperature|soil\s+moisture)\s*=\s*\d+", summary_text, re.IGNORECASE):
            return False, "Invented quantitative environmental measurements when no environmental context was provided"

    # 4. Defense-in-Depth Banned Content Checks
    text_blocks: list[str] = [
        advisory.crop_identified,
        *advisory.reported_symptoms,
        *(cond.condition_name for cond in advisory.possible_conditions),
        *(cond.reasoning for cond in advisory.possible_conditions),
        *(action.description for action in advisory.safe_cultural_actions),
        *(advisory.uncertainty_reasons),
        *(advisory.clarifying_questions),
    ]
    if advisory.environmental_context_summary:
        text_blocks.append(advisory.environmental_context_summary)
    if advisory.expert_referral_recommendation:
        text_blocks.append(advisory.expert_referral_recommendation)

    full_text = " ".join(text_blocks)

    for pattern in BANNED_DOSAGE_PATTERNS:
        if pattern.search(full_text):
            return False, f"Banned quantitative chemical dosage detected: {pattern.pattern}"

    for pattern in BANNED_CHEMICAL_PRESCRIPTIONS:
        if pattern.search(full_text):
            return False, f"Banned chemical prescription detected: {pattern.pattern}"

    for pattern in BANNED_NUMERICAL_CONFIDENCE:
        if pattern.search(full_text):
            return False, f"Banned numerical confidence claim detected: {pattern.pattern}"

    for pattern in BANNED_ABSOLUTE_CLAIMS:
        if pattern.search(full_text):
            return False, f"Banned absolute diagnosis claim detected: {pattern.pattern}"

    return True, "Valid"


# ==============================================================================
# Service API
# ==============================================================================


def generate_crop_problem_advisory(
    farmer_query: str,
    retrieved_knowledge: Sequence[KnowledgeEntry | KnowledgeRetrievalResult],
    environmental_context: AgriculturalAssessment | GeminiAssessmentContext | str | None = None,
    language: str = "en",
    client: GeminiModelClient | None = None,
    model: str | None = None,
) -> CropProblemAdvisory:
    """Invokes Gemini to synthesize a grounded CropProblemAdvisory over retrieved evidence.

    Args:
        farmer_query: Free-text question or symptom description reported by farmer.
        retrieved_knowledge: Sequence of KnowledgeEntry or KnowledgeRetrievalResult records.
        environmental_context: Optional Phase 5B/5C environmental assessment or summary string.
        language: Target communication language ('en' or 'hi').
        client: Optional GeminiModelClient for dependency injection (defaults to DefaultGeminiClient).
        model: Optional model name (defaults to config.model / gemini-2.5-flash).

    Returns:
        CropProblemAdvisory: Validated, grounded advisory output.

    Raises:
        ValueError: If farmer_query is invalid.
        GeminiGenerationError: If the Gemini API call fails.
        AdvisoryParsingError: If model response is not valid JSON.
        AdvisoryValidationError: If response violates CropProblemAdvisory schema or enums.
        AdvisorySafetyRejectionError: If response fails defense-in-depth safety checks.
    """
    # 1. Build controlled prompt
    prompt_text = build_crop_problem_prompt(
        farmer_query=farmer_query,
        retrieved_knowledge=retrieved_knowledge,
        environmental_context=environmental_context,
        language=language,
    )

    # Collect valid source IDs for post-validation check
    valid_source_ids: set[str] = set()
    for item in retrieved_knowledge:
        if isinstance(item, KnowledgeRetrievalResult):
            valid_source_ids.add(item.entry.source_id)
        elif isinstance(item, KnowledgeEntry):
            valid_source_ids.add(item.source_id)

    has_env = environmental_context is not None

    # Resolve client and model
    resolved_client = client if client is not None else DefaultGeminiClient()
    resolved_model = model if model is not None else config.model

    # Configure structured JSON output via Google GenAI SDK
    from google.genai import types

    generate_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CropProblemAdvisory,
        temperature=0.2,
    )

    # 2. Invoke Gemini model
    try:
        response_obj = resolved_client.generate_content(
            model=resolved_model,
            contents=prompt_text,
            config=generate_config,
        )
    except Exception as exc:
        logger.error("Gemini generation failed: %s", exc)
        raise GeminiGenerationError(f"Gemini client invocation failed: {exc}") from exc

    # 3. Extract text content
    raw_text = ""
    if hasattr(response_obj, "text") and response_obj.text:
        raw_text = response_obj.text
    elif isinstance(response_obj, str):
        raw_text = response_obj
    else:
        raw_text = str(response_obj)

    if not raw_text or not raw_text.strip():
        raise AdvisoryParsingError("Received empty or whitespace response from Gemini model")

    # 4. Strict JSON Parsing
    try:
        parsed_dict = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to decode Gemini response as JSON: %s", exc)
        raise AdvisoryParsingError(f"Malformed JSON in Gemini response: {exc}") from exc

    if not isinstance(parsed_dict, dict):
        raise AdvisoryValidationError(f"Expected JSON object at root, got {type(parsed_dict).__name__}")

    # 5. Strict Pydantic Schema Validation
    try:
        advisory = CropProblemAdvisory.model_validate(parsed_dict)
    except ValidationError as exc:
        logger.warning("Gemini response failed CropProblemAdvisory validation: %s", exc)
        raise AdvisoryValidationError(f"Schema validation failed: {exc}") from exc

    # 6. Post-Validation Defense-in-Depth & Provenance Checks
    is_valid, reason = validate_advisory_payload(
        advisory=advisory,
        valid_source_ids=valid_source_ids,
        has_env_context=has_env,
    )
    if not is_valid:
        logger.warning("Gemini advisory rejected by safety validation: %s", reason)
        raise AdvisorySafetyRejectionError(f"Advisory safety validation rejected: {reason}")

    return advisory
