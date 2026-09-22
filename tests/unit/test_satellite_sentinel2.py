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
"""Unit tests for Sentinel-2 data pipeline and imagery selection."""

import math
from datetime import date, datetime, timedelta, timezone

import ee
import pytest
from pydantic import ValidationError

from app.satellite.geometry import create_analysis_region
from app.satellite.sentinel2 import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_MAX_CLOUD_PERCENTAGE,
    SENTINEL2_SR_HARMONIZED,
    _parse_date,
    get_most_recent_sentinel2_image,
    get_sentinel2_collection,
    resolve_date_range,
    select_most_recent_sentinel2_image,
)
from app.satellite.types import (
    EarthEngineResult,
    Sentinel2ImageMetadata,
)


def test_sentinel2_default_constants() -> None:
    """Verifies that Sentinel-2 pipeline default constants match DEC-008 specifications."""
    assert SENTINEL2_SR_HARMONIZED == "COPERNICUS/S2_SR_HARMONIZED"
    assert DEFAULT_LOOKBACK_DAYS == 30
    assert DEFAULT_MAX_CLOUD_PERCENTAGE == 20.0


def test_parse_date_valid_formats() -> None:
    """Verifies parsing of strings, dates, and datetimes."""
    assert _parse_date("2026-08-16") == date(2026, 8, 16)
    assert _parse_date("2026-08-16T05:50:41Z") == date(2026, 8, 16)
    assert _parse_date("2026-08-16T05:50:41+00:00") == date(2026, 8, 16)
    assert _parse_date(date(2026, 8, 16)) == date(2026, 8, 16)
    assert _parse_date(datetime(2026, 8, 16, 5, 50, 41)) == date(2026, 8, 16)


@pytest.mark.parametrize(
    "invalid_val",
    [
        "invalid-date",
        "2026-13-01",
        "2026-00-10",
        "2026-08-32",
        "",
        12345,
        None,
        True,
        [],
        {},
    ],
)
def test_parse_date_invalid_formats(invalid_val) -> None:
    """Verifies that invalid date formats raise ValueError."""
    with pytest.raises(ValueError):
        _parse_date(invalid_val)


def test_resolve_date_range_explicit_strings() -> None:
    """Verifies date range resolution with explicit start and end strings."""
    start_str, end_str = resolve_date_range("2026-08-01", "2026-08-31")
    assert start_str == "2026-08-01"
    assert end_str == "2026-08-31"


def test_resolve_date_range_lookback_calculation() -> None:
    """Verifies lookback calculation from a specified end date."""
    start_str, end_str = resolve_date_range(end_date="2026-08-31", lookback_days=10)
    assert start_str == "2026-08-21"
    assert end_str == "2026-08-31"


def test_resolve_date_range_default_today() -> None:
    """Verifies that omitted dates resolve relative to current UTC date."""
    start_str, end_str = resolve_date_range(lookback_days=30)
    today = datetime.now(timezone.utc).date()
    expected_end = today.strftime("%Y-%m-%d")
    expected_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    assert end_str == expected_end
    assert start_str == expected_start


def test_resolve_date_range_start_after_end_rejected() -> None:
    """Verifies that start_date after end_date raises ValueError."""
    with pytest.raises(ValueError, match="cannot be after end_date"):
        resolve_date_range(start_date="2026-09-01", end_date="2026-08-01")


@pytest.mark.parametrize(
    "invalid_lookback",
    [
        0,
        -1,
        -30,
        "30",
        30.5,
        None,
        True,
        False,
    ],
)
def test_resolve_date_range_invalid_lookback_days(invalid_lookback) -> None:
    """Verifies that non-positive or non-integer lookback_days raise ValueError."""
    with pytest.raises(ValueError, match="lookback_days must be a strictly positive integer"):
        resolve_date_range(lookback_days=invalid_lookback)


def test_get_sentinel2_collection_proxy_creation() -> None:
    """Verifies client-side creation of ee.ImageCollection proxy."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    collection = get_sentinel2_collection(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
    )
    assert isinstance(collection, ee.ImageCollection)


def test_get_most_recent_sentinel2_image_proxy_creation() -> None:
    """Verifies client-side creation of ee.Image proxy for the newest candidate."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        max_cloud_percentage=20.0,
    )
    assert isinstance(image, ee.Image)


@pytest.mark.parametrize(
    "invalid_region",
    [
        None,
        "not_a_geometry",
        [75.7196, 30.9157],
        {"type": "Point", "coordinates": [75.7196, 30.9157]},
        12345,
    ],
)
def test_get_sentinel2_collection_invalid_region(invalid_region) -> None:
    """Verifies that non-ee.Geometry region inputs raise TypeError."""
    with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
        get_sentinel2_collection(region=invalid_region)


@pytest.mark.parametrize(
    "invalid_cloud",
    [
        -0.1,
        -20.0,
        100.1,
        150.0,
        math.nan,
        math.inf,
        -math.inf,
        "20.0",
        None,
        True,
        False,
    ],
)
def test_get_sentinel2_collection_invalid_cloud_percentage(invalid_cloud) -> None:
    """Verifies that invalid cloud percentage values raise ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    with pytest.raises(ValueError):
        get_sentinel2_collection(region=region, max_cloud_percentage=invalid_cloud)


def test_sentinel2_image_metadata_model() -> None:
    """Verifies Sentinel2ImageMetadata Pydantic model validation and serialization."""
    metadata = Sentinel2ImageMetadata(
        image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251_20260816T055032_T43REQ",
        acquisition_date="2026-08-16T05:50:41.321000+00:00",
        cloud_percentage=10.995,
        spacecraft_name="Sentinel-2A",
        mgrs_tile="43REQ",
        product_id="S2A_MSIL2A_20260816T054251_N0511_R048_T43REQ_20260816T083432",
        system_time_start=1786859441321,
    )
    assert metadata.image_id.startswith("COPERNICUS/S2_SR_HARMONIZED/")
    assert metadata.cloud_percentage == 10.995
    assert metadata.spacecraft_name == "Sentinel-2A"

    dumped = metadata.model_dump()
    assert dumped["mgrs_tile"] == "43REQ"
    assert dumped["system_time_start"] == 1786859441321


@pytest.mark.parametrize("invalid_cloud", [-1.0, 101.0])
def test_sentinel2_image_metadata_invalid_cloud(invalid_cloud) -> None:
    """Verifies that cloud percentage outside [0, 100] raises ValidationError."""
    with pytest.raises(ValidationError):
        Sentinel2ImageMetadata(
            image_id="test_id",
            acquisition_date="2026-08-16",
            cloud_percentage=invalid_cloud,
        )


def test_select_most_recent_sentinel2_image_invalid_region_error_result() -> None:
    """Verifies that select_most_recent_sentinel2_image encapsulates exceptions into EarthEngineResult(status='error')."""
    result = select_most_recent_sentinel2_image(region="invalid_region")  # type: ignore[arg-type]
    assert isinstance(result, EarthEngineResult)
    assert result.status == "error"
    assert result.error is not None
    assert result.error.type == "TypeError"
    assert "region must be an instance of ee.Geometry" in result.error.message
