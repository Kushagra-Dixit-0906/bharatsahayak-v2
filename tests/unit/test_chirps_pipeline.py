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
"""Unit tests for Phase 3B CHIRPS normalization and pipeline orchestration (DEC-020)."""

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.environment.chirps_pipeline import (
    analyze_chirps_rainfall,
    normalize_raw_chirps_record,
)
from app.environment.chirps_types import (
    CHIRPSRainfallAnalysis,
    DailyRainfallObservation,
)
from app.satellite.types import EarthEngineError, EarthEngineResult
from tests.fixtures.chirps_fixtures import (
    load_chirps_lagged_partial_raw,
    load_chirps_negative_artifact_raw,
    load_chirps_no_data_empty_raw,
    load_punjab_monsoon_wet_raw,
    load_punjab_winter_dry_raw,
)


# ============================================================================
# TIER 2: PURE NORMALIZATION TESTS
# ============================================================================


class TestNormalizeRawCHIRPSRecord:
    """Tests for normalize_raw_chirps_record pure normalization function."""

    def test_normalize_valid_record(self) -> None:
        """Verifies 1:1 unit preservation for valid precipitation."""
        record = {
            "observation_date": "2026-07-15",
            "precipitation": 25.4321,
        }
        obs = normalize_raw_chirps_record(record)
        assert obs is not None
        assert obs.observation_date == date(2026, 7, 15)
        # Verify EXACT floating-point preservation without rounding
        assert obs.precipitation_mm == 25.4321

    def test_normalize_zero_precipitation(self) -> None:
        """Verifies explicit 0.0 remains 0.0."""
        record = {
            "observation_date": "2026-07-15",
            "precipitation": 0.0,
        }
        obs = normalize_raw_chirps_record(record)
        assert obs is not None
        assert obs.precipitation_mm == 0.0

    def test_normalize_missing_precipitation(self) -> None:
        """Verifies missing precipitation remains None."""
        record = {
            "observation_date": "2026-07-15",
            "precipitation": None,
        }
        obs = normalize_raw_chirps_record(record)
        assert obs is not None
        assert obs.precipitation_mm is None

    def test_normalize_negative_artifact_rejected(self) -> None:
        """Verifies negative packing artifacts (< 0.0) are rejected to None rather than clamped."""
        record_neg1 = {
            "observation_date": "2026-07-15",
            "precipitation": -9999.0,
        }
        obs1 = normalize_raw_chirps_record(record_neg1)
        assert obs1 is not None
        assert obs1.precipitation_mm is None  # NOT clamped to 0.0

        record_neg2 = {
            "observation_date": "2026-07-16",
            "precipitation": -0.001,
        }
        obs2 = normalize_raw_chirps_record(record_neg2)
        assert obs2 is not None
        assert obs2.precipitation_mm is None

    def test_normalize_date_formats(self) -> None:
        """Verifies parsing of various date representations."""
        # ISO string with T
        obs1 = normalize_raw_chirps_record({"observation_date": "2026-08-01T00:00:00Z", "precipitation": 5.0})
        assert obs1 is not None
        assert obs1.observation_date == date(2026, 8, 1)

        # Date object
        obs2 = normalize_raw_chirps_record({"observation_date": date(2026, 8, 2), "precipitation": 5.0})
        assert obs2 is not None
        assert obs2.observation_date == date(2026, 8, 2)

        # System time start timestamp in ms (e.g. 2026-08-03 00:00:00 UTC)
        ts_ms = int(datetime(2026, 8, 3, tzinfo=timezone.utc).timestamp() * 1000)
        obs3 = normalize_raw_chirps_record({"system:time_start": ts_ms, "precipitation": 5.0})
        assert obs3 is not None
        assert obs3.observation_date == date(2026, 8, 3)

    def test_normalize_invalid_input(self) -> None:
        """Verifies non-dict or unparseable date returns None."""
        assert normalize_raw_chirps_record("not a dict") is None  # type: ignore[arg-type]
        assert normalize_raw_chirps_record({"observation_date": "invalid-date"}) is None
        assert normalize_raw_chirps_record({}) is None


# ============================================================================
# TIER 3: ROOT ORCHESTRATION TESTS
# ============================================================================


