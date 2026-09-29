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
"""Pure-Python statistical and anomaly calculations for historical NDVI baseline (DEC-013, DEC-014, DEC-017).

This module implements the deterministic, pure-Python calculation engine for Phase 2D:
1. Extracts valid annual regional mean NDVI values from Phase 2C historical observations.
2. Derives the central tendency baseline (historical median) and population dispersion (mean, population std dev ddof=0, min, max).
3. Evaluates historical sufficiency evidence across requested lookback years (N_annual >= 2 required).
4. Quantifies NDVI anomalies:
   - Primary absolute departure: current_mean - baseline_median.
   - Gated percentage departure: ((current - baseline) / baseline) * 100 (only when baseline_median >= 0.15).
   - Gated Z-score: (current - mean) / std_dev (only when N >= 2 and population std dev >= 0.02).
   - Empirical non-agronomic spectral departure band classification.

Architectural Guarantees:
-------------------------
- Pure deterministic Python with zero Earth Engine, network I/O, getInfo(), or asynchronous dependencies.
- Zero mutation of input Pydantic models.
- Strict population standard deviation (ddof=0).
- Explicit gate reasons for withheld metrics (never divide by zero).
"""

import statistics

from .types import (
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    HistoricalAnalysisStatus,
    HistoricalNdviBaseline,
    HistoricalSufficiencyEvidence,
    NdviAnomalyEvidence,
    RegionalNdviAnalysis,
    SpectralDepartureBand,
)

# Operational lookback thresholds (DEC-013, DEC-014, DEC-017)
MINIMUM_REQUIRED_HISTORICAL_YEARS: int = 2
DEFAULT_REQUESTED_HISTORICAL_YEARS: int = 3

# Metric gate thresholds (DEC-013, DEC-017)
PERCENTAGE_MIN_BASELINE_THRESHOLD: float = 0.15
Z_SCORE_MIN_STD_DEV_THRESHOLD: float = 0.02

# Spectral departure band classification thresholds (DEC-017)
DEPARTURE_BAND_STRONG_POSITIVE: float = 0.15
DEPARTURE_BAND_MODERATE_POSITIVE: float = 0.05
DEPARTURE_BAND_MODERATE_NEGATIVE: float = -0.05
DEPARTURE_BAND_STRONG_NEGATIVE: float = -0.15


def extract_valid_annual_observations(
    historical_observations: list[AnnualHistoricalNdviObservation],
) -> tuple[list[int], list[float]]:
    """Extracts represented target years and annual regional mean NDVI values from successful observations.

    Args:
        historical_observations: List of per-year Phase 2C historical observations.

    Returns:
        tuple[list[int], list[float]]:
            - represented_years: List of target years with status='success' and valid statistics, sorted descending.
            - annual_values: List of regional mean NDVI values corresponding positionally to represented_years.
    """
    valid_pairs: list[tuple[int, float]] = []
    for obs in historical_observations:
        if obs.status == "success" and obs.statistics is not None:
            mean_val = float(obs.statistics.mean)
            valid_pairs.append((obs.target_year, mean_val))

    # Sort descending by target_year for deterministic chronological order (e.g. 2025, 2024, 2023)
    valid_pairs.sort(key=lambda pair: pair[0], reverse=True)

    represented_years = [pair[0] for pair in valid_pairs]
    annual_values = [pair[1] for pair in valid_pairs]
    return represented_years, annual_values


