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
"""Pure deterministic agricultural evidence interpretation engine for Phase 5 (DEC-023).

This module contains ZERO Earth Engine imports, ZERO network calls, ZERO LLM calls,
and ZERO filesystem I/O. It evaluates multi-source physical evidence deterministically,
detects environmental patterns, enforces pattern-specific sufficiency, isolates signal conflicts,
and produces an immutable AgriculturalAssessment envelope.
"""

from app.assessment.types import (
    AgriculturalAssessment,
    AssessmentStatus,
    AssessmentSufficiency,
    EnvironmentalStressPattern,
    EnvironmentalStressPatternType,
    EvidenceSupportLevel,
    OverallEnvironmentalCondition,
    SupportingEvidenceItem,
)
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import RegionalNdviAnalysis


def interpret_agricultural_evidence(
    evidence: AgriculturalEnvironmentalEvidence,
) -> AgriculturalAssessment:
    """Deterministically interprets multi-source agricultural and environmental evidence (DEC-023).

    Pure offline reasoning function that evaluates physical observations from Phase 4,
    identifies corroborated environmental stress patterns, detects observable divergences,
    evaluates pattern-specific evidence sufficiency, and constructs an immutable AgriculturalAssessment.

    Args:
        evidence: Authoritative Phase 4 multi-source evidence envelope.

    Returns:
        AgriculturalAssessment: Immutable structured domain assessment.

    Raises:
        TypeError: If input evidence is not an AgriculturalEnvironmentalEvidence instance.
    """
    if not isinstance(evidence, AgriculturalEnvironmentalEvidence):
        raise TypeError(
            f"evidence must be an AgriculturalEnvironmentalEvidence instance, got {type(evidence)!r}"
        )

    # 1. Subsystem Availability & Status Extraction
    veg = evidence.vegetation
    rean = evidence.reanalysis
    rain = evidence.rainfall
    lc = evidence.land_cover

    veg_has_current = (
        veg.current is not None
        and isinstance(veg.current, RegionalNdviAnalysis)
        and veg.current.statistics is not None
    )
    veg_has_baseline = (
        veg.status == "success"
        and veg.anomaly is not None
        and veg.baseline is not None
    )
    veg_usable = veg_has_current
    rean_usable = (rean.status == "success")
    rain_usable = (rain.status == "success")
    lc_usable = (lc.status == "success")

    # 2. Track Missing, Partial Sources & Data Lags
    missing_sources: list[str] = []
    partial_sources: list[str] = []
    available_lags: list[int] = []

    if not veg_has_current:
        missing_sources.append("vegetation")
    elif veg.status == "insufficient_history":
        partial_sources.append("vegetation")

    if veg_has_current and veg.current.freshness and veg.current.freshness.observation_age_days is not None:
        available_lags.append(veg.current.freshness.observation_age_days)

    if not rean_usable:
        missing_sources.append("reanalysis")
    elif rean.data_lag_days is not None:
        available_lags.append(rean.data_lag_days)

    if not rain_usable:
        missing_sources.append("rainfall")
    elif rain.data_lag_days is not None:
        available_lags.append(rain.data_lag_days)

    if not lc_usable:
        missing_sources.append("land_cover")
    elif lc.data_lag_days is not None:
        available_lags.append(lc.data_lag_days)

    max_data_lag_days = max(available_lags) if available_lags else None

    # 3. Limitations & Context Warnings
    limitations: list[str] = []
    if lc_usable:
        if lc.dominant_class != "crops":
            limitations.append(
                f"Analysis region exhibits non-crop dominant land-cover context ('{lc.dominant_class}'). "
                f"Agricultural interpretations may reflect non-vegetated background surfaces rather than active crops."
            )

    if veg.status == "insufficient_history":
        limitations.append(
            "Historical vegetation baseline is unavailable (insufficient historical observations). "
            "Assessment is evaluated against current instantaneous canopy vigor only."
        )

    if "reanalysis" in missing_sources:
        limitations.append(
            "ERA5-Land reanalysis is unavailable; meteorological temperature and topsoil moisture could not be evaluated."
        )

    if "rainfall" in missing_sources:
        limitations.append(
            "CHIRPS precipitation is unavailable; retrospective rainfall could not be evaluated."
        )

    if max_data_lag_days is not None and max_data_lag_days > 7:
        limitations.append(
            f"Environmental data exhibits publication latency (maximum data lag: {max_data_lag_days} days relative to reference date)."
        )

    # 4. Pattern-Specific Evaluation & Conflict Detection
    identified_patterns: list[EnvironmentalStressPattern] = []
    conflicting_signals: list[str] = []

    # Handle Total Failure / Insufficient Evidence Edge Case
    if evidence.status in ("no_data", "error") or evidence.sources_available_count == 0 or not veg_has_current:
        sufficiency = AssessmentSufficiency(
            is_sufficient=False,
            sources_evaluated_count=4,
            sources_available_count=evidence.sources_available_count,
            sources_fully_available_count=evidence.sources_fully_available_count,
            missing_evidence_sources=missing_sources if missing_sources else ["vegetation", "reanalysis", "rainfall", "land_cover"],
            partial_evidence_sources=partial_sources,
            maximum_data_lag_days=max_data_lag_days,
            sufficiency_summary=(
                "Insufficient evidence: core remote-sensing observations failed with errors."
                if evidence.status == "error"
                else "Insufficient evidence: core remote-sensing observations are unavailable."
            ),
        )
        assessment_status: AssessmentStatus = "error" if evidence.status == "error" else "insufficient_evidence"
        top_error = evidence.error
        if assessment_status == "error" and top_error is None:
            top_error = veg.error or rean.error or rain.error or lc.error
        return AgriculturalAssessment(
            region=evidence.region,
            reference_date=evidence.reference_date,
            evidence=evidence,
            status=assessment_status,
            overall_condition="insufficient_evidence",
            identified_patterns=[],
            sufficiency=sufficiency,
            conflicting_signals=[],
            limitations=limitations,
            pipeline_version="5.0.0",
            error=top_error,
        )

    # Extract Baseline Departure Semantics (Phase 2 Sealed Contract)
    departure_band = veg.anomaly.departure_band if veg_has_baseline and veg.anomaly else None
    is_depressed_veg = departure_band in (
        "Strong Negative Spectral Departure",
        "Moderate Negative Spectral Departure",
        "significantly_below_normal",
        "moderately_below_normal",
    )
    is_normal_veg = departure_band in (
        "Near-Baseline Spectral Alignment",
        "normal",
    )
    is_favorable_veg = departure_band in (
        "Strong Positive Spectral Departure",
        "Moderate Positive Spectral Departure",
        "significantly_above_normal",
        "moderately_above_normal",
    )

    # Extract Moisture & Rainfall Indicators
    rain_30d_total = rain.recent_30_days.total_precipitation_mm if rain_usable and rain.recent_30_days else None
    sw_30d_mean = rean.recent_30_days.mean_soil_water_layer_1 if rean_usable and rean.recent_30_days else None
    t_7d_max = rean.recent_7_days.max_temperature_c if rean_usable and rean.recent_7_days else None
    runoff_7d_total = rean.recent_7_days.total_runoff_mm if rean_usable and rean.recent_7_days else None

    # Check for Observable Signal Divergences
    is_conflicting_ndvi_rain = False
    if veg_has_baseline and is_depressed_veg and rain_usable and rain_30d_total is not None and rain_30d_total >= 50.0:
        is_conflicting_ndvi_rain = True
        conflict_msg = (
            "Vegetation vigor is below seasonal baseline despite normal or elevated precipitation. "
            "The available evidence does not identify the cause of this divergence."
        )
        conflicting_signals.append(conflict_msg)
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="conflicting_environmental_signals",
                evidence_support="moderate_support",
                severity=None,
                description=conflict_msg,
                supporting_evidence=[
                    SupportingEvidenceItem(
                        source="vegetation",
                        metric_name="departure_band",
                        observed_value=departure_band,
                        reference_context=f"absolute_departure={veg.anomaly.absolute_departure:.3f}" if veg.anomaly else None,
                    ),
                    SupportingEvidenceItem(
                        source="rainfall",
                        metric_name="recent_30_days.total_precipitation_mm",
                        observed_value=rain_30d_total,
                        reference_context="CHIRPS 30-day cumulative precipitation",
                    ),
                ],
                conflicting_signals=[conflict_msg],
            )
        )
        # Also preserve the depressed vegetation pattern with conflicted support
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="vegetation_stress_pattern",
                evidence_support="conflicted_support",
                severity=None,
                description="Vegetation vigor is below historical seasonal baseline while precipitation records remain elevated.",
                supporting_evidence=[
                    SupportingEvidenceItem(
                        source="vegetation",
                        metric_name="departure_band",
                        observed_value=departure_band,
                        reference_context=f"absolute_departure={veg.anomaly.absolute_departure:.3f}" if veg.anomaly else None,
                    )
                ],
                conflicting_signals=[conflict_msg],
            )
        )

    # Detect Moisture Stress vs Isolated Vegetation Stress (when not a rainfall conflict)
    elif veg_has_baseline and is_depressed_veg:
        has_rain_evidence = (rain_usable and rain_30d_total is not None)
        has_soil_evidence = (rean_usable and sw_30d_mean is not None)

        if has_rain_evidence or has_soil_evidence:
            supp_items = [
                SupportingEvidenceItem(
                    source="vegetation",
                    metric_name="departure_band",
                    observed_value=departure_band,
                    reference_context=f"absolute_departure={veg.anomaly.absolute_departure:.3f}" if veg.anomaly else None,
                )
            ]
            if has_rain_evidence:
                supp_items.append(
                    SupportingEvidenceItem(
                        source="rainfall",
                        metric_name="recent_30_days.total_precipitation_mm",
                        observed_value=rain_30d_total,
                        reference_context="CHIRPS 30-day cumulative precipitation",
                    )
                )
            if has_soil_evidence:
                supp_items.append(
                    SupportingEvidenceItem(
                        source="reanalysis",
                        metric_name="recent_30_days.mean_soil_water_layer_1",
                        observed_value=sw_30d_mean,
                        reference_context="ERA5-Land topsoil volumetric water fraction (m³/m³)",
                    )
                )

            support_level: EvidenceSupportLevel = "high_support" if (has_rain_evidence and has_soil_evidence) else "moderate_support"
            identified_patterns.append(
                EnvironmentalStressPattern(
                    pattern_type="water_stress_consistent_pattern",
                    evidence_support=support_level,
                    severity=None,
                    description="Vegetation vigor is below historical seasonal baseline, corroborated by available meteorological rainfall or topsoil moisture observations.",
                    supporting_evidence=supp_items,
                    conflicting_signals=[],
                )
            )
        else:
            identified_patterns.append(
                EnvironmentalStressPattern(
                    pattern_type="vegetation_stress_pattern",
                    evidence_support="limited_support",
                    severity=None,
                    description="Vegetation vigor is below historical seasonal baseline; corroborating meteorological or soil moisture evidence is unavailable.",
                    supporting_evidence=[
                        SupportingEvidenceItem(
                            source="vegetation",
                            metric_name="departure_band",
                            observed_value=departure_band,
                            reference_context=f"absolute_departure={veg.anomaly.absolute_departure:.3f}" if veg.anomaly else None,
                        )
                    ],
                    conflicting_signals=[],
                )
            )

    # Detect Stable / Baseline Conditions
    elif veg_has_baseline and is_normal_veg and not is_conflicting_ndvi_rain:
        supp_items = [
            SupportingEvidenceItem(
                source="vegetation",
                metric_name="departure_band",
                observed_value=departure_band,
                reference_context="Aligned with 3-year historical seasonal baseline",
            )
        ]
        if rain_usable and rain_30d_total is not None:
            supp_items.append(
                SupportingEvidenceItem(
                    source="rainfall",
                    metric_name="recent_30_days.total_precipitation_mm",
                    observed_value=rain_30d_total,
                    reference_context="CHIRPS 30-day cumulative precipitation",
                )
            )
        if rean_usable and sw_30d_mean is not None:
            supp_items.append(
                SupportingEvidenceItem(
                    source="reanalysis",
                    metric_name="recent_30_days.mean_soil_water_layer_1",
                    observed_value=sw_30d_mean,
                    reference_context="ERA5-Land topsoil volumetric water fraction",
                )
            )

        support_level = "high_support" if (rain_usable and rean_usable) else "moderate_support"
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="near_baseline_stable_condition",
                evidence_support=support_level,
                severity=None,
                description="Vegetative vigor is tracking historical seasonal baselines across the analysis region.",
                supporting_evidence=supp_items,
                conflicting_signals=[],
            )
        )

    # Detect Favorable Growth Conditions
    elif veg_has_baseline and is_favorable_veg and not is_conflicting_ndvi_rain:
        supp_items = [
            SupportingEvidenceItem(
                source="vegetation",
                metric_name="departure_band",
                observed_value=departure_band,
                reference_context="Above 3-year historical seasonal baseline",
            )
        ]
        if rain_usable and rain_30d_total is not None:
            supp_items.append(
                SupportingEvidenceItem(
                    source="rainfall",
                    metric_name="recent_30_days.total_precipitation_mm",
                    observed_value=rain_30d_total,
                    reference_context="CHIRPS 30-day cumulative precipitation",
                )
            )
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="favorable_growth_condition",
                evidence_support="high_support" if rain_usable else "moderate_support",
                severity=None,
                description="Vegetative vigor is elevated above historical seasonal baselines under supportive environmental conditions.",
                supporting_evidence=supp_items,
                conflicting_signals=[],
            )
        )

    # Detect Thermal Heat Stress Pattern when Elevated Temperature is Observed
    if rean_usable and t_7d_max is not None and t_7d_max >= 38.0:
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="heat_stress_consistent_pattern",
                evidence_support="moderate_support",
                severity=None,
                description="Elevated ambient 2m temperature records observed over recent retrospective windows (requires future crop-specific thermal calibration).",
                supporting_evidence=[
                    SupportingEvidenceItem(
                        source="reanalysis",
                        metric_name="recent_7_days.max_temperature_c",
                        observed_value=t_7d_max,
                        reference_context="ERA5-Land 7-day maximum 2m ambient temperature",
                    )
                ],
                conflicting_signals=[],
            )
        )

    # Detect Excess Moisture / Waterlogging Pattern when Runoff is High
    if rain_usable and rean_usable and runoff_7d_total is not None and runoff_7d_total >= 10.0 and rain_30d_total is not None and rain_30d_total >= 100.0:
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="excess_moisture_waterlogging_consistent_pattern",
                evidence_support="moderate_support",
                severity=None,
                description="Precipitation and surface runoff records indicate elevated surface moisture accumulation over the analysis region.",
                supporting_evidence=[
                    SupportingEvidenceItem(
                        source="rainfall",
                        metric_name="recent_30_days.total_precipitation_mm",
                        observed_value=rain_30d_total,
                        reference_context="CHIRPS 30-day cumulative precipitation",
                    ),
                    SupportingEvidenceItem(
                        source="reanalysis",
                        metric_name="recent_7_days.total_runoff_mm",
                        observed_value=runoff_7d_total,
                        reference_context="ERA5-Land 7-day cumulative surface runoff sum",
                    ),
                ],
                conflicting_signals=[],
            )
        )

    # Detect Compound Environmental Stress
    has_water_stress = any(p.pattern_type == "water_stress_consistent_pattern" for p in identified_patterns)
    has_heat_stress = any(p.pattern_type == "heat_stress_consistent_pattern" for p in identified_patterns)
    if has_water_stress and has_heat_stress:
        identified_patterns.append(
            EnvironmentalStressPattern(
                pattern_type="combined_environmental_stress_pattern",
                evidence_support="high_support",
                severity=None,
                description="Coincident thermal conditions and vegetative moisture stress observed across multiple corroborating evidence streams.",
                supporting_evidence=[
                    SupportingEvidenceItem(
                        source="vegetation",
                        metric_name="departure_band",
                        observed_value=departure_band or "below_normal",
                        reference_context="Optical NDVI seasonal anomaly",
                    ),
                    SupportingEvidenceItem(
                        source="reanalysis",
                        metric_name="recent_7_days.max_temperature_c",
                        observed_value=t_7d_max if t_7d_max is not None else "elevated",
                        reference_context="Ambient thermal reanalysis",
                    ),
                ],
                conflicting_signals=[],
            )
        )

    # 5. Assess Overall Sufficiency & Operational Status
    is_sufficient = (
        veg_has_current
        and (veg_has_baseline or veg.status == "insufficient_history")
        and evidence.sources_available_count >= 2
    )

    sufficiency_summary = (
        "Core evidence is sufficient to produce an assessment across available physical streams."
        if is_sufficient
        else "Assessment is constrained due to missing or partial evidence streams."
    )

    sufficiency = AssessmentSufficiency(
        is_sufficient=is_sufficient,
        sources_evaluated_count=4,
        sources_available_count=evidence.sources_available_count,
        sources_fully_available_count=evidence.sources_fully_available_count,
        missing_evidence_sources=missing_sources,
        partial_evidence_sources=partial_sources,
        maximum_data_lag_days=max_data_lag_days,
        sufficiency_summary=sufficiency_summary,
    )

    assessment_status: AssessmentStatus
    if evidence.status == "success" and is_sufficient and evidence.sources_fully_available_count == 4 and veg.status == "success":
        assessment_status = "success"
    elif evidence.sources_available_count > 0 and veg_has_current:
        assessment_status = "partial"
    else:
        assessment_status = "insufficient_evidence"

    # 6. Derive Overall Environmental Condition (Standardized 8-value literal)
    overall_condition: OverallEnvironmentalCondition
    pattern_types = {p.pattern_type for p in identified_patterns}

    if assessment_status == "insufficient_evidence" or "insufficient_evidence_condition" in pattern_types:
        overall_condition = "insufficient_evidence"
    elif "combined_environmental_stress_pattern" in pattern_types:
        overall_condition = "combined_stress_consistent"
    elif "conflicting_environmental_signals" in pattern_types or len(conflicting_signals) > 0:
        overall_condition = "mixed"
    elif "water_stress_consistent_pattern" in pattern_types:
        overall_condition = "moisture_stress_consistent"
    elif "heat_stress_consistent_pattern" in pattern_types:
        overall_condition = "heat_stress_consistent"
    elif "vegetation_stress_pattern" in pattern_types:
        overall_condition = "vegetation_stress"
    elif "favorable_growth_condition" in pattern_types:
        overall_condition = "favorable"
    elif "near_baseline_stable_condition" in pattern_types:
        overall_condition = "stable"
    elif evidence.status == "partial" or assessment_status == "partial":
        overall_condition = "mixed"
    elif not is_sufficient:
        overall_condition = "insufficient_evidence"
    else:
        overall_condition = "stable"

    return AgriculturalAssessment(
        region=evidence.region,
        reference_date=evidence.reference_date,
        evidence=evidence,
        status=assessment_status,
        overall_condition=overall_condition,
        identified_patterns=identified_patterns,
        sufficiency=sufficiency,
        conflicting_signals=conflicting_signals,
        limitations=limitations,
        pipeline_version="5.0.0",
        error=None,
    )


