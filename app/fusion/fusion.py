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
"""Pure local assembly and status resolution engine for multi-source evidence fusion (DEC-022).

This module contains ZERO Earth Engine imports, ZERO network I/O, and ZERO external API dependencies.
It evaluates subsystem availability, resolves operational fusion status, validates invariants,
and constructs the authoritative immutable AgriculturalEnvironmentalEvidence envelope.
"""

from datetime import date, datetime
from typing import Union

from app.environment.chirps_types import CHIRPSRainfallAnalysis
from app.environment.dynamic_world_types import DynamicWorldAnalysis
from app.environment.types import ERA5LandAnalysis
from app.fusion.types import AgriculturalEnvironmentalEvidence, FusionStatus
from app.satellite.types import (
    AnalysisRegionMetadata,
    EarthEngineError,
    HistoricalNdviAnalysis,
)


def _parse_reference_date(reference_date: Union[date, str, datetime]) -> date:
    """Parses and normalizes the authoritative reference date to a UTC date object."""
    if reference_date is None:
        raise TypeError("reference_date cannot be None")
    if isinstance(reference_date, datetime):
        return reference_date.date()
    if isinstance(reference_date, date):
        return reference_date
    if isinstance(reference_date, str):
        cleaned = reference_date.strip()
        if "T" in cleaned:
            cleaned = cleaned.split("T")[0]
        try:
            return datetime.strptime(cleaned, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid reference_date format '{reference_date}', expected 'YYYY-MM-DD' or ISO 8601 string."
            ) from exc
    raise TypeError(f"Unsupported reference_date type {type(reference_date)!r}: {reference_date!r}")


def fuse_agricultural_environmental_evidence(
    reference_date: Union[date, str, datetime],
    region: AnalysisRegionMetadata,
    vegetation: HistoricalNdviAnalysis,
    reanalysis: ERA5LandAnalysis,
    rainfall: CHIRPSRainfallAnalysis,
    land_cover: DynamicWorldAnalysis,
    error: EarthEngineError | None = None,
) -> AgriculturalEnvironmentalEvidence:
    """Deterministically fuses multi-source remote-sensing and environmental intelligence payloads.

    Pure offline function that evaluates the availability states of all 4 evidence subsystems,
    determines the overall fusion status (success, partial, no_data, error), tallies available
    and fully available source counts, and constructs the immutable AgriculturalEnvironmentalEvidence envelope.

    Args:
        reference_date: Authoritative UTC query anchor date (date, datetime, or ISO string).
        region: Geographic footprint and circular parcel buffer metadata.
        vegetation: Historical seasonal NDVI analysis containing current vigor and baseline.
        reanalysis: ERA5-Land daily reanalysis environmental context.
        rainfall: CHIRPS daily precipitation context.
        land_cover: Dynamic World 9-class land-cover context.
        error: Optional top-level error if an orchestrator-level failure occurred.

    Returns:
        AgriculturalEnvironmentalEvidence: Immutable, validated multi-source evidence envelope.

    Raises:
        TypeError: If any input domain object is of an invalid type.
        ValueError: If input date is malformed or invariants are violated.
    """
    # 1. Type Validation
    norm_ref_date = _parse_reference_date(reference_date)

    if not isinstance(region, AnalysisRegionMetadata):
        raise TypeError(f"region must be an AnalysisRegionMetadata instance, got {type(region)!r}")
    if not isinstance(vegetation, HistoricalNdviAnalysis):
        raise TypeError(f"vegetation must be a HistoricalNdviAnalysis instance, got {type(vegetation)!r}")
    if not isinstance(reanalysis, ERA5LandAnalysis):
        raise TypeError(f"reanalysis must be an ERA5LandAnalysis instance, got {type(reanalysis)!r}")
    if not isinstance(rainfall, CHIRPSRainfallAnalysis):
        raise TypeError(f"rainfall must be a CHIRPSRainfallAnalysis instance, got {type(rainfall)!r}")
    if not isinstance(land_cover, DynamicWorldAnalysis):
        raise TypeError(f"land_cover must be a DynamicWorldAnalysis instance, got {type(land_cover)!r}")
    if error is not None and not isinstance(error, EarthEngineError):
        raise TypeError(f"error must be an EarthEngineError instance or None, got {type(error)!r}")

    # 2. Subsystem Availability Evaluation
    veg_full = (vegetation.status == "success")
    veg_usable = (vegetation.status in ("success", "insufficient_history"))

    rean_full = (reanalysis.status == "success")
    rean_usable = rean_full

    rain_full = (rainfall.status == "success")
    rain_usable = rain_full

    lc_full = (land_cover.status == "success")
    lc_usable = lc_full

    sources_requested_count = 4
    sources_fully_available_count = int(veg_full) + int(rean_full) + int(rain_full) + int(lc_full)
    sources_available_count = int(veg_usable) + int(rean_usable) + int(rain_usable) + int(lc_usable)
    is_fully_available = (sources_fully_available_count == sources_requested_count)

    # 3. Overall Status Resolution
    status: FusionStatus
    if error is not None and sources_available_count == 0:
        status = "error"
    elif sources_fully_available_count == sources_requested_count:
        status = "success"
    elif sources_available_count >= 1:
        status = "partial"
    else:
        # Zero usable sources
        subsystem_statuses = (vegetation.status, reanalysis.status, rainfall.status, land_cover.status)
        if any(s == "error" for s in subsystem_statuses) or error is not None:
            status = "error"
        else:
            status = "no_data"

    # 4. Construct Immutable Envelope
    return AgriculturalEnvironmentalEvidence(
        region=region,
        reference_date=norm_ref_date,
        vegetation=vegetation,
        reanalysis=reanalysis,
        rainfall=rainfall,
        land_cover=land_cover,
        status=status,
        sources_requested_count=sources_requested_count,
        sources_available_count=sources_available_count,
        sources_fully_available_count=sources_fully_available_count,
        is_fully_available=is_fully_available,
        pipeline_version="4.0.0",
        error=error,
    )
