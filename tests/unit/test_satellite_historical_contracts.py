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
"""Unit tests for Phase 2C historical satellite observation and composite contracts."""

import json

from pydantic import ValidationError
import pytest

from app.satellite.temporal import construct_historical_temporal_window
from app.satellite.types import (
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    HistoricalObservationSummary,
    HistoricalTemporalWindow,
    NdviRegionalStatistics,
    SatelliteAnnualHistoricalNdviObservation,
    SatelliteHistoricalObservationSummary,
    Sentinel2ImageMetadata,
)


# ============================================================================
# CONTRACT 1: HistoricalObservationSummary Unit Tests
# ============================================================================


class TestHistoricalObservationSummaryContract:
    """Tests for HistoricalObservationSummary data contract (DEC-014 / DEC-016)."""

    def test_alias_equivalence(self) -> None:
        """Verifies SatelliteHistoricalObservationSummary is HistoricalObservationSummary."""
        assert SatelliteHistoricalObservationSummary is HistoricalObservationSummary

    def test_valid_construction_full(self) -> None:
        """Verifies construction with all available metadata and provenance fields."""
        summary = HistoricalObservationSummary(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251_20250815T055032_T43REQ",
            acquisition_date="2025-08-15T05:50:41.321000+00:00",
            target_year=2025,
            cloud_percentage=8.5,
            usable_coverage_percentage=94.2,
            spacecraft_name="Sentinel-2B",
            mgrs_tile="43REQ",
            product_id="S2B_MSIL2A_20250815T054251_N0500_R048_T43REQ_20250815T083000",
            system_time_start=1755237041321,
            selection_rank=1,
            clear_threshold=0.60,
            quality_band="cs_cdf",
        )
        assert summary.image_id == "COPERNICUS/S2_SR_HARMONIZED/20250815T054251_20250815T055032_T43REQ"
        assert summary.acquisition_date == "2025-08-15T05:50:41.321000+00:00"
        assert summary.target_year == 2025
        assert summary.cloud_percentage == 8.5
        assert summary.usable_coverage_percentage == 94.2
        assert summary.spacecraft_name == "Sentinel-2B"
        assert summary.mgrs_tile == "43REQ"
        assert summary.product_id == "S2B_MSIL2A_20250815T054251_N0500_R048_T43REQ_20250815T083000"
        assert summary.system_time_start == 1755237041321
        assert summary.selection_rank == 1
        assert summary.clear_threshold == 0.60
        assert summary.quality_band == "cs_cdf"

    def test_valid_construction_minimal(self) -> None:
        """Verifies construction with only required fields."""
        summary = HistoricalObservationSummary(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20240810T054251_20240810T055032_T43REQ",
            acquisition_date="2024-08-10",
            target_year=2024,
            cloud_percentage=12.0,
        )
        assert summary.image_id == "COPERNICUS/S2_SR_HARMONIZED/20240810T054251_20240810T055032_T43REQ"
        assert summary.acquisition_date == "2024-08-10"
        assert summary.target_year == 2024
        assert summary.cloud_percentage == 12.0
        assert summary.usable_coverage_percentage is None
        assert summary.spacecraft_name is None
        assert summary.selection_rank is None

    def test_from_sentinel2_metadata_factory(self) -> None:
        """Verifies the from_sentinel2_metadata classmethod factory."""
        meta = Sentinel2ImageMetadata(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20230820T054251_20230820T055032_T43REQ",
            acquisition_date="2023-08-20T05:50:41.321000+00:00",
            cloud_percentage=5.0,
            spacecraft_name="Sentinel-2A",
            mgrs_tile="43REQ",
            product_id="S2A_TEST",
            system_time_start=1692510641321,
            usable_coverage_percentage=98.0,
            clear_threshold=0.60,
            quality_band="cs_cdf",
        )
        summary = HistoricalObservationSummary.from_sentinel2_metadata(
            metadata=meta,
            target_year=2023,
            selection_rank=2,
        )
        assert summary.image_id == meta.image_id
        assert summary.acquisition_date == meta.acquisition_date
        assert summary.target_year == 2023
        assert summary.cloud_percentage == meta.cloud_percentage
        assert summary.usable_coverage_percentage == meta.usable_coverage_percentage
        assert summary.spacecraft_name == meta.spacecraft_name
        assert summary.mgrs_tile == meta.mgrs_tile
        assert summary.product_id == meta.product_id
        assert summary.system_time_start == meta.system_time_start
        assert summary.selection_rank == 2
        assert summary.clear_threshold == meta.clear_threshold
        assert summary.quality_band == meta.quality_band

    @pytest.mark.parametrize("invalid_year", [0, -1, -2025, 10000])
    def test_invalid_target_year_rejected(self, invalid_year: int) -> None:
        """Verifies non-positive or out-of-range target years are rejected."""
        with pytest.raises(ValidationError):
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15",
                target_year=invalid_year,
                cloud_percentage=10.0,
            )

    @pytest.mark.parametrize("invalid_cloud", [-0.1, 100.1, 150.0])
    def test_invalid_cloud_percentage_rejected(self, invalid_cloud: float) -> None:
        """Verifies cloud percentage out of [0, 100] is rejected."""
        with pytest.raises(ValidationError):
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15",
                target_year=2025,
                cloud_percentage=invalid_cloud,
            )

    @pytest.mark.parametrize("invalid_coverage", [-0.1, 100.1, 200.0])
    def test_invalid_usable_coverage_percentage_rejected(self, invalid_coverage: float) -> None:
        """Verifies usable coverage percentage out of [0, 100] is rejected."""
        with pytest.raises(ValidationError):
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15",
                target_year=2025,
                cloud_percentage=10.0,
                usable_coverage_percentage=invalid_coverage,
            )

    @pytest.mark.parametrize("invalid_rank", [0, 4, -1])
    def test_invalid_selection_rank_rejected(self, invalid_rank: int) -> None:
        """Verifies selection rank outside [1, 3] is rejected."""
        with pytest.raises(ValidationError):
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
                acquisition_date="2025-08-15",
                target_year=2025,
                cloud_percentage=10.0,
                selection_rank=invalid_rank,
            )

    def test_serialization(self) -> None:
        """Verifies dictionary and JSON serialization."""
        summary = HistoricalObservationSummary(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20250815T054251",
            acquisition_date="2025-08-15",
            target_year=2025,
            cloud_percentage=10.0,
            usable_coverage_percentage=92.0,
            selection_rank=1,
        )
        dumped = summary.model_dump()
        assert dumped["target_year"] == 2025
        assert dumped["selection_rank"] == 1

        json_str = summary.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["image_id"] == "COPERNICUS/S2_SR_HARMONIZED/20250815T054251"
        assert parsed["usable_coverage_percentage"] == 92.0


