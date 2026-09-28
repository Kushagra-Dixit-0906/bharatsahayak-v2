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
"""Phase 5 Deterministic Agricultural Evidence Interpretation and Explanation package (DEC-023 / DEC-024).

Translates multi-source physical evidence (AgriculturalEnvironmentalEvidence) into an
auditable, structured AgriculturalAssessment for downstream communication by Gemini,
and generates farmer-facing natural-language explanations (Phase 5C).
"""

from .gemini_types import (
    AgriculturalAssessmentExplanationResponse,
    FarmerAgriculturalResponse,
    GeminiAssessmentContext,
    PresentationPreferences,
    VerifiedFarmerContext,
    assessment_to_gemini_context,
)
from .pipeline import (
    evaluate_agricultural_assessment,
    evaluate_and_explain_agricultural_assessment,
    fetch_agricultural_assessment,
    fetch_agricultural_assessment_explanation,
)
from .reasoning import interpret_agricultural_evidence
from .types import (
    AgriculturalAssessment,
    AssessmentStatus,
    AssessmentSufficiency,
    EnvironmentalStressPattern,
    EnvironmentalStressPatternType,
    EvidenceSupportLevel,
    OverallEnvironmentalCondition,
    SupportingEvidenceItem,
)

__all__ = [
    "AgriculturalAssessment",
    "AgriculturalAssessmentExplanationResponse",
    "AssessmentStatus",
    "AssessmentSufficiency",
    "EnvironmentalStressPattern",
    "EnvironmentalStressPatternType",
    "EvidenceSupportLevel",
    "FarmerAgriculturalResponse",
    "GeminiAssessmentContext",
    "OverallEnvironmentalCondition",
    "PresentationPreferences",
    "SupportingEvidenceItem",
    "VerifiedFarmerContext",
    "assessment_to_gemini_context",
    "evaluate_agricultural_assessment",
    "evaluate_and_explain_agricultural_assessment",
    "fetch_agricultural_assessment",
    "fetch_agricultural_assessment_explanation",
    "interpret_agricultural_evidence",
]
