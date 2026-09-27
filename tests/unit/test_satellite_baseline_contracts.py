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
"""Unit tests for Phase 2D historical baseline and anomaly data contracts (Step 1)."""

from pydantic import ValidationError
import pytest

from app.satellite.temporal import construct_historical_temporal_window
from app.satellite.types import (
    AnalysisRegionMetadata,
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    HistoricalAnalysisStatus,
    HistoricalNdviAnalysis,
    HistoricalNdviBaseline,
    HistoricalObservationSummary,
    HistoricalSufficiencyEvidence,
    HistoricalTemporalWindow,
    NdviAnomalyEvidence,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    SatelliteHistoricalAnalysisStatus,
    SatelliteHistoricalNdviAnalysis,
    SatelliteHistoricalNdviBaseline,
    SatelliteHistoricalSufficiencyEvidence,
    SatelliteNdviAnomalyEvidence,
    SatelliteSpectralDepartureBand,
    Sentinel2ImageMetadata,
    SpectralDepartureBand,
)


def _make_sample_annual_obs(
    target_year: int,
    mean: float = 0.58,
    status: str = "success",
) -> AnnualHistoricalNdviObservation:
    """Helper to construct valid AnnualHistoricalNdviObservation."""
    window = construct_historical_temporal_window("2026-08-16", target_year, 15)
    if status == "success":
        stats = NdviRegionalStatistics(
            mean=mean,
            median=mean - 0.01,
            min=0.20,
            max=0.85,
            valid_pixel_count=314,
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


# ==============================================================================
# CONTRACT 1: HistoricalNdviBaseline
# ==============================================================================


class TestHistoricalNdviBaselineContract:
    """Tests for HistoricalNdviBaseline domain model (DEC-013 / DEC-014 / DEC-017)."""

    def test_alias_equivalence(self) -> None:
        """Verifies SatelliteHistoricalNdviBaseline is HistoricalNdviBaseline."""
        assert SatelliteHistoricalNdviBaseline is HistoricalNdviBaseline

    def test_valid_construction_3_years(self) -> None:
        """Valid baseline constructed from 3 represented historical years."""
        baseline = HistoricalNdviBaseline(
            median=0.57,
            mean=0.5667,
            standard_deviation=0.0368,
            min=0.52,
            max=0.61,
            represented_years=[2025, 2024, 2023],
            annual_values=[0.52, 0.61, 0.57],
            annual_count=3,
        )
        assert baseline.median == 0.57
        assert baseline.mean == 0.5667
        assert baseline.standard_deviation == 0.0368
        assert baseline.min == 0.52
        assert baseline.max == 0.61
        assert baseline.represented_years == [2025, 2024, 2023]
        assert baseline.annual_values == [0.52, 0.61, 0.57]
        assert baseline.annual_count == 3

    def test_valid_construction_2_years(self) -> None:
        """Valid baseline constructed from 2 represented historical years."""
        baseline = HistoricalNdviBaseline(
            median=0.55,
            mean=0.55,
            standard_deviation=0.05,
            min=0.50,
            max=0.60,
            represented_years=[2025, 2024],
            annual_values=[0.50, 0.60],
            annual_count=2,
        )
        assert baseline.annual_count == 2
        assert baseline.median == 0.55

    @pytest.mark.parametrize("bad_count", [0, 1, -1])
    def test_rejects_annual_count_less_than_2(self, bad_count: int) -> None:
        """Rejects annual_count < 2 (DEC-014 / DEC-017 guardrail)."""
        with pytest.raises(ValidationError):
            HistoricalNdviBaseline(
                median=0.55,
                mean=0.55,
                standard_deviation=0.0,
                min=0.55,
                max=0.55,
                represented_years=[2025] if bad_count == 1 else [],
                annual_values=[0.55] if bad_count == 1 else [],
                annual_count=bad_count,
            )

    def test_rejects_mismatched_represented_years_length(self) -> None:
        """Rejects when len(represented_years) != annual_count."""
        with pytest.raises(ValidationError, match="Length of represented_years"):
            HistoricalNdviBaseline(
                median=0.55,
                mean=0.55,
                standard_deviation=0.05,
                min=0.50,
                max=0.60,
                represented_years=[2025],  # 1 year but annual_count=2
                annual_values=[0.50, 0.60],
                annual_count=2,
            )

    def test_rejects_mismatched_annual_values_length(self) -> None:
        """Rejects when len(annual_values) != annual_count."""
        with pytest.raises(ValidationError, match="Length of annual_values"):
            HistoricalNdviBaseline(
                median=0.55,
                mean=0.55,
                standard_deviation=0.05,
                min=0.50,
                max=0.60,
                represented_years=[2025, 2024],
                annual_values=[0.50],  # 1 value but annual_count=2
                annual_count=2,
            )

    def test_rejects_duplicate_represented_years(self) -> None:
        """Rejects duplicate target years in represented_years."""
        with pytest.raises(ValidationError, match="Duplicate target years"):
            HistoricalNdviBaseline(
                median=0.55,
                mean=0.55,
                standard_deviation=0.05,
                min=0.50,
                max=0.60,
                represented_years=[2025, 2025],  # Duplicate 2025
                annual_values=[0.50, 0.60],
                annual_count=2,
            )

    def test_rejects_annual_values_outside_ndvi_range(self) -> None:
        """Rejects annual NDVI values outside [-1.0, 1.0]."""
        with pytest.raises(ValidationError, match="outside valid NDVI range"):
            HistoricalNdviBaseline(
                median=0.55,
                mean=0.55,
                standard_deviation=0.05,
                min=0.50,
                max=0.90,
                represented_years=[2025, 2024],
                annual_values=[0.50, 1.20],  # 1.20 > 1.0
                annual_count=2,
            )


    def test_rejects_median_outside_min_max(self) -> None:
        """Rejects median < min or median > max."""
        with pytest.raises(ValidationError, match="Baseline median .* outside"):
            HistoricalNdviBaseline(
                median=0.45,  # 0.45 < min 0.50
                mean=0.55,
                standard_deviation=0.05,
                min=0.50,
                max=0.60,
                represented_years=[2025, 2024],
                annual_values=[0.50, 0.60],
                annual_count=2,
            )

    def test_rejects_mean_outside_min_max(self) -> None:
        """Rejects mean < min or mean > max."""
        with pytest.raises(ValidationError, match="Baseline mean .* outside"):
            HistoricalNdviBaseline(
                median=0.55,
                mean=0.65,  # 0.65 > max 0.60
                standard_deviation=0.05,
                min=0.50,
                max=0.60,
                represented_years=[2025, 2024],
                annual_values=[0.50, 0.60],
                annual_count=2,
            )


# ==============================================================================
# CONTRACT 2: HistoricalSufficiencyEvidence
# ==============================================================================


class TestHistoricalSufficiencyEvidenceContract:
    """Tests for HistoricalSufficiencyEvidence domain model (DEC-014 / DEC-017)."""

    def test_alias_equivalence(self) -> None:
        """Verifies SatelliteHistoricalSufficiencyEvidence is HistoricalSufficiencyEvidence."""
        assert SatelliteHistoricalSufficiencyEvidence is HistoricalSufficiencyEvidence

    def test_valid_sufficient_construction(self) -> None:
        """Valid sufficiency evidence with N=3."""
        evidence = HistoricalSufficiencyEvidence(
            requested_years_count=3,
            represented_years_count=3,
            minimum_required_years=2,
            is_sufficient=True,
            represented_years=[2025, 2024, 2023],
            missing_years=[],
            sufficiency_notes="Sufficient historical observations available (N=3).",
        )
        assert evidence.is_sufficient is True
        assert evidence.represented_years_count == 3
        assert evidence.missing_years == []

    def test_valid_insufficient_construction(self) -> None:
        """Valid sufficiency evidence with N=1."""
        evidence = HistoricalSufficiencyEvidence(
            requested_years_count=3,
            represented_years_count=1,
            minimum_required_years=2,
            is_sufficient=False,
            represented_years=[2025],
            missing_years=[2024, 2023],
            sufficiency_notes="1 of 3 requested historical years produced usable annual observations (minimum 2 required).",
        )
        assert evidence.is_sufficient is False
        assert evidence.represented_years_count == 1
        assert evidence.missing_years == [2024, 2023]


# ==============================================================================
# CONTRACT 3 & 4: SpectralDepartureBand & NdviAnomalyEvidence
# ==============================================================================


class TestNdviAnomalyEvidenceContract:
    """Tests for NdviAnomalyEvidence domain model (DEC-013 / DEC-014 / DEC-017)."""

    def test_alias_equivalence(self) -> None:
        """Verifies SatelliteNdviAnomalyEvidence and SatelliteSpectralDepartureBand."""
        assert SatelliteNdviAnomalyEvidence is NdviAnomalyEvidence
        assert SatelliteSpectralDepartureBand is SpectralDepartureBand

    @pytest.mark.parametrize(
        "band",
        [
            "Strong Positive Spectral Departure",
            "Moderate Positive Spectral Departure",
            "Near-Baseline Spectral Alignment",
            "Moderate Negative Spectral Departure",
            "Strong Negative Spectral Departure",
        ],
    )
    def test_all_5_departure_bands_accepted(self, band: str) -> None:
        """Verifies all 5 approved empirical spectral departure bands instantiate successfully."""
        anomaly = NdviAnomalyEvidence(
            current_mean=0.65,
            baseline_median=0.55,
            absolute_departure=0.10,
            percentage_departure=18.18,
            historical_mean=0.55,
            historical_std_dev=0.04,
            z_score=2.50,
            departure_band=band,
        )
        assert anomaly.departure_band == band
        assert anomaly.absolute_departure == 0.10

    def test_invalid_band_rejected(self) -> None:
        """Rejects diagnostic or unauthorized departure band labels."""
        with pytest.raises(ValidationError):
            NdviAnomalyEvidence(
                current_mean=0.65,
                baseline_median=0.55,
                absolute_departure=0.10,
                percentage_departure=18.18,
                historical_mean=0.55,
                historical_std_dev=0.04,
                z_score=2.50,
                departure_band="Severe Crop Disease Deficit",  # Unauthorized label
            )

    def test_gated_unavailable_metrics_with_reasons(self) -> None:
        """Verifies percentage_departure and z_score can be None with explicit reason strings."""
        anomaly = NdviAnomalyEvidence(
            current_mean=0.12,
            baseline_median=0.10,
            absolute_departure=0.02,
            percentage_departure=None,
            historical_mean=0.10,
            historical_std_dev=0.01,
            z_score=None,
            departure_band="Near-Baseline Spectral Alignment",
            percentage_unavailable_reason="baseline_below_threshold",
            z_score_unavailable_reason="negligible_variance",
        )
        assert anomaly.percentage_departure is None
        assert anomaly.percentage_unavailable_reason == "baseline_below_threshold"
        assert anomaly.z_score is None
        assert anomaly.z_score_unavailable_reason == "negligible_variance"

    def test_is_anomalous_is_not_a_field(self) -> None:
        """Verifies is_anomalous boolean was permanently removed (Final Refinement)."""
        assert "is_anomalous" not in NdviAnomalyEvidence.model_fields


# ==============================================================================
# CONTRACT 5 & 6: HistoricalAnalysisStatus & HistoricalNdviAnalysis
# ==============================================================================


class TestHistoricalNdviAnalysisContract:
    """Tests for HistoricalNdviAnalysis root container (DEC-014 / DEC-017)."""

    def test_alias_equivalence(self) -> None:
        """Verifies SatelliteHistoricalNdviAnalysis and SatelliteHistoricalAnalysisStatus."""
        assert SatelliteHistoricalNdviAnalysis is HistoricalNdviAnalysis
        assert SatelliteHistoricalAnalysisStatus is HistoricalAnalysisStatus

    def test_valid_success_construction(self) -> None:
        """Verifies complete successful HistoricalNdviAnalysis construction."""
        cur_meta = Sentinel2ImageMetadata(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251",
            acquisition_date="2026-08-16T05:50:41+00:00",
            cloud_percentage=5.0,
        )
        cur_stats = NdviRegionalStatistics(
            mean=0.65,
            median=0.64,
            min=0.30,
            max=0.88,
            valid_pixel_count=314,
        )
        cur_analysis = RegionalNdviAnalysis(
            observation=cur_meta,
            quality=ObservationQualityEvidence(quality_mask_applied=True, is_usable=True),
            freshness=ObservationFreshness(reference_date="2026-08-16", observation_age_days=0),
            region=AnalysisRegionMetadata(latitude=30.9157, longitude=75.7196),
            statistics=cur_stats,
        )
        hist_obs = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, mean=0.60),
            _make_sample_annual_obs(2023, mean=0.58),
        ]
        baseline = HistoricalNdviBaseline(
            median=0.58,
            mean=0.5767,
            standard_deviation=0.0205,
            min=0.55,
            max=0.60,
            represented_years=[2025, 2024, 2023],
            annual_values=[0.55, 0.60, 0.58],
            annual_count=3,
        )
        sufficiency = HistoricalSufficiencyEvidence(
            requested_years_count=3,
            represented_years_count=3,
            minimum_required_years=2,
            is_sufficient=True,
            represented_years=[2025, 2024, 2023],
            missing_years=[],
            sufficiency_notes="Sufficient historical observations available (N=3).",
        )
        anomaly = NdviAnomalyEvidence(
            current_mean=0.65,
            baseline_median=0.58,
            absolute_departure=0.07,
            percentage_departure=12.07,
            historical_mean=0.5767,
            historical_std_dev=0.0205,
            z_score=3.58,
            departure_band="Moderate Positive Spectral Departure",
        )

        analysis = HistoricalNdviAnalysis(
            current=cur_analysis,
            historical_observations=hist_obs,
            baseline=baseline,
            sufficiency=sufficiency,
            anomaly=anomaly,
            status="success",
            pipeline_version="2.0.0",
        )

        assert analysis.status == "success"
        assert analysis.pipeline_version == "2.0.0"
        assert analysis.baseline is not None
        assert analysis.anomaly is not None
        assert analysis.current is not None
        assert len(analysis.historical_observations) == 3

    def test_valid_insufficient_history_construction(self) -> None:
        """Verifies construction when historical evidence is insufficient (baseline/anomaly are None)."""
        hist_obs = [
            _make_sample_annual_obs(2025, mean=0.55),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, status="no_data"),
        ]
        sufficiency = HistoricalSufficiencyEvidence(
            requested_years_count=3,
            represented_years_count=1,
            minimum_required_years=2,
            is_sufficient=False,
            represented_years=[2025],
            missing_years=[2024, 2023],
            sufficiency_notes="1 of 3 requested historical years produced usable annual observations (minimum 2 required).",
        )

        analysis = HistoricalNdviAnalysis(
            current=None,
            historical_observations=hist_obs,
            baseline=None,
            sufficiency=sufficiency,
            anomaly=None,
            status="insufficient_history",
        )

        assert analysis.status == "insufficient_history"
        assert analysis.baseline is None
        assert analysis.anomaly is None
        assert analysis.sufficiency.is_sufficient is False
        assert len(analysis.historical_observations) == 3
