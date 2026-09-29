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
"""Unit tests for Phase 2D multi-year historical orchestration and anomaly integration (Step 3)."""

from unittest.mock import patch
import pytest

import app.satellite
from app.satellite.baseline import (
    calculate_historical_ndvi_statistics,
)
from app.satellite.historical_analysis import (
    analyze_historical_ndvi,
    build_historical_ndvi_analysis,
)
from app.satellite.temporal import construct_historical_temporal_window
from app.satellite.types import (
    AnalysisRegionMetadata,
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    EarthEngineResult,
    HistoricalAnalysisStatus,
    HistoricalNdviAnalysis,
    HistoricalNdviBaseline,
    HistoricalObservationSummary,
    HistoricalSufficiencyEvidence,
    NdviAnomalyEvidence,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    Sentinel2ImageMetadata,
    SpectralDepartureBand,
)


def _make_sample_current_analysis(
    mean: float = 0.60,
    acquisition_date: str = "2026-08-16T05:50:41+00:00",
) -> RegionalNdviAnalysis:
    """Helper to construct a valid RegionalNdviAnalysis payload."""
    return RegionalNdviAnalysis(
        observation=Sentinel2ImageMetadata(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251",
            acquisition_date=acquisition_date,
            cloud_percentage=4.5,
            spacecraft_name="Sentinel-2A",
            mgrs_tile="43REQ",
            product_id="S2A_MSIL2A_20260816T054251_N0500_R005_T43REQ",
            system_time_start=1786859441000,
            usable_coverage_percentage=98.5,
            clear_threshold=0.60,
            quality_band="cs_cdf",
        ),
        quality=ObservationQualityEvidence(
            quality_dataset="GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED",
            min_usable_coverage_threshold=0.70,
            max_scene_cloud_threshold=20.0,
            quality_mask_applied=True,
            is_usable=True,
        ),
        freshness=ObservationFreshness(
            reference_date="2026-08-16",
            observation_age_days=0,
            lookback_window_days=30,
        ),
        region=AnalysisRegionMetadata(
            latitude=30.9157,
            longitude=75.7196,
            radius_m=100.0,
            geometry_type="PointBuffer",
            scale_m=10.0,
        ),
        statistics=NdviRegionalStatistics(
            mean=mean,
            median=mean - 0.01,
            min=mean - 0.20,
            max=mean + 0.20,
            valid_pixel_count=314,
        ),
        pipeline_version="1.0.0",
    )


