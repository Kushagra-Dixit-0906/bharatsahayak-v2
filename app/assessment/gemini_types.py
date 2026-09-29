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
"""Phase 5C Structured Context Models and Projection Serializer for Gemini Explanation (DEC-024).

This module defines the purpose-built, auditable, and immutable input boundary
(`GeminiAssessmentContext`) that projects the deterministic `AgriculturalAssessment`
from Phase 5B into structured context for downstream Gemini natural-language explanation.

Boundary Invariants:
- Phase 5B remains the sole authoritative deterministic interpretation layer.
- This module contains ZERO Gemini API calls, ZERO prompt templates, and ZERO network I/O.
- The projection is purely functional: it copies verified facts without reinterpreting,
  recalculating, mutating, or overriding them.
- Farmer context is strictly personalization context, NEVER environmental evidence.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.assessment.types import (
    AgriculturalAssessment,
    AssessmentStatus,
    EnvironmentalStressPatternType,
    EvidenceSupportLevel,
    OverallEnvironmentalCondition,
    SupportingEvidenceItem,
)
from app.satellite.types import AnalysisRegionMetadata

ContextStatus = Literal["verified", "stale", "unknown"]
TargetLanguage = Literal["en", "hi", "pa", "mr", "te", "ta", "kn", "bn", "gu"]


class ContextPatternSummary(BaseModel):
    """Lean summary of an identified environmental stress pattern for LLM context."""

    pattern_type: EnvironmentalStressPatternType = Field(
        description="Canonical evidence pattern type from the Phase 5 taxonomy"
    )
    evidence_support: EvidenceSupportLevel = Field(
        description="Auditable categorical level of corroborating verified evidence"
    )
    technical_summary: str = Field(
        description="Deterministic internal diagnostic summary of the pattern (grounding context only; not farmer-facing text)"
    )
    supporting_evidence: list[SupportingEvidenceItem] = Field(
        default_factory=list,
        description="Structured, traceable physical observations backing this pattern (primary grounding input for Gemini)",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class VerifiedFarmerContext(BaseModel):
    """Restricted whitelisted farmer personalization context. Not environmental evidence."""

    crop: str | None = Field(
        default=None,
        description="Verified crop name (e.g. 'wheat') to contextualize conversational phrasing",
    )
    crop_stage: str | None = Field(
        default=None,
        description="Verified crop growth stage (e.g. 'vegetative', 'flowering')",
    )
    irrigation_available: bool | None = Field(
        default=None,
        description="Verified presence of on-farm irrigation capability (e.g. tube-well, canal)",
    )
    preferred_language: TargetLanguage = Field(
        default="en",
        description="Target output language code (e.g. 'en', 'hi')",
    )
    context_status: ContextStatus = Field(
        default="unknown",
        description="Operational freshness state: verified | stale | unknown",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class PresentationPreferences(BaseModel):
    """Output presentation preferences."""

    target_language: TargetLanguage = Field(
        default="en",
        description="Desired natural language ISO code for the generated explanation",
    )
    communication_tone: Literal["rural_empathetic_concise", "technical_standard"] = Field(
        default="rural_empathetic_concise",
        description="Conversational framing style for the output",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class GeminiAssessmentContext(BaseModel):
    """Authoritative input envelope passed to the Gemini explanation layer (DEC-024)."""

    # 1. Deterministic Environmental Assessment Data
    overall_condition: OverallEnvironmentalCondition = Field(
        description="Canonical high-level summary condition derived deterministically from Phase 5B"
    )
    assessment_status: AssessmentStatus = Field(
        description="Overall operational status of the assessment: success | partial | insufficient_evidence | error"
    )
    reference_date: date = Field(
        description="Authoritative reference / query anchor date (UTC)"
    )
    region: AnalysisRegionMetadata = Field(
        description="Geographic location and circular parcel buffer metadata"
    )
    identified_patterns: list[ContextPatternSummary] = Field(
        default_factory=list,
        description="List of detected environmental stress patterns and structured supporting evidence",
    )
    conflicting_signals: list[str] = Field(
        default_factory=list,
        description="List of observable divergences detected between independent physical streams",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Transparent caveats regarding data lag, resolution, or missing observations",
    )
    is_sufficient: bool = Field(
        description="True when core evidence is sufficient for an authoritative assessment"
    )
    missing_evidence_sources: list[str] = Field(
        default_factory=list,
        description="List of evidence subsystems that are completely missing",
    )
    partial_evidence_sources: list[str] = Field(
        default_factory=list,
        description="List of evidence subsystems that are partially available",
    )
    maximum_data_lag_days: int | None = Field(
        default=None,
        ge=0,
        description="Observational metadata: maximum publication latency in days across available sources",
    )

    # 2. Verified Farmer Personalization Context
    farmer_context: VerifiedFarmerContext = Field(
        default_factory=VerifiedFarmerContext,
        description="Whitelisted farmer personalization profile (not environmental evidence)",
    )

    # 3. Presentation Preferences
    presentation: PresentationPreferences = Field(
        default_factory=PresentationPreferences,
        description="Output language and communication tone preferences",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


# Allowed recommendation action literals (DEC-024 Allowlist)
AuthorizedActionType = Literal[
    "field_visual_inspection",
    "soil_moisture_manual_check",
    "ongoing_monitoring",
    "missing_information_gathering",
]

# Allowed urgency levels (Strictly limited to routine or advisory)
AuthorizedUrgency = Literal["routine", "advisory"]


class RecommendedNextStep(BaseModel):
    """Constrained, safe, evidence-linked field observation or monitoring step."""

    action_type: AuthorizedActionType = Field(
        description="Authorized low-risk field action category"
    )
    description: str = Field(
        description="Clear, low-risk practical step (e.g. 'Check soil moisture directly in the field')"
    )
    urgency: AuthorizedUrgency = Field(
        default="routine",
        description="Operational urgency level for field check (strictly limited to 'routine' or 'advisory')",
    )

    model_config = ConfigDict(frozen=True)


class FarmerAgriculturalResponse(BaseModel):
    """Authoritative farmer-facing explanation payload generated by Gemini 2.5 Flash (DEC-024)."""

    language: str = Field(
        description="ISO language code of the response (e.g. 'en', 'hi')"
    )
    headline: str = Field(
        description="One concise summary sentence suitable for a mobile UI header"
    )
    summary: str = Field(
        description="2-3 sentence farmer-friendly overview of regional environmental conditions"
    )
    observations: list[str] = Field(
        description="Key observable facts cited directly from supporting evidence"
    )
    interpretation: str = Field(
        description="Farmer-friendly explanation of the deterministic Phase 5B assessment and patterns"
    )
    recommended_next_steps: list[RecommendedNextStep] = Field(
        default_factory=list,
        description="Zero or more safe, constrained field verification or monitoring steps",
    )
    limitations: list[str] = Field(
        description="Transparent caveats regarding data lag, resolution, or missing observations"
    )
    is_fallback: bool = Field(
        default=False,
        description="True if this response was generated by the deterministic fallback engine",
    )

    model_config = ConfigDict(frozen=True)


class AgriculturalAssessmentExplanationResponse(BaseModel):
    """Complete API response envelope containing both deterministic truth and conversational explanation."""

    assessment: AgriculturalAssessment = Field(
        description="Untouched Phase 5B deterministic ground truth assessment"
    )
    explanation: FarmerAgriculturalResponse = Field(
        description="Phase 5C Gemini or deterministic fallback explanation"
    )
    context_used: GeminiAssessmentContext = Field(
        description="Exact structured context passed into the explanation layer"
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


def assessment_to_gemini_context(
    assessment: AgriculturalAssessment,
    farmer_context: VerifiedFarmerContext | None = None,
    presentation: PresentationPreferences | None = None,
) -> GeminiAssessmentContext:
    """Projects an immutable AgriculturalAssessment into a GeminiAssessmentContext (DEC-024).

    Pure projection function that maps authoritative Phase 5B deterministic assessment data
    and optional personalization context into a structured, minimal context object.

    Invariants:
    - Does NOT recalculate, mutate, reinterpret, or override the assessment.
    - Does NOT make network calls or invoke LLM inference.
    - Copies structured SupportingEvidenceItem items faithfully without adding arbitrary units or thresholds.

    Args:
        assessment: Authoritative Phase 5B deterministic assessment.
        farmer_context: Optional whitelisted farmer personalization context.
        presentation: Optional presentation and tone preferences.

    Returns:
        GeminiAssessmentContext: Immutable context payload for downstream Gemini explanation.

    Raises:
        TypeError: If assessment is not an instance of AgriculturalAssessment.
    """
    if not isinstance(assessment, AgriculturalAssessment):
        raise TypeError(
            f"assessment must be an AgriculturalAssessment instance, got {type(assessment)!r}"
        )

    # Resolve farmer context and presentation preferences with safe defaults
    resolved_farmer_context = farmer_context if farmer_context is not None else VerifiedFarmerContext()
    resolved_presentation = presentation if presentation is not None else PresentationPreferences(
        target_language=resolved_farmer_context.preferred_language
    )

    # Project identified patterns into ContextPatternSummary
    pattern_summaries = [
        ContextPatternSummary(
            pattern_type=pattern.pattern_type,
            evidence_support=pattern.evidence_support,
            technical_summary=pattern.description,
            supporting_evidence=list(pattern.supporting_evidence),
        )
        for pattern in assessment.identified_patterns
    ]

    return GeminiAssessmentContext(
        overall_condition=assessment.overall_condition,
        assessment_status=assessment.status,
        reference_date=assessment.reference_date,
        region=assessment.region,
        identified_patterns=pattern_summaries,
        conflicting_signals=list(assessment.conflicting_signals),
        limitations=list(assessment.limitations),
        is_sufficient=assessment.sufficiency.is_sufficient,
        missing_evidence_sources=list(assessment.sufficiency.missing_evidence_sources),
        partial_evidence_sources=list(assessment.sufficiency.partial_evidence_sources),
        maximum_data_lag_days=assessment.sufficiency.maximum_data_lag_days,
        farmer_context=resolved_farmer_context,
        presentation=resolved_presentation,
    )
