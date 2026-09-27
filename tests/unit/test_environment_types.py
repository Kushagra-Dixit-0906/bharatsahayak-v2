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
"""Unit tests for Phase 3A environmental domain contracts and offline fixtures (DEC-018)."""

from datetime import date
import json

from pydantic import ValidationError
import pytest

from app.environment.types import (
    DailyEnvironmentalObservation,
    EnvironmentalWindowStatistics,
    ERA5LandAnalysis,
)
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError, EarthEngineStatus
from tests.fixtures.era5_fixtures import (
    load_lagged_partial_raw,
    load_negative_artifact_raw,
    load_no_data_empty_raw,
    load_punjab_monsoon_raw,
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
# CONTRACT 1: DailyEnvironmentalObservation Tests
# ============================================================================


class TestDailyEnvironmentalObservationContract:
    """Tests for DailyEnvironmentalObservation domain model."""

    def test_valid_observation_full(self) -> None:
        """Verifies valid observation with all physical fields populated."""
        obs = DailyEnvironmentalObservation(
            observation_date=date(2026, 7, 15),
            temperature_c=30.5,
            precipitation_mm=25.4,
            volumetric_soil_water_layer_1=0.35,
            runoff_sum_mm=3.2,
        )
        assert obs.observation_date == date(2026, 7, 15)
        assert obs.temperature_c == 30.5
        assert obs.precipitation_mm == 25.4
        assert obs.volumetric_soil_water_layer_1 == 0.35
        assert obs.runoff_sum_mm == 3.2
        assert obs.runoff_mm == 3.2

    def test_temperature_normalization_contract(self) -> None:
        """Verifies temperature supports negative, zero, and high positive degrees Celsius."""
        obs_subzero = DailyEnvironmentalObservation(
            observation_date=date(2026, 1, 10),
            temperature_c=-5.2,
        )
        assert obs_subzero.temperature_c == -5.2

        obs_zero = DailyEnvironmentalObservation(
            observation_date=date(2026, 1, 11),
            temperature_c=0.0,
        )
        assert obs_zero.temperature_c == 0.0

        obs_hot = DailyEnvironmentalObservation(
            observation_date=date(2026, 5, 25),
            temperature_c=48.5,
        )
        assert obs_hot.temperature_c == 48.5

    def test_precipitation_normalization_contract(self) -> None:
        """Verifies precipitation supports zero and positive values."""
        obs_dry = DailyEnvironmentalObservation(
            observation_date=date(2026, 2, 1),
            precipitation_mm=0.0,
        )
        assert obs_dry.precipitation_mm == 0.0

        obs_rain = DailyEnvironmentalObservation(
            observation_date=date(2026, 7, 20),
            precipitation_mm=105.6,
        )
        assert obs_rain.precipitation_mm == 105.6

    def test_runoff_normalization_contract(self) -> None:
        """Verifies runoff supports zero and positive values."""
        obs = DailyEnvironmentalObservation(
            observation_date=date(2026, 8, 1),
            runoff_sum_mm=12.4,
        )
        assert obs.runoff_sum_mm == 12.4
        assert obs.runoff_mm == 12.4

    def test_soil_water_valid_physical_range(self) -> None:
        """Verifies soil water accepts values in [0.0, 1.0] and rejects outside."""
        obs_min = DailyEnvironmentalObservation(
            observation_date=date(2026, 5, 1),
            volumetric_soil_water_layer_1=0.0,
        )
        assert obs_min.volumetric_soil_water_layer_1 == 0.0

        obs_max = DailyEnvironmentalObservation(
            observation_date=date(2026, 8, 1),
            volumetric_soil_water_layer_1=1.0,
        )
        assert obs_max.volumetric_soil_water_layer_1 == 1.0

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DailyEnvironmentalObservation(
                observation_date=date(2026, 5, 1),
                volumetric_soil_water_layer_1=-0.05,
            )

        with pytest.raises(ValidationError, match="less than or equal to 1"):
            DailyEnvironmentalObservation(
                observation_date=date(2026, 5, 1),
                volumetric_soil_water_layer_1=1.05,
            )

    def test_negative_precipitation_rejected_not_clamped(self) -> None:
        """Verifies negative precipitation raises explicit ValidationError without silent clamping."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DailyEnvironmentalObservation(
                observation_date=date(2026, 7, 1),
                precipitation_mm=-0.1,
            )

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DailyEnvironmentalObservation(
                observation_date=date(2026, 7, 1),
                precipitation_mm=-10.0,
            )

    def test_negative_runoff_rejected_not_clamped(self) -> None:
        """Verifies negative runoff raises explicit ValidationError without silent clamping."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            DailyEnvironmentalObservation(
                observation_date=date(2026, 7, 1),
                runoff_sum_mm=-0.05,
            )

    def test_missing_precipitation_distinguishable_from_zero(self) -> None:
        """Verifies missing precipitation is None and distinguishable from 0.0."""
        obs_missing = DailyEnvironmentalObservation(
            observation_date=date(2026, 7, 1),
            precipitation_mm=None,
        )
        obs_zero = DailyEnvironmentalObservation(
            observation_date=date(2026, 7, 1),
            precipitation_mm=0.0,
        )
        assert obs_missing.precipitation_mm is None
        assert obs_zero.precipitation_mm == 0.0
        assert obs_missing.precipitation_mm != obs_zero.precipitation_mm

    def test_missing_runoff_distinguishable_from_zero(self) -> None:
        """Verifies missing runoff is None and distinguishable from 0.0."""
        obs_missing = DailyEnvironmentalObservation(
            observation_date=date(2026, 7, 1),
            runoff_sum_mm=None,
        )
        obs_zero = DailyEnvironmentalObservation(
            observation_date=date(2026, 7, 1),
            runoff_sum_mm=0.0,
        )
        assert obs_missing.runoff_sum_mm is None
        assert obs_zero.runoff_sum_mm == 0.0
        assert obs_missing.runoff_sum_mm != obs_zero.runoff_sum_mm

    def test_missing_all_variables_preserves_date(self) -> None:
        """Verifies observation can represent an unpopulated date placeholder."""
        obs = DailyEnvironmentalObservation(observation_date=date(2026, 7, 1))
        assert obs.observation_date == date(2026, 7, 1)
        assert obs.temperature_c is None
        assert obs.precipitation_mm is None
        assert obs.volumetric_soil_water_layer_1 is None
        assert obs.runoff_sum_mm is None


