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
"""Unit tests for Phase 3B CHIRPS rainfall domain contracts and fixtures (DEC-020)."""

from datetime import date
import json

from pydantic import ValidationError
import pytest

from app.environment.chirps_types import (
    CHIRPSRainfallAnalysis,
    DailyRainfallObservation,
    RainfallWindowStatistics,
)
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError
from tests.fixtures.chirps_fixtures import (
    load_chirps_lagged_partial_raw,
    load_chirps_negative_artifact_raw,
    load_chirps_no_data_empty_raw,
    load_punjab_monsoon_wet_raw,
    load_punjab_winter_dry_raw,
)


@pytest.fixture
def sample_region() -> AnalysisRegionMetadata:
    """Deterministic region metadata for testing."""
    return AnalysisRegionMetadata(
        latitude=30.9157,
        longitude=75.7196,
        radius_m=100.0,
        geometry_type="PointBuffer",
        scale_m=10.0,
    )


# ============================================================================
# CONTRACT 1: DailyRainfallObservation Tests
# ============================================================================


class TestDailyRainfallObservationContract:
    """Tests for DailyRainfallObservation domain model."""

    def test_valid_observation_with_precipitation(self) -> None:
        """Verifies valid observation with positive rainfall."""
        obs = DailyRainfallObservation(
            observation_date=date(2026, 7, 15),
            precipitation_mm=25.4,
        )
        assert obs.observation_date == date(2026, 7, 15)
        assert obs.precipitation_mm == 25.4

    def test_valid_observation_zero_precipitation(self) -> None:
        """Verifies valid observation with explicit zero rainfall."""
        obs = DailyRainfallObservation(
            observation_date=date(2026, 7, 15),
            precipitation_mm=0.0,
        )
        assert obs.precipitation_mm == 0.0

    def test_valid_observation_missing_precipitation(self) -> None:
        """Verifies observation with missing (None) precipitation."""
        obs = DailyRainfallObservation(
            observation_date=date(2026, 7, 15),
            precipitation_mm=None,
        )
        assert obs.precipitation_mm is None

    def test_invalid_negative_precipitation(self) -> None:
        """Verifies rejection of negative precipitation (ge=0.0)."""
        with pytest.raises(ValidationError):
            DailyRainfallObservation(
                observation_date=date(2026, 7, 15),
                precipitation_mm=-1.5,
            )

    def test_json_serialization_roundtrip(self) -> None:
        """Verifies clean JSON serialization and deserialization."""
        obs = DailyRainfallObservation(
            observation_date=date(2026, 8, 1),
            precipitation_mm=12.8,
        )
        data = obs.model_dump(mode="json")
        assert data["observation_date"] == "2026-08-01"
        assert data["precipitation_mm"] == 12.8

        reconstructed = DailyRainfallObservation.model_validate(data)
        assert reconstructed == obs


# ============================================================================
# CONTRACT 2: RainfallWindowStatistics Tests
# ============================================================================


