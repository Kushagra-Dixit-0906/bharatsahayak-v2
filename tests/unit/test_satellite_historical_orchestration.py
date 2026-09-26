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
"""Unit tests for Phase 2C multi-year historical orchestration (Step 4)."""

from datetime import date, datetime, timezone
import math
from unittest.mock import MagicMock, call, patch

import ee
import pytest

from app.satellite.geometry import create_analysis_region
from app.satellite.historical import (
    DEFAULT_HISTORICAL_MAX_OBSERVATIONS,
    analyze_historical_years,
    compute_multi_year_historical_ndvi,
    orchestrate_historical_ndvi,
)
from app.satellite.temporal import (
    DEFAULT_HISTORICAL_YEARS,
    DEFAULT_WINDOW_HALF_DAYS,
    construct_historical_temporal_window,
)
from app.satellite.types import (
    AnalysisRegionMetadata,
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    EarthEngineResult,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
    NdviRegionalStatistics,
    ObservationFreshness,
    ObservationQualityEvidence,
    RegionalNdviAnalysis,
    Sentinel2ImageMetadata,
)


@pytest.fixture(autouse=True)
def init_mock_ee():
    """Ensures Earth Engine is initialized for client proxy objects."""
    ee.Initialize(project="bharatsahayak-v2")


@pytest.fixture
def sample_region() -> ee.Geometry:
    """Returns a valid circular parcel buffer geometry."""
    return create_analysis_region(30.9157, 75.7196, radius_m=100.0)


@pytest.fixture
def sample_statistics() -> NdviRegionalStatistics:
    """Returns sample valid NdviRegionalStatistics."""
    return NdviRegionalStatistics(
        mean=0.58,
        median=0.57,
        min=0.25,
        max=0.82,
        valid_pixel_count=314,
    )


def _make_sample_annual_obs(
    target_year: int,
    reference_date: str = "2026-08-16",
    status: str = "success",
    mean: float = 0.58,
    error: EarthEngineError | None = None,
) -> AnnualHistoricalNdviObservation:
    """Helper to construct a valid AnnualHistoricalNdviObservation for mocking."""
    window = construct_historical_temporal_window(
        reference_date=reference_date,
        target_year=target_year,
        window_half_days=15,
    )
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
            available_usable_scenes_count=2,
            selected_scenes_count=1,
            selected_observations=scenes,
            statistics=stats,
            status="success",
            composite_method="identity",
            pipeline_version="1.0.0",
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
            composite_method="none",
            pipeline_version="1.0.0",
        )
    elif status == "error":
        return AnnualHistoricalNdviObservation(
            target_year=target_year,
            temporal_window=window,
            available_usable_scenes_count=0,
            selected_scenes_count=0,
            selected_observations=[],
            statistics=None,
            status="error",
            composite_method="none",
            pipeline_version="1.0.0",
            error=error or EarthEngineError(type="EEError", message="Mock EE failure"),
        )
    raise ValueError(f"Unknown status {status}")


# ==============================================================================
# 1. INPUT VALIDATION TESTS
# ==============================================================================


class TestHistoricalOrchestrationInputValidation:
    """Tests synchronous argument validation for multi-year orchestrator."""

    def test_alias_equivalence(self) -> None:
        """Verifies semantic aliases point to analyze_historical_years."""
        assert orchestrate_historical_ndvi is analyze_historical_years
        assert compute_multi_year_historical_ndvi is analyze_historical_years

    @pytest.mark.parametrize(
        "bad_ref_date",
        [None, 12345, True, False, {"date": "2026-08-16"}, [2026, 8, 16], "not-a-date", "2026/08/16", ""],
    )
    def test_invalid_reference_date_rejected(
        self,
        bad_ref_date,
        sample_region: ee.Geometry,
    ) -> None:
        """Invalid reference_date format or type is rejected with TypeError or ValueError."""
        with pytest.raises((TypeError, ValueError)):
            analyze_historical_years(reference_date=bad_ref_date, region=sample_region)

    @pytest.mark.parametrize("bad_region", [None, "region", 123, {"type": "PointBuffer"}])
    def test_invalid_region_rejected(self, bad_region) -> None:
        """Invalid region geometry is rejected with TypeError."""
        with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
            analyze_historical_years(reference_date="2026-08-16", region=bad_region)

    @pytest.mark.parametrize("bad_years", [0, -1, -5, 3.5, True, False, "3", None])
    def test_invalid_history_years_rejected(
        self,
        bad_years,
        sample_region: ee.Geometry,
    ) -> None:
        """Non-positive or non-integer history_years is rejected with ValueError."""
        with pytest.raises(ValueError):
            analyze_historical_years(
                reference_date="2026-08-16",
                region=sample_region,
                history_years=bad_years,
            )

    @pytest.mark.parametrize("bad_half_days", [-1, -15, 15.5, True, False, "15", None])
    def test_invalid_window_half_days_rejected(
        self,
        bad_half_days,
        sample_region: ee.Geometry,
    ) -> None:
        """Negative or non-integer window_half_days is rejected with ValueError."""
        with pytest.raises(ValueError):
            analyze_historical_years(
                reference_date="2026-08-16",
                region=sample_region,
                window_half_days=bad_half_days,
            )

    @pytest.mark.parametrize("bad_max_obs", [0, -1, 4, 10, 2.5, True, False, "3", None])
    def test_invalid_max_observations_rejected(
        self,
        bad_max_obs,
        sample_region: ee.Geometry,
    ) -> None:
        """max_observations not in [1, 3] is rejected with ValueError."""
        with pytest.raises(ValueError):
            analyze_historical_years(
                reference_date="2026-08-16",
                region=sample_region,
                max_observations=bad_max_obs,
            )

    @pytest.mark.parametrize("bad_scale", [0, -10.0, math.nan, math.inf, "10", None])
    def test_invalid_scale_rejected(
        self,
        bad_scale,
        sample_region: ee.Geometry,
    ) -> None:
        """scale_m not strictly positive is rejected with ValueError."""
        with pytest.raises(ValueError):
            analyze_historical_years(
                reference_date="2026-08-16",
                region=sample_region,
                scale_m=bad_scale,
            )


