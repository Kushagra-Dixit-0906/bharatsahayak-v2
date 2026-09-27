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
"""Unit tests for Phase 2D pure-Python statistical and anomaly calculations (baseline.py)."""

import math
import statistics

import pytest

from app.satellite.baseline import (
    DEPARTURE_BAND_MODERATE_NEGATIVE,
    DEPARTURE_BAND_MODERATE_POSITIVE,
    DEPARTURE_BAND_STRONG_NEGATIVE,
    DEPARTURE_BAND_STRONG_POSITIVE,
    MINIMUM_REQUIRED_HISTORICAL_YEARS,
    PERCENTAGE_MIN_BASELINE_THRESHOLD,
    Z_SCORE_MIN_STD_DEV_THRESHOLD,
    calculate_absolute_departure,
    calculate_historical_baseline,
    calculate_historical_ndvi_statistics,
    calculate_ndvi_anomaly_evidence,
    calculate_percentage_departure,
    calculate_sufficiency_evidence,
    calculate_z_score,
    classify_spectral_departure,
    compute_historical_baseline,
    compute_historical_ndvi_statistics,
    compute_historical_sufficiency,
    compute_ndvi_anomaly_evidence,
    extract_valid_annual_observations,
)
from app.satellite.temporal import construct_historical_temporal_window
from app.satellite.types import (
    AnalysisRegionMetadata,
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    HistoricalNdviBaseline,
    HistoricalObservationSummary,
    HistoricalSufficiencyEvidence,
    NdviAnomalyEvidence,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    Sentinel2ImageMetadata,
)


def _make_sample_annual_obs(
    target_year: int,
    mean: float = 0.58,
    status: str = "success",
) -> AnnualHistoricalNdviObservation:
    """Helper to construct a valid AnnualHistoricalNdviObservation."""
    window = construct_historical_temporal_window("2026-08-16", target_year, 15)
    if status == "success":
        stats = NdviRegionalStatistics(
            mean=mean,
            median=mean - 0.01,
            min=mean - 0.20,
            max=mean + 0.20,
            valid_pixel_count=300,
        )
        scenes = [
            HistoricalObservationSummary(
                image_id=f"COPERNICUS/S2_SR_HARMONIZED/{target_year}0816T054251",
                acquisition_date=f"{target_year}-08-16T05:50:41+00:00",
                target_year=target_year,
                cloud_percentage=5.0,
                usable_coverage_percentage=95.0,
                selection_rank=1,
            )
        ]
        return AnnualHistoricalNdviObservation(
            target_year=target_year,
            temporal_window=window,
            available_usable_scenes_count=1,
            selected_scenes_count=1,
            selected_observations=scenes,
            statistics=stats,
            status="success",
        )
    return AnnualHistoricalNdviObservation(
        target_year=target_year,
        temporal_window=window,
        available_usable_scenes_count=0,
        selected_scenes_count=0,
        selected_observations=[],
        statistics=None,
        status="no_data",
    )


def _make_sample_current_analysis(
    mean: float = 0.65,
    status: str = "success",
) -> RegionalNdviAnalysis:
    """Helper to construct a valid current RegionalNdviAnalysis."""
    meta = Sentinel2ImageMetadata(
        image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251",
        acquisition_date="2026-08-16T05:50:41+00:00",
        cloud_percentage=5.0,
    )
    stats = NdviRegionalStatistics(
        mean=mean,
        median=mean - 0.01,
        min=mean - 0.25,
        max=mean + 0.20,
        valid_pixel_count=314,
    )
    return RegionalNdviAnalysis(
        observation=meta,
        quality=ObservationQualityEvidence(quality_mask_applied=True, is_usable=True),
        freshness=ObservationFreshness(reference_date="2026-08-16", observation_age_days=0),
        region=AnalysisRegionMetadata(latitude=30.9157, longitude=75.7196),
        statistics=stats,
    )


# ==============================================================================
# 1. EXTRACT VALID ANNUAL OBSERVATIONS
# ==============================================================================