def calculate_historical_baseline(
    annual_values: list[float],
    represented_years: list[int],
) -> HistoricalNdviBaseline | None:
    """Calculates statistical baseline metrics across represented annual historical NDVI values.

    Calculates:
    - median: Central tendency (primary baseline)
    - mean: Descriptive arithmetic mean
    - standard_deviation: Population standard deviation (ddof=0)
    - min, max: Empirical range envelope
    - represented_years, annual_values, annual_count

    Args:
        annual_values: Regional mean NDVI values for represented years.
        represented_years: Target years corresponding positionally to annual_values.

    Returns:
        HistoricalNdviBaseline | None: The computed baseline model, or None if annual_count < 2.
    """
    if len(annual_values) != len(represented_years):
        return None

    annual_count = len(annual_values)
    if annual_count < MINIMUM_REQUIRED_HISTORICAL_YEARS:
        return None

    # Primary baseline: historical median
    median_val = float(statistics.median(annual_values))

    # Secondary descriptive metrics
    mean_val = float(statistics.fmean(annual_values))
    # Population standard deviation with ddof=0
    std_dev_val = float(statistics.pstdev(annual_values))
    min_val = float(min(annual_values))
    max_val = float(max(annual_values))

    # Floating point precision guard: clamp precision drift within [min, max]
    if median_val < min_val:
        median_val = min_val
    elif median_val > max_val:
        median_val = max_val

    if mean_val < min_val:
        mean_val = min_val
    elif mean_val > max_val:
        mean_val = max_val

    return HistoricalNdviBaseline(
        median=median_val,
        mean=mean_val,
        standard_deviation=std_dev_val,
        min=min_val,
        max=max_val,
        represented_years=list(represented_years),
        annual_values=list(annual_values),
        annual_count=annual_count,
    )


def calculate_sufficiency_evidence(
    historical_observations: list[AnnualHistoricalNdviObservation],
    requested_years_count: int = DEFAULT_REQUESTED_HISTORICAL_YEARS,
    minimum_required_years: int = MINIMUM_REQUIRED_HISTORICAL_YEARS,
) -> HistoricalSufficiencyEvidence:
    """Evaluates empirical data sufficiency for multi-year historical comparison.

    Args:
        historical_observations: List of Phase 2C historical observations.
        requested_years_count: Number of historical years requested in lookback horizon (default 3).
        minimum_required_years: Minimum distinct historical years required for a baseline (default 2).

    Returns:
        HistoricalSufficiencyEvidence: The structured sufficiency evaluation.
    """
    represented_years: list[int] = []
    missing_years: list[int] = []

    for obs in historical_observations:
        if obs.status == "success" and obs.statistics is not None:
            represented_years.append(obs.target_year)
        else:
            missing_years.append(obs.target_year)

    # Sort descending
    represented_years.sort(reverse=True)
    missing_years.sort(reverse=True)

    represented_count = len(represented_years)
    is_sufficient = represented_count >= minimum_required_years

    # Neutral evidence-based sufficiency notes
    if represented_count == 0:
        notes = f"0 of {requested_years_count} requested historical years produced usable annual observations."
    elif represented_count < minimum_required_years:
        notes = (
            f"{represented_count} of {requested_years_count} requested historical years "
            f"produced usable annual observations (minimum {minimum_required_years} required)."
        )
    else:
        notes = f"Sufficient historical observations available (N={represented_count})."

    return HistoricalSufficiencyEvidence(
        requested_years_count=requested_years_count,
        represented_years_count=represented_count,
        minimum_required_years=minimum_required_years,
        is_sufficient=is_sufficient,
        represented_years=represented_years,
        missing_years=missing_years,
        sufficiency_notes=notes,
    )


def calculate_absolute_departure(
    current_mean: float,
    baseline_median: float,
) -> float:
    """Calculates the primary absolute NDVI departure in index units.

    Formula: current_mean - baseline_median

    Args:
        current_mean: Current regional mean NDVI.
        baseline_median: Historical baseline median NDVI.

    Returns:
        float: Absolute departure value in [-2.0, 2.0].
    """
    return current_mean - baseline_median


