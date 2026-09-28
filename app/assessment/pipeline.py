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
"""Assessment orchestration pipeline for Phase 5 (DEC-023 / DEC-024).

Coordinates multi-source evidence retrieval (via Phase 4), delegates to the pure
deterministic reasoning engine to construct the authoritative AgriculturalAssessment (Phase 5B),
and optionally orchestrates natural-language explanation via Gemini 2.5 Flash (Phase 5C).
"""

from datetime import date, datetime
from typing import Union

from app.assessment.gemini_service import (
    GeminiModelClient,
    explain_agricultural_assessment,
)
from app.assessment.gemini_types import (
    AgriculturalAssessmentExplanationResponse,
    FarmerAgriculturalResponse,
    GeminiAssessmentContext,
    PresentationPreferences,
    RecommendedNextStep,
    VerifiedFarmerContext,
    assessment_to_gemini_context,
)
from app.assessment.reasoning import interpret_agricultural_evidence
from app.assessment.types import AgriculturalAssessment, AssessmentSufficiency
from app.fusion.pipeline import fetch_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.geometry import DEFAULT_ANALYSIS_RADIUS_M
from app.satellite.historical import (
    DEFAULT_HISTORICAL_YEARS,
    DEFAULT_WINDOW_HALF_DAYS,
)
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError


def evaluate_agricultural_assessment(
    evidence: AgriculturalEnvironmentalEvidence,
) -> AgriculturalAssessment:
    """Evaluates an existing AgriculturalEnvironmentalEvidence envelope to produce an AgriculturalAssessment.

    Args:
        evidence: Authoritative Phase 4 multi-source evidence envelope.

    Returns:
        AgriculturalAssessment: Structured domain assessment.
    """
    return interpret_agricultural_evidence(evidence)


def fetch_agricultural_assessment(
    latitude: float,
    longitude: float,
    reference_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    ndvi_lookback_days: int = 30,
    history_years: int = DEFAULT_HISTORICAL_YEARS,
    window_half_days: int = DEFAULT_WINDOW_HALF_DAYS,
    reanalysis_lookback_days: int = 90,
    rainfall_lookback_days: int = 90,
    land_cover_lookback_days: int = 30,
) -> AgriculturalAssessment:
    """Fetches multi-source evidence and performs deterministic agricultural interpretation (DEC-023).

    Args:
        latitude: Target center latitude coordinate [-90.0, 90.0].
        longitude: Target center longitude coordinate [-180.0, 180.0].
        reference_date: Anchor query reference date (UTC). Defaults to current UTC date.
        radius_m: Circular analysis region radius in meters (default 100.0m).
        ndvi_lookback_days: Retrospective lookback window for Sentinel-2 NDVI (default 30 days).
        history_years: Number of historical target years for seasonal NDVI baseline (default 3).
        window_half_days: Half-width of historical seasonal matching window (default 15 days).
        reanalysis_lookback_days: Retrospective window for ERA5-Land (default 90 days).
        rainfall_lookback_days: Retrospective window for CHIRPS rainfall (default 90 days).
        land_cover_lookback_days: Retrospective window for Dynamic World land cover (default 30 days).

    Returns:
        AgriculturalAssessment: Authoritative structured assessment envelope.
    """
    try:
        evidence = fetch_agricultural_environmental_evidence(
            latitude=latitude,
            longitude=longitude,
            reference_date=reference_date,
            radius_m=radius_m,
            ndvi_lookback_days=ndvi_lookback_days,
            history_years=history_years,
            window_half_days=window_half_days,
            reanalysis_lookback_days=reanalysis_lookback_days,
            rainfall_lookback_days=rainfall_lookback_days,
            land_cover_lookback_days=land_cover_lookback_days,
        )
        return interpret_agricultural_evidence(evidence)
    except Exception as exc:
        # Construct fallback error assessment envelope
        ref_date = date.today() if reference_date is None else (
            reference_date if isinstance(reference_date, date) else date.today()
        )
        region = AnalysisRegionMetadata(
            latitude=float(latitude) if isinstance(latitude, (int, float)) else 0.0,
            longitude=float(longitude) if isinstance(longitude, (int, float)) else 0.0,
            radius_m=float(radius_m) if isinstance(radius_m, (int, float)) else 100.0,
            geometry_type="PointBuffer",
            scale_m=10.0,
        )
        # Attempt to retrieve fallback evidence from Phase 4 if available
        fallback_evidence = fetch_agricultural_environmental_evidence(
            latitude=0.0, longitude=0.0, reference_date=ref_date
        ) if False else None  # Avoid recursive calls on error

        raise exc