# ==============================================================================
# 2. REFERENCE DATE INPUT POLYMORPHISM TESTS
# ==============================================================================


class TestReferenceDatePolymorphism:
    """Tests that various valid reference date types and domain models are accepted."""

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_iso_string_reference_date(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Accepts plain ISO date string 'YYYY-MM-DD'."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
        )
        assert len(results) == 3
        assert [r.target_year for r in results] == [2025, 2024, 2023]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_iso_datetime_string_reference_date(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Accepts ISO datetime string with timestamp and timezone."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date="2026-08-16T05:50:41.321000+00:00",
            region=sample_region,
        )
        assert len(results) == 3
        assert [r.target_year for r in results] == [2025, 2024, 2023]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_date_object_reference_date(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Accepts datetime.date object."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date=date(2026, 8, 16),
            region=sample_region,
        )
        assert len(results) == 3
        assert [r.target_year for r in results] == [2025, 2024, 2023]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_datetime_object_reference_date(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Accepts datetime.datetime object."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date=datetime(2026, 8, 16, 5, 50, 41, tzinfo=timezone.utc),
            region=sample_region,
        )
        assert len(results) == 3
        assert [r.target_year for r in results] == [2025, 2024, 2023]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_sentinel2_image_metadata_reference_date(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Accepts Sentinel2ImageMetadata domain model and extracts acquisition_date."""
        meta = Sentinel2ImageMetadata(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251",
            acquisition_date="2026-08-16T05:50:41+00:00",
            cloud_percentage=5.0,
        )
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date=meta,
            region=sample_region,
        )
        assert len(results) == 3
        assert [r.target_year for r in results] == [2025, 2024, 2023]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_regional_ndvi_analysis_reference_date(
        self,
        mock_compute,
        sample_region: ee.Geometry,
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """Accepts RegionalNdviAnalysis domain payload from Phase 1 and extracts observation acquisition date."""
        meta = Sentinel2ImageMetadata(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251",
            acquisition_date="2026-08-16T05:50:41+00:00",
            cloud_percentage=5.0,
        )
        analysis = RegionalNdviAnalysis(
            observation=meta,
            quality=ObservationQualityEvidence(
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
            ),
            statistics=sample_statistics,
        )
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date=analysis,
            region=sample_region,
        )
        assert len(results) == 3
        assert [r.target_year for r in results] == [2025, 2024, 2023]


# ==============================================================================
# 3. TARGET YEARS & CURRENT YEAR EXCLUSION TESTS
# ==============================================================================


class TestTargetYearsAndExclusion:
    """Tests historical target year calculations and current year exclusion."""

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_current_year_strictly_excluded(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies current year (2026) is NOT queried as a historical target."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]
        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
            history_years=3,
        )

        target_years_called = [call_args[1]["temporal_window"].target_year for call_args in mock_compute.call_args_list]
        assert 2026 not in target_years_called
        assert target_years_called == [2025, 2024, 2023]
        assert [r.target_year for r in results] == [2025, 2024, 2023]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_configurable_history_years_count(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies history_years=2 produces Y-1 and Y-2."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
        ]
        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
            history_years=2,
        )
        assert len(results) == 2
        assert [r.target_year for r in results] == [2025, 2024]

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_leap_year_reference_date_handling(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C13: Reference date Feb 29 in leap year (2024) generates Feb 28 anchor in common years."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023, reference_date="2024-02-29")),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2022, reference_date="2024-02-29")),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2021, reference_date="2024-02-29")),
        ]
        results = analyze_historical_years(
            reference_date="2024-02-29",
            region=sample_region,
            history_years=3,
        )
        assert len(results) == 3
        # Check anchors passed to compute_annual_historical_ndvi
        windows = [call_args[1]["temporal_window"] for call_args in mock_compute.call_args_list]
        assert windows[0].anchor_date == date(2023, 2, 28)
        assert windows[1].anchor_date == date(2022, 2, 28)
        assert windows[2].anchor_date == date(2021, 2, 28)

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_year_crossing_window_ownership(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C12: Reference date Jan 5 generates cross-year window owned strictly by target year."""
        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2025, reference_date="2026-01-05")),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024, reference_date="2026-01-05")),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023, reference_date="2026-01-05")),
        ]
        results = analyze_historical_years(
            reference_date="2026-01-05",
            region=sample_region,
            history_years=3,
        )
        assert len(results) == 3
        windows = [call_args[1]["temporal_window"] for call_args in mock_compute.call_args_list]
        assert windows[0].target_year == 2025
        assert windows[0].start_date == date(2024, 12, 21)
        assert windows[0].end_date == date(2025, 1, 20)