def calculate_percentage_departure(
    current_mean: float,
    baseline_median: float,
    min_threshold: float = PERCENTAGE_MIN_BASELINE_THRESHOLD,
) -> tuple[float | None, str | None]:
    """Calculates gated relative percentage departure against baseline median.

    Formula: ((current_mean - baseline_median) / baseline_median) * 100.0

    Gated: Only computed when baseline_median >= min_threshold (default 0.15).

    Args:
        current_mean: Current regional mean NDVI.
        baseline_median: Historical baseline median NDVI.
        min_threshold: Minimum baseline median required for percentage calculation (default 0.15).

    Returns:
        tuple[float | None, str | None]:
            - percentage_departure: Computed percentage or None if gated.
            - percentage_unavailable_reason: Explicit neutral reason if None ('baseline_below_threshold').
    """
    if baseline_median < min_threshold:
        return None, "baseline_below_threshold"

    pct = ((current_mean - baseline_median) / baseline_median) * 100.0
    return pct, None


def calculate_z_score(
    current_mean: float,
    historical_mean: float,
    historical_std_dev: float,
    annual_count: int,
    min_std_dev_threshold: float = Z_SCORE_MIN_STD_DEV_THRESHOLD,
    min_annual_count: int = MINIMUM_REQUIRED_HISTORICAL_YEARS,
) -> tuple[float | None, str | None]:
    """Calculates gated standardized Z-score anomaly against historical distribution.

    Formula: (current_mean - historical_mean) / historical_std_dev

    Gated: Only computed when annual_count >= min_annual_count (2) AND historical_std_dev >= min_std_dev_threshold (0.02).

    Args:
        current_mean: Current regional mean NDVI.
        historical_mean: Historical descriptive arithmetic mean NDVI.
        historical_std_dev: Historical population standard deviation (ddof=0).
        annual_count: Number of represented historical years.
        min_std_dev_threshold: Minimum population std dev to avoid dividing by near-zero (default 0.02).
        min_annual_count: Minimum represented years required (default 2).

    Returns:
        tuple[float | None, str | None]:
            - z_score: Standardized departure score or None if gated.
            - z_score_unavailable_reason: Reason if None ('insufficient_sample_size' or 'negligible_variance').
    """
    if annual_count < min_annual_count:
        return None, "insufficient_sample_size"

    if historical_std_dev < min_std_dev_threshold:
        return None, "negligible_variance"

    z = (current_mean - historical_mean) / historical_std_dev
    return z, None


def classify_spectral_departure(
    absolute_departure: float,
) -> SpectralDepartureBand:
    """Classifies absolute departure into an empirical non-agronomic spectral departure band.

    Threshold Boundaries:
        delta >= +0.15              -> "Strong Positive Spectral Departure"
        +0.05 <= delta < +0.15      -> "Moderate Positive Spectral Departure"
        -0.05 < delta < +0.05       -> "Near-Baseline Spectral Alignment"
        -0.15 < delta <= -0.05      -> "Moderate Negative Spectral Departure"
        delta <= -0.15              -> "Strong Negative Spectral Departure"

    Args:
        absolute_departure: Primary departure delta (current_mean - baseline_median).

    Returns:
        SpectralDepartureBand: Empirical spectral departure category.
    """
    if absolute_departure >= DEPARTURE_BAND_STRONG_POSITIVE:
        return "Strong Positive Spectral Departure"
    elif absolute_departure >= DEPARTURE_BAND_MODERATE_POSITIVE:
        return "Moderate Positive Spectral Departure"
    elif absolute_departure > DEPARTURE_BAND_MODERATE_NEGATIVE:
        return "Near-Baseline Spectral Alignment"
    elif absolute_departure > DEPARTURE_BAND_STRONG_NEGATIVE:
        return "Moderate Negative Spectral Departure"
    else:
        return "Strong Negative Spectral Departure"


