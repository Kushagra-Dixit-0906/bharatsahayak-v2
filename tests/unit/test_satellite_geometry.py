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
"""Unit tests for satellite geometry helpers and analysis region creation (DEC-007)."""

import os

import ee
import pytest

from app.satellite.geometry import (
    DEFAULT_ANALYSIS_RADIUS_M,
    create_analysis_region,
)

# Test fixture coordinates: Farmland near Ludhiana, Punjab
PUNJAB_LATITUDE = 30.9157
PUNJAB_LONGITUDE = 75.7196


@pytest.fixture(scope="module", autouse=True)
def ee_init() -> None:
    """Initializes Earth Engine for geometry instantiation or skips if unavailable."""
    project_id = os.environ.get("EE_PROJECT_ID", "bharatsahayak-v2")
    try:
        ee.Initialize(project=project_id)
    except Exception as exc:
        pytest.skip(
            f"Earth Engine authentication not available or initialization failed: {exc}"
        )


def test_create_analysis_region_valid_punjab() -> None:
    """Test creating an analysis region with default radius for Punjab coordinates."""
    region = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
    )
    assert isinstance(region, ee.Geometry)
    assert region.name() == "Geometry"


def test_create_analysis_region_custom_radius() -> None:
    """Test creating an analysis region with a custom positive radius (e.g. 250m, 50m)."""
    region_250m = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=250.0,
    )
    assert isinstance(region_250m, ee.Geometry)

    region_50m = create_analysis_region(
        latitude=PUNJAB_LATITUDE,
        longitude=PUNJAB_LONGITUDE,
        radius_m=50,
    )
    assert isinstance(region_50m, ee.Geometry)


def test_create_analysis_region_boundary_coordinates() -> None:
    """Test creating analysis regions at valid coordinate limits [-90, 90] and [-180, 180]."""
    region_max = create_analysis_region(latitude=90.0, longitude=180.0)
    assert isinstance(region_max, ee.Geometry)

    region_min = create_analysis_region(latitude=-90.0, longitude=-180.0)
    assert isinstance(region_min, ee.Geometry)

    region_equator = create_analysis_region(latitude=0.0, longitude=0.0)
    assert isinstance(region_equator, ee.Geometry)


@pytest.mark.parametrize(
    "invalid_lat",
    [
        90.0001,
        -90.0001,
        150.0,
        -100.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        "30.9157",
        None,
        True,
    ],
)
def test_create_analysis_region_invalid_latitude(invalid_lat: object) -> None:
    """Test that latitude values outside [-90, 90] or non-finite types raise ValueError."""
    with pytest.raises(ValueError, match="Latitude"):
        create_analysis_region(
            latitude=invalid_lat,  # type: ignore[arg-type]
            longitude=PUNJAB_LONGITUDE,
        )


@pytest.mark.parametrize(
    "invalid_lon",
    [
        180.0001,
        -180.0001,
        200.0,
        -250.0,
        float("nan"),
        float("inf"),
        float("-inf"),
        "75.7196",
        None,
        False,
    ],
)
def test_create_analysis_region_invalid_longitude(invalid_lon: object) -> None:
    """Test that longitude values outside [-180, 180] or non-finite types raise ValueError."""
    with pytest.raises(ValueError, match="Longitude"):
        create_analysis_region(
            latitude=PUNJAB_LATITUDE,
            longitude=invalid_lon,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "invalid_radius",
    [
        0,
        0.0,
        -1,
        -100.0,
        -0.0001,
        float("nan"),
        float("inf"),
        float("-inf"),
        "100",
        None,
        True,
    ],
)
def test_create_analysis_region_invalid_radius(invalid_radius: object) -> None:
    """Test that radius_m <= 0 or non-finite/non-numeric values raise ValueError."""
    with pytest.raises(ValueError, match="Radius"):
        create_analysis_region(
            latitude=PUNJAB_LATITUDE,
            longitude=PUNJAB_LONGITUDE,
            radius_m=invalid_radius,  # type: ignore[arg-type]
        )


def test_default_analysis_radius_constant() -> None:
    """Test that the default analysis radius constant is set to 100 meters per DEC-007."""
    assert DEFAULT_ANALYSIS_RADIUS_M == 100.0