# ============================================================================
# CONTRACT 2: AnnualHistoricalNdviObservation Unit Tests
# ============================================================================


class TestAnnualHistoricalNdviObservationContract:
    """Tests for AnnualHistoricalNdviObservation data contract (DEC-014 / DEC-016)."""

    @pytest.fixture
    def sample_window_2025(self) -> HistoricalTemporalWindow:
        """Returns a valid 2025 seasonal temporal window for Aug 16 anchor."""
        return construct_historical_temporal_window(
            reference_date="2026-08-16",
            target_year=2025,
            window_half_days=15,
        )

    @pytest.fixture
    def sample_statistics(self) -> NdviRegionalStatistics:
        """Returns sample valid NdviRegionalStatistics."""
        return NdviRegionalStatistics(
            mean=0.58,
            median=0.57,
            min=0.25,
            max=0.82,
            valid_pixel_count=314,
        )

    @pytest.fixture
    def sample_scenes_2025(self) -> list[HistoricalObservationSummary]:
        """Returns 3 valid HistoricalObservationSummary items for 2025."""
        return [
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250826T054251",
                acquisition_date="2025-08-26",
                target_year=2025,
                cloud_percentage=2.0,
                usable_coverage_percentage=98.0,
                selection_rank=1,
            ),
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250816T054251",
                acquisition_date="2025-08-16",
                target_year=2025,
                cloud_percentage=8.0,
                usable_coverage_percentage=92.0,
                selection_rank=2,
            ),
            HistoricalObservationSummary(
                image_id="COPERNICUS/S2_SR_HARMONIZED/20250806T054251",
                acquisition_date="2025-08-06",
                target_year=2025,
                cloud_percentage=14.0,
                usable_coverage_percentage=85.0,
                selection_rank=3,
            ),
        ]

    def test_alias_equivalence(self) -> None:
        """Verifies SatelliteAnnualHistoricalNdviObservation is AnnualHistoricalNdviObservation."""
        assert SatelliteAnnualHistoricalNdviObservation is AnnualHistoricalNdviObservation

    def test_valid_success_observation_3_scenes(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """Verifies a full successful observation with 3 selected scenes."""
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=6,
            selected_scenes_count=3,
            selected_observations=sample_scenes_2025,
            statistics=sample_statistics,
            status="success",
            composite_method="pixel_median",
            pipeline_version="1.0.0",
        )
        assert obs.target_year == 2025
        assert obs.temporal_window == sample_window_2025
        assert obs.available_usable_scenes_count == 6
        assert obs.selected_scenes_count == 3
        assert len(obs.selected_observations) == 3
        assert obs.selected_scenes == sample_scenes_2025  # property alias
        assert obs.statistics == sample_statistics
        assert obs.status == "success"
        assert obs.composite_method == "pixel_median"
        assert obs.pipeline_version == "1.0.0"
        assert obs.error is None

    def test_valid_success_observation_2_scenes(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """Verifies a successful observation with 2 selected scenes."""
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=2,
            selected_scenes_count=2,
            selected_observations=sample_scenes_2025[:2],
            statistics=sample_statistics,
            status="success",
            composite_method="pixel_median",
        )
        assert obs.available_usable_scenes_count == 2
        assert obs.selected_scenes_count == 2
        assert len(obs.selected_observations) == 2

    def test_valid_success_observation_1_scene(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """Verifies a valid observation with 1 selected scene (identity composite)."""
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=1,
            selected_scenes_count=1,
            selected_observations=sample_scenes_2025[:1],
            statistics=sample_statistics,
            status="success",
            composite_method="identity",
        )
        assert obs.available_usable_scenes_count == 1
        assert obs.selected_scenes_count == 1
        assert obs.composite_method == "identity"

    def test_valid_no_data_observation(
        self,
        sample_window_2025: HistoricalTemporalWindow,
    ) -> None:
        """Verifies a no_data observation when 0 usable scenes exist."""
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=0,
            selected_scenes_count=0,
            selected_observations=[],
            statistics=None,
            status="no_data",
            composite_method="none",
        )
        assert obs.target_year == 2025
        assert obs.available_usable_scenes_count == 0
        assert obs.selected_scenes_count == 0
        assert obs.selected_observations == []
        assert obs.statistics is None
        assert obs.status == "no_data"

    def test_valid_error_observation(
        self,
        sample_window_2025: HistoricalTemporalWindow,
    ) -> None:
        """Verifies an error observation with structured error details."""
        err = EarthEngineError(
            type="EEComputationTimeout",
            message="Historical collection query timed out",
        )
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=0,
            selected_scenes_count=0,
            selected_observations=[],
            statistics=None,
            status="error",
            error=err,
        )
        assert obs.status == "error"
        assert obs.error == err
        assert obs.statistics is None

    # ========================================================================
    # Validation Invariant Checks
    # ========================================================================

    def test_available_less_than_selected_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """available_usable_scenes_count cannot be less than selected_scenes_count."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=2,  # < 3
                selected_scenes_count=3,
                selected_observations=sample_scenes_2025,
                statistics=sample_statistics,
                status="success",
            )
        assert "cannot be less than selected_scenes_count" in str(exc_info.value)

    def test_selected_scenes_count_max_bound_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """selected_scenes_count cannot exceed 3."""
        extra_scene = HistoricalObservationSummary(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20250801T054251",
            acquisition_date="2025-08-01",
            target_year=2025,
            cloud_percentage=5.0,
        )
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=5,
                selected_scenes_count=4,  # > 3
                selected_observations=sample_scenes_2025 + [extra_scene],
                statistics=sample_statistics,
                status="success",
            )
        assert "selected_scenes_count" in str(exc_info.value)

    def test_selected_scenes_count_negative_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
    ) -> None:
        """selected_scenes_count cannot be negative."""
        with pytest.raises(ValidationError):
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=0,
                selected_scenes_count=-1,
                selected_observations=[],
                status="no_data",
            )

    def test_mismatched_selected_observations_length_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """selected_observations list length must exactly match selected_scenes_count."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=3,
                selected_scenes_count=3,
                selected_observations=sample_scenes_2025[:2],  # only 2 items
                statistics=sample_statistics,
                status="success",
            )
        assert "must equal selected_scenes_count" in str(exc_info.value)

    def test_mismatched_temporal_window_target_year_rejected(
        self,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """temporal_window.target_year must match observation target_year."""
        window_2024 = construct_historical_temporal_window(
            reference_date="2026-08-16",
            target_year=2024,
            window_half_days=15,
        )
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,  # Mismatch with window 2024
                temporal_window=window_2024,
                available_usable_scenes_count=3,
                selected_scenes_count=3,
                selected_observations=sample_scenes_2025,
                statistics=sample_statistics,
                status="success",
            )
        assert "must match observation target_year" in str(exc_info.value)

    def test_mismatched_selected_observation_target_year_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """Every item in selected_observations must have target_year matching observation."""
        foreign_scene = HistoricalObservationSummary(
            image_id="COPERNICUS/S2_SR_HARMONIZED/20240816T054251",
            acquisition_date="2024-08-16",
            target_year=2024,  # Mismatch: 2024 scene in 2025 observation
            cloud_percentage=5.0,
        )
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=3,
                selected_scenes_count=3,
                selected_observations=[sample_scenes_2025[0], sample_scenes_2025[1], foreign_scene],
                statistics=sample_statistics,
                status="success",
            )
        assert "does not match observation target_year" in str(exc_info.value)

    def test_success_with_zero_scenes_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """status='success' requires at least 1 selected observation."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=0,
                selected_scenes_count=0,
                selected_observations=[],
                statistics=sample_statistics,
                status="success",
            )
        assert "status='success' requires at least 1 selected observation" in str(exc_info.value)

    def test_success_with_missing_statistics_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
    ) -> None:
        """status='success' requires valid statistics."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=1,
                selected_scenes_count=1,
                selected_observations=sample_scenes_2025[:1],
                statistics=None,
                status="success",
            )
        assert "requires valid composite NdviRegionalStatistics" in str(exc_info.value)

    def test_no_data_with_selected_scenes_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
    ) -> None:
        """status='no_data' cannot contain selected observations."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=1,
                selected_scenes_count=1,
                selected_observations=sample_scenes_2025[:1],
                statistics=None,
                status="no_data",
            )
        assert "status='no_data' cannot contain selected observations" in str(exc_info.value)

    def test_no_data_with_statistics_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """status='no_data' cannot contain regional statistics."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=0,
                selected_scenes_count=0,
                selected_observations=[],
                statistics=sample_statistics,
                status="no_data",
            )
        assert "status='no_data' cannot contain regional statistics" in str(exc_info.value)

    def test_error_with_statistics_rejected(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """status='error' cannot contain regional statistics."""
        with pytest.raises(ValidationError) as exc_info:
            AnnualHistoricalNdviObservation(
                target_year=2025,
                temporal_window=sample_window_2025,
                available_usable_scenes_count=0,
                selected_scenes_count=0,
                selected_observations=[],
                statistics=sample_statistics,
                status="error",
                error=EarthEngineError(type="TestError", message="Test error"),
            )
        assert "status='error' cannot contain regional statistics" in str(exc_info.value)

    def test_serialization_roundtrip(
        self,
        sample_window_2025: HistoricalTemporalWindow,
        sample_scenes_2025: list[HistoricalObservationSummary],
        sample_statistics: NdviRegionalStatistics,
    ) -> None:
        """Verifies serialization and deserialization roundtrip."""
        obs = AnnualHistoricalNdviObservation(
            target_year=2025,
            temporal_window=sample_window_2025,
            available_usable_scenes_count=5,
            selected_scenes_count=3,
            selected_observations=sample_scenes_2025,
            statistics=sample_statistics,
            status="success",
            composite_method="pixel_median",
            pipeline_version="1.0.0",
        )
        dumped_json = obs.model_dump_json()
        parsed = json.loads(dumped_json)

        assert parsed["target_year"] == 2025
        assert parsed["available_usable_scenes_count"] == 5
        assert parsed["selected_scenes_count"] == 3
        assert len(parsed["selected_observations"]) == 3
        assert parsed["statistics"]["mean"] == 0.58

        # Re-parse into model
        reconstructed = AnnualHistoricalNdviObservation.model_validate_json(dumped_json)
        assert reconstructed == obs