# ==============================================================================
# Phase 5C Step 4: Unified Assessment & Explanation Integration
# ==============================================================================

_ERROR_FALLBACK_TEMPLATES = {
    "en": {
        "headline": "Environmental assessment is currently unavailable due to a service error.",
        "summary": "We could not retrieve or process the required environmental data services at this time. No assessment could be completed.",
        "interpretation": "An unexpected service error occurred while processing environmental data streams for this region.",
        "steps": [
            RecommendedNextStep(
                action_type="missing_information_gathering",
                description="Please try again later once environmental data services have resumed.",
                urgency="routine",
            ),
            RecommendedNextStep(
                action_type="field_visual_inspection",
                description="Perform direct visual inspection in your field for current crop and soil conditions.",
                urgency="routine",
            ),
        ],
    },
    "hi": {
        "headline": "तकनीकी त्रुटि के कारण वर्तमान में पर्यावरणीय मूल्यांकन उपलब्ध नहीं है।",
        "summary": "इस समय आवश्यक पर्यावरणीय डेटा सेवाओं को प्राप्त या संसाधित नहीं किया जा सका। कोई मूल्यांकन पूरा नहीं किया जा सका।",
        "interpretation": "इस क्षेत्र के लिए पर्यावरणीय डेटा धाराओं को संसाधित करते समय एक सेवा त्रुटि हुई।",
        "steps": [
            RecommendedNextStep(
                action_type="missing_information_gathering",
                description="कृपया पर्यावरणीय डेटा सेवाएं फिर से शुरू होने के बाद पुनः प्रयास करें।",
                urgency="routine",
            ),
            RecommendedNextStep(
                action_type="field_visual_inspection",
                description="फसल और मिट्टी की वर्तमान स्थिति के लिए अपने खेत का प्रत्यक्ष निरीक्षण करें।",
                urgency="routine",
            ),
        ],
    },
}


def _generate_error_farmer_response(
    context: GeminiAssessmentContext,
) -> FarmerAgriculturalResponse:
    """Generates a deterministic farmer-facing response when assessment status is error.

    Bypasses Gemini API invocation completely to avoid hallucinating condition assertions
    when upstream infrastructure or data processing failed.

    Args:
        context: Authoritative projected context envelope.

    Returns:
        FarmerAgriculturalResponse: Constrained, deterministic error explanation.
    """
    target_lang = context.presentation.target_language
    template = _ERROR_FALLBACK_TEMPLATES.get(
        target_lang, _ERROR_FALLBACK_TEMPLATES["en"]
    )

    limitations = (
        list(context.limitations)
        if context.limitations
        else ["Environmental data services were temporarily unavailable or encountered a processing error."]
    )

    return FarmerAgriculturalResponse(
        language=target_lang,
        headline=template["headline"],
        summary=template["summary"],
        observations=[],
        interpretation=template["interpretation"],
        recommended_next_steps=template["steps"],
        limitations=limitations,
        is_fallback=True,
    )


