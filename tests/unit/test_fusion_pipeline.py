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
"""Unit tests for Phase 4 Multi-Source Evidence Fusion pipeline orchestrator (DEC-022)."""

from datetime import date
from unittest.mock import MagicMock, patch
import pytest

from app.fusion.pipeline import _resolve_reference_date, fetch_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.types import EarthEngineResult
from tests.fixtures.fusion_fixtures import build_evidence_from_fixture


class TestFusionPipelineValidation:
    """Tests synchronous argument and date validation in fetch_agricultural_environmental_evidence."""

    def test_invalid_latitude_types(self):
        with pytest.raises(TypeError, match="Latitude must be a valid number"):
            fetch_agricultural_environmental_evidence("30.9", 75.8573)

        with pytest.raises(TypeError, match="Latitude must be a valid number"):
            fetch_agricultural_environmental_evidence(True, 75.8573)

    def test_invalid_latitude_bounds(self):
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            fetch_agricultural_environmental_evidence(91.0, 75.8573)

        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            fetch_agricultural_environmental_evidence(-95.0, 75.8573)

    def test_invalid_longitude_types(self):
        with pytest.raises(TypeError, match="Longitude must be a valid number"):
            fetch_agricultural_environmental_evidence(30.9, None)

    def test_invalid_longitude_bounds(self):
        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            fetch_agricultural_environmental_evidence(30.9, 181.0)

    def test_invalid_radius_bounds(self):
        with pytest.raises(ValueError, match="Radius must be strictly positive"):
            fetch_agricultural_environmental_evidence(30.9, 75.8573, radius_m=0.0)

        with pytest.raises(ValueError, match="Radius must be strictly positive"):
            fetch_agricultural_environmental_evidence(30.9, 75.8573, radius_m=-50.0)

    def test_date_resolution_formats(self):
        assert _resolve_reference_date("2026-09-20") == date(2026, 9, 20)
        assert _resolve_reference_date("2026-09-20T12:00:00Z") == date(2026, 9, 20)
        assert _resolve_reference_date(date(2026, 9, 20)) == date(2026, 9, 20)

    def test_date_resolution_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid reference_date format"):
            _resolve_reference_date("not-a-date")

    def test_date_resolution_invalid_type(self):
        with pytest.raises(TypeError, match="Unsupported reference_date type"):
            _resolve_reference_date(12345)  # type: ignore