# ==============================================================================
# 4. MULTI-YEAR OUTCOMES & FAULT ISOLATION TESTS
# ==============================================================================


class TestMultiYearOutcomesAndFaultIsolation:
    """Tests heterogeneous year results and failure isolation."""

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_all_years_success(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """All 3 historical years succeed and return valid AnnualHistoricalNdviObservation items."""
        obs_2025 = _make_sample_annual_obs(2025, mean=0.62)
        obs_2024 = _make_sample_annual_obs(2024, mean=0.55)
        obs_2023 = _make_sample_annual_obs(2023, mean=0.59)

        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=obs_2025),
            EarthEngineResult(status="success", data=obs_2024),
            EarthEngineResult(status="success", data=obs_2023),
        ]

        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
        )

        assert len(results) == 3
        assert results[0] == obs_2025
        assert results[1] == obs_2024
        assert results[2] == obs_2023
        assert all(r.status == "success" for r in results)

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_heterogeneous_years_fault_isolation(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C17: Y-1 success, Y-2 no_data, Y-3 error preserves all 3 records without dropping or aborting."""
        obs_2025 = _make_sample_annual_obs(2025, mean=0.60, status="success")
        obs_2024 = _make_sample_annual_obs(2024, status="no_data")
        err_2023 = EarthEngineError(type="EETimeout", message="Query timed out on 2023")
        obs_2023 = _make_sample_annual_obs(2023, status="error", error=err_2023)

        mock_compute.side_effect = [
            EarthEngineResult(status="success", data=obs_2025),
            EarthEngineResult(status="no_data", data=obs_2024),
            EarthEngineResult(status="error", data=obs_2023, error=err_2023),
        ]

        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
        )

        assert len(results) == 3
        # Year 2025 (Y-1)
        assert results[0].target_year == 2025
        assert results[0].status == "success"
        assert results[0].statistics is not None
        assert results[0].statistics.mean == 0.60

        # Year 2024 (Y-2)
        assert results[1].target_year == 2024
        assert results[1].status == "no_data"
        assert results[1].statistics is None
        assert results[1].selected_scenes_count == 0

        # Year 2023 (Y-3)
        assert results[2].target_year == 2023
        assert results[2].status == "error"
        assert results[2].statistics is None
        assert results[2].error == err_2023

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_all_years_no_data(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """All 3 years returning no_data results in 3 no_data AnnualHistoricalNdviObservation records."""
        mock_compute.side_effect = [
            EarthEngineResult(status="no_data", data=_make_sample_annual_obs(2025, status="no_data")),
            EarthEngineResult(status="no_data", data=_make_sample_annual_obs(2024, status="no_data")),
            EarthEngineResult(status="no_data", data=_make_sample_annual_obs(2023, status="no_data")),
        ]

        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
        )

        assert len(results) == 3
        assert all(r.status == "no_data" for r in results)
        assert all(r.statistics is None for r in results)
        assert all(r.selected_scenes_count == 0 for r in results)

    @patch("app.satellite.historical.compute_annual_historical_ndvi")
    def test_unexpected_compute_error_fallback(
        self,
        mock_compute,
        sample_region: ee.Geometry,
    ) -> None:
        """When compute_annual_historical_ndvi returns result with data=None on error, creates fallback error record."""
        err = EarthEngineError(type="FatalEEError", message="Remote service unavailable")
        mock_compute.side_effect = [
            EarthEngineResult(status="error", data=None, error=err),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2024)),
            EarthEngineResult(status="success", data=_make_sample_annual_obs(2023)),
        ]

        results = analyze_historical_years(
            reference_date="2026-08-16",
            region=sample_region,
        )

        assert len(results) == 3
        assert results[0].target_year == 2025
        assert results[0].status == "error"
        assert results[0].error == err
        assert results[1].status == "success"
        assert results[2].status == "success"
