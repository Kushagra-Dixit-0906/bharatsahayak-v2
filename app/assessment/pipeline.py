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
"""Assessment orchestration pipeline for Phase 5 (DEC-023).

Coordinates multi-source evidence retrieval (via Phase 4) and delegates to the pure
deterministic reasoning engine to construct the authoritative AgriculturalAssessment.
"""

from datetime import date, datetime
from typing import Union

from app.assessment.reasoning import interpret_agricultural_evidence
from app.assessment.types import AgriculturalAssessment, AssessmentSufficiency
from app.fusion.pipeline import fetch_agricultural_environmental_evidence
from app.fusion.types import AgriculturalEnvironmentalEvidence
from app.satellite.geometry import DEFAULT_ANALYSIS_RADIUS_M
from app.satellite.historical import (
    DEFAULT_HISTORICAL_YEARS,
    DEFAULT_WINDOW_HALF_DAYS,
)
from app.satellite.types import AnalysisRegionMetadata, EarthEngineError


def evaluate_agricultural_assessment(
    evidence: AgriculturalEnvironmentalEvidence,
) -> AgriculturalAssessment:
    """Evaluates an existing AgriculturalEnvironmentalEvidence envelope to produce an AgriculturalAssessment.

    Args:
        evidence: Authoritative Phase 4 multi-source evidence envelope.

    Returns:
        AgriculturalAssessment: Structured domain assessment.
    """
    return interpret_agricultural_evidence(evidence)


def fetch_agricultural_assessment(
    latitude: float,
    longitude: float,
    reference_date: Union[date, str, datetime, None] = None,
    radius_m: float = DEFAULT_ANALYSIS_RADIUS_M,
    ndvi_lookback_days: int = 30,
    history_years: int = DEFAULT_HISTORICAL_YEARS,
    window_half_days: int = DEFAULT_WINDOW_HALF_DAYS,
    reanalysis_lookback_days: int = 90,
    rainfall_lookback_days: int = 90,
    land_cover_lookback_days: int = 30,
) -> AgriculturalAssessment:
    """Fetches multi-source evidence and performs deterministic agricultural interpretation (DEC-023).

    Args:
        latitude: Target center latitude coordinate [-90.0, 90.0].
        longitude: Target center longitude coordinate [-180.0, 180.0].
        reference_date: Anchor query reference date (UTC). Defaults to current UTC date.
        radius_m: Circular analysis region radius in meters (default 100.0m).
        ndvi_lookback_days: Retrospective lookback window for Sentinel-2 NDVI (default 30 days).
        history_years: Number of historical target years for seasonal NDVI baseline (default 3).
        window_half_days: Half-width of historical seasonal matching window (default 15 days).
        reanalysis_lookback_days: Retrospective window for ERA5-Land (default 90 days).
        rainfall_lookback_days: Retrospective window for CHIRPS rainfall (default 90 days).
        land_cover_lookback_days: Retrospective window for Dynamic World land cover (default 30 days).

    Returns:
        AgriculturalAssessment: Authoritative structured assessment envelope.
    """
    try:
        evidence = fetch_agricultural_environmental_evidence(
            latitude=latitude,
            longitude=longitude,
            reference_date=reference_date,
            radius_m=radius_m,
            ndvi_lookback_days=ndvi_lookback_days,
            history_years=history_years,
            window_half_days=window_half_days,
            reanalysis_lookback_days=reanalysis_lookback_days,
            rainfall_lookback_days=rainfall_lookback_days,
            land_cover_lookback_days=land_cover_lookback_days,
        )
        return interpret_agricultural_evidence(evidence)
    except Exception as exc:
        # Construct fallback error assessment envelope
        ref_date = date.today() if reference_date is None else (
            reference_date if isinstance(reference_date, date) else date.today()
        )
        region = AnalysisRegionMetadata(
            latitude=float(latitude) if isinstance(latitude, (int, float)) else 0.0,
            longitude=float(longitude) if isinstance(longitude, (int, float)) else 0.0,
            radius_m=float(radius_m) if isinstance(radius_m, (int, float)) else 100.0,
            geometry_type="PointBuffer",
            scale_m=10.0,
        )
        # Attempt to retrieve fallback evidence from Phase 4 if available
        fallback_evidence = fetch_agricultural_environmental_evidence(
            latitude=0.0, longitude=0.0, reference_date=ref_date
        ) if False else None  # Avoid recursive calls on error

        raise exc
