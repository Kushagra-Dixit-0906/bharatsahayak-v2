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
"""Unit tests for Phase 2C historical observation discovery and selection (Step 3A)."""

from unittest.mock import MagicMock, patch

import ee
import pytest

from app.satellite.geometry import create_analysis_region
from app.satellite.historical import (
    DEFAULT_HISTORICAL_MAX_OBSERVATIONS,
    select_historical_observations,
)
from app.satellite.temporal import construct_historical_temporal_window
from app.satellite.types import (
    EarthEngineResult,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
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
    """Helper to create a realistic Earth Engine getInfo() image representation."""
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


# ==============================================================================
# 1. INPUT VALIDATION TESTS
# ==============================================================================


class TestHistoricalSelectionInputValidation:
    """Tests synchronous input argument validation."""

    def test_default_constants(self) -> None:
        """Verifies default architectural constants."""
        assert DEFAULT_HISTORICAL_MAX_OBSERVATIONS == 3

    @pytest.mark.parametrize(
        "bad_window",
        [
            None,
            "2025-08-16",
            {"target_year": 2025},
            2025,
        ],
    )
    def test_invalid_temporal_window_rejected(
        self,
        bad_window,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies non-HistoricalTemporalWindow raises TypeError."""
        with pytest.raises(TypeError, match="temporal_window must be an instance of HistoricalTemporalWindow"):
            select_historical_observations(
                temporal_window=bad_window,  # type: ignore[arg-type]
                region=sample_region,
            )

    @pytest.mark.parametrize(
        "bad_region",
        [
            None,
            "not_a_geometry",
            [75.7196, 30.9157],
            12345,
        ],
    )
    def test_invalid_region_rejected(
        self,
        bad_region,
        sample_window_2025: HistoricalTemporalWindow,
    ) -> None:
        """Verifies non-ee.Geometry raises TypeError."""
        with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
            select_historical_observations(
                temporal_window=sample_window_2025,
                region=bad_region,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        "bad_max_obs",
        [
            0,
            -1,
            -5,
            4,
            5,
            10,
            "3",
            None,
            True,
            False,
        ],
    )
    def test_invalid_max_observations_rejected(
        self,
        bad_max_obs,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies max_observations outside [1, 3] or non-int raises ValueError."""
        with pytest.raises(ValueError):
            select_historical_observations(
                temporal_window=sample_window_2025,
                region=sample_region,
                max_observations=bad_max_obs,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize("bad_cloud", [-0.1, 100.1, float("nan")])
    def test_invalid_cloud_threshold_rejected(
        self,
        bad_cloud: float,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies invalid cloud thresholds raise ValueError."""
        with pytest.raises(ValueError):
            select_historical_observations(
                temporal_window=sample_window_2025,
                region=sample_region,
                max_cloud_percentage=bad_cloud,
            )


# ==============================================================================
# 2. CORE OBSERVATION SELECTION SEMANTICS & BOUNDED SAMPLING
# ==============================================================================


class TestHistoricalSelectionSemantics:
    """Tests selection behavior for N in {0, 1, 2, 3, >3} with mock materialization."""

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_zero_usable_scenes_returns_no_data(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """N=0: Returns status='no_data', image_count=0, data=[]."""
        mock_get_info.return_value = {
            "available_count": 0,
            "selected_images": [],
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert isinstance(result, EarthEngineResult)
        assert result.status == "no_data"
        assert result.image_count == 0
        assert result.data == []
        assert result.error is None

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_one_usable_scene_selected(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """N=1: Selects the single usable observation with selection_rank=1."""
        item = _make_mock_image_item(
            "COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
            time_start_ms=1755237041000,
            cloud_pct=4.2,
            usable_cov=0.92,
        )
        mock_get_info.return_value = {
            "available_count": 1,
            "selected_images": [item],
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "success"
        assert result.image_count == 1  # available count
        assert len(result.data) == 1  # selected count

        summary = result.data[0]
        assert isinstance(summary, HistoricalObservationSummary)
        assert summary.image_id == "COPERNICUS/S2_SR_HARMONIZED/20250815T054251"
        assert summary.target_year == 2025
        assert summary.selection_rank == 1
        assert summary.cloud_percentage == 4.2
        assert summary.usable_coverage_percentage == 92.0

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_two_usable_scenes_both_selected(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """N=2: Selects both usable observations in newest-first order (ranks 1, 2)."""
        item1 = _make_mock_image_item("S2/20250820", 1755669041000, cloud_pct=2.0)
        item2 = _make_mock_image_item("S2/20250810", 1754805041000, cloud_pct=8.0)

        # Returned out of order to verify Python-side sorting
        mock_get_info.return_value = {
            "available_count": 2,
            "selected_images": [item2, item1],
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "success"
        assert result.image_count == 2
        assert len(result.data) == 2

        # Verify newest is rank 1
        assert result.data[0].image_id == "S2/20250820"
        assert result.data[0].selection_rank == 1
        # Verify older is rank 2
        assert result.data[1].image_id == "S2/20250810"
        assert result.data[1].selection_rank == 2

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_three_usable_scenes_all_selected(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """N=3: Selects all 3 scenes in newest-first order (ranks 1, 2, 3)."""
        item1 = _make_mock_image_item("S2/20250825", 1756101041000)
        item2 = _make_mock_image_item("S2/20250815", 1755237041000)
        item3 = _make_mock_image_item("S2/20250805", 1754373041000)

        mock_get_info.return_value = {
            "available_count": 3,
            "selected_images": [item1, item2, item3],
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "success"
        assert result.image_count == 3
        assert len(result.data) == 3
        assert [s.selection_rank for s in result.data] == [1, 2, 3]
        assert [s.image_id for s in result.data] == ["S2/20250825", "S2/20250815", "S2/20250805"]

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_more_than_three_usable_scenes_bounded_to_three_newest(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """N=7: Selects only the 3 newest usable observations; available_count=7, selected_count=3."""
        # 5 candidate items
        items = [
            _make_mock_image_item(f"S2/202508{d:02d}", 1754000000000 + d * 86400000)
            for d in [28, 23, 18, 13, 8]
        ]
        mock_get_info.return_value = {
            "available_count": 7,  # 7 scenes passed quality filter in total
            "selected_images": items[:3],  # EE limit(3) returned 3
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
            max_observations=3,
        )

        assert result.status == "success"
        assert result.image_count == 7  # available count preserved
        assert len(result.data) == 3  # strictly bounded to 3
        assert result.data[0].image_id == "S2/20250828"
        assert result.data[0].selection_rank == 1
        assert result.data[1].image_id == "S2/20250823"
        assert result.data[1].selection_rank == 2
        assert result.data[2].image_id == "S2/20250818"
        assert result.data[2].selection_rank == 3

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_custom_max_observations_bound(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Configuring max_observations=2 selects at most 2 items even when 5 are available."""
        items = [
            _make_mock_image_item("S2/20250825", 1756101041000),
            _make_mock_image_item("S2/20250815", 1755237041000),
        ]
        mock_get_info.return_value = {
            "available_count": 5,
            "selected_images": items,
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
            max_observations=2,
        )

        assert result.status == "success"
        assert result.image_count == 5
        assert len(result.data) == 2
        assert [s.selection_rank for s in result.data] == [1, 2]

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_year_boundary_crossing_window_ownership(
        self,
        mock_get_info: MagicMock,
        sample_region: ee.Geometry,
    ) -> None:
        """Cross-calendar-year window (e.g. Dec 25 anchor) preserves target_year across all scenes."""
        window_cross = construct_historical_temporal_window(
            reference_date="2026-12-25",
            target_year=2025,
            window_half_days=15,
        )
        # One scene in Jan 2026, one scene in Dec 2025
        item_jan = _make_mock_image_item("S2/20260105", 1767571200000)
        item_dec = _make_mock_image_item("S2/20251220", 1766188800000)

        mock_get_info.return_value = {
            "available_count": 2,
            "selected_images": [item_jan, item_dec],
        }

        result = select_historical_observations(
            temporal_window=window_cross,
            region=sample_region,
        )

        assert result.status == "success"
        assert len(result.data) == 2
        # All selected observations belong to target_year 2025 (DEC-015)
        for s in result.data:
            assert s.target_year == 2025

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_no_synthetic_confidence_or_agronomic_fields(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies zero synthetic confidence, crop score, or ranking formulas in output models."""
        item = _make_mock_image_item("S2/20250815", 1755237041000)
        mock_get_info.return_value = {
            "available_count": 1,
            "selected_images": [item],
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        summary = result.data[0]
        dumped = summary.model_dump()
        assert "confidence" not in dumped
        assert "score" not in dumped
        assert "crop_health" not in dumped
        assert "vigor" not in dumped
        assert "anomaly" not in dumped

    @patch("app.satellite.historical.get_sentinel2_collection")
    def test_earth_engine_exception_encapsulation(
        self,
        mock_get_collection: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Verifies that runtime/EE exceptions return EarthEngineResult(status='error')."""
        mock_get_collection.side_effect = ee.EEException("Computation quota exceeded")

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
        )

        assert result.status == "error"
        assert result.error is not None
        assert result.error.type == "EEException"
        assert "Computation quota exceeded" in result.error.message
        assert result.image_count is None
        assert result.data is None

    @patch("app.satellite.historical.ee.Dictionary.getInfo")
    def test_historical_mixed_quality_skips_unusable_selects_up_to_three_usable(
        self,
        mock_get_info: MagicMock,
        sample_window_2025: HistoricalTemporalWindow,
        sample_region: ee.Geometry,
    ) -> None:
        """Requirement B: Mixed quality in historical window: newer unusable scenes are excluded, older usable scenes fill the up-to-3 selection in newest-first order."""
        # 4 usable candidate scenes in collection (after server-side exclusion of cloudy scenes)
        items = [
            _make_mock_image_item("S2/20250824", 1756014600000, cloud_pct=6.0, usable_cov=0.91),
            _make_mock_image_item("S2/20250814", 1755150600000, cloud_pct=8.5, usable_cov=0.88),
            _make_mock_image_item("S2/20250804", 1754286600000, cloud_pct=11.0, usable_cov=0.85),
        ]
        mock_get_info.return_value = {
            "available_count": 4,  # 4 usable scenes available in total
            "selected_images": items,  # Top 3 newest returned by EE limit(3)
        }

        result = select_historical_observations(
            temporal_window=sample_window_2025,
            region=sample_region,
            max_observations=3,
        )

        assert result.status == "success"
        assert result.image_count == 4  # Total available usable count
        assert len(result.data) == 3  # Strictly up to 3 selected
        assert [s.selection_rank for s in result.data] == [1, 2, 3]
        assert [s.image_id for s in result.data] == ["S2/20250824", "S2/20250814", "S2/20250804"]
        assert result.data[0].usable_coverage_percentage == 91.0
        assert result.data[1].usable_coverage_percentage == 88.0
        assert result.data[2].usable_coverage_percentage == 85.0