class TestExtractValidAnnualObservations:
    """Tests for extract_valid_annual_observations helper."""

    def test_extracts_and_sorts_descending(self) -> None:
        """Extracts successful observations and sorts target years descending."""
        obs = [
            _make_sample_annual_obs(2023, mean=0.50),
            _make_sample_annual_obs(2025, mean=0.60),
            _make_sample_annual_obs(2024, mean=0.55),
        ]
        years, values = extract_valid_annual_observations(obs)
        assert years == [2025, 2024, 2023]
        assert values == [0.60, 0.55, 0.50]

    def test_filters_out_no_data_and_failed_observations(self) -> None:
        """Filters out non-success or missing statistics observations."""
        obs = [
            _make_sample_annual_obs(2025, mean=0.60, status="success"),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, mean=0.52, status="success"),
        ]
        years, values = extract_valid_annual_observations(obs)
        assert years == [2025, 2023]
        assert values == [0.60, 0.52]

    def test_empty_list_returns_empty_tuples(self) -> None:
        """Returns empty lists if no observations provided."""
        years, values = extract_valid_annual_observations([])
        assert years == []
        assert values == []


# ==============================================================================
# 2. HISTORICAL BASELINE CALCULATIONS
# ==============================================================================


class TestCalculateHistoricalBaseline:
    """Tests for calculate_historical_baseline (DEC-013, DEC-014, DEC-017)."""

    def test_alias_equivalence(self) -> None:
        """Verifies compute_historical_baseline is alias."""
        assert compute_historical_baseline is calculate_historical_baseline

    def test_returns_none_for_0_years(self) -> None:
        """Returns None if represented annual_count == 0."""
        assert calculate_historical_baseline([], []) is None

    def test_returns_none_for_1_year(self) -> None:
        """Returns None if represented annual_count == 1 (minimum 2 required)."""
        assert calculate_historical_baseline([0.55], [2025]) is None

    def test_returns_none_for_length_mismatch(self) -> None:
        """Returns None if annual_values and represented_years have unequal length."""
        assert calculate_historical_baseline([0.55, 0.60], [2025]) is None

    def test_valid_baseline_3_years(self) -> None:
        """Calculates exact baseline statistics across 3 historical years."""
        years = [2025, 2024, 2023]
        values = [0.60, 0.50, 0.55]

        baseline = calculate_historical_baseline(values, years)
        assert baseline is not None
        assert baseline.annual_count == 3
        assert baseline.represented_years == [2025, 2024, 2023]
        assert baseline.annual_values == [0.60, 0.50, 0.55]
        # median of [0.60, 0.50, 0.55] is 0.55
        assert baseline.median == pytest.approx(0.55)
        # mean is (0.60 + 0.50 + 0.55) / 3 = 1.65 / 3 = 0.55
        assert baseline.mean == pytest.approx(0.55)
        # population standard deviation (ddof=0): sqrt(((0.05)^2 + (-0.05)^2 + 0^2)/3) = sqrt(0.005/3) = 0.0408248...
        expected_pstdev = statistics.pstdev(values)
        assert baseline.standard_deviation == pytest.approx(expected_pstdev)
        assert baseline.min == 0.50
        assert baseline.max == 0.60

    def test_population_vs_sample_standard_deviation(self) -> None:
        """Verifies baseline strictly uses population std dev (ddof=0), NOT sample std dev (ddof=1)."""
        values = [0.40, 0.60]
        years = [2025, 2024]
        baseline = calculate_historical_baseline(values, years)
        assert baseline is not None
        # Mean = 0.50. Variances: (0.4-0.5)^2 = 0.01, (0.6-0.5)^2 = 0.01.
        # Population variance (ddof=0) = (0.01 + 0.01) / 2 = 0.01 -> pstdev = 0.10
        # Sample variance (ddof=1) = (0.01 + 0.01) / 1 = 0.02 -> stdev = 0.141421...
        assert baseline.standard_deviation == pytest.approx(0.10)
        assert baseline.standard_deviation != pytest.approx(statistics.stdev(values))

    def test_valid_baseline_2_years_even_count_median(self) -> None:
        """Calculates exact median for 2 years (average of the 2 values)."""
        years = [2025, 2024]
        values = [0.52, 0.58]
        baseline = calculate_historical_baseline(values, years)
        assert baseline is not None
        assert baseline.annual_count == 2
        assert baseline.median == pytest.approx(0.55)
        assert baseline.mean == pytest.approx(0.55)
        assert baseline.min == 0.52
        assert baseline.max == 0.58

    def test_identical_historical_values_zero_std_dev(self) -> None:
        """Handles identical historical values resulting in standard_deviation = 0.0."""
        years = [2025, 2024, 2023]
        values = [0.50, 0.50, 0.50]
        baseline = calculate_historical_baseline(values, years)
        assert baseline is not None
        assert baseline.median == 0.50
        assert baseline.mean == 0.50
        assert baseline.standard_deviation == 0.0
        assert baseline.min == 0.50
        assert baseline.max == 0.50


