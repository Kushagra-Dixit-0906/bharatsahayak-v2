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
"""Phase 5D Crop Problem & Disease Advisory domain contracts and schemas.

Defines immutable Pydantic models for farmer symptom ingestion, qualitative
symptom-matching levels, candidate conditions (non-diagnostic), safe cultural
practices, knowledge provenance, and structured advisory output.

Epistemic Invariants:
- All models are immutable (frozen=True) and strict (extra='forbid').
- ZERO numerical disease confidence or pseudo-probabilities.
- PossibleCondition represents candidate explanations, NOT confirmed diagnoses.
- ZERO autonomous chemical/pesticide dosage prescription fields.
"""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

AdvisoryStatus = Literal["success", "partial", "insufficient_evidence", "error"]

SymptomMatchLevel = Literal[
    "strong_match",
    "possible_match",
    "weak_match",
    "insufficient_information",
]

PathogenCategory = Literal[
    "fungal",
    "bacterial",
    "viral",
    "nematode",
    "pest_damage",
    "abiotic_nutrient",
    "unknown",
]

ExpertReferralUrgency = Literal["none", "advisory", "urgent_inspection"]

SafeActionCategory = Literal[
    "sanitation",
    "water_management",
    "nutrient_balance",
    "field_monitoring",
    "clarification",
    "expert_referral",
]


class KnowledgeReference(BaseModel):
    """Auditable citation linking advisory content to a verified knowledge source."""

    source_id: str = Field(
        description="Unique identifier of the verified knowledge source document"
    )
    document_title: str = Field(
        description="Title of authoritative reference document or guide"
    )
    organization: str = Field(
        description="Publishing authority or extension organization"
    )
    relevant_excerpt: str = Field(
        description="Specific grounded excerpt used to support the advisory statement"
    )

    model_config = ConfigDict(frozen=True)


class PossibleCondition(BaseModel):
    """Structured candidate crop condition or disorder (candidate explanation, NOT confirmed diagnosis)."""

    condition_name: str = Field(
        description="Common name of candidate condition or problem"
    )
    scientific_name: str | None = Field(
        default=None,
        description="Pathogen taxonomy ONLY if explicitly documented in the verified source; never invented",
    )
    category: PathogenCategory = Field(
        description="Broad category of condition"
    )
    symptom_match: SymptomMatchLevel = Field(
        description="Qualitative language-grounding indicator of how closely reported symptoms resemble reference literature (NOT statistical confidence)"
    )
    reasoning: str = Field(
        description="Conservative explanation of why reported symptoms align with this candidate condition"
    )

    model_config = ConfigDict(frozen=True)


class SafeCulturalAction(BaseModel):
    """Authorized non-chemical cultural, preventative, or field monitoring action."""

    action_type: SafeActionCategory = Field(
        description="Authorized non-chemical action category"
    )
    description: str = Field(
        description="Clear, actionable non-chemical guidance for the farmer"
    )

    model_config = ConfigDict(frozen=True)


class CropProblemAdvisory(BaseModel):
    """Authoritative domain contract for farmer crop problem and symptom advisory (Phase 5D)."""

    status: AdvisoryStatus = Field(
        description="Operational status of the advisory: success | partial | insufficient_evidence | error"
    )
    crop_identified: str = Field(
        description="Crop species identified from query (e.g. 'Rice', 'Wheat', 'Unknown')"
    )
    reported_symptoms: list[str] = Field(
        description="Parsed visual symptoms and field observations reported by farmer"
    )
    possible_conditions: list[PossibleCondition] = Field(
        default_factory=list,
        description="Ranked candidate conditions consistent with reported symptoms (candidate explanations, not confirmed diagnoses)",
    )
    safe_cultural_actions: list[SafeCulturalAction] = Field(
        default_factory=list,
        description="Approved non-chemical cultural practices and field verification steps",
    )
    environmental_context_summary: str | None = Field(
        default=None,
        description="Optional Phase 5B environmental summary if parcel location was provided and evaluated",
    )
    uncertainty_reasons: list[str] = Field(
        default_factory=list,
        description="Explicit factors preventing definitive diagnosis or requiring field verification",
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        description="Targeted follow-up questions when reported symptoms are ambiguous or incomplete",
    )
    expert_referral_urgency: ExpertReferralUrgency = Field(
        default="none",
        description="Urgency of extension or KVK referral: none | advisory | urgent_inspection",
    )
    expert_referral_recommendation: str | None = Field(
        default=None,
        description="Conditional referral to Krishi Vigyan Kendra (KVK) or extension officer when uncertainty is high or problem is severe; omitted for routine inquiries",
    )
    knowledge_sources: list[KnowledgeReference] = Field(
        default_factory=list,
        description="Verified citations backing this advisory",
    )
    is_fallback: bool = Field(
        default=False,
        description="True if produced by the deterministic fallback engine",
    )

    model_config = ConfigDict(frozen=True)


class KnowledgeSourceProvenance(BaseModel):
    """Auditable metadata and legal usage terms for a verified knowledge document."""

    source_id: str = Field(
        description="Unique identifier for the knowledge source"
    )
    organization: str = Field(
        description="Publishing authority or institution"
    )
    document_title: str = Field(
        description="Official title of the document or guide"
    )
    version_or_year: str | None = Field(
        default=None,
        description="Publication version, edition, or year if available",
    )
    source_url: str = Field(
        description="Official online repository or retrieval URL"
    )
    license_or_usage_terms: str = Field(
        description="Explicitly verified license or usage permission terms"
    )
    retrieval_date: str = Field(
        description="ISO date when document was accessed or retrieved"
    )
    crops_covered: list[str] = Field(
        description="List of crop species covered by this document"
    )
    disease_topics: list[str] = Field(
        description="List of disease or disorder topics covered"
    )
    attribution_requirement: str = Field(
        description="Mandatory attribution or citation statement"
    )
    redistribution_status: Literal["bundled_permitted", "fetch_on_demand", "reference_only"] = Field(
        description="Legal redistribution classification under verified terms"
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class KnowledgeEntry(BaseModel):
    """Structured representation of a single verified agricultural knowledge entry."""

    entry_id: str = Field(
        description="Unique identifier for this knowledge record"
    )
    crop: str = Field(
        description="Crop species (e.g. 'Rice', 'Wheat')"
    )
    plant_part: str = Field(
        description="Primary affected plant part (e.g. 'leaf', 'stem', 'root', 'panicle')"
    )
    symptom_keywords: list[str] = Field(
        description="Normalized symptom keywords for deterministic matching"
    )
    condition_name: str = Field(
        description="Name of the condition or disorder"
    )
    scientific_name: str | None = Field(
        default=None,
        description="Pathogen taxonomy if explicitly provided in the verified source",
    )
    category: PathogenCategory = Field(
        description="Broad category of condition"
    )
    description: str = Field(
        description="Authoritative, factual symptom and progression description"
    )
    safe_cultural_practices: list[str] = Field(
        default_factory=list,
        description="Grounded non-chemical cultural, preventative, and sanitation practices",
    )
    clarifying_observations: list[str] = Field(
        default_factory=list,
        description="Key field observations to distinguish this condition from lookalikes",
    )
    source_id: str = Field(
        description="Foreign key linking to KnowledgeSourceProvenance.source_id"
    )

    model_config = ConfigDict(frozen=True, extra="forbid")
