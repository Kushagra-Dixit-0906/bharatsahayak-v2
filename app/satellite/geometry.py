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
"""Geographic geometry helpers for satellite analysis regions.

This module implements the spatial geometry abstraction defined in DEC-007
(Geographic Analysis Region Strategy).

Architectural Concepts:
-----------------------
- FarmerLocation:
    The original point coordinate (latitude, longitude) selected by or resolved
    for the farmer via GPS geolocation, map place search, or interactive pin-drop.
    Farmers are never required to manually type coordinates or draw polygons.

- Region Resolution:
    The intermediate transformation translating a FarmerLocation point into an
    operational AnalysisRegion for Earth Engine processing.

- AnalysisRegion:
    The derived Earth Engine spatial geometry (initially a circular buffer)
    used for spatial filtering and zonal statistical reductions (e.g. NDVI mean,
    median, min, max).

Important Limitation & Boundary Notice:
---------------------------------------
The default 100-meter circular buffer is an engineering choice for local
satellite data sampling, NOT an exact farm boundary. It represents an
approximate local observation area that may sample neighboring plots, field
bunds, farm roads, irrigation channels, trees, or rural structures. It must
NEVER be represented or described to the farmer as their exact cadastral, legal,
or revenue parcel boundary.
"""

import math
from typing import Union

import ee

# Default radius in meters for the circular analysis buffer (DEC-007)
DEFAULT_ANALYSIS_RADIUS_M: float = 100.0


def create_analysis_region(
    latitude: Union[int, float],
    longitude: Union[int, float],
    radius_m: Union[int, float] = DEFAULT_ANALYSIS_RADIUS_M,
) -> ee.Geometry:
    """Creates a circular analysis region geometry centered on a farmer's location.

    Converts a point location (latitude, longitude) into a circular buffer
    geometry in Google Earth Engine suitable for spatial filtering and zonal
    statistical reductions (DEC-007).

    Args:
        latitude: Latitude coordinate in decimal degrees, must be in [-90, 90].
        longitude: Longitude coordinate in decimal degrees, must be in [-180, 180].
        radius_m: Buffer radius in meters, must be strictly positive (> 0).
            Defaults to 100.0 meters.

    Returns:
        ee.Geometry: An Earth Engine circular buffer geometry centered at
            [longitude, latitude].

    Raises:
        ValueError: If latitude, longitude, or radius_m are out of valid bounds
            or non-finite numbers.
    """
    if (
        not isinstance(latitude, (int, float))
        or isinstance(latitude, bool)
        or math.isnan(latitude)
        or math.isinf(latitude)
    ):
        raise ValueError(
            f"Latitude must be a valid finite number, got {latitude!r}"
        )
    if not (-90.0 <= float(latitude) <= 90.0):
        raise ValueError(
            f"Latitude must be between -90 and 90 degrees, got {latitude}"
        )

    if (
        not isinstance(longitude, (int, float))
        or isinstance(longitude, bool)
        or math.isnan(longitude)
        or math.isinf(longitude)
    ):
        raise ValueError(
            f"Longitude must be a valid finite number, got {longitude!r}"
        )
    if not (-180.0 <= float(longitude) <= 180.0):
        raise ValueError(
            f"Longitude must be between -180 and 180 degrees, got {longitude}"
        )

    if (
        not isinstance(radius_m, (int, float))
        or isinstance(radius_m, bool)
        or math.isnan(radius_m)
        or math.isinf(radius_m)
    ):
        raise ValueError(
            f"Radius must be a valid finite number, got {radius_m!r}"
        )
    if float(radius_m) <= 0.0:
        raise ValueError(
            f"Radius must be strictly positive (> 0 meters), got {radius_m}"
        )

    # Earth Engine expects coordinates in [longitude, latitude] (x, y) order
    point = ee.Geometry.Point([float(longitude), float(latitude)])
    return point.buffer(float(radius_m))
