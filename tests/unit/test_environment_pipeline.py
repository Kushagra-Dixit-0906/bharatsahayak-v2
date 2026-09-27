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
"""Unit tests for Phase 3A Step 3 ERA5-Land normalization and orchestration pipeline (DEC-019)."""

from datetime import date, datetime, timezone
import math
from typing import Any
from unittest.mock import MagicMock, patch

import ee
import pytest

from app.environment.era5 import (
    DEFAULT_LOOKBACK_DAYS,
    ERA5_LAND_BANDS,
    ERA5_LAND_DATASET,
    ERA5_LAND_NOMINAL_SCALE_M,
    _parse_date,
    fetch_raw_era5_land_timeseries,
)
from app.environment.pipeline import (
    _is_valid_numeric,
    _parse_observation_date,
    _resolve_requested_date,
    analyze_era5_land,
    normalize_raw_era5_record,
)
from app.environment.types import (
    DailyEnvironmentalObservation,
    EnvironmentalWindowStatistics,
    ERA5LandAnalysis,
)
from app.satellite.geometry import create_analysis_region
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    EarthEngineResult,
)
from tests.fixtures.era5_fixtures import (
    load_lagged_partial_raw,
    load_punjab_monsoon_raw,
    load_punjab_winter_dry_raw,
)


@pytest.fixture(autouse=True)
def init_mock_ee():
    """Ensures Earth Engine client is initialized for unit testing."""
    ee.Initialize(project="bharatsahayak-v2")


# ==============================================================================
# 1. TIER 2 — NORMALIZATION TESTS (Conversion, Missing Data, Edge Cases)
# ==============================================================================


