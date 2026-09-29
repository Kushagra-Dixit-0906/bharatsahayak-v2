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
"""Phase 5D Deterministic Safe Fallback Generator.

Generates 100% deterministic, pure-Python CropProblemAdvisory payloads when Gemini
is unavailable or when Gemini output fails strict validation.

CRITICAL ARCHITECTURAL INVARIANTS:
1. THE FALLBACK IS NOT A SECOND DIAGNOSIS MODEL: It does not map keywords to definitive diseases.
2. Grounded Only: Synthesizes exclusively from retrieved KnowledgeEntry records, farmer observations,
   and optional Phase 5B/5C environmental context.
3. Zero Chemical Prescriptions: Strictly zero pesticide/fungicide spray recommendations or dosages.
4. Qualitative Match Levels Only: Uses SymptomMatchLevel literals derived deterministically from overlap.
5. Preserves Candidate Semantics: Conditions are differential candidates, NEVER confirmed diagnoses.
"""

from typing import Sequence

from app.assessment.gemini_types import GeminiAssessmentContext
from app.assessment.types import AgriculturalAssessment
from app.disease.corpus import AgriculturalKnowledgeCorpus
from app.disease.retriever import KnowledgeRetrievalResult, ParsedQueryTerms
from app.disease.types import (
    AdvisoryStatus,
    CropProblemAdvisory,
    ExpertReferralUrgency,
    KnowledgeEntry,
    KnowledgeReference,
    PossibleCondition,
    SafeActionCategory,
    SafeCulturalAction,
    SymptomMatchLevel,
)


def _determine_match_level(
    matched_fields: list[str],
    matched_terms: list[str],
) -> SymptomMatchLevel:
    """Deterministically derives a qualitative SymptomMatchLevel from keyword overlap.

    Note: This is an internal heuristic for qualitative literature grounding and has
    NO statistical confidence or probability meaning.
    """
    has_crop = "crop" in matched_fields
    has_part = "plant_part" in matched_fields
    has_symptoms = "symptom_keywords" in matched_fields
    term_count = len(matched_terms)

    if has_crop and has_part and has_symptoms and term_count >= 3:
        return "strong_match"
    if (has_crop and has_symptoms) or term_count >= 2:
        return "possible_match"
    if term_count >= 1:
        return "weak_match"
    return "insufficient_information"


def _categorize_action(practice_text: str) -> SafeActionCategory:
    """Categorizes a safe cultural practice text into an authorized SafeActionCategory."""
    lower = practice_text.lower()
    if any(k in lower for k in ["water", "irrigation", "drainage", "moisture", "जल", "सिंचाई", "नमी"]):
        return "water_management"
    if any(k in lower for k in ["remove", "burn", "clean", "destroy", "sanitation", "debris", "सफाई", "नष्ट"]):
        return "sanitation"
    if any(k in lower for k in ["nitrogen", "potash", "phosphorus", "fertilizer", "nutrient", "उर्वरक", "पोषण"]):
        return "nutrient_balance"
    if any(k in lower for k in ["consult", "kvk", "officer", "expert", "सलाह", "विशेषज्ञ"]):
        return "expert_referral"
    return "field_monitoring"


def _format_env_fallback_summary(
    env_context: AgriculturalAssessment | GeminiAssessmentContext | str | None,
    language: str,
) -> str | None:
    """Builds a conservative, non-diagnostic environmental summary for fallback."""
    if env_context is None:
        return None

    if isinstance(env_context, str):
        return env_context.strip()

    if isinstance(env_context, AgriculturalAssessment):
        cond = env_context.overall_condition
        if language == "hi":
            return (
                f"क्षेत्रीय पर्यावरणीय स्थिति '{cond}' के रूप में दर्ज की गई है। "
                "यह केवल पृष्ठभूमि संदर्भ प्रदान करता है और रोग की पुष्टि नहीं करता।"
            )
        return (
            f"Regional environmental condition is recorded as '{cond}'. "
            "This provides background context only and does not establish disease identity."
        )

    if isinstance(env_context, GeminiAssessmentContext):
        cond = env_context.overall_condition
        if language == "hi":
            return (
                f"क्षेत्रीय उपग्रह व मौसम स्थिति '{cond}' आंकी गई है। "
                "यह केवल पृष्ठभूमि संदर्भ है और रोग का निदान नहीं करता।"
            )
        return (
            f"Regional satellite and meteorological condition is assessed as '{cond}'. "
            "This provides background context only and does not diagnose disease."
        )

    return str(env_context)