def evaluate_and_explain_agricultural_assessment(
    evidence: AgriculturalEnvironmentalEvidence,
    farmer_context: VerifiedFarmerContext | None = None,
    presentation: PresentationPreferences | None = None,
    client: GeminiModelClient | None = None,
) -> AgriculturalAssessmentExplanationResponse:
    """Evaluates multi-source evidence and generates an authoritative explanation (DEC-024).

    Composes Phase 5B deterministic reasoning with Phase 5C Gemini natural language explanation.
    Phase 5B remains the sole authoritative source of truth.

    Policy:
    - status in ('success', 'partial', 'insufficient_evidence'): invokes Gemini explanation service
    - status == 'error': bypasses Gemini and produces deterministic error explanation

    Args:
        evidence: Authoritative Phase 4 multi-source evidence envelope.
        farmer_context: Optional whitelisted farmer personalization context.
        presentation: Optional presentation and tone preferences.
        client: Optional GeminiModelClient instance for dependency injection.

    Returns:
        AgriculturalAssessmentExplanationResponse: Unified envelope containing deterministic assessment,
        natural-language explanation, and exact context used.
    """
    assessment = evaluate_agricultural_assessment(evidence)
    context = assessment_to_gemini_context(
        assessment=assessment,
        farmer_context=farmer_context,
        presentation=presentation,
    )

    if assessment.status == "error":
        explanation = _generate_error_farmer_response(context)
    else:
        explanation = explain_agricultural_assessment(context, client=client)

    return AgriculturalAssessmentExplanationResponse(
        assessment=assessment,
        explanation=explanation,
        context_used=context,
    )


def fetch_agricultural_assessment_explanation(
    latitude: float,
    longitude: float,
    reference_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    ndvi_lookback_days: int = 30,
    history_years: int = DEFAULT_HISTORICAL_YEARS,
    window_half_days: int = DEFAULT_WINDOW_HALF_DAYS,
    reanalysis_lookback_days: int = 90,
    rainfall_lookback_days: int = 90,
    land_cover_lookback_days: int = 30,
    farmer_context: VerifiedFarmerContext | None = None,
    presentation: PresentationPreferences | None = None,
    client: GeminiModelClient | None = None,
) -> AgriculturalAssessmentExplanationResponse:
    """Fetches multi-source evidence, evaluates assessment, and generates explanation (DEC-024).

    Args:
        latitude: Target center latitude coordinate [-90.0, 90.0].
        longitude: Target center longitude coordinate [-180.0, 180.0].
        reference_date: Anchor query reference date (UTC). Defaults to current UTC date.
        radius_m: Circular analysis region radius in meters (default 100.0m).
        ndvi_lookback_days: Retrospective lookback window for Sentinel-2 NDVI (default 30 days).
        history_years: Number of historical target years for seasonal NDVI baseline (default 3).
        window_half_days: Half-width of historical seasonal matching window (default 15 days).
        reanalysis_lookback_days: Retrospective window for ERA5-Land (default 90 days).
        rainfall_lookback_days: Retrospective window for CHIRPS rainfall (default 90 days).
        land_cover_lookback_days: Retrospective window for Dynamic World land cover (default 30 days).
        farmer_context: Optional whitelisted farmer personalization context.
        presentation: Optional presentation and tone preferences.
        client: Optional GeminiModelClient instance for dependency injection.

    Returns:
        AgriculturalAssessmentExplanationResponse: Unified assessment and explanation envelope.
    """
    evidence = fetch_agricultural_environmental_evidence(
        latitude=latitude,
        longitude=longitude,
        reference_date=reference_date,
        radius_m=radius_m,
        ndvi_lookback_days=ndvi_lookback_days,
        history_years=history_years,
        window_half_days=window_half_days,
        reanalysis_lookback_days=reanalysis_lookback_days,
        rainfall_lookback_days=rainfall_lookback_days,
        land_cover_lookback_days=land_cover_lookback_days,
    )
    return evaluate_and_explain_agricultural_assessment(
        evidence=evidence,
        farmer_context=farmer_context,
        presentation=presentation,
        client=client,
    )
