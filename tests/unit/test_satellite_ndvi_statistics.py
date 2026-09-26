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
"""Unit tests for regional NDVI summary statistics calculation (DEC-002, Phase 1G)."""

import math
from unittest.mock import MagicMock, patch

import ee
import pytest
from pydantic import ValidationError

from app.satellite.geometry import create_analysis_region
from app.satellite.ndvi import (
    NDVI_BAND_NAME,
    calculate_ndvi_statistics,
    compute_ndvi_statistics,
)
from app.satellite.types import (
    EarthEngineResult,
    NdviRegionalStatistics,
)


@pytest.mark.parametrize(
    "invalid_image",
    [
        None,
        "not_an_image",
        12345,
        3.14,
        True,
        False,
        [],
        {},
    ],
)
def test_calculate_ndvi_statistics_invalid_image_type(invalid_image) -> None:
    """Verifies that non-ee.Image inputs raise TypeError directly."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    with pytest.raises(TypeError, match="ndvi_image must be an instance of ee.Image"):
        calculate_ndvi_statistics(invalid_image, region=region)


@pytest.mark.parametrize(
    "invalid_region",
    [
        None,
        "not_a_geometry",
        12345,
        3.14,
        True,
        False,
        [75.7196, 30.9157],
        {"type": "Point", "coordinates": [75.7196, 30.9157]},
    ],
)
def test_calculate_ndvi_statistics_invalid_region_type(invalid_region) -> None:
    """Verifies that non-ee.Geometry region inputs raise TypeError directly."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename("NDVI")
    with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
        calculate_ndvi_statistics(image, region=invalid_region)


@pytest.mark.parametrize(
    "invalid_scale",
    [
        0,
        0.0,
        -1,
        -10.0,
        math.nan,
        math.inf,
        -math.inf,
        "10",
        None,
        True,
        False,
        [],
        {},
    ],
)
def test_calculate_ndvi_statistics_invalid_scale(invalid_scale) -> None:
    """Verifies that non-positive, boolean, NaN, or non-numeric scale raises ValueError directly."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename("NDVI")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    with pytest.raises(ValueError):
        calculate_ndvi_statistics(image, region=region, scale=invalid_scale)


@pytest.mark.parametrize(
    "invalid_band",
    [
        "",
        "   ",
        None,
        123,
        True,
        False,
        [],
        {},
    ],
)
def test_calculate_ndvi_statistics_invalid_band_name(invalid_band) -> None:
    """Verifies that empty, whitespace, or non-string band names raise ValueError directly."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename("NDVI")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    with pytest.raises(ValueError):
        calculate_ndvi_statistics(image, region=region, band_name=invalid_band)


def test_compute_ndvi_statistics_alias() -> None:
    """Verifies that compute_ndvi_statistics is an exact functional alias."""
    assert compute_ndvi_statistics is calculate_ndvi_statistics


def test_ndvi_regional_statistics_model_valid() -> None:
    """Verifies valid instantiation and serialization of NdviRegionalStatistics."""
    stats = NdviRegionalStatistics(
        mean=0.521,
        median=0.518,
        min=0.142,
        max=0.875,
        valid_pixel_count=314,
    )
    assert stats.mean == 0.521
    assert stats.median == 0.518
    assert stats.min == 0.142
    assert stats.max == 0.875
    assert stats.valid_pixel_count == 314

    dumped = stats.model_dump()
    assert dumped["mean"] == 0.521
    assert dumped["valid_pixel_count"] == 314


@pytest.mark.parametrize(
    ("field", "bad_val"),
    [
        ("mean", -1.01),
        ("mean", 1.01),
        ("median", -1.5),
        ("median", 1.5),
        ("min", -2.0),
        ("min", 1.1),
        ("max", -1.1),
        ("max", 2.0),
    ],
)
def test_ndvi_regional_statistics_model_invalid_bounds(field, bad_val) -> None:
    """Verifies that values outside [-1.0, 1.0] raise ValidationError."""
    data = {"mean": 0.5, "median": 0.5, "min": 0.1, "max": 0.8, "valid_pixel_count": 100}
    data[field] = bad_val
    with pytest.raises(ValidationError):
        NdviRegionalStatistics(**data)