# ==============================================================================
# 3. SUFFICIENCY EVIDENCE
# ==============================================================================


class TestCalculateSufficiencyEvidence:
    """Tests for calculate_sufficiency_evidence (DEC-014, DEC-017)."""

    def test_alias_equivalence(self) -> None:
        """Verifies compute_historical_sufficiency is alias."""
        assert compute_historical_sufficiency is calculate_sufficiency_evidence

    def test_all_3_years_successful(self) -> None:
        """Evaluates sufficiency when all 3 requested years succeed."""
        obs = [
            _make_sample_annual_obs(2025, status="success"),
            _make_sample_annual_obs(2024, status="success"),
            _make_sample_annual_obs(2023, status="success"),
        ]
        evidence = calculate_sufficiency_evidence(obs)
        assert evidence.requested_years_count == 3
        assert evidence.represented_years_count == 3
        assert evidence.minimum_required_years == 2
        assert evidence.is_sufficient is True
        assert evidence.represented_years == [2025, 2024, 2023]
        assert evidence.missing_years == []
        assert evidence.sufficiency_notes == "Sufficient historical observations available (N=3)."

    def test_2_of_3_years_successful(self) -> None:
        """Evaluates sufficiency when 2 of 3 requested years succeed."""
        obs = [
            _make_sample_annual_obs(2025, status="success"),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, status="success"),
        ]
        evidence = calculate_sufficiency_evidence(obs)
        assert evidence.represented_years_count == 2
        assert evidence.is_sufficient is True
        assert evidence.represented_years == [2025, 2023]
        assert evidence.missing_years == [2024]
        assert evidence.sufficiency_notes == "Sufficient historical observations available (N=2)."

    def test_1_of_3_years_successful_insufficient(self) -> None:
        """Evaluates sufficiency when only 1 requested year succeeds (insufficient)."""
        obs = [
            _make_sample_annual_obs(2025, status="success"),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, status="no_data"),
        ]
        evidence = calculate_sufficiency_evidence(obs)
        assert evidence.represented_years_count == 1
        assert evidence.is_sufficient is False
        assert evidence.represented_years == [2025]
        assert evidence.missing_years == [2024, 2023]
        assert (
            evidence.sufficiency_notes
            == "1 of 3 requested historical years produced usable annual observations (minimum 2 required)."
        )

    def test_0_of_3_years_successful(self) -> None:
        """Evaluates sufficiency when 0 requested years succeed."""
        obs = [
            _make_sample_annual_obs(2025, status="no_data"),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, status="no_data"),
        ]
        evidence = calculate_sufficiency_evidence(obs)
        assert evidence.represented_years_count == 0
        assert evidence.is_sufficient is False
        assert evidence.represented_years == []
        assert evidence.missing_years == [2025, 2024, 2023]
        assert (
            evidence.sufficiency_notes
            == "0 of 3 requested historical years produced usable annual observations."
        )


# ==============================================================================
# 4. DEPARTURES, PERCENTAGE, Z-SCORE, AND SPECTRAL BANDS
# ==============================================================================