class TestFusionPipelineExecution:
    """Tests execution flow, Phase 1 -> Phase 2 reuse, and error isolation."""

    @patch("app.fusion.pipeline.analyze_dynamic_world_land_cover")
    @patch("app.fusion.pipeline.analyze_chirps_rainfall")
    @patch("app.fusion.pipeline.analyze_era5_land")
    @patch("app.fusion.pipeline.analyze_historical_years")
    @patch("app.fusion.pipeline.create_analysis_region")
    @patch("app.fusion.pipeline.analyze_regional_ndvi")
    def test_orchestration_successful_reuse_flow(
        self,
        mock_ndvi,
        mock_region,
        mock_hist_years,
        mock_era5,
        mock_chirps,
        mock_dw,
    ):
        """Verifies Phase 1 -> Phase 2 reuse and successful assembly across all pipelines."""
        region_meta, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")

        # Mock Phase 1 returning success with RegionalNdviAnalysis
        mock_ndvi.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=1,
            data=veg.current,
        )
        mock_region.return_value = MagicMock()
        mock_hist_years.return_value = veg.historical_observations
        mock_era5.return_value = rean
        mock_chirps.return_value = rain
        mock_dw.return_value = lc

        evidence = fetch_agricultural_environmental_evidence(
            latitude=30.9010,
            longitude=75.8573,
            reference_date="2026-09-20",
            radius_m=100.0,
        )

        assert isinstance(evidence, AgriculturalEnvironmentalEvidence)
        assert evidence.status == "success"
        assert evidence.sources_available_count == 4
        assert evidence.sources_fully_available_count == 4
        assert evidence.is_fully_available is True

        # Verify Phase 1 output was passed to Phase 2
        mock_ndvi.assert_called_once()
        mock_hist_years.assert_called_once_with(
            region=mock_region.return_value,
            reference_date=veg.current,
            history_years=3,
            window_half_days=15,
        )
        mock_era5.assert_called_once()
        mock_chirps.assert_called_once()
        mock_dw.assert_called_once()

    @patch("app.fusion.pipeline.analyze_dynamic_world_land_cover")
    @patch("app.fusion.pipeline.analyze_chirps_rainfall")
    @patch("app.fusion.pipeline.analyze_era5_land")
    @patch("app.fusion.pipeline.analyze_historical_years")
    @patch("app.fusion.pipeline.create_analysis_region")
    @patch("app.fusion.pipeline.analyze_regional_ndvi")
    def test_orchestration_phase1_no_data_runs_historical_queries(
        self,
        mock_ndvi,
        mock_region,
        mock_hist_years,
        mock_era5,
        mock_chirps,
        mock_dw,
    ):
        """Verifies that when Phase 1 returns no_data, Phase 2 historical queries still execute with resolved reference date."""
        _, veg, rean, rain, lc = build_evidence_from_fixture("complete_success.json")

        mock_ndvi.return_value = EarthEngineResult(
            status="no_data",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=0,
            data=None,
        )
        mock_region.return_value = MagicMock()
        mock_hist_years.return_value = veg.historical_observations
        mock_era5.return_value = rean
        mock_chirps.return_value = rain
        mock_dw.return_value = lc

        evidence = fetch_agricultural_environmental_evidence(
            latitude=30.9010,
            longitude=75.8573,
            reference_date="2026-09-20",
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.vegetation.status == "no_data"
        assert evidence.vegetation.current is None
        assert evidence.vegetation.baseline is not None
        assert evidence.vegetation.baseline.annual_count == 3
        assert evidence.vegetation.anomaly is None
        # Historical queries MUST be called with resolved reference date
        mock_hist_years.assert_called_once_with(
            region=mock_region.return_value,
            reference_date=date(2026, 9, 20),
            history_years=3,
            window_half_days=15,
        )

    @patch("app.fusion.pipeline.analyze_dynamic_world_land_cover")
    @patch("app.fusion.pipeline.analyze_chirps_rainfall")
    @patch("app.fusion.pipeline.analyze_era5_land")
    @patch("app.fusion.pipeline.analyze_historical_years")
    @patch("app.fusion.pipeline.create_analysis_region")
    @patch("app.fusion.pipeline.analyze_regional_ndvi")
    def test_orchestration_subsystem_exception_isolated(
        self,
        mock_ndvi,
        mock_region,
        mock_hist_years,
        mock_era5,
        mock_chirps,
        mock_dw,
    ):
        """Verifies that an unhandled exception in one sub-pipeline is isolated into a structured error."""
        _, veg, _, rain, lc = build_evidence_from_fixture("complete_success.json")

        mock_ndvi.return_value = EarthEngineResult(
            status="success",
            data=veg.current,
        )
        mock_region.return_value = MagicMock()
        mock_hist_years.return_value = veg.historical_observations
        # ERA5 raises an unhandled runtime error
        mock_era5.side_effect = RuntimeError("Remote network dropped connection")
        mock_chirps.return_value = rain
        mock_dw.return_value = lc

        evidence = fetch_agricultural_environmental_evidence(
            latitude=30.9010,
            longitude=75.8573,
            reference_date="2026-09-20",
        )

        assert evidence.status == "partial"
        assert evidence.sources_available_count == 3
        assert evidence.reanalysis.status == "error"
        assert evidence.reanalysis.error is not None
        assert evidence.reanalysis.error.type == "RuntimeError"
        assert "Remote network dropped connection" in evidence.reanalysis.error.message
        assert evidence.rainfall.status == "success"
        assert evidence.land_cover.status == "success"