# ============================================================================
# CONTRACT 2: EnvironmentalWindowStatistics Tests
# ============================================================================


class TestEnvironmentalWindowStatisticsContract:
    """Tests for EnvironmentalWindowStatistics aggregation model."""

    def test_valid_complete_window(self) -> None:
        """Verifies complete 30-day window construction."""
        window = EnvironmentalWindowStatistics(
            window_name="recent_30_days",
            window_start=date(2026, 8, 27),
            window_end=date(2026, 9, 25),
            days_requested=30,
            days_available=30,
            is_complete=True,
            mean_temperature_c=31.2,
            min_temperature_c=28.5,
            max_temperature_c=34.0,
            total_precipitation_mm=142.5,
            mean_soil_water_layer_1=0.32,
            total_runoff_mm=18.6,
        )
        assert window.window_name == "recent_30_days"
        assert window.days_requested == 30
        assert window.days_available == 30
        assert window.is_complete is True
        assert window.total_precipitation_mm == 142.5

    def test_valid_partial_window(self) -> None:
        """Verifies partial / incomplete window construction."""
        window = EnvironmentalWindowStatistics(
            window_name="recent_90_days",
            window_start=date(2026, 6, 28),
            window_end=date(2026, 9, 25),
            days_requested=90,
            days_available=85,
            is_complete=False,
            mean_temperature_c=31.8,
            min_temperature_c=28.0,
            max_temperature_c=35.1,
            total_precipitation_mm=380.0,
            mean_soil_water_layer_1=0.31,
            total_runoff_mm=55.2,
        )
        assert window.is_complete is False
        assert window.days_available == 85
        assert window.days_requested == 90

    def test_days_available_cannot_exceed_days_requested(self) -> None:
        """Verifies invariant days_available <= days_requested."""
        with pytest.raises(ValidationError, match="days_available .* cannot exceed days_requested"):
            EnvironmentalWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=8,
                is_complete=False,
            )

    def test_is_complete_flag_consistency(self) -> None:
        """Verifies is_complete must strictly equal (days_available == days_requested)."""
        with pytest.raises(ValidationError, match="is_complete .* does not match"):
            EnvironmentalWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=7,
                is_complete=False,  # False when available == requested
            )

        with pytest.raises(ValidationError, match="is_complete .* does not match"):
            EnvironmentalWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=5,
                is_complete=True,  # True when available < requested
            )

    def test_window_date_ordering_invariant(self) -> None:
        """Verifies window_start cannot be after window_end."""
        with pytest.raises(ValidationError, match="window_start .* cannot be after window_end"):
            EnvironmentalWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 25),
                window_end=date(2026, 9, 19),
                days_requested=7,
                days_available=7,
                is_complete=True,
            )

    def test_temperature_min_max_mean_invariants(self) -> None:
        """Verifies min <= mean <= max temperature bounds."""
        with pytest.raises(ValidationError, match="min_temperature_c .* cannot be greater than max_temperature_c"):
            EnvironmentalWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=7,
                is_complete=True,
                min_temperature_c=35.0,
                max_temperature_c=25.0,
            )

        with pytest.raises(ValidationError, match="min_temperature_c .* cannot be greater than mean_temperature_c"):
            EnvironmentalWindowStatistics(
                window_name="recent_7_days",
                window_start=date(2026, 9, 19),
                window_end=date(2026, 9, 25),
                days_requested=7,
                days_available=7,
                is_complete=True,
                min_temperature_c=30.0,
                mean_temperature_c=28.0,
                max_temperature_c=35.0,
            )


