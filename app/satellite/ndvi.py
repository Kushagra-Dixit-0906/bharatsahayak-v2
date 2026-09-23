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
"""Normalized Difference Vegetation Index (NDVI) calculation for Sentinel-2 imagery.

This module implements the NDVI computation strategy defined in DEC-009
(Phase 1F — NDVI Calculation).

Architectural Responsibilities:
-------------------------------
1. Consumes a selected Sentinel-2 Surface Reflectance image (ee.Image) from Phase 1E.
2. Applies normalized difference band mathematics:
       NDVI = (NIR - Red) / (NIR + Red) = (B8 - B4) / (B8 + B4)
   using Earth Engine's native `image.normalizedDifference(['B8', 'B4'])`.
3. Renames the output band to 'NDVI'.
4. Optionally clips the resulting raster extent to the AnalysisRegion (ee.Geometry).
5. Preserves invalid and masked pixels (zero denominator or sensor masked) without
   inventing artificial zero or null replacement values.
6. Returns an un-evaluated ee.Image proxy containing the NDVI band for downstream
   zonal reduction in Phase 1G.

Important Scope Boundaries:
---------------------------
- Reflectance scale factors (0.0001) are not manually multiplied since multiplicative
  constants cancel out identically in normalized ratios:
      (0.0001*B8 - 0.0001*B4) / (0.0001*B8 + 0.0001*B4) == (B8 - B4) / (B8 + B4)
- Zonal statistical reductions (mean, median, min, max) are NOT performed here (Phase 1G).
- Crop-health interpretations and arbitrary thresholds (e.g. NDVI > 0.5 = healthy) are
  strictly prohibited.
- Pixel-level cloud masking (QA60/SCL) is deferred; Phase 1E's scene-level filter
  (CLOUDY_PIXEL_PERCENTAGE < 20%) remains active.
- The 100m circular AnalysisRegion is an approximate local satellite observation area,
  NOT an exact cadastral farm parcel boundary.
"""

from typing import Union

import ee

# Standard band names for Sentinel-2 Level-2A (DEC-009)
NIR_BAND: str = "B8"
RED_BAND: str = "B4"

# Canonical output band name for NDVI
NDVI_BAND_NAME: str = "NDVI"


def calculate_ndvi(
    image: ee.Image,
    region: Union[ee.Geometry, None] = None,
    nir_band: str = NIR_BAND,
    red_band: str = RED_BAND,
    band_name: str = NDVI_BAND_NAME,
) -> ee.Image:
    """Calculates Normalized Difference Vegetation Index (NDVI) from a Sentinel-2 image.

    Applies the normalized difference index ((NIR - Red) / (NIR + Red)) using
    Earth Engine's native `normalizedDifference` method and renames the resulting
    band to 'NDVI' (DEC-009).

    Optionally clips the resulting raster to the provided AnalysisRegion geometry.

    Args:
        image: Earth Engine Sentinel-2 image proxy (ee.Image) containing NIR and Red bands.
        region: Optional Earth Engine spatial geometry (ee.Geometry) to clip the NDVI raster.
        nir_band: Name of the Near-Infrared band. Defaults to 'B8'.
        red_band: Name of the Red band. Defaults to 'B4'.
        band_name: Name for the computed output band. Defaults to 'NDVI'.

    Returns:
        ee.Image: Earth Engine image containing the single computed NDVI band, optionally
            clipped to the specified region.

    Raises:
        TypeError: If image is not an ee.Image or if region is provided but not an ee.Geometry.
        ValueError: If nir_band, red_band, or band_name are empty or non-string values.
    """
    if not isinstance(image, ee.Image):
        raise TypeError(
            f"image must be an instance of ee.Image, got {type(image)!r}"
        )

    if region is not None and not isinstance(region, ee.Geometry):
        raise TypeError(
            f"region must be an instance of ee.Geometry, got {type(region)!r}"
        )

    if not isinstance(nir_band, str) or not nir_band.strip():
        raise ValueError(
            f"nir_band must be a non-empty string, got {nir_band!r}"
        )

    if not isinstance(red_band, str) or not red_band.strip():
        raise ValueError(
            f"red_band must be a non-empty string, got {red_band!r}"
        )

    if not isinstance(band_name, str) or not band_name.strip():
        raise ValueError(
            f"band_name must be a non-empty string, got {band_name!r}"
        )

    ndvi = image.normalizedDifference([nir_band, red_band]).rename(band_name)

    if region is not None:
        ndvi = ndvi.clip(region)

    return ndvi


# Semantic alias
compute_ndvi = calculate_ndvi