class TestDepartureAndMetricCalculations:
    """Tests for departure calculations and gates (DEC-013, DEC-017)."""

    def test_calculate_absolute_departure(self) -> None:
        """Verifies delta_abs = current_mean - baseline_median."""
        assert calculate_absolute_departure(0.65, 0.55) == pytest.approx(0.10)
        assert calculate_absolute_departure(0.50, 0.55) == pytest.approx(-0.05)
        assert calculate_absolute_departure(0.55, 0.55) == pytest.approx(0.00)

    # --- Percentage Departure ---

    def test_percentage_departure_calculated_when_baseline_ge_0_15(self) -> None:
        """Calculates percentage departure when baseline >= 0.15."""
        pct, reason = calculate_percentage_departure(0.60, 0.50)
        # ((0.60 - 0.50) / 0.50) * 100 = 20.0%
        assert pct == pytest.approx(20.0)
        assert reason is None

    def test_percentage_departure_at_exact_threshold_0_15(self) -> None:
        """Calculates percentage departure at exact boundary 0.15."""
        pct, reason = calculate_percentage_departure(0.18, 0.15)
        # ((0.18 - 0.15) / 0.15) * 100 = 20.0%
        assert pct == pytest.approx(20.0)
        assert reason is None

    def test_percentage_departure_withheld_below_0_15(self) -> None:
        """Returns None with reason 'baseline_below_threshold' when baseline < 0.15."""
        pct, reason = calculate_percentage_departure(0.14, 0.1499)
        assert pct is None
        assert reason == "baseline_below_threshold"

    # --- Z-Score ---

    def test_z_score_calculated_when_valid(self) -> None:
        """Calculates Z-score when N >= 2 and std_dev >= 0.02."""
        z, reason = calculate_z_score(
            current_mean=0.65,
            historical_mean=0.55,
            historical_std_dev=0.05,
            annual_count=3,
        )
        # (0.65 - 0.55) / 0.05 = 2.0
        assert z == pytest.approx(2.0)
        assert reason is None

    def test_z_score_at_exact_std_dev_threshold_0_02(self) -> None:
        """Calculates Z-score at exact std dev boundary 0.02."""
        z, reason = calculate_z_score(
            current_mean=0.57,
            historical_mean=0.55,
            historical_std_dev=0.02,
            annual_count=2,
        )
        # (0.57 - 0.55) / 0.02 = 1.0
        assert z == pytest.approx(1.0)
        assert reason is None

    def test_z_score_withheld_when_std_dev_below_0_02(self) -> None:
        """Returns None with reason 'negligible_variance' when std_dev < 0.02."""
        z, reason = calculate_z_score(
            current_mean=0.56,
            historical_mean=0.55,
            historical_std_dev=0.0199,
            annual_count=3,
        )
        assert z is None
        assert reason == "negligible_variance"

    def test_z_score_withheld_when_std_dev_is_zero(self) -> None:
        """Never divides by zero; returns None with reason 'negligible_variance'."""
        z, reason = calculate_z_score(
            current_mean=0.55,
            historical_mean=0.55,
            historical_std_dev=0.0,
            annual_count=3,
        )
        assert z is None
        assert reason == "negligible_variance"

    def test_z_score_withheld_when_annual_count_less_than_2(self) -> None:
        """Returns None with reason 'insufficient_sample_size' when annual_count < 2."""
        z, reason = calculate_z_score(
            current_mean=0.60,
            historical_mean=0.55,
            historical_std_dev=0.05,
            annual_count=1,
        )
        assert z is None
        assert reason == "insufficient_sample_size"

    # --- Spectral Departure Bands ---

    @pytest.mark.parametrize(
        "delta,expected_band",
        [
            # Strong Positive: delta >= +0.15
            (0.25, "Strong Positive Spectral Departure"),
            (0.15, "Strong Positive Spectral Departure"),
            # Moderate Positive: +0.05 <= delta < +0.15
            (0.1499, "Moderate Positive Spectral Departure"),
            (0.10, "Moderate Positive Spectral Departure"),
            (0.05, "Moderate Positive Spectral Departure"),
            # Near-Baseline: -0.05 < delta < +0.05
            (0.0499, "Near-Baseline Spectral Alignment"),
            (0.00, "Near-Baseline Spectral Alignment"),
            (-0.0499, "Near-Baseline Spectral Alignment"),
            # Moderate Negative: -0.15 < delta <= -0.05
            (-0.05, "Moderate Negative Spectral Departure"),
            (-0.10, "Moderate Negative Spectral Departure"),
            (-0.1499, "Moderate Negative Spectral Departure"),
            # Strong Negative: delta <= -0.15
            (-0.15, "Strong Negative Spectral Departure"),
            (-0.25, "Strong Negative Spectral Departure"),
        ],
    )
    def test_spectral_departure_band_thresholds(
        self, delta: float, expected_band: str
    ) -> None:
        """Verifies exact threshold boundaries for all 5 empirical spectral departure bands."""
        assert classify_spectral_departure(delta) == expected_band


# ==============================================================================
# 5. FULL ANOMALY EVIDENCE CALCULATION
# ==============================================================================