class TestAnalyzeCHIRPSRainfall:
    """Tests for analyze_chirps_rainfall root orchestration."""

    def test_invalid_spatial_inputs(self) -> None:
        """Verifies invalid latitude/longitude/radius raises ValueError/TypeError."""
        with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
            analyze_chirps_rainfall(latitude=95.0, longitude=75.0)

        with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
            analyze_chirps_rainfall(latitude=30.0, longitude=200.0)

        with pytest.raises(ValueError, match="Radius must be strictly positive"):
            analyze_chirps_rainfall(latitude=30.0, longitude=75.0, radius_m=-10.0)

        with pytest.raises(TypeError, match="Latitude must be a valid number"):
            analyze_chirps_rainfall(latitude="invalid", longitude=75.0)  # type: ignore[arg-type]

        with pytest.raises(ValueError, match="lookback_days must be a strictly positive integer"):
            analyze_chirps_rainfall(latitude=30.0, longitude=75.0, lookback_days=-5)

    def test_invalid_requested_end_date(self) -> None:
        """Verifies invalid date format raises ValueError/TypeError."""
        with pytest.raises(ValueError, match="Invalid requested_end_date format"):
            analyze_chirps_rainfall(
                latitude=30.9157,
                longitude=75.7196,
                requested_end_date="invalid-date",
            )

        with pytest.raises(TypeError, match="Unsupported requested_end_date type"):
            analyze_chirps_rainfall(
                latitude=30.9157,
                longitude=75.7196,
                requested_end_date=12345,  # type: ignore[arg-type]
            )

    @patch("app.environment.chirps_pipeline.fetch_raw_chirps_rainfall_timeseries")
    def test_successful_analysis_pipeline(
        self,
        mock_fetch: MagicMock,
    ) -> None:
        """Verifies complete successful orchestration with dynamic lag and 7/30/90d statistics."""
        raw_fixture = load_punjab_monsoon_wet_raw()
        # Convert daily_observations from fixture into raw format for fetch result
        raw_records = [
            {"observation_date": obs["observation_date"], "precipitation": obs["precipitation_mm"]}
            for obs in raw_fixture["daily_observations"]
        ]
        mock_fetch.return_value = EarthEngineResult(
            status="success",
            dataset="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
            image_count=len(raw_records),
            data=raw_records,
        )

        res = analyze_chirps_rainfall(
            latitude=30.9157,
            longitude=75.7196,
            requested_end_date="2026-09-25",
        )

        assert res.status == "success"
        assert res.requested_end_date == date(2026, 9, 25)
        assert res.latest_available_date == date(2026, 9, 25)
        assert res.data_lag_days == 0
        assert len(res.daily_observations) == 90
        assert res.recent_7_days is not None
        assert res.recent_7_days.is_complete is True
        assert res.recent_30_days is not None
        assert res.recent_30_days.is_complete is True
        assert res.recent_90_days is not None
        assert res.recent_90_days.is_complete is True

    @patch("app.environment.chirps_pipeline.fetch_raw_chirps_rainfall_timeseries")
    def test_lagged_partial_analysis_pipeline(
        self,
        mock_fetch: MagicMock,
    ) -> None:
        """Verifies dynamic publication lag derivation and partial window handling."""
        raw_fixture = load_chirps_lagged_partial_raw()
        raw_records = [
            {"observation_date": obs["observation_date"], "precipitation": obs["precipitation_mm"]}
            for obs in raw_fixture["daily_observations"]
        ]
        mock_fetch.return_value = EarthEngineResult(
            status="success",
            dataset="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
            image_count=len(raw_records),
            data=raw_records,
        )

        res = analyze_chirps_rainfall(
            latitude=30.9157,
            longitude=75.7196,
            requested_end_date="2026-09-25",
        )

        assert res.status == "success"
        assert res.requested_end_date == date(2026, 9, 25)
        assert res.latest_available_date == date(2026, 9, 20)
        assert res.data_lag_days == 5
        assert len(res.daily_observations) == 85
        # 7-day window from 2026-09-19 to 2026-09-25 has observations on 09-19 and 09-20 (2 days)
        assert res.recent_7_days is not None
        assert res.recent_7_days.days_available == 2
        assert res.recent_7_days.is_complete is False
        # 30-day window has 25 days available
        assert res.recent_30_days is not None
        assert res.recent_30_days.days_available == 25
        assert res.recent_30_days.is_complete is False
        # 90-day window has 85 days available
        assert res.recent_90_days is not None
        assert res.recent_90_days.days_available == 85
        assert res.recent_90_days.is_complete is False

    @patch("app.environment.chirps_pipeline.fetch_raw_chirps_rainfall_timeseries")
    def test_no_data_response_pipeline(
        self,
        mock_fetch: MagicMock,
    ) -> None:
        """Verifies no_data handling conforms to DEC-020 contracts."""
        mock_fetch.return_value = EarthEngineResult(
            status="no_data",
            dataset="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
            image_count=0,
            data=[],
        )

        res = analyze_chirps_rainfall(
            latitude=30.9157,
            longitude=75.7196,
            requested_end_date="2026-09-25",
        )

        assert res.status == "no_data"
        assert res.daily_observations == []
        assert res.latest_available_date is None
        assert res.data_lag_days is None
        assert res.recent_7_days is None
        assert res.recent_30_days is None
        assert res.recent_90_days is None
        assert res.error is None

    @patch("app.environment.chirps_pipeline.fetch_raw_chirps_rainfall_timeseries")
    def test_error_response_pipeline(
        self,
        mock_fetch: MagicMock,
    ) -> None:
        """Verifies error propagation conforms to DEC-020 contracts."""
        mock_fetch.return_value = EarthEngineResult(
            status="error",
            dataset="UCSB-CHC/CHIRPS/V3/DAILY_SAT",
            image_count=None,
            data=None,
            error=EarthEngineError(
                type="EEException",
                message="Collection query timeout",
            ),
        )

        res = analyze_chirps_rainfall(
            latitude=30.9157,
            longitude=75.7196,
            requested_end_date="2026-09-25",
        )

        assert res.status == "error"
        assert res.error is not None
        assert res.error.type == "EEException"
        assert "timeout" in res.error.message.lower()
        assert res.daily_observations == []


# ============================================================================
# ARCHITECTURAL ISOLATION AUDIT
# ============================================================================


class TestArchitecturalIsolation:
    """Verifies that pure modules do not import Earth Engine (ee)."""

    def test_pure_modules_do_not_import_ee(self) -> None:
        """Ensures chirps_types, chirps_aggregation, chirps_pipeline have no ee imports."""
        import app.environment.chirps_aggregation as agg_mod
        import app.environment.chirps_pipeline as pipe_mod
        import app.environment.chirps_types as types_mod

        assert not hasattr(agg_mod, "ee")
        assert not hasattr(pipe_mod, "ee")
        assert not hasattr(types_mod, "ee")
