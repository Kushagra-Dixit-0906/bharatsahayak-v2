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
"""Domain models and types for Phase 5 Deterministic Agricultural Evidence Interpretation (DEC-023)."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError

AssessmentStatus = Literal["success", "partial", "insufficient_evidence", "error"]

EvidenceSupportLevel = Literal[
    "high_support",
    "moderate_support",
    "limited_support",
    "conflicted_support",
]

EnvironmentalStressPatternType = Literal[
    "vegetation_stress_pattern",
    "water_stress_consistent_pattern",
    "rainfall_deficit_consistent_pattern",
    "heat_stress_consistent_pattern",
    "excess_moisture_waterlogging_consistent_pattern",
    "combined_environmental_stress_pattern",
    "near_baseline_stable_condition",
    "favorable_growth_condition",
    "conflicting_environmental_signals",
    "insufficient_evidence_condition",
]

OverallEnvironmentalCondition = Literal[
    "stable",
    "vegetation_stress",
    "moisture_stress_consistent",
    "heat_stress_consistent",
    "combined_stress_consistent",
    "favorable",
    "mixed",
    "insufficient_evidence",
]


class SupportingEvidenceItem(BaseModel):
    """Traceable reference to an underlying physical observation in Phase 4 evidence."""

    source: Literal["vegetation", "reanalysis", "rainfall", "land_cover"] = Field(
        description="Originating evidence subsystem for this observation"
    )
    metric_name: str = Field(
        description="Specific metric or band name from the underlying domain model"
    )
    observed_value: str | float | int | bool = Field(
        description="Physical observation or categorical value recorded in the evidence envelope"
    )
    reference_context: str | None = Field(
        default=None,
        description="Optional contextual explanation or baseline reference for this metric",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class EnvironmentalStressPattern(BaseModel):
    """Structured representation of a single detected environmental or agricultural pattern."""

    pattern_type: EnvironmentalStressPatternType = Field(
        description="Canonical evidence pattern type from the Phase 5 taxonomy"
    )
    evidence_support: EvidenceSupportLevel = Field(
        description="Qualitative level of multi-source corroboration backing this pattern"
    )
    severity: str | None = Field(
        default=None,
        description="Optional severity qualifier (Future work: requires agronomic calibration; None in MVP)",
    )
    description: str = Field(
        description="Conservative, evidence-grounded textual explanation of this observed pattern"
    )
    supporting_evidence: list[SupportingEvidenceItem] = Field(
        default_factory=list,
        description="List of exact underlying observations that justify this pattern",
    )
    conflicting_signals: list[str] = Field(
        default_factory=list,
        description="Specific contradictory or divergent observations identified during evaluation",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")


class AssessmentSufficiency(BaseModel):
    """Evaluation of evidence completeness, pattern-specific availability, and sensor data lag."""

    is_sufficient: bool = Field(
        description="True when the available core evidence is sufficient to produce the overall assessment without requiring unavailable critical evidence"
    )
    sources_evaluated_count: int = Field(
        default=4,
        description="Total distinct evidence subsystems evaluated (Vegetation, Reanalysis, Rainfall, Land Cover)",
    )
    sources_available_count: int = Field(
        ge=0,
        le=4,
        description="Count of distinct evidence subsystems providing usable evidence (full or partial)",
    )
    sources_fully_available_count: int = Field(
        ge=0,
        le=4,
        description="Count of distinct evidence subsystems returning status='success'",
    )
    missing_evidence_sources: list[str] = Field(
        default_factory=list,
        description="List of evidence subsystems that are completely missing (status in ['no_data', 'error'])",
    )
    partial_evidence_sources: list[str] = Field(
        default_factory=list,
        description="List of evidence subsystems that are partially available (e.g. vegetation with insufficient history)",
    )
    maximum_data_lag_days: int | None = Field(
        default=None,
        ge=0,
        description="Maximum publication latency in days across all available evidence sources",
    )
    sufficiency_summary: str = Field(
        description="Human-readable summary of evidence completeness and evaluation constraints"
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="after")
    def validate_sufficiency_counts(self) -> "AssessmentSufficiency":
        if not (0 <= self.sources_fully_available_count <= self.sources_available_count <= self.sources_evaluated_count):
            raise ValueError(
                f"Count violation: sources_fully_available_count ({self.sources_fully_available_count}) "
                f"<= sources_available_count ({self.sources_available_count}) "
                f"<= sources_evaluated_count ({self.sources_evaluated_count})"
            )
        return self


class AgriculturalAssessment(BaseModel):
    """Authoritative root domain envelope for agricultural evidence interpretation (DEC-023)."""

    region: AnalysisRegionMetadata = Field(
        description="Shared geographic footprint and circular parcel buffer metadata"
    )
    reference_date: date = Field(
        description="Authoritative reference / query anchor date (UTC)"
    )
    evidence: AgriculturalEnvironmentalEvidence = Field(
        description="Authoritative Phase 4 multi-source physical evidence envelope"
    )
    status: AssessmentStatus = Field(
        description="Overall operational status of the assessment: success | partial | insufficient_evidence | error"
    )
    overall_condition: OverallEnvironmentalCondition = Field(
        description="Lightweight high-level summary condition derived deterministically from identified patterns"
    )
    identified_patterns: list[EnvironmentalStressPattern] = Field(
        default_factory=list,
        description="Authoritative list of detected environmental and agricultural stress patterns",
    )
    sufficiency: AssessmentSufficiency = Field(
        description="Structural evaluation of evidence completeness and sensor data lags"
    )
    conflicting_signals: list[str] = Field(
        default_factory=list,
        description="List of observable divergences detected between independent physical streams",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Transparent record of contextual caveats, data gaps, and publication latencies",
    )
    pipeline_version: str = Field(
        default="5.0.0",
        description="Semantic version of the agricultural evidence interpretation pipeline",
    )
    error: EarthEngineError | None = Field(
        default=None,
        description="Structured error details if an unhandled pipeline error occurred",
    )

    model_config = ConfigDict(frozen=True, extra="forbid")

    @model_validator(mode="after")
    def validate_assessment_invariants(self) -> "AgriculturalAssessment":
        if self.status == "error":
            if self.error is None:
                raise ValueError("status='error' requires an error to be specified")
        elif self.error is not None:
            raise ValueError(f"status='{self.status}' cannot contain a top-level error")

        if self.status == "success":
            if not self.sufficiency.is_sufficient:
                raise ValueError("status='success' requires sufficiency.is_sufficient == True")
            if self.sufficiency.sources_fully_available_count != self.sufficiency.sources_evaluated_count:
                raise ValueError("status='success' requires all sources to be fully available")

        return self