def _make_sample_annual_obs(
    target_year: int,
    mean: float = 0.58,
    status: str = "success",
    error: EarthEngineError | None = None,
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
    elif status == "no_data":
        return AnnualHistoricalNdviObservation(
            target_year=target_year,
            temporal_window=window,
            available_usable_scenes_count=0,
            selected_scenes_count=0,
            selected_observations=[],
            statistics=None,
            status="no_data",
        )
    else:  # status == "error"
        return AnnualHistoricalNdviObservation(
            target_year=target_year,
            temporal_window=window,
            available_usable_scenes_count=0,
            selected_scenes_count=0,
            selected_observations=[],
            statistics=None,
            status="error",
            error=error or EarthEngineError(type="SyntheticError", message="Test error"),
        )


class TestSatelliteHistoricalBaselineIntegration:
    """Tests for Phase 2D Step 3 root orchestration and anomaly integration."""

    def test_current_success_with_3_historical_years_success(self) -> None:
        """TC-1: Current success + 3 successful historical years -> status='success'."""
        current = _make_sample_current_analysis(mean=0.62)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.55),
            _make_sample_annual_obs(2023, mean=0.50),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert isinstance(result, HistoricalNdviAnalysis)
        assert result.status == "success"
        assert result.pipeline_version == "2.0.0"
        assert result.error is None
        assert result.current == current
        assert len(result.historical_observations) == 3

        # Baseline assertions
        assert result.baseline is not None
        assert result.baseline.annual_count == 3
        assert result.baseline.represented_years == [2025, 2024, 2023]
        assert result.baseline.median == 0.55
        assert result.baseline.min == 0.50
        assert result.baseline.max == 0.58

        # Sufficiency assertions
        assert result.sufficiency.is_sufficient is True
        assert result.sufficiency.represented_years_count == 3
        assert result.sufficiency.missing_years == []

        # Anomaly assertions
        assert result.anomaly is not None
        assert result.anomaly.current_mean == 0.62
        assert result.anomaly.baseline_median == 0.55
        assert round(result.anomaly.absolute_departure, 4) == 0.07
        assert result.anomaly.departure_band == "Moderate Positive Spectral Departure"


    def test_current_success_with_2_historical_years_success(self) -> None:
        """TC-2: Current success + 2 successful historical years -> status='success' (N=2 threshold)."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert result.status == "success"
        assert result.baseline is not None
        assert result.baseline.annual_count == 2
        assert result.baseline.represented_years == [2025, 2024]
        assert result.sufficiency.is_sufficient is True
        assert result.anomaly is not None

    def test_current_success_with_1_historical_year_insufficient(self) -> None:
        """TC-3: Current success + 1 successful historical year -> status='insufficient_history'."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert result.status == "insufficient_history"
        assert result.baseline is None
        assert result.anomaly is None
        assert result.error is None
        assert result.current == current
        assert result.sufficiency.is_sufficient is False
        assert result.sufficiency.represented_years_count == 1

    def test_current_success_with_0_historical_years_insufficient(self) -> None:
        """TC-4: Current success + 0 successful historical years -> status='insufficient_history'."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, status="no_data"),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, status="no_data"),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert result.status == "insufficient_history"
        assert result.baseline is None
        assert result.anomaly is None
        assert result.sufficiency.is_sufficient is False
        assert result.sufficiency.represented_years_count == 0
        assert result.sufficiency.missing_years == [2025, 2024, 2023]
        assert len(result.historical_observations) == 3

    def test_current_success_with_2_success_1_no_data(self) -> None:
        """TC-5: Current success + 2 success + 1 no_data -> status='success', failed year preserved."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58, status="success"),
            _make_sample_annual_obs(2024, status="no_data"),
            _make_sample_annual_obs(2023, mean=0.52, status="success"),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert result.status == "success"
        assert result.baseline is not None
        assert result.baseline.annual_count == 2
        assert result.baseline.represented_years == [2025, 2023]
        assert result.sufficiency.represented_years == [2025, 2023]
        assert result.sufficiency.missing_years == [2024]
        assert len(result.historical_observations) == 3
        assert result.historical_observations[1].status == "no_data"

    def test_current_success_with_2_success_1_error(self) -> None:
        """TC-6: Current success + 2 success + 1 error -> status='success', error year preserved."""
        current = _make_sample_current_analysis(mean=0.60)
        err = EarthEngineError(type="QuotaExceededError", message="Historical year timed out")
        history = [
            _make_sample_annual_obs(2025, mean=0.58, status="success"),
            _make_sample_annual_obs(2024, status="error", error=err),
            _make_sample_annual_obs(2023, mean=0.52, status="success"),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert result.status == "success"
        assert result.baseline is not None
        assert result.baseline.annual_count == 2
        assert result.baseline.represented_years == [2025, 2023]
        assert result.sufficiency.missing_years == [2024]
        assert len(result.historical_observations) == 3
        assert result.historical_observations[1].status == "error"
        assert result.historical_observations[1].error == err

    def test_current_no_data_propagates_no_data_status(self) -> None:
        """TC-7: Current is None/no_data -> status='no_data', baseline computed if sufficient, anomaly=None."""
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.55),
            _make_sample_annual_obs(2023, mean=0.50),
        ]

        result = build_historical_ndvi_analysis(current=None, historical_observations=history)

        assert result.status == "no_data"
        assert result.current is None
        assert result.baseline is not None
        assert result.baseline.annual_count == 3
        assert result.baseline.median == 0.55
        assert result.anomaly is None
        assert result.error is None
        assert len(result.historical_observations) == 3
        assert result.sufficiency.is_sufficient is True

    def test_current_error_propagates_error_status_and_payload(self) -> None:
        """TC-8: Current has error -> status='error', baseline computed if sufficient, anomaly=None, exact error preserved."""
        curr_err = EarthEngineError(type="MetadataExtractionError", message="Cloud Score+ unavailable")
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.55),
            _make_sample_annual_obs(2023, mean=0.50),
        ]

        result = build_historical_ndvi_analysis(
            current=None,
            historical_observations=history,
            current_error=curr_err,
        )

        assert result.status == "error"
        assert result.current is None
        assert result.baseline is not None
        assert result.baseline.annual_count == 3
        assert result.anomaly is None
        assert result.error == curr_err
        assert len(result.historical_observations) == 3

    def test_accepts_earth_engine_result_wrapper_for_current(self) -> None:
        """TC-9: EarthEngineResult wrapper inputs are normalized correctly."""
        current_analysis = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
        ]

        # 9a: EarthEngineResult status='success'
        ee_success = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=5,
            data=current_analysis,
        )
        res_success = build_historical_ndvi_analysis(current=ee_success, historical_observations=history)
        assert res_success.status == "success"
        assert res_success.current == current_analysis
        assert res_success.baseline is not None
        assert res_success.anomaly is not None

        # 9b: EarthEngineResult status='no_data'
        ee_nodata = EarthEngineResult(
            status="no_data",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=0,
            data=None,
        )
        res_nodata = build_historical_ndvi_analysis(current=ee_nodata, historical_observations=history)
        assert res_nodata.status == "no_data"
        assert res_nodata.current is None
        assert res_nodata.baseline is not None
        assert res_nodata.anomaly is None

        # 9c: EarthEngineResult status='error'
        ee_err_obj = EarthEngineError(type="EEException", message="Remote compute failed")
        ee_err = EarthEngineResult(
            status="error",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=None,
            data=None,
            error=ee_err_obj,
        )
        res_err = build_historical_ndvi_analysis(current=ee_err, historical_observations=history)
        assert res_err.status == "error"
        assert res_err.current is None
        assert res_err.baseline is not None
        assert res_err.anomaly is None
        assert res_err.error == ee_err_obj

    def test_input_immutability(self) -> None:
        """TC-10: Neither current nor historical_observations are mutated."""
        current = _make_sample_current_analysis(mean=0.60)
        current_dict_before = current.model_dump()
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.55),
        ]
        history_len_before = len(history)

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert current.model_dump() == current_dict_before
        assert len(history) == history_len_before
        assert result.historical_observations is not history  # Defensively copied list

    def test_step2_engine_equivalence(self) -> None:
        """TC-11: Result matches direct calculate_historical_ndvi_statistics output."""
        current = _make_sample_current_analysis(mean=0.62)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
            _make_sample_annual_obs(2023, mean=0.50),
        ]

        expected_baseline, expected_suff, expected_anom, expected_stat, expected_err = (
            calculate_historical_ndvi_statistics(
                current=current,
                historical_observations=history,
            )
        )

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert result.baseline == expected_baseline
        assert result.sufficiency == expected_suff
        assert result.anomaly == expected_anom
        assert result.status == expected_stat
        assert result.error == expected_err

    def test_current_year_strictly_excluded_from_baseline(self) -> None:
        """TC-12: Current year (2026) is strictly excluded from baseline represented_years."""
        current = _make_sample_current_analysis(mean=0.60, acquisition_date="2026-08-16T05:50:41+00:00")
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
            _make_sample_annual_obs(2023, mean=0.50),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)

        assert 2026 not in result.baseline.represented_years
        assert result.baseline.represented_years == [2025, 2024, 2023]

    def test_zero_earth_engine_calls_guarantee(self) -> None:
        """TC-13: Execution of build_historical_ndvi_analysis makes zero EE or network calls."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
        ]

        with patch("ee.Image") as mock_ee_img, patch("ee.ImageCollection") as mock_ee_col:
            result = build_historical_ndvi_analysis(current=current, historical_observations=history)
            assert result.status == "success"
            mock_ee_img.assert_not_called()
            mock_ee_col.assert_not_called()

    def test_pipeline_version_is_2_0_0(self) -> None:
        """TC-14: pipeline_version is strictly '2.0.0'."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)
        assert result.pipeline_version == "2.0.0"

    def test_no_subjective_agronomic_fields(self) -> None:
        """TC-15: Confirms no diagnostic, disease, confidence, or risk fields exist."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
        ]

        result = build_historical_ndvi_analysis(current=current, historical_observations=history)
        data_dict = result.model_dump()

        forbidden_fields = [
            "confidence",
            "reliability",
            "severity",
            "diagnosis",
            "risk_score",
            "is_anomalous",
            "health_score",
        ]
        for field in forbidden_fields:
            assert field not in data_dict
            if result.anomaly is not None:
                assert field not in result.anomaly.model_dump()

    def test_input_type_validation(self) -> None:
        """TC-16: Rejects malformed arguments with TypeError / ValueError."""
        current = _make_sample_current_analysis(mean=0.60)
        valid_history = [_make_sample_annual_obs(2025, mean=0.58)]

        # Non-list historical_observations
        with pytest.raises(TypeError, match="historical_observations must be a list"):
            build_historical_ndvi_analysis(current=current, historical_observations="invalid")  # type: ignore

        # List with invalid items
        with pytest.raises(TypeError, match="must be an instance of AnnualHistoricalNdviObservation"):
            build_historical_ndvi_analysis(current=current, historical_observations=["not_an_obs"])  # type: ignore

        # Invalid requested_years_count
        with pytest.raises(ValueError, match="requested_years_count must be a strictly positive integer"):
            build_historical_ndvi_analysis(current=current, historical_observations=valid_history, requested_years_count=0)

        # Invalid minimum_required_years
        with pytest.raises(ValueError, match="minimum_required_years must be a strictly positive integer"):
            build_historical_ndvi_analysis(current=current, historical_observations=valid_history, minimum_required_years=-1)

        # Invalid current type
        with pytest.raises(TypeError, match="current must be RegionalNdviAnalysis, EarthEngineResult, or None"):
            build_historical_ndvi_analysis(current=12345, historical_observations=valid_history)  # type: ignore

    def test_public_export_verification(self) -> None:
        """TC-17: Verifies package-level exports in app.satellite."""
        # Main entry points and alias
        assert hasattr(app.satellite, "build_historical_ndvi_analysis")
        assert hasattr(app.satellite, "analyze_historical_ndvi")
        assert app.satellite.analyze_historical_ndvi is app.satellite.build_historical_ndvi_analysis

        # Public Phase 2D types
        assert hasattr(app.satellite, "HistoricalNdviAnalysis")
        assert hasattr(app.satellite, "HistoricalNdviBaseline")
        assert hasattr(app.satellite, "HistoricalSufficiencyEvidence")
        assert hasattr(app.satellite, "NdviAnomalyEvidence")
        assert hasattr(app.satellite, "HistoricalAnalysisStatus")
        assert hasattr(app.satellite, "SpectralDepartureBand")

        # Satellite* aliases
        assert hasattr(app.satellite, "SatelliteHistoricalNdviAnalysis")
        assert hasattr(app.satellite, "SatelliteHistoricalNdviBaseline")
        assert hasattr(app.satellite, "SatelliteHistoricalSufficiencyEvidence")
        assert hasattr(app.satellite, "SatelliteNdviAnomalyEvidence")
        assert hasattr(app.satellite, "SatelliteHistoricalAnalysisStatus")
        assert hasattr(app.satellite, "SatelliteSpectralDepartureBand")

        # Internal helpers MUST NOT be exported in app.satellite
        assert not hasattr(app.satellite, "calculate_historical_baseline")
        assert not hasattr(app.satellite, "calculate_historical_ndvi_statistics")
        assert not hasattr(app.satellite, "calculate_sufficiency_evidence")
        assert not hasattr(app.satellite, "calculate_absolute_departure")
        assert not hasattr(app.satellite, "calculate_percentage_departure")
        assert not hasattr(app.satellite, "calculate_z_score")
        assert not hasattr(app.satellite, "classify_spectral_departure")
        assert not hasattr(app.satellite, "extract_valid_annual_observations")

    def test_alias_equivalence(self) -> None:
        """TC-18: analyze_historical_ndvi is identical to build_historical_ndvi_analysis."""
        current = _make_sample_current_analysis(mean=0.60)
        history = [
            _make_sample_annual_obs(2025, mean=0.58),
            _make_sample_annual_obs(2024, mean=0.54),
        ]

        res1 = build_historical_ndvi_analysis(current=current, historical_observations=history)
        res2 = analyze_historical_ndvi(current=current, historical_observations=history)

        assert res1 == res2