def test_normalize_kelvin_to_celsius():
    """Verifies Kelvin to Celsius conversion: T_C = T_K - 273.15."""
    raw = {
        "observation_date": "2026-08-01",
        "temperature_2m": 300.15,  # 300.15 K -> 27.0 °C
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.observation_date == date(2026, 8, 1)
    assert math.isclose(obs.temperature_c, 27.0, rel_tol=1e-9, abs_tol=1e-9)


def test_normalize_preserves_exact_floating_point_without_rounding():
    """Verifies that normalization does not round values and preserves high-precision floating point."""
    raw = {
        "observation_date": "2026-08-01",
        "temperature_2m": 300.123456,
        "total_precipitation_sum": 0.001234567,
        "volumetric_soil_water_layer_1": 0.321987654,
        "runoff_sum": 0.000987654,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.temperature_c is not None
    assert obs.precipitation_mm is not None
    assert obs.volumetric_soil_water_layer_1 is not None
    assert obs.runoff_sum_mm is not None

    # Expected exact values (using math.isclose with 1e-9 tolerance for standard float arithmetic)
    assert math.isclose(obs.temperature_c, 300.123456 - 273.15, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(obs.temperature_c, 26.973456, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(obs.precipitation_mm, 1.234567, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(obs.runoff_sum_mm, 0.987654, rel_tol=1e-9, abs_tol=1e-9)
    assert math.isclose(obs.volumetric_soil_water_layer_1, 0.321987654, rel_tol=1e-9, abs_tol=1e-9)

    # Expose and verify that rounding to 2 or 4 decimals did NOT occur
    assert obs.temperature_c != 26.97
    assert obs.precipitation_mm != 1.23
    assert obs.runoff_sum_mm != 0.99
    assert obs.volumetric_soil_water_layer_1 != 0.3220



def test_normalize_meters_to_mm_precipitation():
    """Verifies precipitation conversion from meters to millimeters (m * 1000.0)."""
    raw = {
        "observation_date": "2026-08-01",
        "total_precipitation_sum": 0.0254,  # 0.0254 m -> 25.4 mm
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.precipitation_mm == 25.4


def test_normalize_meters_to_mm_runoff():
    """Verifies runoff conversion from meters to millimeters (m * 1000.0)."""
    raw = {
        "observation_date": "2026-08-01",
        "runoff_sum": 0.0035,  # 0.0035 m -> 3.5 mm
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.runoff_sum_mm == 3.5


def test_normalize_soil_water_unchanged():
    """Verifies volumetric soil water fraction (m³/m³) is preserved unchanged."""
    raw = {
        "observation_date": "2026-08-01",
        "volumetric_soil_water_layer_1": 0.3421,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.volumetric_soil_water_layer_1 == 0.3421


def test_normalize_fully_valid_record():
    """Verifies complete valid raw record produces fully populated DailyEnvironmentalObservation."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": 305.15,  # 32.0 °C
        "total_precipitation_sum": 0.0125,  # 12.5 mm
        "volumetric_soil_water_layer_1": 0.28,
        "runoff_sum": 0.0012,  # 1.2 mm
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.observation_date == date(2026, 8, 15)
    assert obs.temperature_c == 32.0
    assert obs.precipitation_mm == 12.5
    assert obs.volumetric_soil_water_layer_1 == 0.28
    assert obs.runoff_sum_mm == 1.2
    assert obs.runoff_mm == 1.2


def test_normalize_missing_temperature():
    """Verifies missing/null temperature_2m sets temperature_c=None without discarding record."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": None,
        "total_precipitation_sum": 0.010,
        "volumetric_soil_water_layer_1": 0.30,
        "runoff_sum": 0.001,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.temperature_c is None
    assert obs.precipitation_mm == 10.0


def test_normalize_missing_precipitation():
    """Verifies missing/null total_precipitation_sum sets precipitation_mm=None (missing != zero)."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": 300.0,
        "total_precipitation_sum": None,
        "volumetric_soil_water_layer_1": 0.30,
        "runoff_sum": 0.001,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.precipitation_mm is None


def test_normalize_missing_soil_water():
    """Verifies missing/null volumetric_soil_water_layer_1 sets field to None."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": 300.0,
        "volumetric_soil_water_layer_1": None,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.volumetric_soil_water_layer_1 is None


def test_normalize_missing_runoff():
    """Verifies missing/null runoff_sum sets runoff_sum_mm to None (missing != zero)."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": 300.0,
        "runoff_sum": None,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.runoff_sum_mm is None


def test_normalize_multiple_missing_variables():
    """Verifies record with only date and temperature is valid with other metrics None."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": 303.15,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.temperature_c == 30.0
    assert obs.precipitation_mm is None
    assert obs.volumetric_soil_water_layer_1 is None
    assert obs.runoff_sum_mm is None


def test_normalize_observed_zero_precipitation():
    """Verifies explicit 0.0 precipitation is preserved as 0.0 mm (not confused with missing)."""
    raw = {
        "observation_date": "2026-08-15",
        "total_precipitation_sum": 0.0,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.precipitation_mm == 0.0


def test_normalize_observed_zero_runoff():
    """Verifies explicit 0.0 runoff is preserved as 0.0 mm (not confused with missing)."""
    raw = {
        "observation_date": "2026-08-15",
        "runoff_sum": 0.0,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.runoff_sum_mm == 0.0


def test_normalize_negative_precipitation_rejected():
    """Verifies negative precipitation artifacts are rejected to None (never clamped to 0.0)."""
    raw = {
        "observation_date": "2026-08-15",
        "total_precipitation_sum": -0.002,  # Negative artifact
        "temperature_2m": 300.15,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.precipitation_mm is None
    assert obs.temperature_c == 27.0


def test_normalize_negative_runoff_rejected():
    """Verifies negative runoff artifacts are rejected to None (never clamped to 0.0)."""
    raw = {
        "observation_date": "2026-08-15",
        "runoff_sum": -0.001,  # Negative artifact
        "temperature_2m": 300.15,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.runoff_sum_mm is None
    assert obs.temperature_c == 27.0


def test_normalize_invalid_soil_water_rejected():
    """Verifies soil water outside [0.0, 1.0] is rejected to None."""
    raw_high = {
        "observation_date": "2026-08-15",
        "volumetric_soil_water_layer_1": 1.45,  # > 1.0
    }
    obs_high = normalize_raw_era5_record(raw_high)
    assert obs_high is not None
    assert obs_high.volumetric_soil_water_layer_1 is None

    raw_low = {
        "observation_date": "2026-08-15",
        "volumetric_soil_water_layer_1": -0.05,  # < 0.0
    }
    obs_low = normalize_raw_era5_record(raw_low)
    assert obs_low is not None
    assert obs_low.volumetric_soil_water_layer_1 is None


def test_normalize_invalid_temperature_rejected():
    """Verifies temperature outside [-100.0, 100.0] °C is rejected to None."""
    raw_hot = {
        "observation_date": "2026-08-15",
        "temperature_2m": 450.0,  # 176.85 °C > 100 °C
    }
    obs_hot = normalize_raw_era5_record(raw_hot)
    assert obs_hot is not None
    assert obs_hot.temperature_c is None


def test_normalize_malformed_and_missing_dates():
    """Verifies missing or unparseable dates return None."""
    assert normalize_raw_era5_record({"temperature_2m": 300.0}) is None
    assert normalize_raw_era5_record({"observation_date": "invalid-date"}) is None
    assert normalize_raw_era5_record({"observation_date": None}) is None
    assert normalize_raw_era5_record("not a dict") is None  # type: ignore


def test_normalize_from_epoch_timestamp():
    """Verifies observation date extraction from system:time_start millisecond epoch."""
    # 1786859441321 ms -> 2026-08-16
    raw = {
        "system:time_start": 1786859441321,
        "temperature_2m": 300.15,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.observation_date == date(2026, 8, 16)


def test_normalize_boolean_rejection():
    """Verifies boolean values are not treated as numbers."""
    raw = {
        "observation_date": "2026-08-15",
        "temperature_2m": True,  # boolean
        "total_precipitation_sum": False,
        "volumetric_soil_water_layer_1": True,
        "runoff_sum": False,
    }
    obs = normalize_raw_era5_record(raw)
    assert obs is not None
    assert obs.temperature_c is None
    assert obs.precipitation_mm is None
    assert obs.volumetric_soil_water_layer_1 is None
    assert obs.runoff_sum_mm is None


# ==============================================================================
# 2. TIER 3 — ROOT ORCHESTRATION TESTS (Mocked EE / End-to-End)
# ==============================================================================


def _generate_mock_raw_series(
    start_date_val: date,
    num_days: int,
    base_temp_c: float = 30.0,
    base_precip_mm: float = 5.0,
) -> list[dict[str, Any]]:
    """Generates a synthetic raw ERA5-Land property dictionary sequence."""
    from datetime import timedelta

    records: list[dict[str, Any]] = []
    for i in range(num_days):
        day = start_date_val + timedelta(days=i)
        records.append(
            {
                "observation_date": day.isoformat(),
                "system:time_start": int(datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000),
                "temperature_2m": (base_temp_c + (i % 5)) + 273.15,
                "total_precipitation_sum": (base_precip_mm + (i % 3)) / 1000.0,
                "volumetric_soil_water_layer_1": 0.25 + (i % 10) * 0.01,
                "runoff_sum": ((base_precip_mm + (i % 3)) * 0.1) / 1000.0,
            }
        )
    return records


@patch("app.environment.pipeline.fetch_raw_era5_land_timeseries")
def test_analyze_era5_land_success_90_days(mock_fetch):
    """Verifies full 90-day pipeline success with 0-day publication lag."""
    req_end = date(2026, 9, 25)
    start_d = date(2026, 6, 28)  # 90 days inclusive [2026-06-28, 2026-09-25]
    mock_records = _generate_mock_raw_series(start_d, 90, base_temp_c=32.0, base_precip_mm=10.0)

    mock_fetch.return_value = EarthEngineResult(
        status="success",
        dataset=ERA5_LAND_DATASET,
        image_count=90,
        data=mock_records,
        error=None,
    )

    analysis = analyze_era5_land(
        latitude=30.9157,
        longitude=75.7196,
        requested_end_date=req_end,
        radius_m=100.0,
    )

    assert analysis.status == "success"
    assert analysis.requested_end_date == req_end
    assert analysis.latest_available_date == req_end
    assert analysis.data_lag_days == 0
    assert len(analysis.daily_observations) == 90
    assert analysis.dataset == "ECMWF/ERA5_LAND/DAILY_AGGR"
    assert analysis.spatial_resolution_km == 11.1
    assert analysis.pipeline_version == "3.0.0"
    assert analysis.error is None

    # Verify Step 2 window integration
    assert analysis.recent_7_days is not None
    assert analysis.recent_7_days.days_requested == 7
    assert analysis.recent_7_days.days_available == 7
    assert analysis.recent_7_days.is_complete is True
    assert analysis.recent_7_days.window_start == date(2026, 9, 19)
    assert analysis.recent_7_days.window_end == date(2026, 9, 25)

    assert analysis.recent_30_days is not None
    assert analysis.recent_30_days.days_requested == 30
    assert analysis.recent_30_days.days_available == 30
    assert analysis.recent_30_days.is_complete is True
    assert analysis.recent_30_days.window_start == date(2026, 8, 27)
    assert analysis.recent_30_days.window_end == date(2026, 9, 25)

    assert analysis.recent_90_days is not None
    assert analysis.recent_90_days.days_requested == 90
    assert analysis.recent_90_days.days_available == 90
    assert analysis.recent_90_days.is_complete is True
    assert analysis.recent_90_days.window_start == date(2026, 6, 28)
    assert analysis.recent_90_days.window_end == date(2026, 9, 25)


@patch("app.environment.pipeline.fetch_raw_era5_land_timeseries")
def test_analyze_era5_land_with_publication_data_lag(mock_fetch):
    """Verifies dynamic data lag calculation when archive ends 5 days before requested_end_date."""
    req_end = date(2026, 9, 25)
    start_d = date(2026, 6, 28)
    # Only 85 days available, ending on 2026-09-20 (5 days lag)
    mock_records = _generate_mock_raw_series(start_d, 85, base_temp_c=30.0, base_precip_mm=4.0)

    mock_fetch.return_value = EarthEngineResult(
        status="success",
        dataset=ERA5_LAND_DATASET,
        image_count=85,
        data=mock_records,
        error=None,
    )

    analysis = analyze_era5_land(
        latitude=30.9157,
        longitude=75.7196,
        requested_end_date=req_end,
    )

    assert analysis.status == "success"
    assert analysis.requested_end_date == req_end
    assert analysis.latest_available_date == date(2026, 9, 20)
    assert analysis.data_lag_days == 5
    assert len(analysis.daily_observations) == 85

    # 7-day window [2026-09-19, 2026-09-25] has only 2 days available (19th and 20th)
    assert analysis.recent_7_days is not None
    assert analysis.recent_7_days.days_requested == 7
    assert analysis.recent_7_days.days_available == 2
    assert analysis.recent_7_days.is_complete is False


@patch("app.environment.pipeline.fetch_raw_era5_land_timeseries")
def test_analyze_era5_land_no_data(mock_fetch):
    """Verifies no_data payload construction when Earth Engine returns 0 records."""
    mock_fetch.return_value = EarthEngineResult(
        status="no_data",
        dataset=ERA5_LAND_DATASET,
        image_count=0,
        data=[],
        error=None,
    )

    analysis = analyze_era5_land(
        latitude=30.9157,
        longitude=75.7196,
        requested_end_date=date(2026, 9, 25),
    )

    assert analysis.status == "no_data"
    assert analysis.requested_end_date == date(2026, 9, 25)
    assert analysis.latest_available_date is None
    assert analysis.data_lag_days is None
    assert analysis.daily_observations == []
    assert analysis.recent_7_days is None
    assert analysis.recent_30_days is None
    assert analysis.recent_90_days is None
    assert analysis.error is None


@patch("app.environment.pipeline.fetch_raw_era5_land_timeseries")
def test_analyze_era5_land_error_propagation(mock_fetch):
    """Verifies structured EarthEngineError is preserved and status is error."""
    mock_fetch.return_value = EarthEngineResult(
        status="error",
        dataset=ERA5_LAND_DATASET,
        image_count=None,
        data=None,
        error=EarthEngineError(
            type="EEException",
            message="User does not have permission to access Earth Engine",
        ),
    )

    analysis = analyze_era5_land(
        latitude=30.9157,
        longitude=75.7196,
        requested_end_date=date(2026, 9, 25),
    )

    assert analysis.status == "error"
    assert analysis.latest_available_date is None
    assert analysis.data_lag_days is None
    assert analysis.daily_observations == []
    assert analysis.recent_7_days is None
    assert analysis.recent_30_days is None
    assert analysis.recent_90_days is None
    assert analysis.error is not None
    assert analysis.error.type == "EEException"
    assert "User does not have permission" in analysis.error.message


@patch("app.environment.pipeline.fetch_raw_era5_land_timeseries")
def test_analyze_era5_land_all_normalized_invalid_yields_no_data(mock_fetch):
    """Verifies that if all returned records fail normalization, status becomes no_data."""
    mock_fetch.return_value = EarthEngineResult(
        status="success",
        dataset=ERA5_LAND_DATASET,
        image_count=2,
        data=[
            {"observation_date": "invalid-date"},
            {"observation_date": None},
        ],
        error=None,
    )

    analysis = analyze_era5_land(
        latitude=30.9157,
        longitude=75.7196,
        requested_end_date=date(2026, 9, 25),
    )

    assert analysis.status == "no_data"
    assert analysis.daily_observations == []


def test_analyze_era5_land_input_validation():
    """Verifies coordinate and parameter validation raises appropriate exceptions."""
    # Bad latitude
    with pytest.raises(ValueError, match="Latitude"):
        analyze_era5_land(latitude=95.0, longitude=75.0)
    with pytest.raises(ValueError, match="Latitude"):
        analyze_era5_land(latitude=-95.0, longitude=75.0)
    with pytest.raises(TypeError, match="Latitude"):
        analyze_era5_land(latitude="30.0", longitude=75.0)  # type: ignore
    with pytest.raises(TypeError, match="Latitude"):
        analyze_era5_land(latitude=True, longitude=75.0)  # type: ignore

    # Bad longitude
    with pytest.raises(ValueError, match="Longitude"):
        analyze_era5_land(latitude=30.0, longitude=185.0)
    with pytest.raises(ValueError, match="Longitude"):
        analyze_era5_land(latitude=30.0, longitude=-185.0)
    with pytest.raises(TypeError, match="Longitude"):
        analyze_era5_land(latitude=30.0, longitude=None)  # type: ignore

    # Bad radius
    with pytest.raises(ValueError, match="Radius"):
        analyze_era5_land(latitude=30.0, longitude=75.0, radius_m=-10.0)
    with pytest.raises(ValueError, match="Radius"):
        analyze_era5_land(latitude=30.0, longitude=75.0, radius_m=0.0)

    # Bad lookback_days
    with pytest.raises(ValueError, match="lookback_days"):
        analyze_era5_land(latitude=30.0, longitude=75.0, lookback_days=0)
    with pytest.raises(ValueError, match="lookback_days"):
        analyze_era5_land(latitude=30.0, longitude=75.0, lookback_days=-5)

    # Bad date format string
    with pytest.raises(ValueError, match="Invalid requested_end_date"):
        analyze_era5_land(latitude=30.0, longitude=75.0, requested_end_date="not-a-date")


# ==============================================================================
# 3. TIER 1 — ADAPTER CONTRACT TESTS (Mocked EE Calls)
# ==============================================================================


def test_fetch_raw_era5_invalid_parameters():
    """Verifies validation in fetch_raw_era5_land_timeseries."""
    with pytest.raises(ValueError, match="lookback_days"):
        fetch_raw_era5_land_timeseries(region=None, lookback_days=0)  # type: ignore

    with pytest.raises(TypeError, match="region"):
        fetch_raw_era5_land_timeseries(region=12345)  # type: ignore


@patch("ee.ImageCollection")
def test_fetch_raw_era5_query_construction(mock_ee_ic):
    """Verifies Earth Engine query collection and filter construction."""
    mock_collection = MagicMock()
    mock_ee_ic.return_value = mock_collection
    mock_collection.filterBounds.return_value = mock_collection
    mock_collection.filterDate.return_value = mock_collection
    mock_collection.select.return_value = mock_collection
    mock_collection.sort.return_value = mock_collection
    mock_collection.map.return_value = mock_collection
    mock_collection.getInfo.return_value = {
        "features": [
            {
                "properties": {
                    "observation_date": "2026-09-25",
                    "system:time_start": 1786859441321,
                    "temperature_2m": 305.15,
                    "total_precipitation_sum": 0.015,
                    "volumetric_soil_water_layer_1": 0.30,
                    "runoff_sum": 0.002,
                }
            }
        ]
    }

    region_meta = AnalysisRegionMetadata(
        latitude=30.9157,
        longitude=75.7196,
        radius_m=100.0,
    )

    result = fetch_raw_era5_land_timeseries(
        region=region_meta,
        requested_end_date=date(2026, 9, 25),
        lookback_days=90,
    )

    assert result.status == "success"
    assert result.image_count == 1
    assert len(result.data) == 1
    assert result.data[0]["temperature_2m"] == 305.15

    # Verify EE chain was invoked
    mock_ee_ic.assert_called_once_with(ERA5_LAND_DATASET)
    mock_collection.select.assert_called_once_with(ERA5_LAND_BANDS)
    # Check start date was [2026-06-28, 2026-09-26)
    mock_collection.filterDate.assert_called_once_with("2026-06-28", "2026-09-26")


@patch("ee.ImageCollection")
def test_fetch_raw_era5_ee_exception_handling(mock_ee_ic):
    """Verifies that EE server-side exceptions are captured into structured EarthEngineError."""
    mock_collection = MagicMock()
    mock_ee_ic.return_value = mock_collection
    mock_collection.filterBounds.side_effect = RuntimeError("Earth Engine backend quota exceeded")

    region_meta = AnalysisRegionMetadata(
        latitude=30.9157,
        longitude=75.7196,
        radius_m=100.0,
    )

    result = fetch_raw_era5_land_timeseries(
        region=region_meta,
        requested_end_date=date(2026, 9, 25),
        lookback_days=90,
    )

    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "RuntimeError"
    assert "Earth Engine backend quota exceeded" in result.error.message


@patch("app.environment.pipeline.fetch_raw_era5_land_timeseries")
def test_analyze_era5_land_with_fixture_data(mock_fetch):
    """Verifies end-to-end orchestration using loaded Punjab monsoon raw fixture data."""
    fixture_data = load_punjab_monsoon_raw()
    req_end = date.fromisoformat(fixture_data["requested_end_date"])

    mock_fetch.return_value = EarthEngineResult(
        status="success",
        dataset=ERA5_LAND_DATASET,
        image_count=len(fixture_data["daily_observations"]),
        data=fixture_data["daily_observations"],
        error=None,
    )

    analysis = analyze_era5_land(
        latitude=fixture_data["region"]["latitude"],
        longitude=fixture_data["region"]["longitude"],
        requested_end_date=req_end,
    )

    assert analysis.status == "success"
    assert analysis.requested_end_date == req_end
    assert analysis.latest_available_date == date(2026, 9, 25)
    assert analysis.data_lag_days == 0
    assert len(analysis.daily_observations) == 90
    assert analysis.recent_7_days is not None
    assert analysis.recent_7_days.is_complete is True
