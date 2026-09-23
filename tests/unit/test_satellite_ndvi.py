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
"""Unit tests for NDVI band calculation and validation."""

import ee
import pytest

from app.satellite.geometry import create_analysis_region
from app.satellite.ndvi import (
    NDVI_BAND_NAME,
    NIR_BAND,
    RED_BAND,
    calculate_ndvi,
    compute_ndvi,
)


def test_ndvi_default_constants() -> None:
    """Verifies that NDVI calculation default constants match DEC-009 specifications."""
    assert NDVI_BAND_NAME == "NDVI"
    assert NIR_BAND == "B8"
    assert RED_BAND == "B4"


def test_calculate_ndvi_client_side_proxy() -> None:
    """Verifies client-side creation of ee.Image proxy without network evaluation."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)  # Synthetic un-evaluated client proxy
    ndvi = calculate_ndvi(image)
    assert isinstance(ndvi, ee.Image)


def test_calculate_ndvi_with_region_clipping() -> None:
    """Verifies client-side proxy creation of NDVI with region clipping."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    ndvi = calculate_ndvi(image, region=region)
    assert isinstance(ndvi, ee.Image)


def test_calculate_ndvi_custom_band_names() -> None:
    """Verifies client-side proxy creation with custom band and output names."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    ndvi = calculate_ndvi(
        image,
        nir_band="B8A",
        red_band="B4",
        band_name="CUSTOM_NDVI",
    )
    assert isinstance(ndvi, ee.Image)


def test_compute_ndvi_alias() -> None:
    """Verifies that compute_ndvi is a functional alias for calculate_ndvi."""
    assert compute_ndvi is calculate_ndvi


@pytest.mark.parametrize(
    "invalid_image",
    [
        None,
        "COPERNICUS/S2_SR_HARMONIZED/test",
        12345,
        3.14,
        True,
        False,
        [],
        {},
    ],
)
def test_calculate_ndvi_invalid_image_type(invalid_image) -> None:
    """Verifies that non-ee.Image inputs raise TypeError."""
    with pytest.raises(TypeError, match="image must be an instance of ee.Image"):
        calculate_ndvi(invalid_image)


@pytest.mark.parametrize(
    "invalid_region",
    [
        "not_a_geometry",
        12345,
        3.14,
        True,
        False,
        [75.7196, 30.9157],
        {"type": "Point", "coordinates": [75.7196, 30.9157]},
    ],
)
def test_calculate_ndvi_invalid_region_type(invalid_region) -> None:
    """Verifies that non-ee.Geometry region inputs raise TypeError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
        calculate_ndvi(image, region=invalid_region)


@pytest.mark.parametrize(
    "invalid_band",
    [
        "",
        "   ",
        None,
        123,
        True,
        [],
    ],
)
def test_calculate_ndvi_invalid_nir_band(invalid_band) -> None:
    """Verifies that empty or invalid nir_band parameter raises ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    with pytest.raises(ValueError, match="nir_band must be a non-empty string"):
        calculate_ndvi(image, nir_band=invalid_band)


@pytest.mark.parametrize(
    "invalid_band",
    [
        "",
        "   ",
        None,
        123,
        True,
        [],
    ],
)
def test_calculate_ndvi_invalid_red_band(invalid_band) -> None:
    """Verifies that empty or invalid red_band parameter raises ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    with pytest.raises(ValueError, match="red_band must be a non-empty string"):
        calculate_ndvi(image, red_band=invalid_band)


@pytest.mark.parametrize(
    "invalid_band",
    [
        "",
        "   ",
        None,
        123,
        True,
        [],
    ],
)
def test_calculate_ndvi_invalid_band_name(invalid_band) -> None:
    """Verifies that empty or invalid band_name parameter raises ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    with pytest.raises(ValueError, match="band_name must be a non-empty string"):
        calculate_ndvi(image, band_name=invalid_band)