def test_ndvi_regional_statistics_model_negative_count() -> None:
    """Verifies that negative valid_pixel_count raises ValidationError."""
    with pytest.raises(ValidationError):
        NdviRegionalStatistics(
            mean=0.5,
            median=0.5,
            min=0.1,
            max=0.8,
            valid_pixel_count=-1,
        )


def test_calculate_ndvi_statistics_mocked_success() -> None:
    """Verifies successful reduction mapping from mock Earth Engine dictionary to NdviRegionalStatistics."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename(NDVI_BAND_NAME)
    region = create_analysis_region(30.9157, 75.7196, 100.0)

    mock_stats = {
        "NDVI_mean": 0.554,
        "NDVI_median": 0.550,
        "NDVI_min": 0.210,
        "NDVI_max": 0.820,
        "NDVI_count": 314,
    }

    with patch.object(ee.Dictionary, "getInfo", return_value=mock_stats):
        result = calculate_ndvi_statistics(image, region=region, scale=10)

    assert isinstance(result, EarthEngineResult)
    assert result.status == "success"
    assert result.error is None
    assert isinstance(result.data, NdviRegionalStatistics)
    assert result.data.mean == 0.554
    assert result.data.median == 0.550
    assert result.data.min == 0.210
    assert result.data.max == 0.820
    assert result.data.valid_pixel_count == 314


def test_calculate_ndvi_statistics_mocked_no_data_empty() -> None:
    """Verifies that empty reducer dictionary produces status='no_data'."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename(NDVI_BAND_NAME)
    region = create_analysis_region(30.9157, 75.7196, 100.0)

    with patch.object(ee.Dictionary, "getInfo", return_value={}):
        result = calculate_ndvi_statistics(image, region=region, scale=10)

    assert isinstance(result, EarthEngineResult)
    assert result.status == "no_data"
    assert result.data is None
    assert result.error is None


def test_calculate_ndvi_statistics_mocked_no_data_null_mean() -> None:
    """Verifies that null mean in reduction produces status='no_data'."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename(NDVI_BAND_NAME)
    region = create_analysis_region(30.9157, 75.7196, 100.0)

    mock_stats = {
        "NDVI_mean": None,
        "NDVI_median": None,
        "NDVI_min": None,
        "NDVI_max": None,
        "NDVI_count": 0,
    }

    with patch.object(ee.Dictionary, "getInfo", return_value=mock_stats):
        result = calculate_ndvi_statistics(image, region=region, scale=10)

    assert isinstance(result, EarthEngineResult)
    assert result.status == "no_data"
    assert result.data is None
    assert result.error is None


def test_calculate_ndvi_statistics_mocked_no_data_zero_count() -> None:
    """Verifies that valid_pixel_count == 0 produces status='no_data'."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename(NDVI_BAND_NAME)
    region = create_analysis_region(30.9157, 75.7196, 100.0)

    mock_stats = {
        "NDVI_mean": 0.5,
        "NDVI_median": 0.5,
        "NDVI_min": 0.5,
        "NDVI_max": 0.5,
        "NDVI_count": 0,
    }

    with patch.object(ee.Dictionary, "getInfo", return_value=mock_stats):
        result = calculate_ndvi_statistics(image, region=region, scale=10)

    assert isinstance(result, EarthEngineResult)
    assert result.status == "no_data"
    assert result.data is None
    assert result.error is None


def test_calculate_ndvi_statistics_mocked_remote_error() -> None:
    """Verifies that remote Earth Engine exceptions are mapped to status='error'."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename(NDVI_BAND_NAME)
    region = create_analysis_region(30.9157, 75.7196, 100.0)

    with patch.object(ee.Dictionary, "getInfo", side_effect=ee.EEException("Computation timed out")):
        result = calculate_ndvi_statistics(image, region=region, scale=10)

    assert isinstance(result, EarthEngineResult)
    assert result.status == "error"
    assert result.data is None
    assert result.error is not None
    assert result.error.type == "EEException"
    assert "Computation timed out" in result.error.message
