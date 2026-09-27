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
"""Multi-year historical NDVI orchestration and anomaly integration (DEC-014, DEC-017).

This module implements the Phase 2D Step 3 integration layer:
- Receives authoritative Phase 1 current observation evidence (RegionalNdviAnalysis or EarthEngineResult).
- Receives pre-materialized Phase 2C multi-year historical observations (list[AnnualHistoricalNdviObservation]).
- Delegates statistical baseline and anomaly evaluation to the pure calculation engine (baseline.py).
- Synthesizes and packages the complete HistoricalNdviAnalysis domain payload (pipeline_version="2.0.0").

Architectural Guarantees:
-------------------------
- Pure deterministic Python with zero Earth Engine, network I/O, getInfo(), or asynchronous dependencies.
- Complete evidence preservation: all requested historical target years (success, no_data, error) are retained.
- Current-year exclusion: only historical_observations contribute to baseline derivations.
- Absolute current failure precedence: errors/no_data in current observation take priority over historical availability.
- Zero mutation of input arguments.
"""

from typing import Union

from .baseline import (
    DEFAULT_REQUESTED_HISTORICAL_YEARS,
    MINIMUM_REQUIRED_HISTORICAL_YEARS,
    calculate_historical_ndvi_statistics,
)
from .types import (
    AnnualHistoricalNdviObservation,
    EarthEngineError,
    EarthEngineResult,
    HistoricalNdviAnalysis,
    RegionalNdviAnalysis,
)


def build_historical_ndvi_analysis(
    current: Union[RegionalNdviAnalysis, EarthEngineResult, None],
    historical_observations: list[AnnualHistoricalNdviObservation],
    requested_years_count: int = DEFAULT_REQUESTED_HISTORICAL_YEARS,
    minimum_required_years: int = MINIMUM_REQUIRED_HISTORICAL_YEARS,
    current_error: EarthEngineError | None = None,
) -> HistoricalNdviAnalysis:
    """Orchestrates Phase 2D multi-year historical baseline comparison and anomaly integration.

    Synthesizes current observation evidence with pre-materialized Phase 2C historical observations,
    evaluates statistical sufficiency, computes baseline central tendency and dispersion, quantifies
    spectral departures (anomalies), and returns the authoritative HistoricalNdviAnalysis.

    Args:
        current: Authoritative Phase 1 current observation payload (RegionalNdviAnalysis),
            Phase 1 pipeline result (EarthEngineResult), or None.
        historical_observations: List of Phase 2C AnnualHistoricalNdviObservation objects.
        requested_years_count: Configured historical lookback horizon (default 3).
        minimum_required_years: Minimum distinct historical years required for a baseline (default 2).
        current_error: Optional EarthEngineError if an error occurred during current acquisition.

    Returns:
        HistoricalNdviAnalysis: Strongly typed multi-year satellite intelligence payload.

    Raises:
        TypeError: If historical_observations is not a list or contains invalid items,
            or if numeric bounds are of invalid types.
        ValueError: If requested_years_count or minimum_required_years <= 0.
    """
    # 1. Validate argument types and bounds
    if not isinstance(historical_observations, list):
        raise TypeError(
            f"historical_observations must be a list, got {type(historical_observations).__name__}: {historical_observations!r}"
        )
    for i, obs in enumerate(historical_observations):
        if not isinstance(obs, AnnualHistoricalNdviObservation):
            raise TypeError(
                f"historical_observations[{i}] must be an instance of AnnualHistoricalNdviObservation, got {type(obs).__name__}: {obs!r}"
            )

    if (
        not isinstance(requested_years_count, int)
        or isinstance(requested_years_count, bool)
        or requested_years_count <= 0
    ):
        raise ValueError(
            f"requested_years_count must be a strictly positive integer (> 0), got {requested_years_count!r}"
        )

    if (
        not isinstance(minimum_required_years, int)
        or isinstance(minimum_required_years, bool)
        or minimum_required_years <= 0
    ):
        raise ValueError(
            f"minimum_required_years must be a strictly positive integer (> 0), got {minimum_required_years!r}"
        )

    # 2. Normalize Current Observation Input
    current_analysis: RegionalNdviAnalysis | None = None
    effective_error: EarthEngineError | None = current_error

    if isinstance(current, EarthEngineResult):
        if current.status == "success":
            if isinstance(current.data, RegionalNdviAnalysis):
                current_analysis = current.data
            else:
                current_analysis = None
        elif current.status == "no_data":
            current_analysis = None
        elif current.status == "error":
            current_analysis = None
            if effective_error is None:
                effective_error = current.error
    elif isinstance(current, RegionalNdviAnalysis):
        current_analysis = current
    elif current is None:
        current_analysis = None
    else:
        raise TypeError(
            f"current must be RegionalNdviAnalysis, EarthEngineResult, or None, got {type(current).__name__}: {current!r}"
        )

    # 3. Delegate Pure Statistical and Anomaly Calculations to Step 2 Engine
    baseline, sufficiency, anomaly, status, final_error = calculate_historical_ndvi_statistics(
        current=current_analysis,
        historical_observations=historical_observations,
        requested_years_count=requested_years_count,
        minimum_required_years=minimum_required_years,
        current_error=effective_error,
    )

    # 4. Construct and return authoritative HistoricalNdviAnalysis payload
    return HistoricalNdviAnalysis(
        current=current_analysis,
        historical_observations=list(historical_observations),
        baseline=baseline,
        sufficiency=sufficiency,
        anomaly=anomaly,
        status=status,
        pipeline_version="2.0.0",
        error=final_error,
    )


# Semantic alias for discoverability and ergonomic usage
analyze_historical_ndvi = build_historical_ndvi_analysis
