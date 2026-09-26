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
"""Unit tests for Sentinel-2 observation quality filtering using Cloud Score+ (DEC-010)."""

import math

import ee
import pytest
from pydantic import ValidationError

from app.satellite.geometry import create_analysis_region
from app.satellite.sentinel2 import (
    CLOUD_SCORE_PLUS_S2_HARMONIZED,
    DEFAULT_CLEAR_THRESHOLD,
    DEFAULT_MIN_USABLE_COVERAGE,
    DEFAULT_QUALITY_BAND,
    calculate_usable_coverage,
    get_most_recent_sentinel2_image,
    get_sentinel2_collection,
    mask_observation_quality,
)
from app.satellite.types import (
    Sentinel2ImageMetadata,
)


def test_observation_quality_default_constants() -> None:
    """Verifies that Cloud Score+ observation quality constants match DEC-010 specifications."""
    assert CLOUD_SCORE_PLUS_S2_HARMONIZED == "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
    assert DEFAULT_QUALITY_BAND == "cs_cdf"
    assert DEFAULT_CLEAR_THRESHOLD == 0.60
    assert DEFAULT_MIN_USABLE_COVERAGE == 0.70


@pytest.mark.parametrize(
    "invalid_threshold",
    [
        -0.01,
        -1.0,
        1.01,
        2.0,
        math.nan,
        math.inf,
        -math.inf,
        "0.60",
        None,
        True,
        False,
        [],
        {},
    ],
)
def test_mask_observation_quality_invalid_clear_threshold(invalid_threshold) -> None:
    """Verifies that invalid clear_threshold inputs raise ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    with pytest.raises(ValueError):
        mask_observation_quality(image, clear_threshold=invalid_threshold)


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
def test_mask_observation_quality_invalid_quality_band(invalid_band) -> None:
    """Verifies that invalid quality_band inputs raise ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1)
    with pytest.raises(ValueError):
        mask_observation_quality(image, quality_band=invalid_band)


@pytest.mark.parametrize(
    "invalid_image",
    [
        None,
        "not_an_image",
        123,
        3.14,
        True,
        [],
        {},
    ],
)
def test_mask_observation_quality_invalid_image_type(invalid_image) -> None:
    """Verifies that non-ee.Image inputs raise TypeError."""
    with pytest.raises(TypeError, match="image must be an instance of ee.Image"):
        mask_observation_quality(invalid_image)


def test_mask_observation_quality_proxy_creation() -> None:
    """Verifies client-side creation of quality-masked ee.Image proxy without network call."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename("cs_cdf")
    masked = mask_observation_quality(image, clear_threshold=0.60, quality_band="cs_cdf")
    assert isinstance(masked, ee.Image)


def test_calculate_usable_coverage_proxy_creation() -> None:
    """Verifies client-side creation of usable coverage ee.Number proxy without network call."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename("cs_cdf")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    coverage = calculate_usable_coverage(image, region=region, clear_threshold=0.60)
    assert isinstance(coverage, ee.Number)


@pytest.mark.parametrize(
    "invalid_region",
    [
        None,
        "not_a_geometry",
        123,
        [75.7196, 30.9157],
    ],
)
def test_calculate_usable_coverage_invalid_region_type(invalid_region) -> None:
    """Verifies that non-ee.Geometry region inputs raise TypeError."""
    ee.Initialize(project="bharatsahayak-v2")
    image = ee.Image(1).rename("cs_cdf")
    with pytest.raises(TypeError, match="region must be an instance of ee.Geometry"):
        calculate_usable_coverage(image, region=invalid_region)


@pytest.mark.parametrize(
    "invalid_coverage",
    [
        -0.01,
        -1.0,
        1.01,
        1.5,
        math.nan,
        math.inf,
        -math.inf,
        "0.70",
        None,
        True,
        False,
        [],
        {},
    ],
)
def test_get_sentinel2_collection_invalid_min_usable_coverage(invalid_coverage) -> None:
    """Verifies that invalid min_usable_coverage inputs raise ValueError."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    with pytest.raises(ValueError):
        get_sentinel2_collection(region=region, min_usable_coverage=invalid_coverage)


def test_get_sentinel2_collection_with_quality_filter_proxy() -> None:
    """Verifies client-side creation of quality-linked ee.ImageCollection proxy."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    collection = get_sentinel2_collection(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        clear_threshold=0.60,
        min_usable_coverage=0.70,
        apply_quality_filter=True,
    )
    assert isinstance(collection, ee.ImageCollection)


def test_get_most_recent_sentinel2_image_with_quality_mask_proxy() -> None:
    """Verifies client-side creation of quality-masked ee.Image proxy."""
    ee.Initialize(project="bharatsahayak-v2")
    region = create_analysis_region(30.9157, 75.7196, 100.0)
    image = get_most_recent_sentinel2_image(
        region=region,
        start_date="2026-08-01",
        end_date="2026-08-31",
        clear_threshold=0.60,
        min_usable_coverage=0.70,
        apply_quality_mask=True,
    )
    assert isinstance(image, ee.Image)


def test_sentinel2_image_metadata_with_quality_fields() -> None:
    """Verifies Sentinel2ImageMetadata model with observation quality fields."""
    metadata = Sentinel2ImageMetadata(
        image_id="COPERNICUS/S2_SR_HARMONIZED/20260816T054251_20260816T055032_T43REQ",
        acquisition_date="2026-08-16T05:50:41.321000+00:00",
        cloud_percentage=10.995,
        spacecraft_name="Sentinel-2A",
        mgrs_tile="43REQ",
        product_id="S2A_MSIL2A_20260816T054251_N0511_R048_T43REQ_20260816T083432",
        system_time_start=1786859441321,
        usable_coverage_percentage=94.50,
        clear_threshold=0.60,
        quality_band="cs_cdf",
    )
    assert metadata.usable_coverage_percentage == 94.50
    assert metadata.clear_threshold == 0.60
    assert metadata.quality_band == "cs_cdf"

    dumped = metadata.model_dump()
    assert dumped["usable_coverage_percentage"] == 94.50
    assert dumped["clear_threshold"] == 0.60
    assert dumped["quality_band"] == "cs_cdf"


def test_sentinel2_image_metadata_without_quality_fields_backward_compat() -> None:
    """Verifies Sentinel2ImageMetadata backward compatibility when quality fields are omitted."""
    metadata = Sentinel2ImageMetadata(
        image_id="test_id",
        acquisition_date="2026-08-16",
        cloud_percentage=15.0,
    )
    assert metadata.usable_coverage_percentage is None
    assert metadata.clear_threshold is None
    assert metadata.quality_band is None


@pytest.mark.parametrize("invalid_cov", [-1.0, 100.1])
def test_sentinel2_image_metadata_invalid_coverage_percentage(invalid_cov) -> None:
    """Verifies that usable_coverage_percentage outside [0.0, 100.0] raises ValidationError."""
    with pytest.raises(ValidationError):
        Sentinel2ImageMetadata(
            image_id="test_id",
            acquisition_date="2026-08-16",
            cloud_percentage=10.0,
            usable_coverage_percentage=invalid_cov,
        )


@pytest.mark.parametrize("invalid_thresh", [-0.1, 1.1])
def test_sentinel2_image_metadata_invalid_clear_threshold(invalid_thresh) -> None:
    """Verifies that clear_threshold outside [0.0, 1.0] raises ValidationError."""
    with pytest.raises(ValidationError):
        Sentinel2ImageMetadata(
            image_id="test_id",
            acquisition_date="2026-08-16",
            cloud_percentage=10.0,
            clear_threshold=invalid_thresh,
        )