# ============================================================================
# CONTRACT 3: ERA5LandAnalysis Tests
# ============================================================================


class TestERA5LandAnalysisContract:
    """Tests for authoritative ERA5LandAnalysis root domain model."""

    def test_valid_successful_analysis(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies valid successful analysis payload construction."""
        obs = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 25),
                temperature_c=32.0,
                precipitation_mm=5.0,
                volumetric_soil_water_layer_1=0.25,
                runoff_sum_mm=0.5,
            )
        ]
        w7 = EnvironmentalWindowStatistics(
            window_name="recent_7_days",
            window_start=date(2026, 9, 19),
            window_end=date(2026, 9, 25),
            days_requested=7,
            days_available=7,
            is_complete=True,
            mean_temperature_c=32.0,
            min_temperature_c=30.0,
            max_temperature_c=33.5,
            total_precipitation_mm=15.0,
            mean_soil_water_layer_1=0.26,
            total_runoff_mm=1.2,
        )

        analysis = ERA5LandAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            latest_available_date=date(2026, 9, 25),
            data_lag_days=0,
            recent_7_days=w7,
            daily_observations=obs,
            status="success",
            pipeline_version="3.0.0",
        )

        assert analysis.status == "success"
        assert analysis.requested_end_date == date(2026, 9, 25)
        assert analysis.latest_available_date == date(2026, 9, 25)
        assert analysis.data_lag_days == 0
        assert analysis.dataset == "ECMWF/ERA5_LAND/DAILY_AGGR"
        assert analysis.spatial_resolution_km == 11.1
        assert len(analysis.daily_observations) == 1
        assert analysis.error is None

    def test_publication_lag_representation(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies latest_available_date earlier than requested_end_date with matching data_lag_days."""
        analysis = ERA5LandAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            latest_available_date=date(2026, 9, 20),
            data_lag_days=5,
            daily_observations=[
                DailyEnvironmentalObservation(
                    observation_date=date(2026, 9, 20),
                    temperature_c=30.0,
                )
            ],
            status="success",
        )
        assert analysis.requested_end_date == date(2026, 9, 25)
        assert analysis.latest_available_date == date(2026, 9, 20)
        assert analysis.data_lag_days == 5

    def test_future_latest_available_date_rejected(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies latest_available_date cannot be in the future relative to requested_end_date."""
        with pytest.raises(ValidationError, match="cannot be in the future relative to requested_end_date"):
            ERA5LandAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 20),
                latest_available_date=date(2026, 9, 25),
                status="success",
            )

    def test_data_lag_days_consistency_validation(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies data_lag_days must match requested_end_date - latest_available_date."""
        with pytest.raises(ValidationError, match="data_lag_days .* does not match difference"):
            ERA5LandAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                latest_available_date=date(2026, 9, 20),
                data_lag_days=3,  # actual difference is 5
                status="success",
            )

    def test_status_uses_existing_earth_engine_status_type(self) -> None:
        """Verifies ERA5LandAnalysis.status strictly uses EarthEngineStatus Literal values."""
        assert EarthEngineStatus.__args__ == ("success", "no_data", "error")

    def test_no_data_status_contract(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies no_data status representation."""
        analysis = ERA5LandAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            latest_available_date=None,
            data_lag_days=None,
            daily_observations=[],
            status="no_data",
        )
        assert analysis.status == "no_data"
        assert analysis.latest_available_date is None
        assert analysis.daily_observations == []
        assert analysis.recent_7_days is None

    def test_no_data_rejects_observations(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies status='no_data' cannot contain observations."""
        with pytest.raises(ValidationError, match="status='no_data' cannot contain daily_observations"):
            ERA5LandAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                daily_observations=[
                    DailyEnvironmentalObservation(observation_date=date(2026, 9, 25))
                ],
                status="no_data",
            )

    def test_error_status_contract(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies error status integrates existing EarthEngineError."""
        err = EarthEngineError(
            type="EarthEngineComputeError",
            message="Internal computation timeout on ERA5-Land reduction",
        )
        analysis = ERA5LandAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            status="error",
            error=err,
        )
        assert analysis.status == "error"
        assert analysis.error is not None
        assert analysis.error.type == "EarthEngineComputeError"
        assert analysis.error.message == "Internal computation timeout on ERA5-Land reduction"

    def test_error_status_requires_error_field(self, sample_region: AnalysisRegionMetadata) -> None:
        """Verifies status='error' requires a non-null error object."""
        with pytest.raises(ValidationError, match="status='error' requires a populated error field"):
            ERA5LandAnalysis(
                region=sample_region,
                requested_end_date=date(2026, 9, 25),
                status="error",
                error=None,
            )

    def test_json_serialization_and_deserialization_roundtrip(
        self, sample_region: AnalysisRegionMetadata
    ) -> None:
        """Verifies complete Pydantic JSON serialization and deserialization roundtrip."""
        w7 = EnvironmentalWindowStatistics(
            window_name="recent_7_days",
            window_start=date(2026, 9, 19),
            window_end=date(2026, 9, 25),
            days_requested=7,
            days_available=7,
            is_complete=True,
            mean_temperature_c=31.5,
            min_temperature_c=29.0,
            max_temperature_c=33.0,
            total_precipitation_mm=12.0,
            mean_soil_water_layer_1=0.28,
            total_runoff_mm=1.0,
        )
        obs = [
            DailyEnvironmentalObservation(
                observation_date=date(2026, 9, 25),
                temperature_c=33.0,
                precipitation_mm=0.0,
                volumetric_soil_water_layer_1=0.25,
                runoff_sum_mm=0.0,
            )
        ]
        original = ERA5LandAnalysis(
            region=sample_region,
            requested_end_date=date(2026, 9, 25),
            latest_available_date=date(2026, 9, 25),
            data_lag_days=0,
            recent_7_days=w7,
            daily_observations=obs,
            status="success",
            pipeline_version="3.0.0",
        )

        json_str = original.model_dump_json()
        restored = ERA5LandAnalysis.model_validate_json(json_str)

        assert restored == original
        assert restored.requested_end_date == date(2026, 9, 25)
        assert restored.recent_7_days is not None
        assert restored.recent_7_days.total_precipitation_mm == 12.0
        assert len(restored.daily_observations) == 1
        assert restored.daily_observations[0].temperature_c == 33.0


# ============================================================================
# DETERMINISTIC FIXTURE LOADING TESTS
# ============================================================================


class TestERA5LandFixtures:
    """Tests loading and validation of deterministic offline test fixtures."""

    def test_load_punjab_monsoon_fixture(self) -> None:
        """Verifies loading and parsing of the 90-day Punjab monsoon fixture."""
        raw = load_punjab_monsoon_raw()
        assert raw["requested_end_date"] == "2026-09-25"
        assert len(raw["daily_observations"]) == 90

        # Validate observations through domain model
        observations = [DailyEnvironmentalObservation(**o) for o in raw["daily_observations"]]
        assert len(observations) == 90
        assert observations[0].observation_date == date(2026, 6, 28)
        assert observations[-1].observation_date == date(2026, 9, 25)

        # Confirm non-trivial rainfall occurs in monsoon
        total_precip = sum(o.precipitation_mm for o in observations if o.precipitation_mm is not None)
        assert total_precip > 500.0

    def test_load_punjab_winter_dry_fixture(self) -> None:
        """Verifies loading and parsing of the 90-day Punjab winter dry fixture."""
        raw = load_punjab_winter_dry_raw()
        assert raw["requested_end_date"] == "2026-01-29"
        assert len(raw["daily_observations"]) == 90

        observations = [DailyEnvironmentalObservation(**o) for o in raw["daily_observations"]]
        assert len(observations) == 90

        # Confirm winter temperatures and low precipitation
        temps = [o.temperature_c for o in observations if o.temperature_c is not None]
        assert all(t < 25.0 for t in temps)
        total_precip = sum(o.precipitation_mm for o in observations if o.precipitation_mm is not None)
        assert total_precip < 100.0

    def test_load_lagged_partial_fixture(self) -> None:
        """Verifies loading and parsing of the lagged partial fixture."""
        raw = load_lagged_partial_raw()
        assert raw["requested_end_date"] == "2026-09-25"
        assert raw["latest_available_date"] == "2026-09-20"
        assert raw["data_lag_days"] == 5
        assert len(raw["daily_observations"]) == 85

        observations = [DailyEnvironmentalObservation(**o) for o in raw["daily_observations"]]
        assert len(observations) == 85
        assert observations[-1].observation_date == date(2026, 9, 20)

    def test_load_negative_artifact_fixture_rejection(self) -> None:
        """Verifies that the negative artifact fixture triggers validation failure on invalid values."""
        raw = load_negative_artifact_raw()
        valid_count = 0
        error_count = 0

        for item in raw["daily_observations"]:
            try:
                DailyEnvironmentalObservation(**item)
                valid_count += 1
            except ValidationError:
                error_count += 1

        assert valid_count == 1
        assert error_count == 1

    def test_load_no_data_empty_fixture(self) -> None:
        """Verifies loading and parsing of the empty no-data fixture."""
        raw = load_no_data_empty_raw()
        analysis = ERA5LandAnalysis(**raw)
        assert analysis.status == "no_data"
        assert analysis.daily_observations == []
        assert analysis.latest_available_date is None