class TestRainfallWindowStatisticsContract:
    """Tests for RainfallWindowStatistics domain model."""

    def test_valid_complete_window(self) -> None:
        """Verifies a fully populated, complete 7-day window."""
        stats = RainfallWindowStatistics(
            window_name="recent_7_days",
            window_start=date(2026, 9, 19),
            window_end=date(2026, 9, 25),
            days_requested=7,
            days_available=7,
            is_complete=True,
            total_precipitation_mm=35.0,
            mean_daily_precipitation_mm=5.0,
            max_daily_precipitation_mm=20.0,
        )
        assert stats.is_complete is True
        assert stats.days_available == 7
        assert stats.total_precipitation_mm == 35.0
        assert stats.mean_daily_precipitation_mm == 5.0
        assert stats.max_daily_precipitation_mm == 20.0

    def test_valid_partial_window(self) -> None:
        """Verifies partial window where days_available < days_requested."""
        stats = RainfallWindowStatistics(
            window_name="recent_30_days",
            window_start=date(2026, 8, 27),
            window_end=date(2026, 9, 25),
            days_requested=30,
            days_available=25,
            is_complete=False,
            total_precipitation_mm=50.0,
            mean_daily_precipitation_mm=2.0,
            max_daily_precipitation_mm=15.0,
        )
        assert stats.is_complete is False
        assert stats.days_available == 25
        assert stats.days_requested == 30

    def test_valid_empty_window(self) -> None:
        """Verifies empty window with days_available=0 and None metrics."""
        stats = RainfallWindowStatistics(
            window_name="recent_90_days",
            window_start=date(2026, 6, 28),
            window_end=date(2026, 9, 25),
            days_requested=90,
            days_available=0,
            is_complete=False,
            total_precipitation_mm=None,
            mean_daily_precipitation_mm=None,
            max_daily_precipitation_mm=None,
        )
        assert stats.is_complete is False
        assert stats.days_available == 0
        assert stats.total_precipitation_mm is None

    def test_invalid_start_after_end(self) -> None:
        """Verifies rejection when window_start > window_end."""
        with pytest.raises(ValidationError, match="cannot be after window_end"):
            RainfallWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 25),
                window_end=date(2026, 9, 19),
                days_requested=7,
                days_available=7,
                is_complete=True,
            )

    def test_invalid_available_exceeds_requested(self) -> None:
        """Verifies rejection when days_available > days_requested."""
        with pytest.raises(ValidationError, match="cannot exceed days_requested"):
            RainfallWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=8,
                is_complete=False,
            )

    def test_invalid_completeness_flag_mismatch(self) -> None:
        """Verifies rejection when is_complete flag contradicts days_available == days_requested."""
        with pytest.raises(ValidationError, match="does not match days_available == days_requested"):
            RainfallWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=5,
                is_complete=True,  # Contradiction: 5 != 7
            )

    def test_invalid_mean_greater_than_max(self) -> None:
        """Verifies rejection when mean precipitation exceeds max precipitation."""
        with pytest.raises(ValidationError, match="cannot be greater than max_daily_precipitation_mm"):
            RainfallWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=7,
                is_complete=True,
                total_precipitation_mm=100.0,
                mean_daily_precipitation_mm=25.0,
                max_daily_precipitation_mm=15.0,  # Contradiction: mean > max
            )


# ============================================================================
# CONTRACT 3: CHIRPSRainfallAnalysis Tests
# ============================================================================