def generate_deterministic_crop_advisory(
    farmer_query: str,
    retrieved_results: Sequence[KnowledgeRetrievalResult | KnowledgeEntry],
    corpus: AgriculturalKnowledgeCorpus | None = None,
    environmental_context: AgriculturalAssessment | GeminiAssessmentContext | str | None = None,
    language: str = "en",
) -> CropProblemAdvisory:
    """Generates a pure-Python deterministic CropProblemAdvisory without invoking Gemini.

    Args:
        farmer_query: Raw symptom description or localized query from farmer.
        retrieved_results: Sequence of KnowledgeRetrievalResult or KnowledgeEntry records.
        corpus: Optional AgriculturalKnowledgeCorpus to resolve document titles and provenance.
        environmental_context: Optional Phase 5B/5C environmental context.
        language: Target communication language ('en' or 'hi').

    Returns:
        CropProblemAdvisory: Fully compliant, grounded deterministic fallback advisory (is_fallback=True).

    Raises:
        ValueError: If farmer_query is empty or whitespace-only.
    """
    if not farmer_query or not farmer_query.strip():
        raise ValueError("farmer_query must not be empty or whitespace-only")

    parsed_query = ParsedQueryTerms(farmer_query)

    # 1. Identify Crop
    if retrieved_results:
        first_entry = (
            retrieved_results[0].entry
            if isinstance(retrieved_results[0], KnowledgeRetrievalResult)
            else retrieved_results[0]
        )
        crop_identified = first_entry.crop
    elif parsed_query.detected_crops:
        crop_identified = sorted(parsed_query.detected_crops)[0].capitalize()
    else:
        crop_identified = "Unknown"

    # 2. Extract Reported Symptoms
    if parsed_query.detected_symptoms:
        reported_symptoms = [s.capitalize() for s in sorted(parsed_query.detected_symptoms)]
    else:
        # Fallback to non-stopword tokens or general query indication
        meaningful_tokens = [t for t in parsed_query.canonical_tokens if len(t) > 2]
        reported_symptoms = [t.capitalize() for t in meaningful_tokens[:5]] if meaningful_tokens else ["Unspecified visible symptoms"]

    # 3. Environmental Context Summary
    env_summary = _format_env_fallback_summary(environmental_context, language)

    # -----------------------------------------------------------------------
    # Case A: No Retrieved Knowledge Entries Available
    # -----------------------------------------------------------------------
    if not retrieved_results:
        status: AdvisoryStatus = "insufficient_evidence"
        uncertainty_reasons = (
            [
                "बताए गए लक्षणों के लिए ज्ञानकोष में कोई प्रमाणित कृषि संदर्भ नहीं मिला।",
                "किसी भी रासायनिक या कृषि हस्तक्षेप से पहले प्रत्यक्ष निरीक्षण की सलाह दी जाती है।",
            ]
            if language == "hi"
            else [
                "No matching verified agricultural extension literature found for reported symptoms.",
                "Direct field examination by an agricultural expert is recommended before taking any intervention.",
            ]
        )
        clarifying_questions = (
            [
                "कौन सी फसल प्रभावित है?",
                "पौधे का कौन सा भाग (पत्ती, तना, जड़, दाना) लक्षण दिखा रहा है?",
                "दिखाई देने वाले धब्बों या निशानों का रंग और आकार कैसा है?",
            ]
            if language == "hi"
            else [
                "Which crop species is showing symptoms?",
                "Which plant part (leaf, stem, root, grain) is primarily affected?",
                "What specific color, shape, or pattern do the spots/lesions exhibit?",
            ]
        )
        expert_urgency: ExpertReferralUrgency = "advisory"
        expert_rec = (
            "कृपया खेत में प्रत्यक्ष निरीक्षण हेतु अपने नजदीकी कृषि विज्ञान केंद्र (KVK) या कृषि विस्तार अधिकारी से संपर्क करें।"
            if language == "hi"
            else "Please consult your local Krishi Vigyan Kendra (KVK) or agricultural extension officer for on-field visual examination."
        )

        return CropProblemAdvisory(
            status=status,
            crop_identified=crop_identified,
            reported_symptoms=reported_symptoms,
            possible_conditions=[],
            safe_cultural_actions=[],
            environmental_context_summary=env_summary,
            uncertainty_reasons=uncertainty_reasons,
            clarifying_questions=clarifying_questions,
            expert_referral_urgency=expert_urgency,
            expert_referral_recommendation=expert_rec,
            knowledge_sources=[],
            is_fallback=True,
        )

    # -----------------------------------------------------------------------
    # Case B & C: Retrieved Knowledge Entries Available
    # -----------------------------------------------------------------------
    possible_conditions: list[PossibleCondition] = []
    safe_cultural_actions: list[SafeCulturalAction] = []
    knowledge_sources: list[KnowledgeReference] = []
    clarifying_questions_set: list[str] = []
    seen_conditions: set[str] = set()
    seen_actions: set[str] = set()
    seen_sources: set[str] = set()

    has_strong_match = False

    # Process up to top 3 candidate records
    for item in retrieved_results[:3]:
        if isinstance(item, KnowledgeRetrievalResult):
            entry = item.entry
            matched_fields = item.matched_fields
            matched_terms = item.matched_terms
        else:
            entry = item
            matched_fields = ["crop", "symptom_keywords"]
            matched_terms = list(entry.symptom_keywords)

        if entry.condition_name in seen_conditions:
            continue
        seen_conditions.add(entry.condition_name)

        match_level = _determine_match_level(matched_fields, matched_terms)
        if match_level == "strong_match":
            has_strong_match = True

        reasoning = (
            f"बताए गए लक्षण संदर्भ साहित्य में दर्ज '{entry.condition_name}' के विवरण से मेल खाते हैं। "
            "यह एक संभावित स्थिति है; प्रत्यक्ष पुष्टि आवश्यक है।"
            if language == "hi"
            else f"Reported symptoms align with reference literature for candidate condition '{entry.condition_name}'. "
            "This is a differential hypothesis; ground verification is required."
        )

        possible_conditions.append(
            PossibleCondition(
                condition_name=entry.condition_name,
                scientific_name=entry.scientific_name,
                category=entry.category,
                symptom_match=match_level,
                reasoning=reasoning,
            )
        )

        # Collect safe cultural practices strictly from entry
        for practice in entry.safe_cultural_practices:
            if practice not in seen_actions:
                seen_actions.add(practice)
                action_cat = _categorize_action(practice)
                safe_cultural_actions.append(
                    SafeCulturalAction(
                        action_type=action_cat,
                        description=practice,
                    )
                )

        # Collect clarifying observations strictly from entry
        for obs in entry.clarifying_observations:
            if obs not in clarifying_questions_set:
                clarifying_questions_set.append(obs)

        # Collect citation strictly linking to entry.source_id
        if entry.source_id not in seen_sources:
            seen_sources.add(entry.source_id)
            doc_title = f"Agricultural Field Guide ({entry.crop})"
            org = "Agricultural Extension Service"
            if corpus:
                prov = corpus.get_source(entry.source_id)
                if prov:
                    doc_title = prov.document_title
                    org = prov.organization

            knowledge_sources.append(
                KnowledgeReference(
                    source_id=entry.source_id,
                    document_title=doc_title,
                    organization=org,
                    relevant_excerpt=entry.description,
                )
            )

    # Determine top-level operational status
    status = "success" if has_strong_match else "partial"

    # Uncertainty reasons
    uncertainty_reasons = (
        [
            "केवल दृश्य लक्षणों के आधार पर रोग की निश्चित पुष्टि नहीं की जा सकती।",
            "सटीक पहचान के लिए स्थानीय कृषि विशेषज्ञ या प्रयोगशाला जांच की आवश्यकता होती है।",
        ]
        if language == "hi"
        else [
            "Visual field symptoms alone cannot definitively distinguish lookalike disorders.",
            "Extension officer or laboratory verification is recommended before taking major interventions.",
        ]
    )

    # Referral policy
    expert_urgency = "none" if status == "success" and len(possible_conditions) == 1 else "advisory"
    expert_rec = (
        (
            "यदि लक्षण तेजी से फैलते हैं या फसल का 5% से अधिक भाग प्रभावित होता है, तो KVK से परामर्श लें।"
            if language == "hi"
            else "Consult your local Krishi Vigyan Kendra (KVK) if symptoms spread rapidly or exceed 5% of canopy."
        )
        if expert_urgency != "none"
        else None
    )

    return CropProblemAdvisory(
        status=status,
        crop_identified=crop_identified,
        reported_symptoms=reported_symptoms,
        possible_conditions=possible_conditions,
        safe_cultural_actions=safe_cultural_actions,
        environmental_context_summary=env_summary,
        uncertainty_reasons=uncertainty_reasons,
        clarifying_questions=clarifying_questions_set[:3],
        expert_referral_urgency=expert_urgency,
        expert_referral_recommendation=expert_rec,
        knowledge_sources=knowledge_sources,
        is_fallback=True,
    )
