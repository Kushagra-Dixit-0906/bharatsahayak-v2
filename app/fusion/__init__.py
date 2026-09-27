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
"""Phase 4 Multi-Source Evidence Fusion package (DEC-022).

This package unifies independent remote-sensing and environmental intelligence streams
(Sentinel-2 NDVI, Historical NDVI Baseline, ERA5-Land Reanalysis, CHIRPS Precipitation,
and Dynamic World Land Cover) into an immutable, strongly typed evidence envelope.
"""

from .fusion import fuse_agricultural_environmental_evidence
from .pipeline import fetch_agricultural_environmental_evidence
from .types import AgriculturalEnvironmentalEvidence, FusionStatus

__all__ = [
    "AgriculturalEnvironmentalEvidence",
    "FusionStatus",
    "fetch_agricultural_environmental_evidence",
    "fuse_agricultural_environmental_evidence",
]
