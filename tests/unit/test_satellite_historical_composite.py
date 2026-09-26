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
"""Unit tests for Phase 2C historical NDVI compositing and annual statistics (Step 3B)."""

import math
from unittest.mock import MagicMock, patch

import ee
import pytest

from app.satellite.geometry import create_analysis_region
from app.satellite.historical import (
    DEFAULT_HISTORICAL_MAX_OBSERVATIONS,
    build_annual_historical_composite,
    build_annual_historical_ndvi_observation,
    build_historical_ndvi_composite,
    compute_annual_historical_ndvi,
    select_historical_observations,
)
from app.satellite.temporal import construct_historical_temporal_window
from app.satellite.types import (
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    EarthEngineResult,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
    NdviRegionalStatistics,
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
def sample_window_2025() -> HistoricalTemporalWindow:
    """Returns a valid 2025 seasonal temporal window."""
    return construct_historical_temporal_window(
        reference_date="2026-08-16",
        target_year=2025,
        window_half_days=15,
    )


def _make_mock_image_item(
    image_id: str,
    time_start_ms: int,
    cloud_pct: float = 5.0,
    usable_cov: float = 0.95,
    spacecraft: str = "Sentinel-2A",
    mgrs_tile: str = "43REQ",
) -> dict:
    """Helper to create a realistic Earth Engine getInfo() image dictionary."""
    return {
        "id": image_id,
        "properties": {
            "system:time_start": time_start_ms,
            "CLOUDY_PIXEL_PERCENTAGE": cloud_pct,
            "USABLE_COVERAGE": usable_cov,
            "SPACECRAFT_NAME": spacecraft,
            "MGRS_TILE": mgrs_tile,
            "PRODUCT_ID": f"{spacecraft}_{image_id.split('/')[-1]}",
        },
    }


def _sample_statistics(
    mean: float = 0.580,
    median: float = 0.575,
    min_val: float = 0.250,
    max_val: float = 0.820,
    count: int = 314,
) -> NdviRegionalStatistics:
    """Helper to create a sample NdviRegionalStatistics instance."""
    return NdviRegionalStatistics(
        mean=mean,
        median=median,
        min=min_val,
        max=max_val,
        valid_pixel_count=count,
    )


# ==============================================================================
# 1. INPUT VALIDATION TESTS
# ==============================================================================


class TestHistoricalCompositeInputValidation:
    """Tests synchronous input argument validation for Step 3B functions."""

    def test_alias_equivalence(self) -> None:
        """Verifies function aliases point to compute_annual_historical_ndvi."""
        assert build_annual_historical_composite is compute_annual_historical_ndvi
        assert build_annual_historical_ndvi_observation is compute_annual_historical_ndvi

    # --- build_historical_ndvi_composite validation ---

    @pytest.mark.parametrize("bad_images", [None, 123, "COPERNICUS/S2_SR_HARMONIZED", {"img": 1}])
    def test_composite_invalid_images_type_rejected(
        self,
        bad_images,
        sample_region: ee.Geometry,
    ) -> None:
        """Non-ImageCollection/non-list images argument is rejected with TypeError."""
        with pytest.raises(TypeError, match="must be an instance of ee.ImageCollection or list"):
            build_historical_ndvi_composite(bad_images, region=sample_region)

    def test_composite_empty_list_rejected(self, sample_region: ee.Geometry) -> None:
        """Empty list of images is rejected with ValueError."""
        with pytest.raises(ValueError, match="images list cannot be empty"):
            build_historical_ndvi_composite([], region=sample_region)

    def test_composite_list_with_invalid_item_rejected(self, sample_region: ee.Geometry) -> None:
        """List containing a non-ee.Image element is rejected with TypeError."""
        with pytest.raises(TypeError, match="must be an instance of ee.Image"):
            build_historical_ndvi_composite([ee.Image(0), "bad_item"], region=sample_region)

    @pytest.mark.parametrize("bad_region", ["not_a_geom", 123, {"type": "Point"}])
    def test_composite_invalid_region_rejected(self, bad_region) -> None:
        """Non-ee.Geometry region is rejected with TypeError."""
        with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
            build_historical_ndvi_composite([ee.Image(0)], region=bad_region)

    @pytest.mark.parametrize("bad_thresh", [-0.1, 1.1, math.nan, math.inf, "0.60"])
    def test_composite_invalid_clear_threshold_rejected(
        self,
        bad_thresh,
        sample_region: ee.Geometry,
    ) -> None:
        """Invalid clear_threshold is rejected with ValueError."""
        with pytest.raises(ValueError):
            build_historical_ndvi_composite([ee.Image(0)], region=sample_region, clear_threshold=bad_thresh)

    @pytest.mark.parametrize("bad_band", ["", "   "])
    def test_composite_invalid_quality_band_rejected(
        self,
        bad_band,
        sample_region: ee.Geometry,
    ) -> None:
        """Empty quality_band string is rejected with ValueError."""
        with pytest.raises(ValueError):
            build_historical_ndvi_composite([ee.Image(0)], region=sample_region, quality_band=bad_band)

    # --- compute_annual_historical_ndvi validation ---

    @pytest.mark.parametrize("bad_window", [None, "2025-08-16", 2025, {"window": 1}])
    def test_annual_invalid_temporal_window_rejected(
        self,
        bad_window,
        sample_region: ee.Geometry,
    ) -> None:
        """Invalid temporal_window is rejected with TypeError."""
        with pytest.raises(TypeError, match="must be an instance of HistoricalTemporalWindow"):
            compute_annual_historical_ndvi(bad_window, region=sample_region)

    @pytest.mark.parametrize("bad_region", [None, "region", [30.9, 75.7], 123])
    def test_annual_invalid_region_rejected(
        self,
        bad_region,
        sample_window_2025: HistoricalTemporalWindow,
    ) -> None:
        """Invalid region is rejected with TypeError."""
        with pytest.raises(TypeError, match="must be an instance of ee.Geometry"):
            compute_annual_historical_ndvi(sample_window_2025, region=bad_region)

    @pytest.mark.parametrize("bad_max_obs", [0, -1, 4, 10, 2.5, True, False, "3", None])
    def test_annual_invalid_max_observations_rejected(
        self,
        bad_max_obs,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """max_observations not in [1, 3] is rejected with ValueError."""
        with pytest.raises(ValueError):
            compute_annual_historical_ndvi(
                sample_window_2025,
                region=sample_region,
                max_observations=bad_max_obs,
            )

    @pytest.mark.parametrize("bad_scale", [0, -10.0, math.nan, math.inf, "10", None])
    def test_annual_invalid_scale_rejected(
        self,
        bad_scale,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """scale_m not strictly positive is rejected with ValueError."""
        with pytest.raises(ValueError):
            compute_annual_historical_ndvi(
                sample_window_2025,
                region=sample_region,
                scale_m=bad_scale,
            )


# ==============================================================================
# 2. BUILD HISTORICAL NDVI COMPOSITE TESTS
# ==============================================================================


class TestBuildHistoricalNdviComposite:
    """Tests for build_historical_ndvi_composite function."""

    def test_composite_from_single_image_list(self, sample_region: ee.Geometry) -> None:
        """Single image list produces an ee.Image proxy."""
        img = ee.Image.constant([1000, 2000, 0.9]).rename(["B4", "B8", "cs_cdf"])
        composite = build_historical_ndvi_composite([img], region=sample_region)
        assert isinstance(composite, ee.Image)

    def test_composite_from_multi_image_list(self, sample_region: ee.Geometry) -> None:
        """List of 3 images produces an ee.Image proxy with median reduction."""
        img1 = ee.Image.constant([1000, 2000, 0.9]).rename(["B4", "B8", "cs_cdf"])
        img2 = ee.Image.constant([1100, 2100, 0.85]).rename(["B4", "B8", "cs_cdf"])
        img3 = ee.Image.constant([900, 1900, 0.92]).rename(["B4", "B8", "cs_cdf"])
        composite = build_historical_ndvi_composite([img1, img2, img3], region=sample_region)
        assert isinstance(composite, ee.Image)

    def test_composite_from_image_collection(self, sample_region: ee.Geometry) -> None:
        """ee.ImageCollection produces an ee.Image proxy via .map() and .median()."""
        img1 = ee.Image.constant([1000, 2000, 0.9]).rename(["B4", "B8", "cs_cdf"])
        img2 = ee.Image.constant([1100, 2100, 0.85]).rename(["B4", "B8", "cs_cdf"])
        coll = ee.ImageCollection([img1, img2])
        composite = build_historical_ndvi_composite(coll, region=sample_region)
        assert isinstance(composite, ee.Image)

    @patch("app.satellite.historical.calculate_ndvi")
    @patch("app.satellite.historical.mask_observation_quality")
    def test_quality_mask_and_ndvi_applied_per_image(
        self,
        mock_mask,
        mock_ndvi,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies mask_observation_quality and calculate_ndvi are applied to each image."""
        img1 = ee.Image(1)
        img2 = ee.Image(2)
        mock_mask.side_effect = lambda img, **kw: img
        mock_ndvi.side_effect = lambda img, **kw: img

        build_historical_ndvi_composite(
            [img1, img2],
            region=sample_region,
            clear_threshold=0.65,
            quality_band="cs_cdf",
        )

        assert mock_mask.call_count == 2
        assert mock_ndvi.call_count == 2


# ==============================================================================
# 3. COMPUTE ANNUAL HISTORICAL NDVI ORCHESTRATION TESTS
# ==============================================================================


class TestComputeAnnualHistoricalNdviOrchestration:
    """Tests for compute_annual_historical_ndvi across different observation count scenarios."""

    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_three_usable_scenes_success(
        self,
        mock_select,
        mock_stats,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C01 / TC-C05: 3+ usable scenes -> 3 newest selected, pixel_median composite, status=success."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250826T054251",
                acquisition_date="2025-08-26T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=2.0,
                usable_coverage_percentage=98.0,
                selection_rank=1,
            ),
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250816T054251",
                acquisition_date="2025-08-16T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=8.0,
                usable_coverage_percentage=92.0,
                selection_rank=2,
            ),
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250806T054251",
                acquisition_date="2025-08-06T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=14.0,
                usable_coverage_percentage=85.0,
                selection_rank=3,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=6,  # 6 available, 3 selected
            data=summaries,
        )
        sample_stats = _sample_statistics(mean=0.620, median=0.615, min_val=0.300, max_val=0.850, count=314)
        mock_stats.return_value = EarthEngineResult(
            status="success",
            data=sample_stats,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "success"
        assert result.image_count == 6
        assert isinstance(result.data, AnnualHistoricalNdviObservation)

        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.target_year == 2025
        assert obs.temporal_window == sample_window_2025
        assert obs.available_usable_scenes_count == 6
        assert obs.selected_scenes_count == 3
        assert len(obs.selected_observations) == 3
        assert obs.composite_method == "pixel_median"
        assert obs.statistics == sample_stats
        assert obs.status == "success"
        assert obs.error is None

    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_two_usable_scenes_success(
        self,
        mock_select,
        mock_stats,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C02: 2 usable scenes -> both selected, pixel_median composite, status=success."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250820T054251",
                acquisition_date="2025-08-20T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=5.0,
                usable_coverage_percentage=94.0,
                selection_rank=1,
            ),
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250810T054251",
                acquisition_date="2025-08-10T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=10.0,
                usable_coverage_percentage=88.0,
                selection_rank=2,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=2,
            data=summaries,
        )
        sample_stats = _sample_statistics(mean=0.550, median=0.540, min_val=0.200, max_val=0.780, count=314)
        mock_stats.return_value = EarthEngineResult(
            status="success",
            data=sample_stats,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "success"
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.available_usable_scenes_count == 2
        assert obs.selected_scenes_count == 2
        assert len(obs.selected_observations) == 2
        assert obs.composite_method == "pixel_median"
        assert obs.statistics == sample_stats

    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_one_usable_scene_identity_composite_success(
        self,
        mock_select,
        mock_stats,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C03: 1 usable scene -> single scene selected, identity composite, status=success."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=4.0,
                usable_coverage_percentage=96.0,
                selection_rank=1,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=1,
            data=summaries,
        )
        sample_stats = _sample_statistics(mean=0.590, median=0.585, min_val=0.220, max_val=0.810, count=314)
        mock_stats.return_value = EarthEngineResult(
            status="success",
            data=sample_stats,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "success"
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.available_usable_scenes_count == 1
        assert obs.selected_scenes_count == 1
        assert len(obs.selected_observations) == 1
        assert obs.composite_method == "identity"
        assert obs.statistics == sample_stats

    @patch("app.satellite.historical.select_historical_observations")
    def test_zero_usable_scenes_returns_no_data(
        self,
        mock_select,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C04: 0 usable scenes -> status=no_data, selected_scenes_count=0, statistics=None."""
        mock_select.return_value = EarthEngineResult(
            status="no_data",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=0,
            data=[],
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "no_data"
        assert result.image_count == 0
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.target_year == 2025
        assert obs.available_usable_scenes_count == 0
        assert obs.selected_scenes_count == 0
        assert obs.selected_observations == []
        assert obs.statistics is None
        assert obs.status == "no_data"
        assert obs.composite_method == "none"

    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_total_masking_reduction_no_data(
        self,
        mock_select,
        mock_stats,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C11: Selected scenes exist but composite reduction returns 0 valid pixels -> status=no_data."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=15.0,
                usable_coverage_percentage=72.0,
                selection_rank=1,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=1,
            data=summaries,
        )
        # Reduction returns no_data (e.g. 0 unmasked pixels inside parcel buffer)
        mock_stats.return_value = EarthEngineResult(
            status="no_data",
            data=None,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "no_data"
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.available_usable_scenes_count == 1
        assert obs.selected_scenes_count == 0
        assert obs.selected_observations == []
        assert obs.statistics is None
        assert obs.status == "no_data"

    @patch("app.satellite.historical.select_historical_observations")
    def test_selection_error_propagates(
        self,
        mock_select,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C19: Selection error produces status=error with structured error details."""
        err = EarthEngineError(type="EEQuotaExceeded", message="Quota exceeded during selection")
        mock_select.return_value = EarthEngineResult(
            status="error",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            error=err,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "error"
        assert result.error.type == "EEQuotaExceeded"
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.status == "error"
        assert obs.statistics is None
        assert obs.error == err

    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_reduction_error_propagates(
        self,
        mock_select,
        mock_stats,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Earth Engine reduction error produces status=error and preserves selected observation metadata."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=5.0,
                usable_coverage_percentage=95.0,
                selection_rank=1,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=1,
            data=summaries,
        )
        err = EarthEngineError(type="EEComputationTimeout", message="Zonal reduction timed out")
        mock_stats.return_value = EarthEngineResult(
            status="error",
            error=err,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "error"
        assert result.error == err
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.status == "error"
        assert obs.selected_scenes_count == 1
        assert len(obs.selected_observations) == 1
        assert obs.statistics is None
        assert obs.error == err

    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_statistical_invariant_violation_handled(
        self,
        mock_select,
        mock_stats,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """TC-C16: Statistical envelope violation (min > mean or mean > max) produces StatisticalInvariantError."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=5.0,
                usable_coverage_percentage=95.0,
                selection_rank=1,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=1,
            data=summaries,
        )
        # Corrupt stats: mean (0.95) > max (0.80)
        corrupt_stats = _sample_statistics(mean=0.950, median=0.550, min_val=0.200, max_val=0.800)
        mock_stats.return_value = EarthEngineResult(
            status="success",
            data=corrupt_stats,
        )

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "error"
        assert result.error.type == "StatisticalInvariantError"
        assert "Statistical invariant violation" in result.error.message
        obs: AnnualHistoricalNdviObservation = result.data
        assert obs.status == "error"
        assert obs.statistics is None

    @patch("app.satellite.historical.select_historical_observations")
    def test_unexpected_exception_encapsulated(
        self,
        mock_select,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Unhandled Python exception is encapsulated into EarthEngineResult(status='error')."""
        mock_select.side_effect = RuntimeError("Unexpected connection reset")

        result = compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "error"
        assert result.error.type == "RuntimeError"
        assert "Unexpected connection reset" in result.error.message


# ==============================================================================
# 4. ARCHITECTURAL & SCIENTIFIC INVARIANT TESTS
# ==============================================================================


class TestScientificAndArchitecturalInvariants:
    """Tests verifying the architectural invariants specified in PHASE_02C."""

    @patch("app.satellite.historical.calculate_ndvi")
    @patch("app.satellite.historical.mask_observation_quality")
    @patch("app.satellite.historical.calculate_ndvi_statistics")
    @patch("app.satellite.historical.select_historical_observations")
    def test_per_scene_ndvi_before_median_compositing(
        self,
        mock_select,
        mock_stats,
        mock_mask,
        mock_ndvi,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies NDVI is computed per-scene before compositing (Approach E: pixel_median of NDVI)."""
        summaries = [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250820T054251",
                acquisition_date="2025-08-20T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=5.0,
                usable_coverage_percentage=94.0,
                selection_rank=1,
            ),
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250810T054251",
                acquisition_date="2025-08-10T05:50:41+00:00",
                target_year=2025,
                cloud_percentage=8.0,
                usable_coverage_percentage=90.0,
                selection_rank=2,
            ),
        ]
        mock_select.return_value = EarthEngineResult(
            status="success",
            dataset="COPERNICUS/S2_SR_HARMONIZED",
            image_count=2,
            data=summaries,
        )
        mock_mask.side_effect = lambda img, **kw: img
        mock_ndvi.side_effect = lambda img, **kw: img
        mock_stats.return_value = EarthEngineResult(
            status="success",
            data=_sample_statistics(),
        )

        compute_annual_historical_ndvi(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        # calculate_ndvi_statistics is called exactly ONCE on the final composite image
        assert mock_stats.call_count == 1

    def test_no_synthetic_confidence_or_crop_health_in_payload(
        self,
        sample_window_2025: HistoricalTemporalWindow,
    ) -> None:
        """Verifies no synthetic confidence, health scores, or agronomic classifications exist in model."""
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=2,
            selected_scenes_count=1,
            selected_observations=[
                HistoricalObservationSummary(
                    image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                    acquisition_date="2025-08-15",
                    target_year=2025,
                    cloud_percentage=5.0,
                    selection_rank=1,
                )
            ],
            statistics=_sample_statistics(),
            status="success",
            composite_method="identity",
        )
        dumped = obs.model_dump()
        for forbidden in ["confidence", "health_score", "crop_condition", "vigor_class", "disease_risk"]:
            assert forbidden not in dumped
