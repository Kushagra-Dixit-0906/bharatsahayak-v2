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
"""Environmental data sources module for BharatSahayak (Phase 3)."""

from app.environment.aggregation import (
    aggregate_window_statistics,
    compute_environmental_window_suite,
)
from app.environment.chirps import (
    CHIRPS_BANDS,
    CHIRPS_DATASET,
    CHIRPS_NOMINAL_SCALE_M,
    DEFAULT_LOOKBACK_DAYS as CHIRPS_DEFAULT_LOOKBACK_DAYS,
    fetch_raw_chirps_rainfall_timeseries,
)
from app.environment.chirps_aggregation import (
    aggregate_rainfall_window_statistics,
    compute_rainfall_window_suite,
)
from app.environment.chirps_pipeline import (
    analyze_chirps_rainfall,
    normalize_raw_chirps_record,
)
from app.environment.chirps_types import (
    CHIRPSRainfallAnalysis,
    DailyRainfallObservation,
    RainfallWindowStatistics,
)
from app.environment.era5 import (
    fetch_raw_era5_land_timeseries,
)
from app.environment.pipeline import (
    analyze_era5_land,
    normalize_raw_era5_record,
)
from app.environment.types import (
    DailyEnvironmentalObservation,
    EnvironmentalWindowStatistics,
    ERA5LandAnalysis,
)

__all__ = [
    # Phase 3A: ERA5-Land
    "DailyEnvironmentalObservation",
    "EnvironmentalWindowStatistics",
    "ERA5LandAnalysis",
    "aggregate_window_statistics",
    "analyze_era5_land",
    "compute_environmental_window_suite",
    "fetch_raw_era5_land_timeseries",
    "normalize_raw_era5_record",
    # Phase 3B: CHIRPS Rainfall Backup
    "CHIRPSRainfallAnalysis",
    "CHIRPS_BANDS",
    "CHIRPS_DATASET",
    "CHIRPS_DEFAULT_LOOKBACK_DAYS",
    "CHIRPS_NOMINAL_SCALE_M",
    "DailyRainfallObservation",
    "RainfallWindowStatistics",
    "aggregate_rainfall_window_statistics",
    "analyze_chirps_rainfall",
    "compute_rainfall_window_suite",
    "fetch_raw_chirps_rainfall_timeseries",
    "normalize_raw_chirps_record",
]