def calculate_ndvi_anomaly_evidence(
    current_mean: float,
    baseline: HistoricalNdviBaseline,
) -> NdviAnomalyEvidence:
    """Calculates all quantified anomaly departure metrics against a valid historical baseline.

    Args:
        current_mean: Current regional mean NDVI.
        baseline: Valid multi-year HistoricalNdviBaseline.

    Returns:
        NdviAnomalyEvidence: Quantified departure evidence container.
    """
    abs_departure = calculate_absolute_departure(current_mean, baseline.median)
    pct_departure, pct_reason = calculate_percentage_departure(current_mean, baseline.median)
    z_score, z_reason = calculate_z_score(
        current_mean=current_mean,
        historical_mean=baseline.mean,
        historical_std_dev=baseline.standard_deviation,
        annual_count=baseline.annual_count,
    )
    departure_band = classify_spectral_departure(abs_departure)

    return NdviAnomalyEvidence(
        current_mean=current_mean,
        baseline_median=baseline.median,
        absolute_departure=abs_departure,
        percentage_departure=pct_departure,
        historical_mean=baseline.mean,
        historical_std_dev=baseline.standard_deviation,
        z_score=z_score,
        departure_band=departure_band,
        percentage_unavailable_reason=pct_reason,
        z_score_unavailable_reason=z_reason,
    )


def calculate_historical_ndvi_statistics(
    current: RegionalNdviAnalysis | None,
    historical_observations: list[AnnualHistoricalNdviObservation],
    requested_years_count: int = DEFAULT_REQUESTED_HISTORICAL_YEARS,
    minimum_required_years: int = MINIMUM_REQUIRED_HISTORICAL_YEARS,
    current_error: EarthEngineError | None = None,
) -> tuple[
    HistoricalNdviBaseline | None,
    HistoricalSufficiencyEvidence,
    NdviAnomalyEvidence | None,
    HistoricalAnalysisStatus,
    EarthEngineError | None,
]:
    """Main pure-Python entry point to evaluate sufficiency, baseline, and anomaly for historical NDVI.

    Status semantics:
    - If current_error is provided or current has error status:
        status='error', baseline=computed if sufficient else None, anomaly=None, error=current_error.
    - If current is None or has no_data / no statistics:
        status='no_data', baseline=computed if sufficient else None, anomaly=None.
    - If current is success but represented historical years < minimum_required_years:
        status='insufficient_history', baseline=None, anomaly=None.
    - If current is success and represented historical years >= minimum_required_years:
        status='success', baseline=computed, anomaly=computed.

    Args:
        current: RegionalNdviAnalysis of the current satellite observation (or None).
        historical_observations: List of Phase 2C AnnualHistoricalNdviObservation objects.
        requested_years_count: Configured historical horizon years (default 3).
        minimum_required_years: Minimum required historical years for a valid baseline (default 2).
        current_error: Optional EarthEngineError if an error occurred during current acquisition.

    Returns:
        tuple[
            HistoricalNdviBaseline | None,
            HistoricalSufficiencyEvidence,
            NdviAnomalyEvidence | None,
            HistoricalAnalysisStatus,
            EarthEngineError | None,
        ]
    """
    sufficiency = calculate_sufficiency_evidence(
        historical_observations=historical_observations,
        requested_years_count=requested_years_count,
        minimum_required_years=minimum_required_years,
    )

    baseline: HistoricalNdviBaseline | None = None
    if sufficiency.is_sufficient:
        represented_years, annual_values = extract_valid_annual_observations(historical_observations)
        baseline = calculate_historical_baseline(
            annual_values=annual_values,
            represented_years=represented_years,
        )

    # 1. Error state handling
    if current_error is not None:
        return baseline, sufficiency, None, "error", current_error

    if current is None:
        return baseline, sufficiency, None, "no_data", None

    # Check if current has statistics
    if current.statistics is None:
        return baseline, sufficiency, None, "no_data", None

    # 2. Historical sufficiency gate
    if not sufficiency.is_sufficient or baseline is None:
        return None, sufficiency, None, "insufficient_history", None

    # 3. Anomaly calculation
    anomaly = calculate_ndvi_anomaly_evidence(
        current_mean=current.statistics.mean,
        baseline=baseline,
    )

    return baseline, sufficiency, anomaly, "success", None


# Backward/forward ergonomic aliases
compute_historical_baseline = calculate_historical_baseline
compute_ndvi_anomaly_evidence = calculate_ndvi_anomaly_evidence
compute_historical_sufficiency = calculate_sufficiency_evidence
compute_historical_ndvi_statistics = calculate_historical_ndvi_statistics