class TestCHIRPSRainfallAnalysisContract:
    """Tests for root CHIRPSRainfallAnalysis domain payload."""

    def test_valid_success_payload(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies successful analysis payload construction."""
        obs = [
            DailyRainfallObservation(observation_date=date(2026, 9, 25), precipitation_mm=5.0)
        ]
        r7 = RainfallWindowStatistics(
            window_name="recent_7_days",
            window_start=date(2026, 9, 19),
            window_end=date(2026, 9, 25),
            days_requested=7,
            days_available=1,
            is_complete=False,
            total_precipitation_mm=5.0,
            mean_daily_precipitation_mm=5.0,
            max_daily_precipitation_mm=5.0,
        )
        analysis = CHIRPSRainfallAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            latest_available_date=date(2026, 9, 25),
            data_lag_days=0,
            recent_7_days=r7,
            daily_observations=obs,
            dataset="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
            spatial_resolution_km=5.566,
            status="success",
            pipeline_version="3.1.0",
        )
        assert analysis.status == "success"
        assert analysis.latest_available_date == date(2026, 9, 25)
        assert analysis.data_lag_days == 0
        assert analysis.dataset == "UCSB-CHC/CHIRPS/V3/DAILY_SAT"
        assert analysis.spatial_resolution_km == 5.566
        assert analysis.pipeline_version == "3.1.0"

    def test_success_missing_latest_date_raises(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies success status requires latest_available_date."""
        with pytest.raises(ValidationError, match="requires a non-null latest_available_date"):
            CHIRPSRainfallAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                latest_available_date=None,
                status="success",
            )

    def test_success_future_latest_date_raises(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies success status rejects latest_available_date in future of requested_end_date."""
        with pytest.raises(ValidationError, match="cannot be in the future"):
            CHIRPSRainfallAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 20),
                latest_available_date=date(2026, 9, 25),
                status="success",
            )

    def test_success_lag_mismatch_raises(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies rejection when data_lag_days does not equal requested - latest."""
        with pytest.raises(ValidationError, match="does not match difference"):
            CHIRPSRainfallAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                latest_available_date=date(2026, 9, 20),
                data_lag_days=2,  # Should be 5
                daily_observations=[
                    DailyRainfallObservation(observation_date=date(2026, 9, 20), precipitation_mm=0.0)
                ],
                status="success",
            )

    def test_valid_no_data_payload(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies clean no_data status payload."""
        analysis = CHIRPSRainfallAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            status="no_data",
            latest_available_date=None,
            data_lag_days=None,
            recent_7_days=None,
            recent_30_days=None,
            recent_90_days=None,
            daily_observations=[],
        )
        assert analysis.status == "no_data"
        assert analysis.daily_observations == []
        assert analysis.latest_available_date is None

    def test_no_data_with_observations_raises(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies no_data status cannot contain observations."""
        with pytest.raises(ValidationError, match="cannot contain daily_observations"):
            CHIRPSRainfallAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                status="no_data",
                daily_observations=[
                    DailyRainfallObservation(observation_date=date(2026, 9, 25), precipitation_mm=1.0)
                ],
            )

    def test_valid_error_payload(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies structured error status payload."""
        analysis = CHIRPSRainfallAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            status="error",
            error=EarthEngineError(
                type="EEException",
                message="Earth Engine quota exceeded",
            ),
            daily_observations=[],
        )
        assert analysis.status == "error"
        assert analysis.error is not None
        assert analysis.error.type == "EEException"

    def test_error_missing_error_field_raises(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies error status requires an error object."""
        with pytest.raises(ValidationError, match="requires a populated error field"):
            CHIRPSRainfallAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                status="error",
                error=None,
            )


# ============================================================================
# FIXTURE COMPLIANCE TESTS
# ============================================================================


class TestCHIRPSFixturesValidation:
    """Tests loading and validating all 5 deterministic CHIRPS fixtures."""

    def test_punjab_monsoon_wet_fixture(self) -> None:
        raw = load_punjab_monsoon_wet_raw()
        assert raw["status"] == "success"
        assert raw["dataset"] == "UCSB-CHC/CHIRPS/V3/DAILY_SAT"
        assert len(raw["daily_observations"]) == 90
        # Parse into model
        analysis = CHIRPSRainfallAnalysis.model_validate(raw)
        assert len(analysis.daily_observations) == 90
        assert analysis.requested_end_date == date(2026, 9, 25)

    def test_punjab_winter_dry_fixture(self) -> None:
        raw = load_punjab_winter_dry_raw()
        assert raw["status"] == "success"
        analysis = CHIRPSRainfallAnalysis.model_validate(raw)
        assert len(analysis.daily_observations) == 90
        assert analysis.requested_end_date == date(2026, 1, 29)

    def test_lagged_partial_fixture(self) -> None:
        raw = load_chirps_lagged_partial_raw()
        assert raw["status"] == "success"
        assert raw["data_lag_days"] == 5
        analysis = CHIRPSRainfallAnalysis.model_validate(raw)
        assert len(analysis.daily_observations) == 85
        assert analysis.data_lag_days == 5

    def test_negative_artifact_fixture(self) -> None:
        raw = load_chirps_negative_artifact_raw()
        assert "raw_records" in raw
        assert len(raw["raw_records"]) == 90
        # Check artifact values present in raw
        records = raw["raw_records"]
        assert any(r.get("precipitation") == -9999.0 for r in records)
        assert any(r.get("precipitation") == -1.5 for r in records)
        assert any(r.get("precipitation") is None for r in records)

    def test_no_data_empty_fixture(self) -> None:
        raw = load_chirps_no_data_empty_raw()
        assert raw["status"] == "no_data"
        analysis = CHIRPSRainfallAnalysis.model_validate(raw)
        assert analysis.status == "no_data"
        assert len(analysis.daily_observations) == 0