class TestCalculateNdviAnomalyEvidence:
    """Tests for calculate_ndvi_anomaly_evidence container creation."""

    def test_alias_equivalence(self) -> None:
        """Verifies compute_ndvi_anomaly_evidence is alias."""
        assert compute_ndvi_anomaly_evidence is calculate_ndvi_anomaly_evidence

    def test_complete_anomaly_evidence_computation(self) -> None:
        """Calculates full NdviAnomalyEvidence from current mean and valid baseline."""
        baseline = HistoricalNdviBaseline(
            median=0.55,
            mean=0.55,
            standard_deviation=0.04,
            min=0.50,
            max=0.60,
            represented_years=[2025, 2024],
            annual_values=[0.50, 0.60],
            annual_count=2,
        )
        anomaly = calculate_ndvi_anomaly_evidence(0.65, baseline)
        assert anomaly.current_mean == 0.65
        assert anomaly.baseline_median == 0.55
        assert anomaly.absolute_departure == pytest.approx(0.10)
        assert anomaly.percentage_departure == pytest.approx(18.18181818)
        assert anomaly.historical_mean == 0.55
        assert anomaly.historical_std_dev == 0.04
        assert anomaly.z_score == pytest.approx(2.50)
        assert anomaly.departure_band == "Moderate Positive Spectral Departure"
        assert anomaly.percentage_unavailable_reason is None
        assert anomaly.z_score_unavailable_reason is None

    def test_anomaly_evidence_has_no_is_anomalous_field(self) -> None:
        """Guarantees is_anomalous boolean was removed and cannot be accessed."""
        assert "is_anomalous" not in NdviAnomalyEvidence.model_fields


# ==============================================================================
# 6. OVERALL HISTORICAL STATISTICS ENTRY POINT
# ==============================================================================


class TestCalculateHistoricalNdviStatistics:
    """Tests for calculate_historical_ndvi_statistics entry point."""

    def test_alias_equivalence(self) -> None:
        """Verifies compute_historical_ndvi_statistics is alias."""
        assert compute_historical_ndvi_statistics is calculate_historical_ndvi_statistics

    def test_success_with_3_valid_historical_years(self) -> None:
        """Returns success status with populated baseline and anomaly when N=3."""
        current = _make_sample_current_analysis(mean=0.65)
        hist = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, mean=0.60),
            _make_sample_annual_obs(2023, mean=0.50),
        ]
        baseline, sufficiency, anomaly, status, err = calculate_historical_ndvi_statistics(
            current=current,
            historical_observations=hist,
        )
        assert status == "success"
        assert err is None
        assert sufficiency.is_sufficient is True
        assert baseline is not None
        assert baseline.annual_count == 3
        assert baseline.median == pytest.approx(0.55)
        assert anomaly is not None
        assert anomaly.absolute_departure == pytest.approx(0.10)
        assert anomaly.departure_band == "Moderate Positive Spectral Departure"

    def test_success_with_2_valid_historical_years(self) -> None:
        """Returns success status when 2 of 3 years are valid (N=2)."""
        current = _make_sample_current_analysis(mean=0.65)
        hist = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, mean=0.50),
        ]
        baseline, sufficiency, anomaly, status, err = calculate_historical_ndvi_statistics(
            current=current,
            historical_observations=hist,
        )
        assert status == "success"
        assert err is None
        assert sufficiency.is_sufficient is True
        assert baseline is not None
        assert baseline.annual_count == 2
        assert anomaly is not None

    def test_insufficient_history_when_1_historical_year(self) -> None:
        """Returns insufficient_history status with None baseline and anomaly when N=1."""
        current = _make_sample_current_analysis(mean=0.65)
        hist = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, status="no_data"),
        ]
        baseline, sufficiency, anomaly, status, err = calculate_historical_ndvi_statistics(
            current=current,
            historical_observations=hist,
        )
        assert status == "insufficient_history"
        assert err is None
        assert sufficiency.is_sufficient is False
        assert baseline is None
        assert anomaly is None

    def test_no_data_when_current_is_none(self) -> None:
        """Returns no_data status when current observation is None."""
        hist = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, mean=0.60),
            _make_sample_annual_obs(2023, mean=0.50),
        ]
        baseline, sufficiency, anomaly, status, err = calculate_historical_ndvi_statistics(
            current=None,
            historical_observations=hist,
        )
        assert status == "no_data"
        assert baseline is None
        assert anomaly is None

    def test_error_when_current_error_is_provided(self) -> None:
        """Returns error status and preserves EarthEngineError when error occurred."""
        current_err = EarthEngineError(
            type="EE_COMPUTATION_TIMEOUT",
            message="Reduction computation timed out on Earth Engine backend.",
        )
        hist = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, mean=0.60),
            _make_sample_annual_obs(2023, mean=0.50),
        ]
        baseline, sufficiency, anomaly, status, err = calculate_historical_ndvi_statistics(
            current=None,
            historical_observations=hist,
            current_error=current_err,
        )
        assert status == "error"
        assert err == current_err
        assert baseline is None
        assert anomaly is None
